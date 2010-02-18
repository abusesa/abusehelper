from idiokit import threado
from abusehelper.core import events, rules, taskfarm, bot, services

class RoomGraphBot(bot.ServiceBot):
    def __init__(self, *args, **keys):
        bot.ServiceBot.__init__(self, *args, **keys)
        self.rooms = taskfarm.TaskFarm(self.handle_room)
        self.srcs = dict()

    @threado.stream_fast
    def distribute(inner, self, name):
        count = 0
        while True:
            yield inner

            tests = list(self.srcs.get(name, ()))
            for event in inner:
                count += 1
                if count % 100 == 0:
                    self.log.info("Seen %d events in room %r", count, name)

                for dst, rules in tests:
                    for rule in rules:
                        if rule(event):
                            dst.send(event)
                            break

    @threado.stream
    def handle_room(inner, self, name):
        self.log.info("Joining room %r", name)
        room = yield inner.sub(self.xmpp.muc.join(name, self.bot_name))
        self.log.info("Joined room %r", name)
        try:
            yield inner.sub(events.events_to_elements() 
                            | room 
                            | events.stanzas_to_events()
                            | self.distribute(name))
        finally:
            self.log.info("Left room %r", name)

    @threado.stream
    def session(inner, self, _, src_room, dst_room, rule=rules.CONTAINS(), **keys):
        src = self.rooms.inc(src_room)
        dst = self.rooms.inc(dst_room)

        counter = self.srcs.setdefault(src_room, taskfarm.Counter())
        counter.inc(dst, rule)
        try:
            while True:
                yield inner
        except services.Stop:
            inner.finish()
        finally:
            self.rooms.dec(src_room)
            self.rooms.dec(dst_room)

            counter.dec(dst, rule)
            if not counter:
                self.srcs.pop(src_room, None)

if __name__ == "__main__":
    RoomGraphBot.from_command_line().execute()
