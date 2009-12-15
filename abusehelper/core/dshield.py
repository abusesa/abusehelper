import csv
import urllib
import time
import urllib2
import urlparse
import time
import gzip
import cStringIO as StringIO

from idiokit import threado, util
from abusehelper.core import events, services, dedup

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
def dshield(inner, asn, dedup, url="http://dshield.org/asdetailsascii.html"):
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
        filtered = (x for x in data 
                    if x.strip() and not x.startswith("#") and dedup.add(x))
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
            list(inner)
    finally:
        print "ASN%s: done with %d events" % (asn, count)
        opened.close()

from idiokit import timer
import time
import heapq
from abusehelper.core import roomfarm, services

class DShieldService(roomfarm.RoomFarm):
    def __init__(self, xmpp, state_file=None, poll_interval=60*60.0):
        roomfarm.RoomFarm.__init__(self, state_file)

        self.xmpp = xmpp
        self.poll_interval = poll_interval

        self.asns = roomfarm.Counter()
        self.heap = list()

    @threado.stream
    def handle_room(inner, self, name):
        print "Joining room", repr(name)
        room = yield inner.sub(self.xmpp.muc.join(name))
        print "Joined room", repr(name)
        try:
            yield inner.sub(events.events_to_elements()
                            | room
                            | threado.throws())
        finally:
            print "Left room", repr(name)

    @threado.stream_fast
    def distribute(inner, self, asn):
        while True:
            yield inner

            rooms = self.asns.get(asn)
            for event in inner:
                for room in rooms:
                    room.send(event)

    @threado.stream
    def main(inner, self, global_dedup=None):
        if global_dedup is None:
            global_dedup = dedup.Dedup()

        try:
            while True:
                if not self.heap:
                    yield inner
                    continue

                current_time = time.time()
                expire_time, asn = self.heap[0]
                if expire_time > current_time:
                    yield inner, timer.sleep(expire_time-current_time)
                elif not self.asns.get(asn):
                    heapq.heappop(self.heap)
                else:
                    heapq.heappop(self.heap)
                    yield inner.sub(dshield(asn, global_dedup) 
                                    | self.distribute(asn))
                    expire_time = time.time() + self.poll_interval
                    heapq.heappush(self.heap, (expire_time, asn))
        except services.Stop:
            inner.finish(global_dedup)

    @threado.stream
    def session(inner, self, state, asn, room):
        if not self.asns.get(asn):
            heapq.heappush(self.heap, (time.time(), asn))
            self.send()
        room = self.rooms(inner, room)
        self.asns.inc(asn, room)
        try:
            while True:
                yield inner
        except services.Stop:
            inner.finish()
        finally:
            self.asns.dec(asn, room)
            self.rooms(inner)

def main(name, xmpp_jid, service_room, 
         poll_interval=60*60.0, state_file=None, 
         xmpp_password=None, log_file=None):
    import getpass
    from idiokit.xmpp import connect
    from abusehelper.core import log
    
    if not xmpp_password:
        xmpp_password = getpass.getpass("XMPP password: ")

    logger = log.config_logger(name, filename=log_file)

    @threado.stream
    def bot(inner):
        print "Connecting XMPP server with JID", xmpp_jid
        xmpp = yield connect(xmpp_jid, xmpp_password)
        xmpp.core.presence()

        print "Joining lobby", service_room
        lobby = yield inner.sub(services.join_lobby(xmpp, service_room, name))
        logger.addHandler(log.RoomHandler(lobby.room))

        service = DShieldService(xmpp, state_file, poll_interval)
        yield inner.sub(lobby.offer(name, service))
    return bot()
main.service_room_help = "the room where the services are collected"
main.xmpp_jid_help = "the XMPP JID (e.g. xmppuser@xmpp.example.com)"
main.xmpp_password_help = "the XMPP password"
main.log_file_help = "log to the given file instead of the console"

if __name__ == "__main__":
    from abusehelper.core import opts
    threado.run(opts.optparse(main), throw_on_signal=services.Stop())
