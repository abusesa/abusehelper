"""
Spamhaus sbl feed bot

Maintainer: Codenomicon <clarified@codenomicon.com>
"""

import idiokit
from abusehelper.core import cymruwhois, bot, events


class SpamhausSblBot(bot.PollingBot):
    use_cymru_whois = bot.BoolParam()
    sbl_filepath = bot.Param("Filename of Spamhaus SBL file")

    def _event(self, spamhaus_id):
        event = events.Event()
        event.add("feed", "spamhaus sbl")
        event.add("type", "spam")
        if spamhaus_id:
            spamhaus_id = "SBL" + str(int(spamhaus_id.replace("$", ""), base=10))
            event.add("sbl id", spamhaus_id)
            event.add("description url", "http://www.spamhaus.org/sbl/query/" + spamhaus_id)
        return event

    @idiokit.stream
    def _cymru_augment(self, event):
        if event.contains("ip"):
            key = event.value("ip")
        else:
            key = event.value("netblock")
        values = yield cymruwhois.lookup(key)
        for key, value in values:
            event.add(key, value)

    @idiokit.stream
    def poll(self):
        skip_chars = ["#", ":", "$"]
        self.log.info("Opening %s" % self.sbl_filepath)
        entries = []

        try:
            with open(self.sbl_filepath, "r") as f:
                for line in f:
                    if line and line[0] in skip_chars:
                        continue

                    parts = line.split()

                    if len(parts) == 1:
                        entries.append((parts[0], None))
                    elif len(parts) == 2:
                        entries.append((parts[0], parts[1]))

            self.log.info("Read %d entries" % len(entries))
        except IOError, ioe:
            self.log.error("Could not open %s: %s" % (self.sbl_filepath, ioe))

        for entry, case_id in entries:
            event = self._event(case_id)
            if "/" in entry:
                prefix, suffix = entry.split("/")
                if suffix == "32":
                    event.add("ip", prefix)
                else:
                    event.add("netblock", entry)
            else:
                event.add("ip", entry)
            if self.use_cymru_whois:
                yield self._cymru_augment(event)
            yield idiokit.send(event)

if __name__ == "__main__":
    SpamhausSblBot.from_command_line().execute()
