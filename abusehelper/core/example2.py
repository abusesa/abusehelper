import time
import urllib2
from idiokit.xmpp import connect
from idiokit.jid import JID
from idiokit import threado, timer
from abusehelper.core import roomfarm, events, services

class ExampleService(roomfarm.RoomFarm):
    def __init__(self, xmpp, url, poll_interval=600.0):
        roomfarm.RoomFarm.__init__(self)
        self.xmpp = xmpp
        self.url = url
        self.dsts = roomfarm.Counter()
        self.poll_interval = poll_interval

    @threado.stream
    def session(inner, self, state, room, **keys):
        room = self.rooms(inner, room)
        self.dsts.inc(room)
        try:
            while True:
                yield inner
        except services.Stop:
            inner.finish()
        finally:
            self.dsts.dec(room)
            self.rooms(inner)

    @threado.stream
    def main(inner, self, global_dedup=None):
        """Create pipeline for events. distribute() sends events to 
        specific rooms."""

        try:
            yield inner.sub(self.fetch()
                            | self.timestamp()
                            | self.distribute())
        except services.Stop:
            inner.finish()

    @threado.stream
    def handle_room(inner, self, name):
        """Join the room and create pipeline for incoming elements."""

        print "Joining room", repr(name)
        room = yield inner.sub(self.xmpp.muc.join(name))
        print "Joined room", repr(name)
        try:
            yield inner.sub(events.events_to_elements()
                            | room
                            | threado.throws())
        finally:
            print "Left room", repr(name)

    @threado.stream
    def fetch(inner, self):
        """Fetch content from url, create event and send it to the pipe.
        Sleep a bit and repeat forever."""

        while True:
            fileobj = urllib2.urlopen(self.url)
            content = fileobj.read()
            fileobj.close()

            event = events.Event()
            event.add("content", content)

            yield inner.send(event)
            yield inner.sub(timer.sleep(self.poll_interval))

    @threado.stream_fast
    def timestamp(inner, self):
        while True:
            yield inner

            for event in inner:
                event.add("time", time.strftime("%Y-%m-%d %H:%M:%S"))
                inner.send(event)

    @threado.stream_fast
    def distribute(inner, self):
        """Send event to specific rooms. After this events are handled
        with handle_room()."""

        while True:
            yield inner

            for event in inner:
                for room, _ in self.dsts:
                    room.send(event)

def main(name, xmpp_jid, service_room, url, xmpp_password=None, log_file=None):
    import getpass
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

        service = ExampleService(xmpp, url)

        service.session(None, "target1")
        service.session(None, "target2")
        yield inner.sub(lobby.offer(name, service))
    return bot()

main.service_room_help = "the room where the services are collected"
main.xmpp_jid_help = "the XMPP username (e.g. user@xmpp.example.com)"
main.url_help = "the content url"
main.xmpp_password_help = "the XMPP password"
main.log_file_help = "log to the given file instead of the console"

if __name__ == "__main__":
    from abusehelper.core import opts
    threado.run(opts.optparse(main), throw_on_signal=services.Stop())
