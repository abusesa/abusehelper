from idiokit import threado
from abusehelper.core import events, rules
import services

class Connection(object):
    def __init__(self, source, destination, rule):
        self.source = source
        self.destination = destination
        self.rule = rule

    def disconnect(self):
        self.source._disconnect(self)

class Room(threado.GeneratorStream):
    def __init__(self, room):
        threado.GeneratorStream.__init__(self, fast=True)
        self.room = room
        self.listeners = dict()
        self.start()

    def run(self):
        room = self.room
        pipe = events.events_to_elements() | room | events.stanzas_to_events()
                
        count = 0
        room_name = room.room_jid.node
        try:
            while True:
                yield self.inner, pipe

                for event in self.inner:
                    pipe.send(event)

                for event in pipe:
                    count += 1
                    if count % 100 == 0:
                        print "Room", room_name, "totals in", count, "events"

                    for listener, connections in self.listeners.iteritems():
                        for connection in connections:
                            if connection.rule(event):
                                connection.destination.send(event)
                                break
        finally:
            room.exit()

    def connect(self, room, rule):
        connection = Connection(self, room, rule)
        self.listeners.setdefault(room, set()).add(connection)
        return connection

    def _disconnect(self, connection):
        if connection.destination not in self.listeners:
            return
        connections = self.listeners[connection.destination]
        connections.discard(connection)
        if not connections:
            self.listeners.pop(connection.destination)

class RoomGraph(threado.GeneratorStream):
    def __init__(self, xmpp):
        threado.GeneratorStream.__init__(self)
        self.xmpp = xmpp
        self.rooms = dict()
        self.start()

    @threado.stream
    def get_room(inner, self, name):
        room = yield inner.sub(self.xmpp.muc.join(name))
        room = Room(room)
        services.bind(self, room)
        inner.finish(room)
            
    @threado.stream
    def room(inner, self, name):
        if name not in self.rooms:
            self.rooms[name] = self.get_room(name)
        room = yield inner.sub(self.rooms[name])
        inner.finish(room)

class RoomGraphSession(services.Session):
    def __init__(self, graph):
        services.Session.__init__(self)
        self.graph = graph
        self.connection = None

    @threado.stream
    def config(inner, self, conf):
        old_connection = self.connection

        if conf is not None:
            dst_room = yield inner.sub(self.graph.room(conf["dst"]))
            src_room = yield inner.sub(self.graph.room(conf["src"]))
            filter = rules.CONTAINS(asn=conf["filter"])
            self.connection = src_room.connect(dst_room, filter)
                                               
        if old_connection:
            old_connection.disconnect()
        inner.finish(conf)

class RoomGraphService(services.Service):
    def __init__(self, xmpp):
        services.Service.__init__(self)
        self.graph = RoomGraph(xmpp)
        services.bind(self, self.graph)

    def session(self):
        return RoomGraphSession(self.graph)

def main(xmpp_jid, service_room, xmpp_password=None):
    import getpass
    from idiokit.xmpp import connect

    if not xmpp_password:
        xmpp_password = getpass.getpass("XMPP password: ")

    @threado.stream
    def bot(inner):
        print "Connecting XMPP server with JID", xmpp_jid
        xmpp = yield connect(xmpp_jid, xmpp_password)
        xmpp.core.presence()
        print "Joining lobby", service_room
        lobby = yield services.join_lobby(xmpp, service_room, "dshield")
        print "Offering RoomGraph service"
        offer = yield lobby.offer("roomgraph", RoomGraphService(xmpp))
        yield inner.sub(offer)
    return bot()
main.service_room_help = "the room where the services are collected"
main.xmpp_jid_help = "the XMPP JID (e.g. xmppuser@xmpp.example.com)"
main.xmpp_password_help = "the XMPP password"

if __name__ == "__main__":
    import opts
    threado.run(opts.optparse(main))
