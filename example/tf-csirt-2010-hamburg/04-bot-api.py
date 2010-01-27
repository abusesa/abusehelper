from idiokit import threado
from idiokit import jid
from abusehelper.core import bot

class ForwardBot(bot.XMPPBot):
    # Define two parameters (in addition to the default XMPPBot ones)
    room_src = bot.Param("the source room")
    room_dst = bot.Param("the destination room")

    @threado.stream
    def main(inner, self):
        # Join the XMPP network using credentials given from the command line
        conn = yield self.xmpp_connect()

        # Join the XMPP rooms
        src = yield conn.muc.join(self.room_src, self.bot_name)
        dst = yield conn.muc.join(self.room_dst, self.bot_name)
        self.log.info("Joined rooms %r and %r", self.room_src, self.room_dst)

        # Forward body elements from the src room to the dst room
        # but filter away stuff by the bot itself to avoid nasty loops.
        own_jid = src.nick_jid
        yield src | self.room_filter(own_jid) | dst | threado.dev_null()

    @threado.stream
    def room_filter(inner, self, own_jid):
        while True:
            # Receive one XML element from the pipe input
            element = yield inner
            
            # Prevent endless feedback loops
            sender = jid.JID(element.get_attr("from"))
            if sender == own_jid:
                continue

            # Forward the body elements
            for body in element.named("message").children("body"):
                inner.send(body)

# Instantiate a ForwardBot from command line parameters and run it.
ForwardBot.from_command_line().run()
