import idiokit
from idiokit import timer
from abusehelper.core import bot, taskfarm

class RoomBot(bot.ServiceBot):
    def __init__(self, *args, **keys):
        bot.ServiceBot.__init__(self, *args, **keys)
        self.room_handlers = taskfarm.TaskFarm(self._handle_room)

    @idiokit.stream
    def _handle_room(self, name):
        self.log.info("Joining room %r", name)
        room = yield self.xmpp.muc.join(name, self.bot_name)
        self.log.info("Joined room %r", name)

        try:
            yield room
        finally:
            self.log.info("Left room %r", name)

    def to_room(self, name):
        return self.room_handlers.inc(name) | idiokit.consume()

    def from_room(self, name):
        return idiokit.consume() | self.room_handlers.inc(name)

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
    @idiokit.stream
    def process(self, ids, queue, window_time):
        while True:
            event = yield idiokit.next()

            current_time = time.time()
            expire_time = current_time + window_time

            eid = event_id(event)

            event.add("id", eid)
            yield idiokit.send(event)

            ids[eid] = expire_time
            queue.append((expire_time, eid))

    @idiokit.stream
    def purge(self, ids, queue):
        while True:
            yield timer.sleep(1.0)

            current_time = time.time()

            while queue and queue[0][0] <= current_time:
                expire_time, eid = queue.popleft()
                if ids.get(eid, None) != expire_time:
                    continue

                del ids[eid]

                event = events.Event()
                event.add("id", eid)
                yield idiokit.send(event)

    @idiokit.stream
    def session(self, state, src_room, dst_room, window_time=60.0):
        queue = collections.deque()
        ids = dict()

        to = self.to_room(dst_room)
        idiokit.pipe(self.purge(ids, queue),
                     events.events_to_elements(),
                     to)

        yield (self.from_room(src_room)
               | events.stanzas_to_events()
               | self.process(ids, queue, window_time)
               | events.events_to_elements()
               | to)

if __name__ == "__main__":
    WindowBot.from_command_line().execute()
