import csv
import urllib
import time
import urllib2
import urlparse
import time
import gzip
import cStringIO as StringIO

from idiokit import threado, util
from abusehelper.core import events, services

def sanitize_ip(ip):
    # Remove leading zeros from (strings resembling) IPv4 addresses.
    if not isinstance(ip, basestring):
        return ip
    try:
        return ".".join(map(str, map(int, ip.split("."))))
    except ValueError:
        pass
    return ip

def read_data(fileobj, compression=6):
    stringio = StringIO.StringIO()
    compressed = gzip.GzipFile(None, "wb", compression, stringio)

    while True:
        data = fileobj.read(2**16)
        if not data:
            break
        compressed.write(data)
    compressed.close()

    stringio.seek(0)
    return gzip.GzipFile(fileobj=stringio)

@threado.stream
def dshield(inner, asn, url="http://dshield.org/asdetailsascii.html"):
    asn = str(asn)
    
    # The current DShield csv fields, in order.
    headers = ["ip", "reports", "targets", "firstseen", "lastseen", "updated"]

    # Probably a kosher-ish way to create an ASN specific URL.
    parsed = urlparse.urlparse(url)
    parsed = list(parsed)
    parsed[4] = urllib.urlencode({ "as" : asn })
    url = urlparse.urlunparse(parsed)

    print "ASN%s: connecting" % asn
    opened = yield inner.thread(urllib2.urlopen, url)
    print "ASN%s: downloading" % asn
    data = yield inner.thread(read_data, opened)
    print "ASN%s: downloaded" % asn

    count = 0
    try:
        # Lazily filter away empty lines and lines starting with '#'
        filtered = (x for x in data if x.strip() and not x.startswith("#"))
        reader = csv.DictReader(filtered, headers, delimiter="\t")
        for row in reader:
            row["ip"] = sanitize_ip(row.get("ip", None))

            count += 1
            if count % 100 == 0:
                print "ASN%s: fed %d events" % (asn, count)
            
            event = events.Event()
            event.add('asn', str(asn))
            event.add('feed', 'dshield')
            for key, value in row.items():
                if value is None:
                    continue
                event.add(key, util.guess_encoding(value).strip())
            inner.send(event)
            yield
    finally:
        print "ASN%s: done with %d events" % (asn, count)
        opened.close()

from idiokit import timer
import time
import heapq
from abusehelper.core import roomfarm, services

class DShieldSession(services.Session):
    def __init__(self, service):
        services.Session.__init__(self)
        self.service = service
        self.previous = None, None
    
    @threado.stream
    def config(inner, self, conf):
        if conf is None:
            asn = None
            room = self.service.rooms(self)
        else:
            asn = conf["asn"]
            room = self.service.rooms(self, conf["room"])
            self.service.add_asn(asn, room)

        self.service.remove_asn(*self.previous)
        self.previous = asn, room

        yield
        inner.finish(conf)

class DShieldService(roomfarm.RoomFarm):
    def __init__(self, xmpp, update_interval=300.0):
        roomfarm.RoomFarm.__init__(self, xmpp)

        self.update_interval = update_interval

        self.asns = roomfarm.Counter()
        self.heap = list()

    def add_asn(self, asn, room):
        if not self.asns.get(asn):
            heapq.heappush(self.heap, (time.time(), asn))
            self.send()
        self.asns.inc(asn, room)

    def remove_asn(self, asn, room):
        self.asns.dec(asn, room)

    @threado.stream
    def p(inner, self):
        while True:
            element = yield inner
            print element

    @threado.stream
    def handle_room(inner, self, name):
        print "Joining room", name
        room = yield inner.sub(self.xmpp.muc.join(name))
        print "Joined room", name
        yield inner.sub(events.events_to_elements()
                        | room
                        | threado.throws())

    @threado.stream_fast
    def distribute(inner, self, asn):
        while True:
            yield inner

            rooms = self.asns.get(asn)
            for event in inner:
                for room in rooms:
                    room.send(event)

    def run(self):
        while True:
            if not self.heap:
                yield self.inner
                continue

            current_time = time.time()
            expire_time, asn = self.heap[0]
            if expire_time > current_time:
                yield self.inner, timer.sleep(expire_time-current_time)
            elif not self.asns.get(asn):
                heapq.heappop(self.heap)
            else:
                heapq.heappop(self.heap)
                yield self.inner.sub(dshield(asn) | self.distribute(asn))
                expire_time = time.time() + self.update_interval
                heapq.heappush(self.heap, (expire_time, asn))

    def session(self):
        return DShieldSession(self)

def main(xmpp_jid, service_room, xmpp_password=None, log_file=None):
    import getpass
    from idiokit.xmpp import connect
    from abusehelper.core import log
    
    if not xmpp_password:
        xmpp_password = getpass.getpass("XMPP password: ")

    logger = log.config_logger("dshield", filename=log_file)

    @threado.stream
    def bot(inner):
        print "Connecting XMPP server with JID", xmpp_jid
        xmpp = yield connect(xmpp_jid, xmpp_password)
        xmpp.core.presence()

        print "Joining lobby", service_room
        lobby = yield services.join_lobby(xmpp, service_room, "dshield")
        logger.addHandler(log.RoomHandler(lobby.room))

        yield inner.sub(lobby.offer("dshield", DShieldService(xmpp)))
    return bot()
main.service_room_help = "the room where the services are collected"
main.xmpp_jid_help = "the XMPP JID (e.g. xmppuser@xmpp.example.com)"
main.xmpp_password_help = "the XMPP password"
main.log_file_help = "log to the given file instead of the console"

if __name__ == "__main__":
    from abusehelper.core import opts
    threado.run(opts.optparse(main))
