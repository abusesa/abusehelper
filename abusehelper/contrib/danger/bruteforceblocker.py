"""
Feed handler for bruteforceblocker list in danger.rulez.sk.

Maintainer: Jussi Eronen <exec@iki.fi>
"""

import re

import idiokit
from abusehelper.core import utils, cymruwhois, bot

class BruteForceBlockerBot(bot.PollingBot):
    # Ignore the last column ("id").
    COLUMNS = ["ip", "time", "count", None]

    use_cymru_whois = bot.BoolParam()

    def poll(self):
        if self.use_cymru_whois:
            return self._poll() | cymruwhois.augment("ip")
        return self._poll()

    @idiokit.stream
    def _poll(self, url="http://danger.rulez.sk/projects/bruteforceblocker/blist.php"):
        self.log.info("Downloading %s" % url)
        try:
            info, fileobj = yield utils.fetch_url(url)
        except utils.FetchUrlFailed, fuf:
            self.log.error("Download failed: %r", fuf)
            idiokit.stop(False)
        self.log.info("Downloaded")

        filtered = (x for x in fileobj if x.strip() and not x.startswith("#"))
        lines = (re.sub("\t+", "\t", x) for x in filtered)

        yield (utils.csv_to_events(lines,
                            delimiter="\t",
                            columns=self.COLUMNS,
                            charset=info.get_param("charset"))
                | idiokit.map(self._normalize, url))

    def _normalize(self, event, url):
        for timestamp in event.values("time"):
            event.add("last seen", timestamp.replace("# ", "") + " UTC")
        event.clear("time")

        event.add("description url", url)
        yield event

if __name__ == "__main__":
    BruteForceBlockerBot.from_command_line().execute()
