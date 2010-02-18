from idiokit import threado
from abusehelper.core import events, bot, taskfarm, services

class Sanitizer(bot.ServiceBot):
    def __init__(self, **keys):
        bot.ServiceBot.__init__(self, **keys)
        self.rooms = taskfarm.TaskFarm(self.handle_room)
        self.srcs = taskfarm.Counter()

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

    @threado.stream_fast
    def distribute(inner, self, name):
        while True:
            yield inner
            
            rooms = set(self.srcs.get(name))
            if not rooms:
                list(inner)
                continue

            for event in inner:
                for sanitized_event in self.sanitize(event):
                    for room in rooms:
                        room.send(sanitized_event)

    @threado.stream
    def session(inner, self, _, src_room, dst_room, **keys):
        src = self.rooms.inc(src_room)
        dst = self.rooms.inc(dst_room)
        self.srcs.inc(src_room, dst)
        try:
            while True:
                yield inner
        except services.Stop:
            inner.finish()
        finally:
            self.srcs.dec(src_room, dst)
            self.rooms.dec(src_room)
            self.rooms.dec(dst_room)

    def sanitize(self, event):
        return [event]
