import socket
import idiokit
from abusehelper.core import utils
from idiokit import socket as idiokit_socket, timer

def is_ip(string):
    for addr_type in (socket.AF_INET, socket.AF_INET6):
        try:
            socket.inet_pton(addr_type, string)
        except (TypeError, ValueError, socket.error):
            pass
        else:
            return True
    return False

def ip_values(event, keys):
    for key in keys:
        for value in event.values(key, filter=is_ip):
            yield value

class CymruWhois(object):
    KEYS = "asn", "bgp_prefix", "cc", "registry", "allocated", "as name"

    def __init__(self, wait_time=0.5, cache_time=3600.0):
        self.wait_time = wait_time

        self.cache = utils.TimedCache(cache_time)
        self.buffer = None
        self.socket = None
        self.main = None
        self.count = 0

    @idiokit.stream
    def augment(self, *ip_keys):
        while True:
            event = yield idiokit.next()

            if not ip_keys:
                values = event.values(filter=is_ip)
            else:
                values = ip_values(event, ip_keys)

            for ip in values:
                items = yield self.lookup(ip)
                for key, value in items:
                    event.add(key, value)

            yield idiokit.send(event)

    @idiokit.stream
    def lookup(self, ip):
        if not is_ip(ip):
            idiokit.stop(())

        values = self.cache.get(ip, None)
        if values is None:
            self.count += 1
            try:
                if self.main is None:
                    self.main = self._main()
                    idiokit.pipe(self._alert(self.wait_time / 2), self.main)
                main = self.main

                event = idiokit.Event()
                yield main.send(ip, event)
                values = yield event | main.fork() | event
            finally:
                self.count -= 1
        idiokit.stop([x for x in zip(self.KEYS, values) if x[1] is not None])

    @idiokit.stream
    def _alert(self, interval):
        while True:
            yield timer.sleep(interval)
            yield idiokit.send()

    @idiokit.stream
    def _main(self):
        timeouts = 0
        try:
            while True:
                item = yield idiokit.next()
                if item is None:
                    timeouts += 1
                    if timeouts < 2:
                        continue
                    yield self._close()
                    if self.count > 0:
                        continue
                    break

                ip, event = item
                values = self.cache.get(ip, None)
                if values is None:
                    values = yield self._lookup(ip)
                    self.cache.set(ip, tuple(values))
                    timeouts = 0
                event.succeed(values)
        finally:
            self.main = None

    @idiokit.stream
    def _lookup(self, ip):
        while True:
            if self.socket is None:
                self.socket = idiokit_socket.Socket()
                yield self.socket.connect(("whois.cymru.com", 43))
                yield self.socket.sendall("begin\nverbose\n")

                self.buffer = ""

            yield self.socket.sendall(str(ip) + "\n")
            while True:
                data = yield self.socket.recv(4096)
                if not data:
                    self.socket = None
                    self.buffer = None
                    break

                lines = (self.buffer + data).split("\n")
                self.buffer = lines.pop()

                for line in lines:
                    values = self._parse(line)
                    if values is not None:
                        idiokit.stop(values)

    @idiokit.stream
    def _close(self):
        if self.socket is not None:
            yield self.socket.sendall("end\n")
            yield self.socket.close()
        self.socket = None
        self.buffer = None

    def _parse(self, line):
        line = line.decode("utf-8", "replace")
        bites = [x.strip() for x in line.split("|")]
        bites = [x if x not in ("", "NA") else None for x in bites]
        if len(bites) != 7:
            return None

        bites.pop(1)
        return bites

global_whois = CymruWhois()

augment = global_whois.augment
lookup = global_whois.lookup
