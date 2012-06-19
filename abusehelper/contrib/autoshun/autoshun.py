import idiokit
from abusehelper.core import utils, cymruwhois, bot, events

AUTOSHUN_CSV_URL = "http://www.autoshun.org/files/shunlist.csv"

class AutoshunBot(bot.PollingBot):
    COLUMNS = ["ip", "time", "type"]

    feed_url = bot.Param(default=AUTOSHUN_CSV_URL)
    use_cymru_whois = bot.BoolParam(default=True)

    def poll(self):
        pipe = self._poll(url=self.feed_url)

        if self.use_cymru_whois:
            pipe = pipe | cymruwhois.augment("ip")

        return pipe | self._normalize()

    @idiokit.stream
    def _poll(self, url):
        self.log.info("Downloading %s" % url)
        try:
            info, fileobj = yield utils.fetch_url(url)
        except utils.FetchUrlFailed, fuf:
            self.log.error("Download failed: %r", fuf)
            idiokit.stop()
        self.log.info("Downloaded")

        # Skip first line
        fileobj.readline()

        yield utils.csv_to_events(fileobj,
                                  columns=self.COLUMNS,
                                  charset=info.get_param("charset"))

    @idiokit.stream
    def _normalize(self):
        while True:
            event = yield idiokit.next()
            event.add("feed", "autoshun")
            event.add("source url", self.feed_url)
            yield idiokit.send(event)

if __name__ == "__main__":
    AutoshunBot.from_command_line().execute()
