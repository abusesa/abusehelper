import time
from idiokit.xmpp import connect
from idiokit.jid import JID
from idiokit import threado
from abusehelper.core import roomfarm, events, services

class ExampleService(roomfarm.RoomFarm):
    def __init__(self, xmpp):
        roomfarm.RoomFarm.__init__(self)
        self.xmpp = xmpp
        self.dsts = roomfarm.Counter()

    #TODO: comment @threado.stream
    @threado.stream
    def session(inner, self, state, room, **keys):
        """Add new rooms."""

        room = self.rooms(inner, room)
        self.dsts.inc(room)
        try:
            while True:
                #TODO: comment yield inner
                yield inner

        except services.Stop:
            inner.finish()
        finally:
            self.dsts.dec(room)
            self.rooms(inner)

    @threado.stream
    def handle_room(inner, self, name):
        """Join the room and create pipeline for incoming elements."""

        print "Joining room", repr(name)
        room = yield inner.sub(self.xmpp.muc.join(name))
        print "Joined room", repr(name)

        try:
            yield inner.sub(room
                            | self.listen(room)
                            | self.timestamp()
                            | events.events_to_elements()
                            | self.distribute(room)
                            | threado.throws())
        finally:
            print "Left room", repr(name)

    #TODO: comment @threado.stream_fast
    @threado.stream_fast
    def listen(inner, self, room):
        """Listen room, convert incoming elements to events, add room info
        and send events to the pipe."""

        while True:
            yield inner

            for elements in inner:
                for message in elements.named("message").with_attrs("from"):
                    sender = JID(message.get_attr("from"))
                    if sender == room.nick_jid:
                        continue

                    for body in message.children("body"):
                        event = events.Event()
                        event.add("text", body.text)
                        event.add("room", unicode(room.room_jid))
                        inner.send(event)

    @threado.stream_fast
    def timestamp(inner, self):
        """Add timestamp to incoming events and forward them back
        to the pipeline."""

        while True:
            yield inner

            for event in inner:
                event.add("time", time.strftime("%Y-%m-%d %H:%M:%S"))
                inner.send(event)


    @threado.stream_fast
    def distribute(inner, self, goom):
        """Send incoming elements to rooms configured with session()."""

        while True:
            yield inner

            for element in inner:
                for room, _ in self.dsts:
                    room.send(element)

def main(name, xmpp_jid, service_room, xmpp_password=None, log_file=None):
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

        service = ExampleService(xmpp)
        service.session(None, "target1")
        service.session(None, "target2")
        yield inner.sub(lobby.offer(name, service))
    return bot()

main.service_room_help = "the room where the services are collected"
main.xmpp_jid_help = "the XMPP username (e.g. user@xmpp.example.com)"
main.xmpp_password_help = "the XMPP password"
main.log_file_help = "log to the given file instead of the console"

if __name__ == "__main__":
    from abusehelper.core import opts
    threado.run(opts.optparse(main), throw_on_signal=services.Stop())
