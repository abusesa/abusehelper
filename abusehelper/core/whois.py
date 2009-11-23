import re
import time
import heapq
import urllib2
import services

from xml.etree.ElementTree import fromstring
from idiokit import timer, util, threado, sockets
from abusehelper.core import events

class WhoisItem(object):
    MAIL_REX = re.compile('([\w\-.%]+@(?:[\w\-%]+\.)+[\w\-%]+)', re.S)

    def __init__(self, ip, whois_server, data):
        self.ip = ip
        self.whois_server = whois_server
        self.attrs = dict()
        self.addresses = set()
        self._parse(data)

    def _parse(self, data):
        for line in data.splitlines():
            parts = line.split(":", 2)
            if len(parts) != 2:
                continue

            key, value = parts
            key = key.strip()
            value = value.strip()

            self.attrs.setdefault(key, list()).append(value)
            result = self.MAIL_REX.findall(value)
            for address in result:
                if self.whois_server.split(".")[1] + "." in address:
                    continue
                if 'arin.net' in address or "ripe.net" in address:
                    continue
                self.addresses.add(address)

class Whois(threado.GeneratorStream):
    PREFIX_SOURCE = "http://www.iana.org/assignments/ipv4-address-space/ipv4-address-space.xml"

    def __init__(self, cache_time=60*60.0):
        threado.GeneratorStream.__init__(self)

        self.cache_time = cache_time

        self.prefixes = threado.Channel()
        self.expirations = list()
        self.lookups = dict()

        self.start()

    def run(self):
        print "Updating prefix-to-whois-server dictionary."
        prefixes = yield self.load_prefixes()

        print "Initializing WHOIS server queues:"
        servers = dict()
        for server in set(prefixes.values()):
            print " *", server
            server_queue = self._server_queue(server)
            servers[server] = server_queue
            services.bind(self, server_queue)
        for prefix, server in prefixes.items():
            prefixes[prefix] = servers[server]
        self.prefixes.finish(prefixes)

        print "Running."
        while True:
            yield self.inner.sub(timer.sleep(1.0))
            
            purge_count = 0

            current_time = time.time()
            while self.expirations:
                expire_time, ip = self.expirations[0]
                if expire_time > current_time:
                    break
                heapq.heappop(self.expirations)
                self.lookups.pop(ip, None)
                purge_count += 1

            if purge_count > 0:
                cache_size = len(self.expirations)
                print "Purged %d item(s) from the cache (%d left)." % (purge_count, cache_size)

    @threado.stream
    def load_prefixes(inner, self):
        opened = yield inner.thread(urllib2.urlopen, self.PREFIX_SOURCE)
        data = yield inner.thread(opened.read)

        prefixes = dict()

        etree = fromstring(data)
        for record in etree.findall("{http://www.iana.org/assignments}record"):
            prefix = record.find("{http://www.iana.org/assignments}prefix")
            whois = record.find("{http://www.iana.org/assignments}whois")
            if None in (prefix, whois):
                continue
            prefixes[prefix.text.strip()] = whois.text.strip()

        inner.finish(prefixes)

    def lookup(self, ip):
        lookup = self._lookup(ip)
        services.bind(self, lookup)
        return lookup

    @threado.stream
    def _lookup(inner, self, ip):
        while not self.prefixes.was_source:
            prefixes = yield inner, self.prefixes

        if ip not in self.lookups:
            prefix = ip.split(".")[0].rjust(3, "0") + "/8"
            server = prefixes.get(prefix, None)
            if server is None:
                inner.finish(None)

            lookup = threado.Channel()
            self.lookups[ip] = lookup
            server.send(ip, lookup)
            services.bind(server, lookup)
        lookup = self.lookups[ip]

        while not lookup.was_source:
            result = yield inner, lookup
        inner.finish(result)

    @threado.stream
    def _server_queue(inner, self, server):
        while True:
            ip, lookup = yield inner

            socket = sockets.Socket()
            yield socket.connect((server, 43))
            socket.send(ip + "\n")

            buffer = list()
            try:
                while True:
                    data = yield socket
                    buffer.append(data)
            except sockets.error:
                pass
            finally:
                yield socket.close()
    
            item = WhoisItem(ip, server, "".join(buffer))
            lookup.finish(item)

            expire_time = time.time() + self.cache_time
            heapq.heappush(self.expirations, (expire_time, ip))

