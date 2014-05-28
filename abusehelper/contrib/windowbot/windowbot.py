import idiokit
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
import collections
from abusehelper.core import events


class WindowBot(RoomBot):
    @idiokit.stream
    def match(self, rule):
        while True:
            event = yield idiokit.next()
            if rule.match(event):
                yield idiokit.send(event)

    @idiokit.stream
    def process(self, ids, queue, window_time):
        while True:
            event = yield idiokit.next()

            current_time = time.time()
            expire_time = current_time + window_time

            eid = events.hexdigest(event)
            count, items = ids.get(eid, (0, event.items()))
            ids[eid] = count + 1, items

            if count == 0:
                yield idiokit.send(event.union({
                    "id:open": eid
                }))
            queue.append((expire_time, eid))

    @idiokit.stream
    def purge(self, ids, queue):
        while True:
            yield idiokit.sleep(1.0)

            current_time = time.time()

            while queue and queue[0][0] <= current_time:
                expire_time, eid = queue.popleft()

                count, items = ids.pop(eid)
                if count > 1:
                    ids[eid] = count - 1, items
                else:
                    yield idiokit.send(events.Event(items).union({
                        "id:close": eid
                    }))

    @idiokit.stream
    def session(self, state, src_room, dst_room, window_time=60.0, rule=None):
        if rule is None:
            rule = rules.Anything()
        rule = rules.rule(rule)

        queue = collections.deque()
        ids = dict()

        to = self.to_room(dst_room)
        idiokit.pipe(self.purge(ids, queue),
                     events.events_to_elements(),
                     to)

        yield (self.from_room(src_room)
               | events.stanzas_to_events()
               | self.match(rule)
               | self.process(ids, queue, window_time)
               | events.events_to_elements()
               | to)

if __name__ == "__main__":
    WindowBot.from_command_line().execute()
