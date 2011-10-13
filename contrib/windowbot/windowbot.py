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
import hashlib
import collections
from abusehelper.core import events

def event_id(event):
    result = list()

    for key in sorted(event.keys()):
        key = key.encode("utf-8")
        for value in sorted(event.values(key)):
            value = value.encode("utf-8")
            result.append(key)
            result.append(value)

    return hashlib.md5("\x80".join(result)).hexdigest()

class WindowBot(RoomBot):
    @threado.stream
    def process(inner, self, window_time):
        ids = dict()
        queue = collections.deque()
        sleeper = timer.sleep(1.0)

        while True:
            if sleeper.has_result():
                sleeper = timer.sleep(1.0)
            source, event = yield threado.any(inner, sleeper)

            current_time = time.time()
            expire_time = current_time + window_time

            if inner is source:
                eid = event_id(event)

                event.add("id", eid)
                inner.send(event)

                ids[eid] = expire_time
                queue.append((expire_time, eid))

            while queue and queue[0][0] <= current_time:
                expire_time, eid = queue.popleft()
                if ids.get(eid, None) != expire_time:
                    continue

                del ids[eid]

                event = events.Event()
                event.add("id", eid)
                inner.send(event)

    @threado.stream
    def session(inner, self, state, src_room, dst_room, window_time=60.0):
        yield inner.sub(self.from_room(src_room)
                        | events.stanzas_to_events()
                        | self.process(window_time)
                        | events.events_to_elements()
                        | self.to_room(dst_room))

if __name__ == "__main__":
    WindowBot.from_command_line().execute()
