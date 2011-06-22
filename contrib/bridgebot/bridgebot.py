import getpass
from idiokit import threado, xmpp
from abusehelper.core import bot

@threado.stream_fast
def peel_messages(inner):
    while True:
        yield inner

        for elements in inner:
            for message in elements.named("message"):
                inner.send(message.children())

class BridgeBot(bot.Bot):
    xmpp_src_jid = bot.Param("the XMPP src JID")
    xmpp_src_password = bot.Param("the XMPP src password", default=None)
    xmpp_src_room = bot.Param("the XMPP src room")
    xmpp_src_ignore_cert = bot.BoolParam("a PEM formatted file of CAs to be "+
                                         "used in addition to the system CAs", 
                                         default=None)
    xmpp_src_extra_ca_certs = bot.Param("do not perform any verification for "+
                                        "the XMPP service's SSL certificate",
                                        default=None)

    xmpp_dst_jid = bot.Param("the XMPP dst JID")
    xmpp_dst_password = bot.Param("the XMPP dst password", default=None)
    xmpp_dst_room = bot.Param("the XMPP dst room")
    xmpp_dst_ignore_cert = bot.BoolParam("a PEM formatted file of CAs to be "+
                                         "used in addition to the system CAs", 
                                         default=None)
    xmpp_dst_extra_ca_certs = bot.Param("do not perform any verification for "+
                                        "the XMPP service's SSL certificate",
                                        default=None)
    
    def __init__(self, **keys):
        bot.Bot.__init__(self, **keys)

        if self.xmpp_src_password is None:
            self.xmpp_src_password = getpass.getpass("XMPP src password: ")
        if self.xmpp_dst_password is None:
            self.xmpp_dst_password = getpass.getpass("XMPP dst password: ")

    def run(self):
        return threado.run(self.main())

    @threado.stream
    def _join(inner, self, _type, jid, password, 
              ignore_cert, ca_certs, room_name):
        verify_cert = not ignore_cert

        self.log.info("Connecting to XMPP %s server with JID %r", _type, jid)
        connection = yield inner.sub(xmpp.connect(jid, password,
                                                  ssl_verify_cert=verify_cert,
                                                  ssl_ca_certs=ca_certs))
        
        self.log.info("Connected to XMPP %s server with JID %r", _type, jid)
        connection.core.presence()

        self.log.info("Joining %s room %r", _type, room_name)
        room = yield inner.sub(connection.muc.join(room_name, self.bot_name))
        
        self.log.info("Joined %s room %r", _type, room_name)
        inner.finish(room)

    @threado.stream
    def main(inner, self):
        dst = yield inner.sub(self._join("dst",
                                         self.xmpp_dst_jid,
                                         self.xmpp_dst_password,
                                         self.xmpp_dst_ignore_cert,
                                         self.xmpp_dst_extra_ca_certs,
                                         self.xmpp_dst_room))
        src = yield inner.sub(self._join("src",
                                         self.xmpp_src_jid,
                                         self.xmpp_src_password,
                                         self.xmpp_src_ignore_cert,
                                         self.xmpp_src_extra_ca_certs,
                                         self.xmpp_src_room))
        yield inner.sub(src | peel_messages() | dst | threado.dev_null())

if __name__ == "__main__":
    BridgeBot.from_command_line().execute()
