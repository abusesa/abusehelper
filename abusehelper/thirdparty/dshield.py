import csv
import urllib
import urllib2
import urlparse

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

@threado.thread
def call_in_thread(inner, func, *args, **keys):
    # Launch a thread, call the given function with the given
    # arguments. Send out the result or the exception.
    inner.send(func(*args, **keys))

@threado.stream
def dshield(inner, asn):
    # The current DShield csv fields, in order.
    headers = ["ip", "reports", "targets", "firstseen", "lastseen", "updated"]

    # Probably a kosher-ish way to create an ASN specific URL.
    parsed = urlparse.urlparse("https://secure.dshield.org/asdetailsascii.html")
    parsed = list(parsed)
    parsed[4] = urllib.urlencode({ "as" : str(asn) })
    url = urlparse.urlunparse(parsed)

    try:
        opened = yield call_in_thread(urllib2.urlopen, url)
    except urllib2.URLError, error:
        if hasattr(error, "code"):
            print "Site borked! HTTP error:", error.core
            raise
        if hasattr(error, "reason"):
            print "Server borked! reason:", error.reason
            raise

    try:
        # Lazily filter away empty lines and lines starting with '#'
        filtered = (x for x in opened if x.strip() and not x.startswith("#"))

        reader = csv.DictReader(filtered, headers, delimiter="\t")
        while True:
            try:
                row = yield call_in_thread(reader.next)
            except StopIteration:
                # StopIteration is OK, means that we've reached the
                # end of reader.
                break
            
            # DShield uses leading zeros for IP addresses. Try to
            # parse and then unparse the ip back, to get rid of those.
            row["ip"] = sanitize_ip(row.get("ip", None))

            # Convert the row to an event, send it forwards in the
            # pipeline. Forcefully encode the values to unicode.
            event = events.Event()
            for key, value in row.items():
                if value is None:
                    continue
                event.add(key, util.guess_encoding(value).strip())
            inner.send(event)
    finally:
        opened.close()

for event in dshield(3249): # dshield("3249") works too, doesn't matter
    print event.attrs
