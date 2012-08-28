import idiokit
from idiokit import timer
from abusehelper.core import events, rules, taskfarm, bot, services


class RoomGraphBot(bot.ServiceBot):
    def __init__(self, *args, **keys):
        bot.ServiceBot.__init__(self, *args, **keys)
        self.rooms = taskfarm.TaskFarm(self.handle_room)
        self.srcs = dict()

    @idiokit.stream
    def _alert(self, interval=15.0):
        while True:
            yield timer.sleep(interval)
            yield idiokit.send(None)

    @idiokit.stream
    def distribute(self, name):
        count = 0
        waiters = dict()

        while True:
            elements = yield idiokit.next()

            if elements is None:
                for waiter in waiters.values():
                    yield waiter
                waiters.clear()

                if count > 0:
                    self.log.info("Seen {0} events in room {1!r}".format(count, name))
                    count = 0
                continue

            classifier = self.srcs.get(name, None)
            if classifier is None:
                continue

            for event in events.Event.from_elements(elements):
                count += 1

                for dst_room in classifier.classify(event):
                    dst = self.rooms.get(dst_room)

                    if dst_room in waiters:
                        yield waiters.pop(dst_room)

                    if dst is not None:
                        waiters[dst_room] = dst.send(event.to_elements())

    @idiokit.stream
    def handle_room(self, name):
        msg = "room {0!r}".format(name)
        attrs = events.Event(type="room", service=self.bot_name, room=name)

        def check(elements):
            if name in self.srcs:
                yield elements

        with self.log.stateful(repr(self.xmpp.jid), "room", repr(name)) as log:
            log.open("Joining " + msg, attrs, status="joining")
            room = yield self.xmpp.muc.join(name, self.bot_name)

            log.open("Joined " + msg, attrs, status="joined")
            try:
                distribute = self.distribute(name)
                idiokit.pipe(self._alert() | distribute)
                yield room | idiokit.map(check) | distribute
            finally:
                log.close("Left " + msg, attrs, status="left")

    @idiokit.stream
    def session(self, _, src_room, dst_room, rule=rules.ANYTHING(), **keys):
        classifier = self.srcs.setdefault(src_room, rules.RuleClassifier())
        classifier.inc(rule, dst_room)

        try:
            yield self.rooms.inc(src_room) | self.rooms.inc(dst_room)
        except services.Stop:
            pass
        finally:
            classifier.dec(rule, dst_room)
            if classifier.is_empty():
                self.srcs.pop(src_room, None)

if __name__ == "__main__":
    RoomGraphBot.from_command_line().execute()
