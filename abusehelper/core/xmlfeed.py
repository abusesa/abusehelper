import csv
import urllib
import time
import urllib2
import urlparse
import time
import gzip
import cStringIO as StringIO
import xml.etree.ElementTree as etree

from idiokit import threado, util
from abusehelper.core import events, services, dedup, cymru

@threado.stream
def xmlfeed(inner, dedup, opener, 
            url="http://xmlfeed.example.com/"):
    try:
        fileobj = opener.open(url)
    except urllib2.HTTPError, e:
        return

    for xmlevent, elem in etree.iterparse(fileobj):
        if elem.tag.endswith('updated'):
            event = events.Event()
            event.add('feed', 'xmlfeed')
            event.add('updated', elem.text)
        elif elem.tag.endswith('subject'):
            event.add('ip', elem.text)
        elif elem.attrib.get('rel', '') == 'detail':
            url = elem.attrib.get('href', None)
            parts = url.split("?")

            if not url or len(parts) < 2 or (dedup and not dedup.add(url)):
                continue

            event.add('url', url)

            parts = parts[1].split("&")
            for part in parts:
                pair = part.split("=")
                if len(pair) < 2:
                    continue

                event.add(pair[0], pair[1])

            inner.send(event)
            yield

    yield
    fileobj.close()

@threado.stream
def asn_filter(inner, asn_list):
    while True:
        for event in inner:
            #event_asn = list(event.attrs.get('url', [None]))[0]
            #if event_asn and event_asn in asn_list:
            #    event.add('asn', str(event_asn))
            #    inner.send(event)
            inner.send(event)
            yield
        yield inner

@threado.stream
def event_extras(inner, opener):
    while True:
        for event in inner:
            url = list(event.attrs.get('url', [None]))[0]
            type = list(event.attrs.get('datasource', [None]))[0]
            if not url or not type:
                continue

            type = type[0].upper() + type[1:]

            try:
                fileobj = opener.open(url)
            except urllib2.HTTPError, e:
                continue

            data = fileobj.read()

            ft = 0
            table = list()
            span = '<span class="title">%s</span>' % type

            for line in data.split("\n"):
                line = line.lstrip()

                if ft == 0 and line.startswith(span):
                    ft = 1
                elif ft == 1 and line.startswith('<table>'):
                    ft = 2
                    table.append(line)
                elif ft == 2 and line:
                    table.append(line)
                    if line.startswith('</table>'):
                        break

            event.add('extras', "\n".join(table))
            inner.send(event)
            yield

        yield inner

from idiokit import timer
import time
import cookielib
from abusehelper.core import roomfarm, services

class XmlFeedService(roomfarm.RoomFarm):
    def __init__(self, xmpp, state_file=None, poll_interval=60*60.0):
        roomfarm.RoomFarm.__init__(self, state_file)

        self.xmpp = xmpp
        self.poll_interval = poll_interval
        self.expire_time = float()

        jar = cookielib.FileCookieJar("cookies")
        self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(jar))

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
                print event.attrs

                asn = list(event.attrs.get('asn', [None]))[0]
                if not asn:
                    continue

                for room in self.asns.get(asn):
                    room.send(event)

    @threado.stream
    def main(inner, self, global_dedup=None):
        if global_dedup is None:
            global_dedup = dedup.Dedup()

        try:
            while True:
                current_time = time.time()
                if self.expire_time > current_time:
                    yield inner, timer.sleep(self.expire_time-current_time)
                else:
                    yield inner.sub(xmlfeed(global_dedup, self.opener) 
                                    | cymru.CymruWhois()
                                    | asn_filter(self.asns.keys.keys())
                                    | event_extras(self.opener)
                                    | self.distribute())
                    self.expire_time = time.time() + self.poll_interval
        except services.Stop:
            inner.finish(global_dedup)

    @threado.stream
    def session(inner, self, state, asn, room):
        if not self.asns.get(asn):
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
         poll_interval=0.15*60.0, state_file=None, 
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
        xmpp = yield inner.sub(connect(xmpp_jid, xmpp_password))
        xmpp.core.presence()

        print "Joining lobby", service_room
        lobby = yield inner.sub(services.join_lobby(xmpp, service_room, name))
        logger.addHandler(log.RoomHandler(lobby.room))

        service = XmlFeedService(xmpp, state_file, poll_interval)
        service.session(None, "007", "keklol")
        service.session(None, "009", "keklol")
        yield inner.sub(lobby.offer(name, service))
    return bot()
main.service_room_help = "the room where the services are collected"
main.xmpp_jid_help = "the XMPP JID (e.g. xmppuser@xmpp.example.com)"
main.xmpp_password_help = "the XMPP password"
main.log_file_help = "log to the given file instead of the console"

if __name__ == "__main__":
    from abusehelper.core import opts
    threado.run(opts.optparse(main), throw_on_signal=services.Stop())


