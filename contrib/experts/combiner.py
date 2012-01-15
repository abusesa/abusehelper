from idiokit import threado, timer
from abusehelper.core import bot, taskfarm

class RoomBot(bot.ServiceBot):
    def __init__(self, *args, **keys):
        bot.ServiceBot.__init__(self, *args, **keys)

        self.room_handlers = taskfarm.TaskFarm(self._handle_room)
        self.room_channels = dict()

    @threado.stream
    def _distribute_room(inner, self, name):
        while True:
            elements = yield inner

            channels = self.room_channels.get(name, ())
            for channel in channels:
                channel.send(elements)

    @threado.stream
    def _handle_room(inner, self, name):
        self.log.info("Joining room %r", name)
        room = yield inner.sub(self.xmpp.muc.join(name, self.bot_name))
        self.log.info("Joined room %r", name)

        try:
            yield inner.sub(room | self._distribute_room(name))
        finally:
            self.log.info("Left room %r", name)

    @threado.stream
    def _to_room(inner, self, room):
        while True:
            source, elements = yield threado.any(inner, room)
            if inner is source:
                room.send(elements)

    @threado.stream
    def to_room(inner, self, name):
        inc = self.room_handlers.inc(name)
        room = self.room_handlers.get(name)

        yield inner.sub(self._to_room(room) | inc)

    @threado.stream
    def _from_room(inner, self, channel):
        while True:
            source, elements = yield threado.any(inner, channel)
            if channel is source:
                inner.send(elements)

    @threado.stream
    def from_room(inner, self, name):
        channel = threado.Channel()
        self.room_channels.setdefault(name, set()).add(channel)

        try:
            yield inner.sub(threado.dev_null()
                            | self.room_handlers.inc(name)
                            | self._from_room(channel))
        finally:
            channels = self.room_channels.get(name, set())
            channels.discard(channel)
            if not channels:
                self.room_channels.pop(name, None)

import time
import codecs
import collections
from hashlib import sha1
from abusehelper.core import events, services

_encoder = codecs.getencoder("utf-8")

def event_id(event):
    result = list()

    for key in sorted(event.keys()):
        key = _encoder(key)[0]
        for value in sorted(event.values(key)):
            value = _encoder(value)[0]
            result.append(key)
            result.append(value)

    return sha1("\xc0".join(result)).hexdigest()

AUGMENT_KEY = "augment sha-1"

@threado.stream
def ignore_augmentations(inner, ignore):
    while True:
        event = yield inner
        if ignore and event.contains(AUGMENT_KEY):
            continue
        inner.send(event)

@threado.stream
def create_eids(inner):
    while True:
        event = yield inner
        inner.send(event_id(event), event)

@threado.stream
def embed_eids(inner):
    while True:
        eid, event = yield inner
        event.add(AUGMENT_KEY, eid)
        inner.send(event)

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

    @threado.stream
    def session(inner, self, state, src_room, dst_room=None, **keys):
        if dst_room is None:
            dst_room = src_room

        augments = list()
        for args in self.augment_keys(src_room=src_room,
                                      dst_room=dst_room,
                                      **keys):
            augments.append(self._augments.inc(src_room, dst_room, args))

        try:
            yield inner.sub(threado.pipe(*augments))
        except services.Stop:
            inner.finish()

    def augment_keys(self, *args, **keys):
        yield ()

    @threado.stream
    def augment(inner, self):
        while True:
            eid, event = yield inner
            # Skip augmenting by default.
            # Implement inner.send(eid, augmentation).

class Combiner(RoomBot):
    @threado.stream
    def collect(inner, self, ids, queue, time_window):
        sleeper = timer.sleep(1.0)

        while True:
            if sleeper.has_result():
                sleeper = timer.sleep(1.0)
            source, event = yield threado.any(inner, sleeper)

            current_time = time.time()
            expire_time = current_time + time_window

            if inner is source:
                eid = event_id(event)
                if eid not in ids:
                    queue.append((expire_time, eid))
                    ids[eid] = event, list()
                else:
                    _, augmentations = ids[eid]
                    ids[eid] = event, augmentations

            while queue and queue[0][0] <= current_time:
                expire_time, eid = queue.popleft()
                event, augmentations = ids.pop(eid)
                if event is not None:
                    inner.send(events.Event(event, *augmentations))

    @threado.stream
    def combine(inner, self, ids, queue, time_window):
        while True:
            augmentation = yield inner

            augmentation = events.Event(augmentation)
            eids = augmentation.values(AUGMENT_KEY)
            augmentation.clear(AUGMENT_KEY)

            for eid in eids:
                if eid not in ids:
                    expire_time = time.time() + time_window
                    queue.append((expire_time, eid))
                    ids[eid] = None, list()
                event, augmentations = ids[eid]
                augmentations.append(augmentation)

    @threado.stream
    def session(inner, self, state, src_room, dst_room,
                augment_room=None, time_window=10.0):
        if augment_room is None:
            augment_room = src_room

        ids = dict()
        queue = collections.deque()
        yield inner.sub(self.from_room(src_room)
                        | events.stanzas_to_events()
                        | ignore_augmentations(augment_room == src_room)
                        | self.collect(ids, queue, time_window)
                        | events.events_to_elements()
                        | self.to_room(dst_room)
                        | self.from_room(augment_room)
                        | events.stanzas_to_events()
                        | self.combine(ids, queue, time_window))

if __name__ == "__main__":
    Combiner.from_command_line().execute()
