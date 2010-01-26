from idiokit import util, threado, sockets, timer

class CymruWhois(threado.GeneratorStream):
    LINE_KEYS = "asn", "bgp_prefix", "cc", "registry", "allocated", "as name"

    def __init__(self, throttle_time=10.0, cache_time=60*60.0):
        threado.GeneratorStream.__init__(self)

        self.cache = util.TimedCache(cache_time)
        self.throttle_time = throttle_time
        self.pending = dict()

        self.start()

    def _augment_events(self, events, values):
        for event in events:
            for key, value in zip(self.LINE_KEYS, values):
                if value is None:
                    continue
                event.add(key, value)
            yield event

    @threado.stream
    def iteration(inner, self, ips):
        for ip in list(ips):
            values = self.cache.get(ip, None)
            if values is None:
                continue
            events = self.pending.pop(ip, ())
            map(inner.send, self._augment_events(events, values))
            ips.discard(ip)
            
        if not ips:
            return

        socket = sockets.Socket()
        connect = socket.connect(("whois.cymru.com", 43))
        try:        
            while not connect.has_result():
                yield inner, connect

            socket.send("begin\n")
            socket.send("verbose\n")
            for ip in ips:
                socket.send(ip + "\n")
            socket.send("end\n")

            line_buffer = util.LineBuffer()
            while ips:
                try:
                    data = yield inner, socket
                except sockets.error:
                    break

                if not socket.was_source:
                    continue

                for line in line_buffer.feed(data):                    
                    bites = [x.strip() for x in line.split("|")]
                    bites = [x if x not in ("", "NA") else None for x in bites]
                    if len(bites) != 7:
                        continue
                    ip = bites.pop(1)

                    events = self.pending.pop(ip, ())
                    ips.discard(ip)
                    self.cache.set(ip, bites)
                    map(inner.send, self._augment_events(events, bites))
        finally:
            yield inner.sub(socket.close())

    @threado.stream_fast
    def collect(inner, self):
        while True:
            yield inner
            for event in inner:
                for ip in event.attrs.get("ip", ()):
                    self.pending.setdefault(ip, list()).append(event)

    @threado.stream
    def wake(inner, self):
        sleeper = timer.sleep(self.throttle_time / 2.0)

        while True:
            yield inner, sleeper
            if sleeper.was_source:
                pending = yield self.inner.sub(self.iteration(set(self.pending)))
                sleeper = timer.sleep(self.throttle_time)

    def run(self):
        yield self.inner.sub(self.collect() | self.wake())
