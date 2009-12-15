from idiokit import util, threado, sockets, timer

class CymruWhois(threado.GeneratorStream):
    LINE_KEYS = "asn", "bgp_prefix", "cc", "registry", "allocated", "as name"

    def __init__(self, throttle_time=10.0, cache_time=60*60.0):
        threado.GeneratorStream.__init__(self)

        self.cache = util.TimedCache(cache_time)
        self.throttle_time = throttle_time

        self.start()

    def _augment_events(self, events, values):
        for event in events:
            for key, value in zip(self.LINE_KEYS, values):
                if value is None:
                    continue
                event.add(key, value)
            yield event

    @threado.stream
    def _iteration(inner, self, pending):
        for ip, events in list(pending.iteritems()):
            values = self.cache.get(ip, None)
            if values is None:
                continue
            map(inner.send, self._augment_events(events, values))
            del pending[ip]
            
        if not pending:
            inner.finish(pending)

        socket = sockets.Socket()
        yield inner.sub(socket.connect(("whois.cymru.com", 43)))

        try:        
            socket.send("begin\n")
            socket.send("verbose\n")
            for ip in pending:
                socket.send(ip + "\n")
            socket.send("end\n")
            
            line_buffer = util.LineBuffer()
            while pending:
                try:
                    data = yield socket
                except sockets.error:
                    break

                for line in line_buffer.feed(data):                    
                    bites = [x.strip() for x in line.split("|")]
                    bites = [x if x not in ("", "NA") else None for x in bites]
                    if len(bites) != 7:
                        continue
                    ip = bites.pop(1)
                    events = pending.pop(ip, ())
                    self.cache.set(ip, bites)
                    map(inner.send, self._augment_events(events, bites))
        finally:
            yield inner.sub(socket.close())

        inner.finish(pending)

    def run(self):
        pending = dict()
        sleeper = timer.sleep(self.throttle_time / 2.0)

        while True:
            item = yield self.inner, sleeper

            if sleeper.was_source:
                pending = yield self.inner.sub(self._iteration(pending))
                sleeper = timer.sleep(self.throttle_time)
                continue

            for event in [item] + list(self.inner):
                for ip in event.attrs.get("ip", ()):
                    pending.setdefault(ip, list()).append(event)
