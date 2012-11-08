import idiokit
import time as _time

from abusehelper.core import utils, cymruwhois, bot, events

OPENBL_FEED_URL = "https://www.openbl.org/lists/date.txt"


class OpenBLBot(bot.PollingBot):
    feed_url = bot.Param(default=OPENBL_FEED_URL)
    use_cymru_whois = bot.BoolParam()

    def poll(self):
        pipe = self._poll(url=self.feed_url)

        if self.use_cymru_whois:
            pipe = pipe | cymruwhois.augment("ip")

        return pipe

    @idiokit.stream
    def _poll(self, url):
        self.log.info("Downloading %s" % url)
        try:
            info, fileobj = yield utils.fetch_url(url)
        except utils.FetchUrlFailed, fuf:
            self.log.error("Download failed: %r", fuf)
            idiokit.stop()
        self.log.info("Downloaded")

        for line in fileobj:
            if line.startswith("#"):
                continue

            ip, time = line.split()
            time = self._normalize_time(time)

            event = events.Event()
            event.add("ip", ip)
            event.add("source time", time)
            event.add("feed", "openbl")
            event.add("description url", self.feed_url)
            event.add("type", "brute-force")
            event.add("protocol", "ssh")

            yield idiokit.send(event)

    def _normalize_time(self, time):
        seconds = int(time)
        seconds -= 1 * 3600  # UTC+1 to UTC
        time_tuple = _time.gmtime(seconds)
        return _time.strftime("%Y-%m-%d %H:%M:%S UTC", time_tuple)

if __name__ == "__main__":
    OpenBLBot.from_command_line().execute()
