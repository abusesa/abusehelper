"""
Read '/repr key=val, key2=val2' style messages from body and throw
back similar message which includes machine readable idiokit
namespace.
"""

from abusehelper.core import bot, events
from idiokit import threado
from idiokit.xmpp import jid

class ReprBot(bot.XMPPBot):
    room = bot.Param("repr room")

    @threado.stream
    def main(inner, self):
        conn = yield self.xmpp_connect()
        src = yield conn.muc.join(self.room, self.bot_name)

        self.log.info("Joined room %r.", self.room)

        yield inner.sub(src
                        | self.repr(src.nick_jid)
                        | events.events_to_elements()
                        | src)

    @threado.stream
    def repr(inner, self, own_jid):
        while True:
            element = yield inner

            sender = jid.JID(element.get_attr("from"))
            if sender == own_jid:
                continue

            for body in element.named("message").children("body"):
                text = body.text.strip()
                if not text.startswith("/repr "):
                    continue

                try:
                    event = events.Event.from_unicode(text[5:])
                except ValueError:
                    continue
                inner.send(event)

if __name__ == "__main__":
    ReprBot.from_command_line().run()
