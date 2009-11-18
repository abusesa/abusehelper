import re
import time

from urllib import urlopen
from xml.dom.minidom import parseString

from idiokit import util, threado, sockets

source = "http://www.iana.org/assignments/ipv4-address-space/ipv4-address-space.xml"
prefix2whois = dict()

def getText(elementlist):
    text = ""
    for element in elementlist:
        for node in element.childNodes:
            if node.nodeType == node.TEXT_NODE:
                text += node.data
    return text

def handle(xml):
    records = xml.getElementsByTagName("record")
    for record in records:
        handleRecord(record)

def handleRecord(record):
    prefix = getText(record.getElementsByTagName("prefix"))
    whois = getText(record.getElementsByTagName("whois"))
    if prefix and whois:
        prefix2whois[prefix] = whois

def getWhoisServer(ip):
    prefix = ip.split(".")[0].rjust(3, "0") + "/8"
    return prefix2whois.get(prefix, None)

print "Updating prefix-to-whois-server dictionary"
handle(parseString(urlopen(source).read()))

mail_re    = re.compile('([\w\-.%]+@(?:[\w\-%]+\.)+[\w\-%]+)', re.S)
maildom_re = re.compile('(@(?:[\w\-%]+\.)+[\w\-%]+)', re.S)

class WhoisItem(object):
    def __init__(self, ip, whoisServer, data):
        self.ip = ip
        self.whoisServer = whoisServer
        self.data = data
        self.attrs = dict()
        self.addresses = set()

        self.parse(data)

    def parse(self, data):
        for line in data.split("\n"):
            if len(line.split(":", 2)) != 2:
                continue

            key, value = line.split(":", 2)
            key = key.strip()
            value = value.strip()
            self.attrs.setdefault(key, list()).append(value)
            result = mail_re.findall(value)
            for address in result:
                if self.whoisServer.split(".")[1] + "." in address:
                    continue
                if 'arin.net' in address or "ripe.net" in address:
                    continue
                self.addresses.add(address)

class Whois(threado.ThreadedStream):
    def __init__(self, cacheTime = 60*60.0):
        threado.ThreadedStream.__init__(self)
        
        self.cache = util.TimedCache(cacheTime)
        self.pending = set()

    def send(self, *args, **keys):
        threado.ThreadedStream.send(self, *args, **keys)
        self.start()

    def throw(self, *args, **keys):
        threado.ThreadedStream.throw(self, *args, **keys)
        self.start()

    def rethrow(self, *args, **keys):
        threado.ThreadedStream.rethrow(self, *args, **keys)
        self.start()

    def _iteration(self, pending):
        for ip in list(pending):
            item = self.cache.get(ip, None)
            if item is not None:
                self.inner.send(item)
                pending.discard(ip)

        if not pending:
            return pending

        for ip in pending:
            whoisServer = getWhoisServer(ip) 
            if whoisServer is None:
                return None

            socket = sockets.Socket()
            socket.connect((whoisServer, 43))

            item = None

            try:
                socket.send(ip + "\n")

                buffer = ""
                try:
                    for data in socket:
                        buffer += data
                except sockets.error:
                    pass

                item = WhoisItem(ip, whoisServer, buffer)
                self.cache.set(item.ip, item)
                self.inner.send(item)
            finally:
                socket.close()
 
    def run(self):
        while True:
            ip = self.inner.next()
            self._iteration([ip])

from idiokit import threado, threadpool
from abusehelper.core import events, rules
import services

class GotRoom(Exception):
    pass

class Connection(object):
    def __init__(self, source, destination):
        self.source = source
        self.destination = destination

    def disconnect(self):
        self.source._disconnect(self)

class Room(threado.GeneratorStream):
    def __init__(self, room, whois):
        threado.GeneratorStream.__init__(self, fast=True)
        self.room = room
        self.whois = whois
        self.listeners = dict()
        self.start()

    def run(self):
        room = self.room
        pipe = events.events_to_elements() | room | events.stanzas_to_events()

        try:
            while True:
                yield self.inner, pipe

                for event in self.inner.iter():
                    pipe.send(event)

                for event in pipe.iter():
                    if "ip" in event.attrs:
                        ip = event.attrs["ip"].pop()
                        self.whois.send(ip)
                        yield self.whois
                        item = self.whois.next()

                        for address in item.addresses:
                            event.add("email", address)
                    for listener, connections in self.listeners.iteritems():
                        for connection in connections:
                            connection.destination.send(event)
                            break
        finally:
            room.exit()

    def connect(self, room):
        connection = Connection(self, room)
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
        self.whois = Whois()
        self.rooms = dict()
        self.start()

    @threado.stream
    def get_room(inner, self, name):
        room = yield threadpool.run(self.xmpp.muc.join, name)
        room = Room(room, self.whois)
        services.bind(self, room)
        raise GotRoom(room)
            
    @threado.stream
    def room(inner, self, name):
        if name not in self.rooms:
            self.rooms[name] = self.get_room(name)
        try:
            yield self.rooms[name]
        except GotRoom, got_room:
            inner.send(got_room.args[0])

class WhoisSession(services.Session):
    def __init__(self, graph):
        services.Session.__init__(self)
        self.graph = graph
        self.connection = None

    @threado.stream
    def config(inner, self, conf):
        old_connection = self.connection

        if conf is not None:
            dst_room = yield self.graph.room(conf["dst"])
            src_room = yield self.graph.room(conf["src"])

            self.connection = src_room.connect(dst_room)
            inner.send(conf)
                                               
        if old_connection:
            old_connection.disconnect()

class WhoisService(services.Service):
    def __init__(self, xmpp):
        services.Service.__init__(self)
        self.graph = RoomGraph(xmpp)
        services.bind(self, self.graph)

    def session(self):
        return WhoisSession(self.graph)

@threado.stream
def main(inner):
    import settings
    from idiokit.xmpp import connect
    
    print "Connecting XMPP server"
    xmpp = yield connect(settings.username, settings.password)
    print "Joining lobby", settings.service_room
    lobby = yield services.join_lobby(xmpp, settings.service_room)
    print "Offering Whois service"

    offer = yield lobby.offer("whois", WhoisService(xmpp))
    yield inner.sub(offer)

if __name__ == "__main__":
    for _ in main(): print _

#if __name__ == "__main__":
#    import sys
#
#    whois = Whois()
#    for ip in sys.argv[1:]:
#        whois.send(ip)
#
#    for item in whois:
#        print item.ip, item.addresses
