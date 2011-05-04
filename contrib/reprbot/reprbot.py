"""
Read '/repr key=val, key2=val2' style messages from body and throw
back similar message which includes machine readable idiokit
namespace.
"""
from idiokit import threado
from abusehelper.core import events
from idiokit import jid
from abusehelper.core import bot
import re


class ReprBot(bot.XMPPBot):
    """
    ReprBot implmentation
    """
    # Define two parameters (in addition to the default XMPPBot ones)
    room = bot.Param("repr room")


    @threado.stream
    def main(inner, self):
        # Join the XMPP network using credentials given from the command line
        conn = yield self.xmpp_connect()

        # Join the XMPP rooms
        src = yield conn.muc.join(self.room, self.bot_name)

        self.log.info("Joined room %r.", self.room)

        # Forward body elements from the src room to the dst room
        # but filter away stuff by the bot itself to avoid nasty loops.
        own_jid = src.nick_jid
        yield inner.sub(src | self.repr(own_jid) | \
                            events.events_to_elements() | src )
    @threado.stream
    def repr(inner, self, own_jid):
        """Create idiokit events and filter own messages."""
        while True:
            # Receive one XML element from the pipe input
            element = yield inner
            # Prevent endless feedback loops
            sender = jid.JID(element.get_attr("from"))
            if sender == own_jid:
                continue

            # Forward the body elements
            for body in element.named("message").children("body"):

                message = re.search("/repr (.*)", body.text)
                if message:
                    event = events.Event()
                    for keyvalue in message.group(1).split(","):
                        keyvalue =  keyvalue.split("=")
                        if len(keyvalue) > 1:

                            key = keyvalue[0].strip()
                            value = keyvalue[1].strip()
                            event.add(key, value)

                    inner.send(event)

                 
# Instantiate a ReprBot from command line parameters and run it.
ReprBot.from_command_line().run()
