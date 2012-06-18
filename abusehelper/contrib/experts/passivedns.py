import idiokit
import socket as _socket
from idiokit import socket
from abusehelper.core import bot, events
from abusehelper.contrib.experts.combiner import Expert

DEFAULT_KEYS = ("domain", "ip", "first seen", "last seen")

def is_ipv4(ip):
    try:
        _socket.inet_aton(ip)
    except (ValueError, _socket.error):
        return False
    return True


def is_ipv6(ip):
    if _socket.has_ipv6:
        try:
            _socket.inet_pton(socket.AF_INET6, ip)
        except(ValueError, _socket.error):
            return False
        return True
    else:
        return False

@idiokit.stream
def lookup(host, port, eid, name, keys=DEFAULT_KEYS):
    sock = socket.Socket()
    try:
        yield sock.connect((host, port))
        yield sock.sendall(name + "\r\n")

        all_data = list()
        while True:
            data = yield sock.recv(4096)
            if not data:
                break
            all_data.append(data)
    except socket.SocketError:
        return

    for line in "".join(all_data).splitlines():
        event = events.Event()
        for key, value in zip(keys, line.split("\t")):
            if key == 'ip':
                if not is_ipv4(value):
                    if not is_ipv6(value):
                        key = 'domain'
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
