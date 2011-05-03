from idiokit import threado, timer
from abusehelper.core import bot, taskfarm

class RoomBot(bot.ServiceBot):
    def __init__(self, *args, **keys):
        bot.ServiceBot.__init__(self, *args, **keys)

        self.room_handlers = taskfarm.TaskFarm(self._handle_room)
        self.room_channels = dict()

    @threado.stream_fast
    def _distribute_room(inner, self, name):
        while True:
            yield inner

            channels = self.room_channels.get(name, ())
            for elements in inner:
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

    @threado.stream_fast
    def _to_room(inner, self, room):
        while True:
            yield inner, room

            for _ in room:
                pass

            for elements in inner:
                room.send(elements)

    @threado.stream
    def to_room(inner, self, name):
        inc = self.room_handlers.inc(name)
        room = self.room_handlers.get(name)

        yield inner.sub(self._to_room(room) | inc)

    @threado.stream_fast
    def _from_room(inner, self, channel):
        while True:
            yield inner, channel

            for _ in inner:
                pass
            
            for elements in channel:
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
from abusehelper.core import events

_encoder = codecs.getencoder("utf-8")

def event_id(event):
    result = list()

    for key in sorted(event.keys()):
        key = _encoder(key)[0]
        for value in sorted(event.values(key)):
            value = _encoder(value)[0]
            result.append(key)
            result.append(value)

    return sha1("\x80".join(result)).hexdigest()

AUGMENT_KEY = "augment sha-1"

@threado.stream_fast
def ignore_augmentations(inner, ignore):
    while True:
        yield inner

        for event in inner:
            if ignore and event.contains(AUGMENT_KEY):
                continue
            inner.send(event)

class Expert(RoomBot):
    @threado.stream
    def augment(inner, self):
        while True:
            original_event = yield inner
            # Skip augmenting by default.
            # Implement inner.send(original_event, augmented_event).

    @threado.stream_fast
    def _handle(inner, self):
        while True:
            yield inner

            for original_event, augmented_event in inner:
                augmented_event.add(AUGMENT_KEY, event_id(original_event))
                inner.send(augmented_event)

    @threado.stream
    def session(inner, self, state, src_room, dst_room=None):
        if dst_room is None:
            dst_room = src_room

        yield inner.sub(self.from_room(src_room)
                        | events.stanzas_to_events()
                        | ignore_augmentations(src_room == dst_room)
                        | self.augment()
                        | self._handle()
                        | events.events_to_elements()
                        | self.to_room(dst_room))

class Combiner(RoomBot):
    @threado.stream_fast
    def collect(inner, self, ids, time_window):
        queue = collections.deque()
        sleeper = timer.sleep(1.0)

        while True:
            try:
                for _ in sleeper: pass
            except threado.Finished:
                sleeper = timer.sleep(1.0)

            yield inner, sleeper

            current_time = time.time()
            expire_time = current_time + time_window

            for event in inner:
                eid = event_id(event)
                ids[eid] = event
                queue.append((expire_time, eid))

            while queue and queue[0][0] <= current_time:
                expire_time, eid = queue.popleft()
                event = ids.pop(eid, None)
                if event is not None:
                    inner.send(event)

    @threado.stream_fast
    def combine(inner, self, ids):
        while True:
            yield inner

            for augmentation in inner:
                augmentation = events.Event(augmentation)
                eids = augmentation.values(AUGMENT_KEY)
                augmentation.clear(AUGMENT_KEY)
                
                for eid in eids:
                    if eid in ids:
                        original_event = ids[eid]
                        ids[eid] = events.Event(original_event, augmentation)

    @threado.stream
    def session(inner, self, state, src_room, dst_room, 
                augment_room=None, time_window=10.0):
        if augment_room is None:
            augment_room = src_room

        ids = dict()
        yield inner.sub(self.from_room(src_room)
                        | events.stanzas_to_events()
                        | ignore_augmentations(augment_room == src_room)
                        | self.collect(ids, time_window)
                        | events.events_to_elements()
                        | self.to_room(dst_room)
                        | self.from_room(augment_room)
                        | events.stanzas_to_events()
                        | self.combine(ids))

if __name__ == "__main__":
    Combiner.from_command_line().execute()
