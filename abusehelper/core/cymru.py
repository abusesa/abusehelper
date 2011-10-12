import idiokit
from abusehelper.core import utils
from idiokit import util, sockets, timer

class Stop(Exception):
    pass

class CymruWhoisAugmenter(object):
    LINE_KEYS = "asn", "bgp_prefix", "cc", "registry", "allocated", "as name"

    def __init__(self, throttle_time=2.0, cache_time=60*60.0):
        self.throttle_time = throttle_time

        self.cache = utils.TimedCache(cache_time)

        self.global_main = None
        self.global_channels = set()
        self.global_pending = dict()

    def main(self, channels, pending):
        main = self._main(channels, pending)
        idiokit.pipe(self._alert(self.throttle_time), main)
        return main

    @idiokit.stream
    def _alert(self, interval):
        yield timer.sleep(interval / 2.0)
        yield idiokit.send()

        while True:
            yield timer.sleep(interval)
            yield idiokit.send()

    @idiokit.stream
    def _main(self, channels, pending):
        try:
            while True:
                yield idiokit.next()
                yield self.iteration(pending)
        except Stop:
            pass
        except:
            for channel in channels:
                channel.throw()
            raise

        for channel in channels:
            channel.throw(Stop())

    @idiokit.stream
    def _forward(self, global_main, local_pending):
        should_stop = False

        while not should_stop or local_pending:
            try:
                ip, values = yield idiokit.next()

                events = local_pending.pop(ip, ())

                for event in events:
                    for key, value in zip(self.LINE_KEYS, values):
                        if value is not None:
                            event.add(key, value)
                    yield idiokit.send(event)
            except StopIteration:
                should_stop = True
                yield global_main.send()

    @idiokit.stream
    def _collect(self, key, channel, local_pending, global_pending):
        while True:
            event = yield idiokit.next()

            for ip in event.values(key):
                local_pending.setdefault(ip, list()).append(event)

                values = self.cache.get(ip, None)
                if values is not None:
                    yield idiokit.send(ip, values)
                else:
                    global_pending.setdefault(ip, set()).add(channel)

    @idiokit.stream
    def augment(self, key="ip"):
        if self.global_main is None:
            self.global_main = self.main(self.global_channels,
                                         self.global_pending)

        global_channels = self.global_channels
        global_pending = self.global_pending
        global_main = self.global_main

        local_pending = dict()
        forward = self._forward(global_main, local_pending)
        collect = self._collect(key, forward, local_pending, global_pending)

        global_channels.add(forward)

        try:
            yield idiokit.pipe(collect, forward)
        finally:
            for ip in local_pending:
                forwards = global_pending.get(ip, set())
                forwards.discard(forward)
                if not forwards:
                    global_pending.pop(ip, None)

            global_channels.discard(forward)
            if not global_channels:
                global_main.throw(Stop())
                if self.global_main is global_main:
                    self.global_main = None
                yield global_main

    @idiokit.stream
    def iteration(self, pending):
        if not pending:
            return

        socket = sockets.Socket()
        try:
            yield socket.connect(("whois.cymru.com", 43))

            ips = set(pending)

            yield socket.writeall("begin\n")
            yield socket.writeall("verbose\n")
            for ip in ips:
                yield socket.writeall(ip + "\n")
            yield socket.writeall("end\n")

            line_buffer = util.LineBuffer()
            while ips:
                data = yield socket.read(4096)

                for line in line_buffer.feed(data):
                    line = line.decode("utf-8", "replace")
                    bites = [x.strip() for x in line.split("|")]
                    bites = [x if x not in ("", "NA") else None for x in bites]
                    if len(bites) != 7:
                        continue
                    ip = bites.pop(1)

                    ips.discard(ip)
                    self.cache.set(ip, bites)

                    channels = pending.pop(ip, ())
                    for channel in channels:
                        channel.send(ip, bites)
        except sockets.error:
            pass
        finally:
            yield socket.close()

global_whois = CymruWhoisAugmenter()

def CymruWhois(key="ip"):
    return global_whois.augment(key)
