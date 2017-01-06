"""
Base for Dataplane bot

Maintainer: DataPlane <info [ at ] dataplane [ dot ] org>
"""

import idiokit
from abusehelper.core import utils, cymruwhois, bot


class DataplaneBot(bot.PollingBot):
    url = bot.Param()
    use_cymru_whois = bot.BoolParam()

    # The first column values (ASN and AS name) are ignored.
    COLUMNS = [None, None, "ip", "time", "category"]

    def poll(self):
        if self.use_cymru_whois:
            return self._poll() | cymruwhois.augment("ip")
        return self._poll()

    @idiokit.stream
    def _poll(self):
        self.log.info("Downloading %s" % self.url)
        try:
            info, fileobj = yield utils.fetch_url(self.url)
        except utils.FetchUrlFailed, fuf:
            self.log.error("Download failed: %r", fuf)
            return
        self.log.info("Downloaded")

        charset = info.get_param("charset")
        filtered = (x for x in fileobj if x.strip() and not x.startswith("#"))
        yield utils.csv_to_events(filtered,
                                  delimiter="|",
                                  columns=self.COLUMNS,
                                  charset=charset)
