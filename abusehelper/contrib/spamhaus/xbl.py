"""
Spamhaus XBL list handler.

Maintainer: Sauli Pahlman <sauli@codenomicon.com>
"""

import idiokit
from abusehelper.core import cymruwhois, bot, events


class SpamhausXblBot(bot.PollingBot):
    xbl_filepath = bot.Param("Filename of Spamhaus XBL file")

    @idiokit.stream
    def poll(self):
        skip_chars = ["#", ":", "$"]
        self.log.info("Opening %s" % self.xbl_filepath)
        entries = []

        try:
            with open(self.xbl_filepath, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and line[0] in skip_chars:
                        continue

                    entries.append(line)

            self.log.info("Read %d entries" % len(entries))
        except IOError, ioe:
            self.log.error("Could not open %s: %s" % (self.xbl_filepath, ioe))

        for entry in entries:
            event = events.Event()
            event.add("ip", entry)
            event.add("description url", "http://www.spamhaus.org/query/bl?ip=" + entry)
            yield idiokit.send(event)

if __name__ == "__main__":
    SpamhausXblBot.from_command_line().execute()
