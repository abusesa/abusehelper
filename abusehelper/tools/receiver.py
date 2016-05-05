import json
import idiokit
from abusehelper.core import bot, events


class Receiver(bot.XMPPBot):
    room = bot.Param("""
        The room for receiving events from
    """)

    @idiokit.stream
    def main(self):
        xmpp = yield self.xmpp_connect()
        room = yield xmpp.muc.join(self.room)

        yield idiokit.pipe(
            room,
            events.stanzas_to_events(),
            self._recv()
        )

    @idiokit.stream
    def _recv(self):
        dumps = json.JSONEncoder(check_circular=False).encode

        while True:
            event = yield idiokit.next()

            out_dict = {}
            for key, value in event.items():
                out_dict.setdefault(key, []).append(value)

            print dumps(out_dict)


if __name__ == "__main__":
    Receiver.from_command_line().execute()
