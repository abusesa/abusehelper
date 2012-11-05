import idiokit
from abusehelper.core import cymruwhois, bot, events


class SpamhausSblBot(bot.PollingBot):
    use_cymru_whois = bot.BoolParam()
    sbl_filepath = bot.Param("Filename of Spamhaus SBL file")

    def _event(self, spamhaus_id):
        event = events.Event()
        event.add("feed", "spamhaus block list")
        event.add("type", "spambot")
        if spamhaus_id:
            spamhaus_id = "SBL" + str(int(spamhaus_id.replace("$", ""), base=10))
            event.add("spamhaus id", spamhaus_id)
            event.add("source url", "http://www.spamhaus.org/sbl/query/" + spamhaus_id)
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
        for ip, spamhaus_id in ips:
            event = self._event(spamhaus_id)
            event.add("ip", ip)
            event = yield self._cymru_augment(event, ip)
            yield idiokit.send(event)

    @idiokit.stream
    def _netblock_events(self, netblocks):
        for netblock, spamhaus_id in netblocks:
            event = self._event(spamhaus_id)
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
                        ips.append((parts[0], None))
                    elif len(parts) == 2:
                        if parts[0].endswith("/32"):
                            ip, _ = parts[0].split("/")
                            ips.append((ip, parts[1]))
                        else:
                            netblocks.append((parts[0], parts[1]))

            self.log.info("Read %d ip addresses, %d netblocks" % (len(ips), len(netblocks)))
        except IOError, ioe:
            self.log.error("Could not open %s: %s" % (self.sbl_filepath, ioe))

        yield self._ip_events(ips)
        yield self._netblock_events(netblocks)

if __name__ == "__main__":
    SpamhausSblBot.from_command_line().execute()
