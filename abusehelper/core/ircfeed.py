import re

from abusehelper.core import events, services, roomfarm
from idiokit import threado, util
from idiokit.irc import IRC

@threado.stream
def filter(inner, channel, nick=None):
    while True:
        prefix, command, params = yield inner

        if command != "PRIVMSG":
            continue
        if not params or params[0] != channel:
            continue

        sender = prefix.split("@", 1)[0].split("!", 1)[0]
        if nick is None or sender == nick:
            inner.send(params[-1])

@threado.stream
def parse(inner):
    field_str = "([^\s=]+)='([^']*)'"
    data_rex = re.compile("^([^\s>]+)>\s*(("+ field_str +"\s*,?\s*)*)\s*$")
    field_rex = re.compile(field_str)

    while True:
        data = yield inner

        match = data_rex.match(util.guess_encoding(data))
        if not match:
            continue

        event = events.Event()
        event.add("type", match.group(1))

        fields = field_rex.findall(match.group(2) or "")
        for key, value in fields:
            event.add(key, value)

        inner.send(event)

class IRCFeedService(roomfarm.RoomFarm):
    def __init__(self, xmpp, 
                 host, port, channel, own_nick, feed_nick, password, use_ssl):
        roomfarm.RoomFarm.__init__(self)

        self.xmpp = xmpp
        self.host = host
        self.port = port
        self.channel = channel
        self.own_nick = own_nick
        self.feed_nick = feed_nick
        self.password = password
        self.use_ssl = use_ssl

        self.asns = roomfarm.Counter()

    @threado.stream_fast
    def distribute(inner, self):
        while True:
            yield inner

            for event in inner:
                for asn in event.attrs.get("asn", ()):
                    rooms = self.asns.get(asn)
                    for room in rooms:
                        room.send(event)

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

    @threado.stream
    def session(inner, self, state, asn, room, **keys):
        asn = str(asn)
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

    @threado.stream
    def main(inner, self, state):
        try:
            irc = IRC(self.host, self.port, ssl=self.use_ssl)
            print "Connecting IRC server", self.host, "port", self.port
            yield inner.sub(irc.connect(self.own_nick, password=self.password))
            print "Connected IRC server", self.host, "port", self.port
            irc.join(self.channel)
            print "Joined IRC channel", self.channel
            
            yield inner.sub(irc 
                            | filter(self.channel, self.feed_nick) 
                            | parse()
                            | self.distribute())
        except services.Stop:
            inner.finish()

def main(name,
         xmpp_jid,
         xmpp_password,
         service_room,
         irc_host,
         irc_channel,
         irc_port=6667, 
         irc_feed_nick=None,
         irc_own_nick="ircbot", 
         irc_password=None, 
         irc_use_ssl=False,
         log_file=None):
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
        lobby = yield services.join_lobby(xmpp, service_room, name)
        logger.addHandler(log.RoomHandler(lobby.room))

        service = IRCFeedService(xmpp, irc_host, irc_port, 
                                 irc_channel, irc_own_nick, irc_feed_nick, 
                                 irc_password, irc_use_ssl)
        yield inner.sub(lobby.offer(name, service))
    return bot()
main.xmpp_jid_help = "the XMPP username (e.g. user@xmpp.example.com)"
main.xmpp_password_help = "the XMPP password"
main.service_room_help = "the room where the services are collected"
main.irc_host_help = "the IRC server hostname"
main.irc_channel_help = "the IRC feed channel"
main.irc_feed_nick_help = "listen this IRC nick (default: listen everybody)"
main.irc_use_ssl_help = "connect the IRC server using SSL (default: no SSL)"
main.irc_port_help = "the IRC port to connect to (default: %default)"
main.irc_own_nick_help = "the IRC own nickname used (default: %default)"
main.irc_password_help = "the IRC password used (default: no password)"

if __name__ == "__main__":
    from abusehelper.core import opts
    threado.run(opts.optparse(main), throw_on_signal=services.Stop())
