import idiokit
from abusehelper.core import events, rules, taskfarm, bot, services

class RoomGraphBot(bot.ServiceBot):
    def __init__(self, *args, **keys):
        bot.ServiceBot.__init__(self, *args, **keys)
        self.rooms = taskfarm.TaskFarm(self.handle_room)
        self.srcs = dict()

    @idiokit.stream
    def distribute(self, name):
        count = 0
        while True:
            event = yield idiokit.next()

            count += 1
            if count % 100 == 0:
                self.log.info("Seen %d events in room %r", count, name)

            classifier = self.srcs.get(name, None)
            if classifier is None:
                continue

            for dst_room in classifier.classify(event):
                dst = self.rooms.get(dst_room)
                if dst is not None:
                    yield dst.send(event)

    @idiokit.stream
    def handle_room(self, name):
        self.log.info("Joining room %r", name)
        room = yield self.xmpp.muc.join(name, self.bot_name)
        self.log.info("Joined room %r", name)
        try:
            yield idiokit.pipe(events.events_to_elements(),
                               room,
                               events.stanzas_to_events(),
                               self.distribute(name))
        finally:
            self.log.info("Left room %r", name)

    @idiokit.stream
    def session(self, _, src_room, dst_room, rule=rules.ANYTHING(), **keys):
        classifier = self.srcs.setdefault(src_room, rules.RuleClassifier())
        classifier.inc(rule, dst_room)
        try:
            yield self.rooms.inc(src_room) | self.rooms.inc(dst_room)
        except services.Stop:
            idiokit.stop()
        finally:
            classifier.dec(rule, dst_room)
            if classifier.is_empty():
                self.srcs.pop(src_room, None)

if __name__ == "__main__":
    RoomGraphBot.from_command_line().execute()
