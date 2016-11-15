import getpass
import idiokit
from idiokit import xmpp
from abusehelper.core import bot


@idiokit.stream
def peel_messages():
    while True:
        elements = yield idiokit.next()

        for message in elements.named("message"):
            yield idiokit.send(message.children())


class BridgeBot(bot.Bot):
    xmpp_src_jid = bot.Param("the XMPP src JID")
    xmpp_src_password = bot.Param(
        "the XMPP src password",
        default=None)
    xmpp_src_room = bot.Param("the XMPP src room")
    xmpp_src_host = bot.Param(
        "the XMPP src service host (default: autodetect)",
        default=None)
    xmpp_src_port = bot.IntParam(
        "the XMPP src service port (default: autodetect)",
        default=None)
    xmpp_src_ignore_cert = bot.BoolParam("""
        do not perform any verification for
        the XMPP service's SSL certificate
        """)
    xmpp_src_extra_ca_certs = bot.Param("""
        a PEM formatted file of CAs to be
        used in addition to the system CAs
        """, default=None)

    xmpp_dst_jid = bot.Param("the XMPP dst JID")
    xmpp_dst_password = bot.Param(
        "the XMPP dst password",
        default=None)
    xmpp_dst_host = bot.Param(
        "the XMPP dst service host (default: autodetect)",
        default=None)
    xmpp_dst_port = bot.IntParam(
        "the XMPP dst service port (default: autodetect)",
        default=None)
    xmpp_dst_room = bot.Param("the XMPP dst room")
    xmpp_dst_ignore_cert = bot.BoolParam("""
        do not perform any verification for
        the XMPP service's SSL certificate
        """)
    xmpp_dst_extra_ca_certs = bot.Param("""
        a PEM formatted file of CAs to be
        used in addition to the system CAs
        """, default=None)

    def __init__(self, **keys):
        bot.Bot.__init__(self, **keys)

        if self.xmpp_src_password is None:
            self.xmpp_src_password = getpass.getpass("XMPP src password: ")
        if self.xmpp_dst_password is None:
            self.xmpp_dst_password = getpass.getpass("XMPP dst password: ")

    @idiokit.stream
    def _join(self, _type, jid, password, host, port, ignore_cert, ca_certs, room_name):
        verify_cert = not ignore_cert

        self.log.info("Connecting to XMPP %s server with JID %r", _type, jid)
        connection = yield xmpp.connect(
            jid, password,
            host=host,
            port=port,
            ssl_verify_cert=verify_cert,
            ssl_ca_certs=ca_certs)

        self.log.info("Connected to XMPP %s server with JID %r", _type, jid)
        connection.core.presence()

        self.log.info("Joining %s room %r", _type, room_name)
        room = yield connection.muc.join(room_name, self.bot_name)

        self.log.info("Joined %s room %r", _type, room_name)
        idiokit.stop(room)

    @idiokit.stream
    def main(self):
        dst = yield self._join(
            "dst",
            self.xmpp_dst_jid,
            self.xmpp_dst_password,
            self.xmpp_dst_host,
            self.xmpp_dst_port,
            self.xmpp_dst_ignore_cert,
            self.xmpp_dst_extra_ca_certs,
            self.xmpp_dst_room)
        src = yield self._join(
            "src",
            self.xmpp_src_jid,
            self.xmpp_src_password,
            self.xmpp_src_host,
            self.xmpp_src_port,
            self.xmpp_src_ignore_cert,
            self.xmpp_src_extra_ca_certs,
            self.xmpp_src_room)

        yield src | peel_messages() | dst | idiokit.consume()

    def run(self):
        try:
            return idiokit.main_loop(self.main())
        except idiokit.Signal:
            pass


if __name__ == "__main__":
    BridgeBot.from_command_line().execute()
