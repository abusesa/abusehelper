import re
import cgi
import sys
import time
import urllib2
import httplib
import socket
import urlparse
import cStringIO as StringIO
import xml.etree.cElementTree as etree

from idiokit import threado, timer
from abusehelper.core import events, services, roomfarm, dedup, cymru

class FetchUrlFailed(Exception):
    pass

@threado.stream
def fetch_url(inner, opener, url):
    try:
        fileobj = yield inner.thread(opener.open, url)
        list(inner)
        try:
            data = yield inner.thread(fileobj.read)
        finally:
            fileobj.close()
    except (urllib2.URLError, httplib.HTTPException, socket.error), error:
        raise FetchUrlFailed, error
    list(inner)
    inner.finish(data)

TABLE_REX = re.compile("</h3>\s*(<table>.*?</table>)", re.I | re.S)

@threado.stream
def fetch_extras(inner, opener, url):
    try:
        data = yield inner.sub(fetch_url(opener, url))
    except FetchUrlFailed:
        inner.finish(list())

    match = TABLE_REX.search(data)
    if match is None:
        inner.finish(list())

    table = etree.XML(match.group(1))
    keys = [th.text or "" for th in table.findall("thead/tr/th")]
    keys = map(str.strip, keys)
    values = [th.text or "" for th in table.findall("tbody/tr/td")]
    values = map(str.strip, values)
    items = [item for item in zip(keys, values) if all(item)]
    inner.finish(items)

ATOM_NS = "http://www.w3.org/2005/Atom"
DC_NS = "http://purl.org/dc/elements/1.1"

@threado.stream
def xmlfeed(inner, dedup, opener, url):
    try:
        print "Downloading the report"
        data = yield inner.sub(fetch_url(opener, url))
    except FetchUrlFailed:
        print >> sys.stderr, "Failed to download the report:", exc
        return
    print "Downloaded the report"

    count = 0
    for _, elem in etree.iterparse(StringIO.StringIO(data)):
        yield
        list(inner)

        if elem.tag != etree.QName(ATOM_NS, "entry"):
            continue
        if not dedup.add(etree.tostring(elem)):
            continue
        
        event = events.Event()
        event.add("feed", "xmlfeed")

        updated = elem.find(str(etree.QName(ATOM_NS, "updated")))
        if updated is not None:
            event.add("updated", updated.text)

        subject = elem.find(str(etree.QName(DC_NS, "subject")))
        if subject is not None:
            event.add("ip", subject.text)

        for link in elem.findall(str(etree.QName(ATOM_NS, "link"))):
            if link.attrib.get("rel", None) != "detail":
                continue
            url = link.attrib.get("href", None)
            if not url:
                continue

            event.add("url", url)

            extras = yield inner.sub(fetch_extras(opener, url))
            for key, value in extras:
                event.add(key, value)

            parsed = urlparse.urlparse(url)
            for key, value in cgi.parse_qsl(parsed.query):
                event.add(key, value)

        inner.send(event)

        count += 1
        if count % 100 == 0:
            print "Fed", count, "new events so far"
    print "Finished feeding, got", count, "new events"

class XmlFeedService(roomfarm.RoomFarm):
    def __init__(self, xmpp, url, state_file=None, poll_interval=60*60.0):
        roomfarm.RoomFarm.__init__(self, state_file)

        self.xmpp = xmpp
        self.url = url
        self.poll_interval = poll_interval

        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
        self.asns = roomfarm.Counter()

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
    def distribute(inner, self):
        while True:
            yield inner

            for event in inner:
                for asn in event.attrs.get("asn", ()):
                    for room in self.asns.get(asn):
                        room.send(event)

    @threado.stream
    def _main(inner, self, global_dedup):
        while True:
            yield inner.sub(xmlfeed(global_dedup, self.opener, self.url))
            yield inner, timer.sleep(self.poll_interval)

    @threado.stream
    def main(inner, self, global_dedup=None):
        if global_dedup is None:
            global_dedup = dedup.Dedup()

        try:
            yield inner.sub(self._main(global_dedup)
                            | cymru.CymruWhois()
                            | self.distribute())
        except services.Stop:
            inner.finish(global_dedup)

    @threado.stream
    def session(inner, self, state, asn, room):
        asn = unicode(asn)

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

def main(name, xmpp_jid, service_room, feed_url, poll_interval=60.0*60.0, 
         state_file=None, xmpp_password=None, log_file=None):
    import getpass
    from idiokit.xmpp import connect
    from abusehelper.core import log
    
    if not xmpp_password:
        xmpp_password = getpass.getpass("XMPP password: ")

    logger = log.config_logger(name, filename=log_file)

    @threado.stream
    def bot(inner):
        print "Connecting XMPP server with JID", xmpp_jid
        xmpp = yield inner.sub(connect(xmpp_jid, xmpp_password))
        xmpp.core.presence()

        print "Joining lobby", service_room
        lobby = yield inner.sub(services.join_lobby(xmpp, service_room, name))
        logger.addHandler(log.RoomHandler(lobby.room))

        service = XmlFeedService(xmpp, feed_url, state_file, poll_interval)
        yield inner.sub(lobby.offer(name, service))
    return bot()
main.service_room_help = "the room where the services are collected"
main.xmpp_jid_help = "the XMPP JID (e.g. xmppuser@xmpp.example.com)"
main.xmpp_password_help = "the XMPP password"
main.log_file_help = "log to the given file instead of the console"

if __name__ == "__main__":
    from abusehelper.core import opts
    threado.run(opts.optparse(main), throw_on_signal=services.Stop())
