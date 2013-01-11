import socket
import idiokit
import collections
from abusehelper.core import utils
from idiokit import socket as idiokit_socket


class Timeout(Exception):
    pass


@idiokit.stream
def timeout(delay):
    yield idiokit.sleep(delay)
    raise Timeout()


def normalized_ip(string):
    for addr_type in (socket.AF_INET, socket.AF_INET6):
        try:
            return socket.inet_ntop(addr_type, socket.inet_pton(addr_type, string))
        except (TypeError, ValueError, socket.error):
            pass
    return None


def ip_values(event, keys):
    for key in keys:
        for value in event.values(key, parser=normalized_ip):
            yield value


class CymruWhois(object):
    KEYS = "asn", "bgp prefix", "cc", "registry", "allocated", "as name"

    def __init__(self, cache_time=3600.0, timeout=30.0):
        self._timeout = timeout
        self._cache = utils.TimedCache(cache_time)
        self._pending = collections.deque()
        self._ips = dict()
        self._next = idiokit.Event()
        self._current = None

    @idiokit.stream
    def augment(self, *ip_keys):
        while True:
            event = yield idiokit.next()
            if not ip_keys:
                values = event.values(parser=normalized_ip)
            else:
                values = ip_values(event, ip_keys)

            for ip in values:
                items = yield self.lookup(ip)
                for key, value in items:
                    event.add(key, value)

            yield idiokit.send(event)

    @idiokit.stream
    def _lookup(self, ip):
        if normalized_ip(ip) is None:
            idiokit.stop(())

        values = self._cache.get(ip, None)
        if values is not None:
            idiokit.stop(values)

        if ip not in self._ips:
            self._ips[ip] = 1, idiokit.Event()
            self._next.succeed()
            self._next = idiokit.Event()
            self._pending.append(ip)
        count, event = self._ips[ip]
        self._ips[ip] = count + 1, event

        try:
            if self._current is None:
                self._current = self._bulk()
            values = yield self._current.fork() | event
        finally:
            count, _ = self._ips[ip]
            if count > 1:
                self._ips[ip] = count - 1, event
            else:
                del self._ips[ip]

        idiokit.stop(values)

    @idiokit.stream
    def lookup(self, ip):
        values = yield self._lookup(ip)
        idiokit.stop([x for x in zip(self.KEYS, values) if x[1] is not None])

    @idiokit.stream
    def _bulk(self):
        try:
            while self._pending:
                try:
                    yield self._once(0.2)
                except idiokit_socket.SocketTimeout:
                    yield idiokit.sleep(1.0)
                except idiokit_socket.SocketError:
                    yield idiokit.sleep(10.0)
                else:
                    yield idiokit.sleep(2.0)
        finally:
            self._current = None

    @idiokit.stream
    def _once(self, wait_timeout):
        sock = idiokit_socket.Socket()
        buffer = ""

        try:
            yield sock.connect(("whois.cymru.com", 43), timeout=self._timeout)
            yield sock.sendall("begin\nverbose\n", timeout=self._timeout)

            while True:
                if not self._pending:
                    try:
                        yield timeout(wait_timeout) | self._next
                    except Timeout:
                        if not self._pending:
                            break

                current_ip = self._pending[0]
                count, event = self._ips[current_ip]
                if count <= 1:
                    del self._ips[current_ip]
                    self._pending.popleft()
                    continue
                count, event = self._ips[current_ip]
                self._ips[current_ip] = count + 1, event

                yield sock.sendall(str(current_ip) + "\n", timeout=self._timeout)
                while True:
                    data = yield sock.recv(4096, timeout=self._timeout)
                    if not data:
                        raise idiokit_socket.SocketError()

                    lines = (buffer + data).split("\n")
                    buffer = lines.pop()

                    parsed = dict(set(self._parse(x) for x in lines) - set([None]))
                    for result_ip, values in parsed.iteritems():
                        self._cache.set(result_ip, values)
                        if result_ip not in self._ips:
                            continue

                        count, event = self._ips[result_ip]
                        if count > 1:
                            self._ips[result_ip] = count - 1, event
                        else:
                            del self._ips[result_ip]
                        event.succeed(values)

                    if current_ip in parsed:
                        self._pending.popleft()
                        break
        finally:
            yield sock.close()

    def _parse(self, line):
        line = line.decode("utf-8", "replace")
        bites = [x.strip() for x in line.split("|")]
        bites = [x if x not in ("", "NA") else None for x in bites]
        if len(bites) != 7:
            return None

        ip = normalized_ip(bites.pop(1))
        if ip is None:
            return None
        return ip, tuple(bites)

global_whois = CymruWhois()

augment = global_whois.augment
lookup = global_whois.lookup
