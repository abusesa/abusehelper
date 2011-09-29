import sys
import combiner
from abusehelper.core import events, utils
from idiokit import util, threado, sockets, timer

class Stop(Exception):
    pass

class CymruWhoisExpert(combiner.Expert):
    THROTTLE_TIME = 2.0
    CACHE_TIME = 60 * 60.0

    LINE_KEYS = "asn", "bgp_prefix", "cc", "registry", "allocated", "as name"

    def __init__(self, *args, **keys):
        combiner.Expert.__init__(self, *args, **keys)

        self.throttle_time = self.THROTTLE_TIME
        self.cache = utils.TimedCache(self.CACHE_TIME)

        self.global_main = None
        self.global_channels = set()
        self.global_pending = dict()

    @threado.stream
    def main_loop(inner, self, channels, pending):
        sleeper = timer.sleep(self.throttle_time / 2.0)

        try:
            while True:
                yield inner, sleeper

                yield inner.sub(self.iteration(pending))

                if sleeper.has_result():
                    sleeper = timer.sleep(self.throttle_time)
        except Stop:
            pass
        except:
            for channel in channels:
                channel.rethrow()
            exc_type, exc_value, exc_tb = sys.exc_info()
            raise exc_type, exc_value, exc_tb

        for channel in channels:
            channel.throw(Stop())

    @threado.stream_fast
    def _forward(inner, self, global_main, local_pending):
        should_stop = False

        while not should_stop or local_pending:
            yield inner

            try:
                for ip, values in inner:
                    for eid in local_pending.pop(ip, ()):
                        augmentation = events.Event()

                        for key, value in zip(self.LINE_KEYS, values):
                            if value is not None:
                                augmentation.add(key, value)

                        inner.send(eid, augmentation)
            except threado.Finished:
                should_stop = True
                global_main.send()

    @threado.stream_fast
    def _collect(inner, self, key, channel, local_pending, global_pending):
        while True:
            yield inner

            for eid, event in inner:
                for ip in event.values(key):
                    local_pending.setdefault(ip, set()).add(eid)

                    values = self.cache.get(ip, None)
                    if values is not None:
                        inner.send(ip, values)
                    else:
                        global_pending.setdefault(ip, set()).add(channel)

    @threado.stream
    def augment(inner, self, key="ip"):
        if self.global_main is None:
            self.global_main = self.main_loop(self.global_channels,
                                              self.global_pending)

        global_channels = self.global_channels
        global_pending = self.global_pending
        global_main = self.global_main

        local_pending = dict()
        forward = self._forward(global_main, local_pending)
        collect = self._collect(key, forward, local_pending, global_pending)

        global_channels.add(forward)

        try:
            yield inner.sub(collect | forward)
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
                yield inner.sub(global_main)

    @threado.stream
    def iteration(inner, self, pending):
        if not pending:
            return

        socket = sockets.Socket()
        connect = socket.connect(("whois.cymru.com", 43))
        try:
            while not connect.has_result():
                yield inner, connect

            ips = set(pending)

            socket.send("begin\n")
            socket.send("verbose\n")
            for ip in ips:
                socket.send(ip + "\n")
            socket.send("end\n")

            line_buffer = util.LineBuffer()
            while ips:
                source, data = yield threado.any(inner, socket)
                if inner is source:
                    continue

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
            yield inner.sub(socket.close())

if __name__ == "__main__":
    CymruWhoisExpert.from_command_line().execute()
