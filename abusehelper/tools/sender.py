import sys
import json
import time
import idiokit
from idiokit import select
from abusehelper.core import bot, events


@idiokit.stream
def _rate_limiter(rate_limit):
    last_output = time.time()

    while True:
        if rate_limit is not None:
            delta = max(time.time() - last_output, 0)
            delay = 1.0 / rate_limit - delta
            if delay > 0.0:
                yield idiokit.sleep(delay)
            last_output = time.time()

        msg = yield idiokit.next()
        yield idiokit.send(msg)


class Receiver(bot.XMPPBot):
    room = bot.Param("""
        the room for receiving events from
    """)
    rate_limit = bot.IntParam("""
        rate limit for the sent stream
    """, default=None)

    @idiokit.stream
    def main(self):
        xmpp = yield self.xmpp_connect()
        room = yield xmpp.muc.join(self.room)

        yield idiokit.pipe(
            self._read_stdin(),
            events.events_to_elements(),
            _rate_limiter(self.rate_limit),
            room,
            idiokit.consume()
        )

    @idiokit.stream
    def _read_stdin(self):
        loads = json.JSONDecoder(parse_float=unicode, parse_int=unicode).decode

        while True:
            yield select.select([sys.stdin], [], [])

            line = sys.stdin.readline()
            if not line:
                break
            if not line.strip():
                continue

            in_dict = loads(line)
            yield idiokit.send(events.Event(in_dict))


if __name__ == "__main__":
    Receiver.from_command_line().execute()
