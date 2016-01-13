import time
import idiokit
import collections
from hashlib import sha1
from ...core import events
from . import AUGMENT_KEY, _RoomBot, _ignore_augmentations


class Combiner(_RoomBot):
    def _add(self, ids, queue, time_window, eid):
        current_time = time.time()
        expire_time = current_time + time_window

        unique = object()
        queue.append((expire_time, eid, unique))

        if eid not in ids:
            ids[eid] = dict(), dict()
        event_set, augment_set = ids[eid]
        return unique, event_set, augment_set

    @idiokit.stream
    def collect(self, ids, queue, time_window):
        while True:
            event = yield idiokit.next()

            eid = events.hexdigest(event, sha1)
            unique, event_set, augment_set = self._add(ids, queue, time_window, eid)
            event_set[unique] = event.union(*augment_set.values())

    @idiokit.stream
    def combine(self, ids, queue, time_window):
        while True:
            augment = yield idiokit.next()
            augment = events.Event(augment)

            eids = augment.values(AUGMENT_KEY)
            augment = augment.difference({AUGMENT_KEY: eids})

            for eid in eids:
                unique, event_set, augment_set = self._add(ids, queue, time_window, eid)
                augment_set[unique] = augment
                for unique, event in event_set.items():
                    event_set[unique] = event.union(augment)

    @idiokit.stream
    def cleanup(self, ids, queue):
        while True:
            yield idiokit.sleep(1.0)

            current_time = time.time()

            while queue and queue[0][0] <= current_time:
                expire_time, eid, unique = queue.popleft()
                event_set, augment_set = ids[eid]

                augment_set.pop(unique, None)

                event = event_set.pop(unique, None)
                if event is not None:
                    yield idiokit.send(event)

                if not event_set and not augment_set:
                    del ids[eid]

    @idiokit.stream
    def session(self, state, src_room, dst_room,
                augment_room=None, time_window=10.0):
        if augment_room is None:
            augment_room = src_room

        ids = dict()
        queue = collections.deque()
        yield idiokit.pipe(
            self.from_room(src_room),
            events.stanzas_to_events(),
            _ignore_augmentations(augment_room == src_room),
            self.collect(ids, queue, time_window),
            self.cleanup(ids, queue),
            events.events_to_elements(),
            self.to_room(dst_room),
            self.from_room(augment_room),
            events.stanzas_to_events(),
            self.combine(ids, queue, time_window)
        )


if __name__ == "__main__":
    Combiner.from_command_line().execute()
