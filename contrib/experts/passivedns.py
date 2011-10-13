import errno

import idiokit
from idiokit import sockets
from abusehelper.core import bot, events
from combiner import Expert

DEFAULT_KEYS = ("domain", "ip", "first seen", "last seen")

@idiokit.stream
def lookup(host, port, eid, name, keys=DEFAULT_KEYS):
    sock = sockets.Socket()
    try:
        yield sock.connect((host, port))
        yield sock.writeall(name + "\r\n")

        data = list()
        try:
            while True:
                data.append((yield sock.read(4096)))
        except sockets.error, error:
            if error.errno != errno.ECONNRESET:
                raise
    except sockets.error, error:
        return

    for line in "".join(data).splitlines():
        event = events.Event()
        for key, value in zip(keys, line.split("\t")):
            event.add(key, value)
        yield idiokit.send(eid, event)

class PassiveDNSExpert(Expert):
    host = bot.Param()
    port = bot.IntParam(default=43)

    @idiokit.stream
    def augment(self):
        while True:
            eid, event = yield idiokit.next()

            for name in set(event.values("domain") +
                            event.values("ip") +
                            event.values("soa")):
                yield lookup(self.host, self.port, eid, name)

if __name__ == "__main__":
    PassiveDNSExpert.from_command_line().execute()
