from idiokit import threado
from abusehelper.core import events, rules, roomfarm, services

class RoomGraphSession(services.Session):
    def __init__(self, service):
        services.Session.__init__(self)

        self.service = service
        self.previous = None, None, None

    @threado.stream
    def config(inner, self, conf):
        src, dst_room, rule = self.previous
        counter = self.service.srcs.get(src, roomfarm.Counter())
        counter.dec(dst_room, rule)
        if not counter:
            self.service.srcs.pop(src, None)

        if conf is None:
            self.service.rooms(self)
            self.previous = None, None, None
        else:
            src = conf["src"]
            _, dst_room = self.service.rooms(self, src, conf["dst"])
            rule = conf["filter"]

            counter = self.service.srcs.setdefault(src, roomfarm.Counter())
            counter.inc(dst_room, rule)
            self.previous = src, dst_room, rule

        yield
        inner.finish(conf)

class RoomGraphService(roomfarm.RoomFarm):
    def __init__(self, xmpp):
        roomfarm.RoomFarm.__init__(self, xmpp)
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
                    print "Room", name, "totals in", count, "events"

                for dst, rules in tests:
                    for rule in rules:
                        if rule(event):
                            dst.send(event)
                            break

    @threado.stream
    def handle_room(inner, self, name):
        room = yield inner.sub(self.xmpp.muc.join(name))
        yield inner.sub(events.events_to_elements() 
                        | room 
                        | events.stanzas_to_events()
                        | self.distribute(name))

    def session(self):
        return RoomGraphSession(self)

def main(xmpp_jid, service_room, xmpp_password=None, log_file=None):
    import getpass
    from idiokit.xmpp import connect
    from abusehelper.core import log

    if not xmpp_password:
        xmpp_password = getpass.getpass("XMPP password: ")

    logger = log.config_logger("roomgraph", filename=log_file)

    @threado.stream
    def bot(inner):
        print "Connecting XMPP server with JID", xmpp_jid
        xmpp = yield connect(xmpp_jid, xmpp_password)
        xmpp.core.presence()

        print "Joining lobby", service_room
        lobby = yield services.join_lobby(xmpp, service_room, "roomgraph")

        logger.addHandler(log.RoomHandler(lobby.room))
        yield inner.sub(lobby.offer("roomgraph", RoomGraphService(xmpp)))
    return bot()
main.service_room_help = "the room where the services are collected"
main.xmpp_jid_help = "the XMPP JID (e.g. xmppuser@xmpp.example.com)"
main.xmpp_password_help = "the XMPP password"
main.log_file_help = "log to the given file instead of the console"

if __name__ == "__main__":
    from abusehelper.core import opts
    threado.run(opts.optparse(main))
