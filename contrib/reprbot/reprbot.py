"""
Read '/repr key=val, key2=val2' style messages from body and throw
back similar message which includes machine readable idiokit
namespace.
"""

import idiokit
from idiokit.xmpp import jid
from abusehelper.core import bot, events

class ReprBot(bot.XMPPBot):
    room = bot.Param("repr room")

    @idiokit.stream
    def main(self):
        conn = yield self.xmpp_connect()
        src = yield conn.muc.join(self.room, self.bot_name)

        self.log.info("Joined room %r.", self.room)

        repr = self.repr(src.jid) | events.events_to_elements()
        yield repr | src | repr

    @idiokit.stream
    def repr(self, own_jid):
        while True:
            element = yield idiokit.next()

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

                yield idiokit.send(event)
                break

if __name__ == "__main__":
    ReprBot.from_command_line().run()
