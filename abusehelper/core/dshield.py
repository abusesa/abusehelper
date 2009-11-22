import csv
import urllib
import time
import urllib2
import urlparse
import time
import gzip
import cStringIO as StringIO

from idiokit import threado, util
from abusehelper.core import events

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
    # The current DShield csv fields, in order.
    headers = ["ip", "reports", "targets", "firstseen", "lastseen", "updated"]

    # Probably a kosher-ish way to create an ASN specific URL.
    parsed = urlparse.urlparse(url)
    parsed = list(parsed)
    parsed[4] = urllib.urlencode({ "as" : str(asn) })
    url = urlparse.urlunparse(parsed)

    print "ASN" + str(asn) + ": connecting", time.time()
    opened = yield inner.thread(urllib2.urlopen, url)
    print "ASN" + str(asn) + ": downloading", time.time()
    data = yield inner.thread(read_data, opened)
    print "ASN" + str(asn) + ": downloaded", time.time()

    count = 0
    try:
        # Lazily filter away empty lines and lines starting with '#'
        filtered = (x for x in data if x.strip() and not x.startswith("#"))
        reader = csv.DictReader(filtered, headers, delimiter="\t")
        for row in reader:
            # DShield uses leading zeros for IP addresses. Try to
            # parse and then unparse the ip back, to get rid of those.
            row["ip"] = sanitize_ip(row.get("ip", None))

            if count % 100 == 0:
                print "ASN" + str(asn) + ": fed", count, "events", time.time()
            count += 1
            
            # Convert the row to an event, send it forwards in the
            # pipeline. Forcefully encode the values to unicode.
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
        print "ASN" + str(asn) + ": done", time.time()
        opened.close()

from idiokit import timer
import time
import heapq
import services

class DShieldSession(services.Session):
    def __init__(self, service):
        services.Session.__init__(self)
        self.service = service
        self.asn = None
    
    @threado.stream
    def config(inner, self, conf):
        asn = None if conf is None else conf.get("asn", None)
        if asn != self.asn:
            if asn is not None:
                self.service.add_asn(asn)
            if self.asn is not None:
                self.service.remove_asn(self.asn)
            self.asn = asn
        yield
        conf = dict(asn=asn, room=unicode(self.service.room.room_jid))
        inner.finish(conf)

class DShieldService(services.Service):
    def __init__(self, xmpp, room, update_interval=300.0):
        services.Service.__init__(self)

        self.xmpp = xmpp
        self.room = room
        self.update_interval = update_interval

        self.asns = dict()
        self.heap = list()

    def add_asn(self, asn):
        self.asns[asn] = self.asns.get(asn, 0) + 1
        if self.asns[asn] == 1:
            heapq.heappush(self.heap, (time.time(), asn))
            self.send()

    def remove_asn(self, asn):
        count = self.asns.get(asn, 0) - 1
        if count <= 0:
            self.asns.pop(asn, None)
            self.send()
        else:
            self.asns[asn] = count

    def run(self):
        yield self.inner.sub(self._run()
                             | events.events_to_elements()
                             | self.room
                             | threado.throws())

    @threado.stream
    def _run(inner, self):
        while True:
            if not self.heap:
                yield inner
                continue

            current_time = time.time()
            expire_time, asn = self.heap[0]
            if expire_time > current_time:
                yield inner, timer.sleep(expire_time-current_time)
            elif self.asns.get(asn, 0) <= 0:
                heapq.heappop(self.heap)
                self.asns.pop(asn, None)
            else:
                heapq.heappop(self.heap)
                yield inner.sub(dshield(asn))
                expire_time = time.time() + self.update_interval
                heapq.heappush(self.heap, (expire_time, asn))

    def session(self):
        return DShieldSession(self)

def main(xmpp_jid, service_room, dshield_room, xmpp_password=None):
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
        print "Joining DShield room", dshield_room
        room = yield xmpp.muc.join(dshield_room)
        print "Offering DShield service"
        offer = yield lobby.offer("dshield", DShieldService(xmpp, room))
        yield inner.sub(offer)
    return bot()
main.service_room_help = "the room where the services are collected"
main.dshield_room_help = "the room where the DShield reports are fed"
main.xmpp_jid_help = "the XMPP JID (e.g. xmppuser@xmpp.example.com)"
main.xmpp_password_help = "the XMPP password"

if __name__ == "__main__":
    import opts
    threado.run(opts.optparse(main))
