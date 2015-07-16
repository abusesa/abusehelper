"""
Important notice:

This bot is deprecated and will not be maintained. Maintained
version will be moved under ahcommunity repository.

abusehelper.contrib package will be removed after 2016-01-01.
During the migration period, you can already update your
references to the bot.
"""

"""
An expert to augment IPs with passive DNS data.

Maintainer: Codenomicon <clarified@codenomicon.com>
"""
import idiokit
import socket as _socket
from idiokit import socket
from abusehelper.core import bot, events, utils
from abusehelper.bots.experts.combiner import Expert

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

class PassiveDNSExpert(Expert):
    host = bot.Param()
    port = bot.IntParam(default=43)

    def __init__(self, *args, **keys):
        cache_time = keys.get('cache_time', 3600.0)
        Expert.__init__(self, *args, **keys)
        self.cache = utils.TimedCache(cache_time)
        self.log.error("This bot is deprecated. It will move permanently under ahcommunity repository after 2016-01-01. Please update your references to the bot.")

    def augment_keys(self, *args, **keys):
        yield (keys.get("resolve", ("host",)))

    @idiokit.stream
    def lookup(self, host, port, eid, name, keys=DEFAULT_KEYS):
        all_data = self.cache.get(name, None)
        if not all_data:
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

            self.cache.set(name, all_data)

        lines = "".join(all_data).splitlines()
        # there will be duplicates
        lines = set(lines)
        eventlist = list()
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
            eventlist.append(event)
        idiokit.stop(eventlist)

    @idiokit.stream
    def augment(self, *args):
        while True:
            eid, event = yield idiokit.next()

            values = set()
            for arg in args:
                values.update(event.values(arg))

            for name in values:
                self.log.info("Querying %r", name)
                answers = yield self.lookup(self.host, self.port, eid, name)
                for answer in answers:
                    yield idiokit.send(eid, answer)

if __name__ == "__main__":
    PassiveDNSExpert.from_command_line().execute()
