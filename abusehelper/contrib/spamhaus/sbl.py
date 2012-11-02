import idiokit
from abusehelper.core import cymruwhois, bot, events


class SpamhausSblBot(bot.PollingBot):
    use_cymru_whois = bot.BoolParam(default=True)
    sbl_filepath = bot.Param("Filename of Spamhaus SBL file")

    def _event(self):
        event = events.Event()
        event.add("feed", "spamhaus block list")
        event.add("type", "spambot")
        return event

    @idiokit.stream
    def _cymru_augment(self, event, key):
        if self.use_cymru_whois:
            values = yield cymruwhois.lookup(key)
            for key, value in values:
                event.add(key, value)
        yield idiokit.stop(event)

    @idiokit.stream
    def _ip_events(self, ips):
        for ip in ips:
            event = self._event()
            event.add("ip", ip)
            event = yield self._cymru_augment(event, ip)
            yield idiokit.send(event)

    @idiokit.stream
    def _netblock_events(self, netblocks):
        for netblock in netblocks:
            event = self._event()
            event.add("netblock", netblock)
            event = yield self._cymru_augment(event, netblock.split("/")[0])
            yield idiokit.send(event)

    @idiokit.stream
    def poll(self):
        skip_chars = ["#", ":", "$"]
        self.log.info("Opening %s" % self.sbl_filepath)
        ips = []
        netblocks = []

        try:
            with open(self.sbl_filepath, "r") as f:
                for line in f:
                    if line and line[0] in skip_chars:
                        continue

                    parts = line.split()

                    if len(parts) == 1:
                        ips.append(parts[0])
                    elif len(parts) == 2:
                        if parts[0].endswith("/32"):
                            ip, _ = parts[0].split("/")
                            ips.append(ip)
                        else:
                            netblocks.append(parts[0])

            self.log.info("Read %d ip addresses, %d netblocks" % (len(ips), len(netblocks)))
        except IOError, ioe:
            self.log.error("Could not open %s: %s" % (self.sbl_filepath, ioe))

        yield self._ip_events(ips)
        yield self._netblock_events(netblocks)

if __name__ == "__main__":
    SpamhausSblBot.from_command_line().execute()
