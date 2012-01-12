import socket
import idiokit
from abusehelper.core import utils
from idiokit import util, sockets, timer

class Stop(Exception):
    pass

def is_ip(string):
    for addr_type in (socket.AF_INET, socket.AF_INET6):
        try:
            socket.inet_pton(addr_type, string)
        except (ValueError, socket.error):
            pass
        else:
            return True
    return False

class CymruWhoisAugmenter(object):
    KEYS = "asn", "bgp_prefix", "cc", "registry", "allocated", "as name"

    def __init__(self, wait_time=0.5, cache_time=3600.0):
        self.wait_time = wait_time

        self.cache = utils.TimedCache(cache_time)
        self.socket = None
        self.buffer = None
        self.main = None
        self.count = 0

    @idiokit.stream
    def augment(self, ip_key="ip"):
        while True:
            event = yield idiokit.next()

            for ip in event.values(ip_key):
                items = yield self.resolve(ip)
                for key, value in items:
                    event.add(key, value)

            yield idiokit.send(event)

    @idiokit.stream
    def resolve(self, ip):
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
            while not (timeouts >= 2 and self.count <= 0):
                item = yield idiokit.next()
                if item is None:
                    timeouts += 1
                    if timeouts >= 2:
                        yield self._close()
                    continue

                ip, event = item
                values = self.cache.get(ip, None)
                if values is None:
                    values = yield self._resolve(ip)
                    self.cache.set(ip, tuple(values))
                    timeouts = 0
                event.succeed(values)
        finally:
            self.main = None

    @idiokit.stream
    def _resolve(self, ip):
        if self.socket is None:
            self.socket = sockets.Socket()
            yield self.socket.connect(("whois.cymru.com", 43))
            yield self.socket.writeall("begin\nverbose\n")

            self.buffer = util.LineBuffer()

        yield self.socket.writeall(ip + "\n")
        while True:
            data = yield self.socket.read(4096)

            for line in self.buffer.feed(data):
                values = self._parse(line)
                if values is not None:
                    idiokit.stop(values)

    @idiokit.stream
    def _close(self):
        if self.socket is not None:
            yield self.socket.writeall("end\n")
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

global_whois = CymruWhoisAugmenter()

def CymruWhois(key="ip"):
    return global_whois.augment(key)
