import errno
from idiokit import threado, sockets
from abusehelper.core import bot, events
from combiner import Expert

DEFAULT_KEYS = ("domain", "ip", "first seen", "last seen")

@threado.stream
def collect(inner):
    result = list()
    while True:
        try:
            data = yield inner
        except sockets.error, error:
            if error.errno == errno.ECONNRESET:
                break
            raise

        result.append(data)
    inner.finish("".join(result))

@threado.stream
def lookup(inner, host, port, eid, name, keys=DEFAULT_KEYS):
    sock = sockets.Socket()
    try:
        yield inner.sub(sock.connect((host, port)))
        sock.send(name + "\r\n")
        data = yield inner.sub(sock | collect())
    except sockets.error, error:
        return

    for line in data.splitlines():
        event = events.Event()
        for key, value in zip(keys, line.split("\t")):
            event.add(key, value)
        yield inner.send(eid, event)

class PassiveDNSExpert(Expert):
    host = bot.Param()
    port = bot.IntParam(default=43)

    @threado.stream
    def augment(inner, self):
        while True:
            eid, event = yield inner
            
            for name in set(event.values("domain") + 
                            event.values("ip") + 
                            event.values("soa")):
                yield inner.sub(lookup(self.host, self.port, eid, name))

if __name__ == "__main__":
    PassiveDNSExpert.from_command_line().execute()
