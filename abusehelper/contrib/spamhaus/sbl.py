import idiokit
from abusehelper.core import cymruwhois, bot, events


class SpamhausSblBot(bot.PollingBot):
    use_cymru_whois = bot.BoolParam(default=True)
    sbl_filepath = bot.Param("Filename of Spamhaus SBL file")

    @idiokit.stream
    def poll(self):
        skip_chars = ["#", ":", "$"]
        self.log.info("Opening %s" % self.sbl_filepath)
        ips = []

        try:
            with open(self.sbl_filepath, "r") as f:
                for line in f:
                    skip = False
                    for c in skip_chars:
                        if line.startswith(c):
                            skip = True

                    if skip:
                        continue

                    parts = line.split()

                    if len(parts) == 1:
                        ip = parts[0]
                    elif len(parts) == 2:
                        ip_parts = parts[0].split("/")
                        if len(ip_parts) != 2:
                            continue

                        # for now we handle only /32 addresses
                        if ip_parts[1] != "/32":
                            continue

                        ip = ip[0]
                    else:
                        continue

                    ips.append(ip)
            self.log.info("Read %d ip addresses" % len(ips))
        except IOError, ioe:
            self.log.error("Could not open %s: %s" % (self.sbl_filepath, ioe))

        for ip in ips:
            event = events.Event()
            event.add("ip", ip)
            event.add("feed", "spamhaus block list")
            event.add("type", "spambot")

            if self.use_cymru_whois:
                values = yield cymruwhois.lookup(ip)
                for key, value in values:
                    event.add(key, value)

            yield idiokit.send(event)

if __name__ == "__main__":
    SpamhausSblBot.from_command_line().execute()
