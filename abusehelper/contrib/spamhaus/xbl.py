"""
Spamhaus XBL list handler.

Maintainer: Sauli Pahlman <sauli@codenomicon.com>
"""

import idiokit
from abusehelper.core import bot, events

class SpamhausXblBot(bot.PollingBot):
    xbl_filepath = bot.Param("Filename of Spamhaus XBL file")

    @idiokit.stream
    def poll(self):
        skip_chars = ["#", ":", "$"]
        self.log.info("Opening %s" % self.xbl_filepath)
        count = 0

        try:
            with open(self.xbl_filepath, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and line[0] in skip_chars:
                        continue

                    event = events.Event()
                    event.add("ip", line)
                    event.add("description url", "http://www.spamhaus.org/query/bl?ip=" + line)
                    yield idiokit.send(event)
                    count += 1

                self.log.info("Sent %d events" % count)
        except IOError, ioe:
            self.log.error("Could not open %s: %s" % (self.xbl_filepath, ioe))

if __name__ == "__main__":
    SpamhausXblBot.from_command_line().execute()
