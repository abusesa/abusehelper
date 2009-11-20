import re

from abusehelper.core import events
from idiokit import threado, util
from idiokit.xmpp import connect
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

def main(xmpp_jid,
         xmpp_password,
         xmpp_room,
         irc_host,
         irc_channel,
         irc_port=6667, 
         irc_feed_nick=None,
         irc_own_nick="ircbot", 
         irc_password=None, 
         irc_use_ssl=False):

    @threado.stream
    def bot(inner):
        irc = IRC(irc_host, irc_port, ssl=irc_use_ssl)
        nick = yield irc.connect(irc_own_nick, password=irc_password)
        irc.join(irc_channel)

        xmpp = yield connect(xmpp_jid, xmpp_password)
        room = yield xmpp.muc.join(xmpp_room, nick)

        yield inner.sub(irc 
                        | filter(irc_channel, irc_feed_nick) 
                        | parse() 
                        | events.events_to_elements()
                        | room 
                        | threado.throws())
    threado.run(bot())
main.xmpp_jid_help = "the XMPP username (e.g. user@xmpp.example.com)"
main.xmpp_password_help = "the XMPP password"
main.xmpp_room_help = "the XMPP room where the feed is forwarded"
main.irc_host_help = "the IRC server hostname"
main.irc_channel_help = "the IRC feed channel"
main.irc_feed_nick_help = "listen this IRC nick (default: listen everybody)"
main.irc_use_ssl_help = "connect the IRC server using SSL (default: no SSL)"
main.irc_port_help = "the IRC port to connect to (default: %default)"
main.irc_own_nick_help = "the IRC own nickname used (default: %default)"
main.irc_password_help = "the IRC password used (default: no password)"

if __name__ == "__main__":
    import opts
    opts.optparse(main)
