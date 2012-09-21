import idiokit
from idiokit import timer
from abusehelper.core import bot, taskfarm


class RoomBot(bot.ServiceBot):
    def __init__(self, *args, **keys):
        bot.ServiceBot.__init__(self, *args, **keys)
        self.room_handlers = taskfarm.TaskFarm(self._handle_room)

    @idiokit.stream
    def _handle_room(self, name):
        msg = "room {0!r}".format(name)
        attrs = events.Event(type="room", service=self.bot_name, room=name)

        with self.log.stateful(repr(self.xmpp.jid), "room", repr(name)) as log:
            log.open("Joining " + msg, attrs, status="joining")
            room = yield self.xmpp.muc.join(name, self.bot_name)

            log.open("Joined " + msg, attrs, status="joined")
            try:
                yield room
            finally:
                log.close("Left " + msg, attrs, status="left")

    def to_room(self, name):
        return self.room_handlers.inc(name) | idiokit.consume()

    def from_room(self, name):
        return idiokit.consume() | self.room_handlers.inc(name)


import time
import codecs
import collections
from hashlib import sha1
from abusehelper.core import events, services

_encoder = codecs.getencoder("utf-8")


def event_id(event):
    result = list()

    for key, value in sorted(event.items()):
        key = _encoder(key)[0]
        value = _encoder(value)[0]
        result.append(key)
        result.append(value)

    return sha1("\xc0".join(result)).hexdigest()


AUGMENT_KEY = "augment sha-1"


@idiokit.stream
def ignore_augmentations(ignore):
    while True:
        event = yield idiokit.next()
        if ignore and event.contains(AUGMENT_KEY):
            continue
        yield idiokit.send(event)


@idiokit.stream
def create_eids():
    while True:
        event = yield idiokit.next()
        yield idiokit.send(event_id(event), event)


@idiokit.stream
def embed_eids():
    while True:
        eid, event = yield idiokit.next()
        yield idiokit.send(event.union({AUGMENT_KEY: eid}))


class Expert(RoomBot):
    def __init__(self, *args, **keys):
        RoomBot.__init__(self, *args, **keys)
        self._augments = taskfarm.TaskFarm(self._handle_augment)

    def _handle_augment(self, src_room, dst_room, args):
        return (self.from_room(src_room)
                | events.stanzas_to_events()
                | ignore_augmentations(src_room == dst_room)
                | create_eids()
                | self.augment(*args)
                | embed_eids()
                | events.events_to_elements()
                | self.to_room(dst_room))

    @idiokit.stream
    def session(self, state, src_room, dst_room=None, **keys):
        if dst_room is None:
            dst_room = src_room

        augments = list()
        for args in self.augment_keys(src_room=src_room,
                                      dst_room=dst_room,
                                      **keys):
            augments.append(self._augments.inc(src_room, dst_room, args))

        try:
            yield idiokit.pipe(*augments)
        except services.Stop:
            idiokit.stop()

    def augment_keys(self, *args, **keys):
        yield ()

    @idiokit.stream
    def augment(self):
        while True:
            eid, event = yield idiokit.next()
            # Skip augmenting by default.
            # Implement yield idiokit.send(eid, augmentation).


class Combiner(RoomBot):
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

            eid = event_id(event)
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
            yield timer.sleep(1.0)

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
        yield (self.from_room(src_room)
               | events.stanzas_to_events()
               | ignore_augmentations(augment_room == src_room)
               | self.collect(ids, queue, time_window)
               | self.cleanup(ids, queue)
               | events.events_to_elements()
               | self.to_room(dst_room)
               | self.from_room(augment_room)
               | events.stanzas_to_events()
               | self.combine(ids, queue, time_window))

if __name__ == "__main__":
    Combiner.from_command_line().execute()
