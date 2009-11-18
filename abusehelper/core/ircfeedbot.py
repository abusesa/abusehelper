import re

from abusehelper.core import events
from idiokit import threado, util
from idiokit.xmpp import connect
from idiokit.irc import IRC

@threado.stream
def filter(inner, channel, nick):
    while True:
        prefix, command, params = yield inner

        if command != "PRIVMSG":
            continue
        if not params or params[0] != channel:
            continue

        sender = prefix.split("@", 1)[0].split("!", 1)[0]
        if sender == nick:
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

@threado.stream
def main(inner):
    channel = "#ircfeedbot"

    irc = IRC("irc.example.com", 6667, ssl=False)
    nick = yield irc.connect("ircbot", password=None)
    irc.join(channel)

    xmpp = yield connect("username@example.com", "password")
    room = yield xmpp.muc.join("room@conference.example.com", nick)

    yield inner.sub(irc 
                    | filter(channel, "feedbot") 
                    | parse() 
                    | events.events_to_elements()
                    | room 
                    | threado.throws())

if __name__ == "__main__":
    threado.run(main())
