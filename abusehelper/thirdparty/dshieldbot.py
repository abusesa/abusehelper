from abusehelper.core import events
from idiokit import threado, util
from idiokit.xmpp import XMPP
import urlparse
import urllib
import urllib2
import csv
import getpass

#import dictnormalizer

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


class DSHIELD(threado.ThreadedStream):
     def __init__(self, url, aslist, poll_frequency=10):
        threado.ThreadedStream.__init__(self)
        self.url = url
        self.aslist = aslist
        self.poll_frequency = poll_frequency
        # The current DShield csv fields, in order.
        self.headers = ["ip", "reports", "targets", "firstseen", "lastseen", "updated"]
        self.start()



     def poll(self):
         for asn in self.aslist:

             # Probably a kosher-ish way to create an ASN specific URL.
             parsed = urlparse.urlparse(self.url)
             parsed = list(parsed)
             parsed[4] = urllib.urlencode({ "as" : str(asn) })
             url = urlparse.urlunparse(parsed)
             print 'url', url
             for event in self.url2csv2events(url,asn):
                 self.inner.send(event)

     def url2csv2events(self,url,asn):
         try:
             opened = urllib2.urlopen(url)
         except urllib2.URLError, error:
             if hasattr(error, "code"):
                 print "Site borked! HTTP error:", error.core
                 raise
             if hasattr(error, "reason"):
                 print "Server borked! reason:", error.reason
                 raise    
         

         filtered = (x for x in opened if x.strip() and not x.startswith("#"))
         reader = csv.DictReader(filtered, self.headers, delimiter="\t")
         while True:
             try:
                 row = reader.next()
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
             event.add('asn', str(asn))
             for key, value in row.items():
                 if value is None:
                     continue
                 event.add(key, util.guess_encoding(value).strip())
             yield event
        
     def run(self):
         print 'running'
         while True:
             self.poll()
             try:
                 print 'try'
                 item = self.inner.next(self.poll_frequency)
             except threado.Timeout:
                 print 'pass'
                 pass
             print 'poll'


if __name__ == "__main__":
    aslist = set((1111,1112))

    dshield = DSHIELD("https://secure.dshield.org/asdetailsascii.html",
                      aslist,poll_frequency=10)

    id = 'janike%iki.fi@clarifiednetworks.com'
    xmpp = XMPP(id, getpass.getpass())
    xmpp.connect()
    room = xmpp.muc.join("abusehelper.dshield@conference.clarifiednetworks.com", "dshield1")

    

    for _ in dshield | events.events_to_elements() | room |threado.throws():
        pass
