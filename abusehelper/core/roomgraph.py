from idiokit import threado
from abusehelper.core import events, rules, roomfarm, services

class RoomGraphService(roomfarm.RoomFarm):
    def __init__(self, xmpp):
        roomfarm.RoomFarm.__init__(self)
        self.xmpp = xmpp
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
                    print "I've seen", count, "events in room", name

                for dst, rules in tests:
                    for rule in rules:
                        if rule(event):
                            dst.send(event)
                            break

    @threado.stream
    def handle_room(inner, self, name):
        print "Joining room", repr(name)
        room = yield inner.sub(self.xmpp.muc.join(name))
        print "Joined room", repr(name)
        try:
            yield inner.sub(events.events_to_elements() 
                            | room 
                            | events.stanzas_to_events()
                            | self.distribute(name))
        finally:
            print "Left room", repr(name)

    @threado.stream
    def session(inner, self, _, src, dst, rule):
        _, dst_room = self.rooms(inner, src, dst)
        counter = self.srcs.setdefault(src, roomfarm.Counter())
        counter.inc(dst_room, rule)
        try:
            while True:
                yield inner
        except services.Stop:
            inner.finish()
        finally:
            self.rooms(inner)
            counter.dec(dst_room, rule)
            if not counter:
                self.srcs.pop(src, None)

def main(name, xmpp_jid, service_room, xmpp_password=None, log_file=None):
    import getpass
    from idiokit.xmpp import connect
    from abusehelper.core import log

    if not xmpp_password:
        xmpp_password = getpass.getpass("XMPP password: ")

    logger = log.config_logger(name, filename=log_file)

    @threado.stream
    def bot(inner):
        print "Connecting XMPP server with JID", xmpp_jid
        xmpp = yield inner.sub(connect(xmpp_jid, xmpp_password))
        xmpp.core.presence()

        print "Joining lobby", service_room
        lobby = yield inner.sub(services.join_lobby(xmpp, service_room, name))
        logger.addHandler(log.RoomHandler(lobby.room))

        yield inner.sub(lobby.offer(name, RoomGraphService(xmpp)))
    return bot()
main.service_room_help = "the room where the services are collected"
main.xmpp_jid_help = "the XMPP JID (e.g. xmppuser@xmpp.example.com)"
main.xmpp_password_help = "the XMPP password"
main.log_file_help = "log to the given file instead of the console"

if __name__ == "__main__":
    from abusehelper.core import opts
    threado.run(opts.optparse(main), throw_on_signal=services.Stop())
