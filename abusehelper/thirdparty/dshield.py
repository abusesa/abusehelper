import csv
import urllib
import urllib2
import urlparse
import zlib
import gzip
import cStringIO as StringIO

from idiokit import threado, util, timer
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

def read_data(fileobj, compression=9):
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
def dshield(inner, asn):
    # The current DShield csv fields, in order.
    headers = ["ip", "reports", "targets", "firstseen", "lastseen", "updated"]

    # Probably a kosher-ish way to create an ASN specific URL.
    parsed = urlparse.urlparse("http://dshield.org/asdetailsascii.html")
    parsed = list(parsed)
    parsed[4] = urllib.urlencode({ "as" : str(asn) })
    url = urlparse.urlunparse(parsed)

    opened = yield inner.thread(urllib2.urlopen, url)
    data = yield inner.thread(read_data, opened)

    try:
        # Lazily filter away empty lines and lines starting with '#'
        filtered = (x for x in data if x.strip() and not x.startswith("#"))
        reader = csv.DictReader(filtered, headers, delimiter="\t")
        for row in reader:
            # DShield uses leading zeros for IP addresses. Try to
            # parse and then unparse the ip back, to get rid of those.
            row["ip"] = sanitize_ip(row.get("ip", None))
            
            # Convert the row to an event, send it forwards in the
            # pipeline. Forcefully encode the values to unicode.
            event = events.Event()
            event.add('asn', str(asn))
            for key, value in row.items():
                if value is None:
                    continue
                event.add(key, util.guess_encoding(value).strip())
            inner.send(event)
            yield
    finally:
        opened.close()

@threado.stream
def dshieldbot(inner, aslist, poll_frequency=10.0):
    aslist = list(set(map(int, aslist)))
    aslist.sort()

    while True:
        for asn in aslist:
            print "Fetching ASN", asn

            yield inner.sub(dshield(asn))

            print "ASN", asn, "done"

        yield timer.sleep(poll_frequency)

@threado.stream
def main(inner):
    import getpass
    from idiokit.xmpp import connect

    jid = raw_input("Username: ")
    password = getpass.getpass()

    xmpp = yield connect(jid, password)
    room = yield xmpp.muc.join("abusehelper.dshield", "dshieldbot")

    asns = [1111, 1112]
    bot = dshieldbot(asns, poll_frequency=10.0)
    yield inner.sub(bot | events.events_to_elements() | room | threado.throws())

if __name__ == "__main__":
    threado.run(main())