class WhoisSession(services.Session):
    def __init__(self, service):
        services.Session.__init__(self)
        self.service = service

    @threado.stream
    def config(inner, self, conf):
        yield
        if conf is None:
            self.service.disconnect(self)
        else:
            self.service.connect(self, conf["src"], conf["dst"])
        inner.finish(conf)

class WhoisService(services.Service):
    def __init__(self, xmpp):
        services.Service.__init__(self)

        self.xmpp = xmpp

        self.rooms = dict()
        self.sessions = dict()
        self.connections = dict()
        self.whois = Whois()
        services.bind(self, self.whois)

        self.start()

    @threado.stream_fast
    def check(inner, self, src):
        while True:
            yield inner

            if src in self.connections:
                map(inner.send, inner)
            else:
                list(inner)

    @threado.stream_fast
    def forward(inner, self, src):
        while True:
            yield inner

            rooms = map(self.rooms.get, self.connections.get(src, ()))
            for item in inner:
                for room, _ in rooms:
                    room.send(item)

    @threado.stream_fast
    def augment(inner, self):
        channel = threado.Channel()
        events = dict()

        @threado.stream
        def collect(collect_inner, ip):
            lookup = self.whois.lookup(ip)
            try:
                while not lookup.was_source:
                    item = yield collect_inner, lookup
            except:
                channel.rethrow()
            else:
                channel.send(ip, item)

        while True:
            yield inner, channel

            for event in inner:
                if "email" in event.attrs:
                    continue
                for ip in event.attrs.get("ip", ()):
                    if ip not in events:
                        collect(ip)
                    events.setdefault(ip, set()).add(event)
                    break
            
            for ip, item in channel:
                ip_events = events.pop(ip, ())
                if item is None or not item.addresses:
                    continue
                for event in ip_events:
                    for address in item.addresses:
                        event.add("email", address)
                inner.send(event)

    @threado.stream
    def _room(inner, self, src):
        room = yield self.xmpp.muc.join(src)
        yield inner.sub(events.events_to_elements()
                        | room
                        | self.check(src)
                        | events.stanzas_to_events()
                        | self.augment()
                        | self.forward(src))

    def connect(self, session, src, dst):
        self._inc(src)
        dst_room = self._inc(dst)
        dsts = self.connections.setdefault(src, dict())
        _, refcount = dsts.get(dst, (None, 0))
        dsts[dst] = dst_room, refcount+1

        if session in self.sessions:
            old_src, old_dst = self.sessions[session]
            self._disconnect(old_src, old_dst)
        self.sessions[session] = src, dst

    def disconnect(self, session):
        if session not in self.sessions:
            return
        src, dst = self.sessions.pop(session)
        self._disconnect(src, dst)

    def _disconnect(self, src, dst):
        dsts = self.connections[src]
        dsts[dst] -= 1
        if dsts[dst] <= 0:
            del dsts[dst]

        self._dec(src)
        self._dec(dst)

    def _inc(self, room_name):
        if room_name not in self.rooms:
            room = self._room(room_name)
            self.rooms[room_name] = room, 0
            services.bind(self, room)
            self.send()
        room, refcount = self.rooms[room_name]
        self.rooms[room_name] = room, refcount+1
        return room

    def _dec(self, room_name):
        if room_name not in self.rooms:
            return
        room, refcount = self.rooms[room_name]
        refcount -= 1
        if refcount > 0:
            self.rooms[room_name] = room, refcount
        else:
            room.finish()
            del self.rooms[room_name]
            
    def session(self):
        return WhoisSession(self)

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
        lobby = yield services.join_lobby(xmpp, service_room, "whois")

        print "Offering WHOIS service"
        yield inner.sub(lobby.offer("whois", WhoisService(xmpp)))
    return bot()
main.service_room_help = "the room where the services are collected"
main.xmpp_jid_help = "the XMPP JID (e.g. xmppuser@xmpp.example.com)"
main.xmpp_password_help = "the XMPP password"

if __name__ == "__main__":
    import opts
    threado.run(opts.optparse(main))
