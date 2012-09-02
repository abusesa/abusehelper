"""
An expert to augment IPs with passive DNS data.

Maintainer: "Juhani Eronen" <exec@iki.fi>
"""
import idiokit
import socket as _socket
from idiokit import socket
from abusehelper.core import bot, events, utils
from abusehelper.contrib.experts.combiner import Expert

DEFAULT_KEYS = ("host", "ip", "first seen", "last seen")


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
        yield sock.sendall(str(name) + "\r\n")

        all_data = list()
        while True:
            data = yield sock.recv(4096)
            if not data:
                break
            all_data.append(data)
    except socket.SocketError:
        return

    lines = "".join(all_data).splitlines()
    # there will be duplicates
    lines = set(lines)
    for line in lines:
        event = events.Event()
        for key, value in zip(keys, line.split("\t")):
            if key == 'ip':
                if not is_ipv4(value):
                    if not is_ipv6(value):
                        # The particular type of pdns server used here
                        # only gives you a and ns.
                        key = 'ns'
            event.add(key, value)
        event.add("expert", "passivedns")
        yield idiokit.send(eid, event)


class PassiveDNSExpert(Expert):
    host = bot.Param()
    port = bot.IntParam(default=43)

    def __init__(self, *args, **keys):
        cache_time = keys.get('cache_time', 3600.0)
        Expert.__init__(self, *args, **keys)
        self.cache = utils.TimedCache(cache_time)

    def augment_keys(self, *args, **keys):
        yield (keys.get("resolve", ("host",)))

    @idiokit.stream
    def augment(self, *args):
        while True:
            eid, event = yield idiokit.next()

            values = set()
            for arg in args:
                values.update(event.values(arg))

            for name in values:
                self.log.info("Querying %r", name)
                answer = self.cache.get(name, None)
                if not answer:
                    answer = lookup(self.host, self.port, eid, name)
                    self.cache.set(name, answer)
                    yield answer

if __name__ == "__main__":
    PassiveDNSExpert.from_command_line().execute()
