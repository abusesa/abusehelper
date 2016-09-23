"""
Autoshun Shun List bot
https://autoshun.org/

Maintainer: Codenomicon <clarified@codenomicon.com>
"""


import idiokit
import time as _time
import calendar
from abusehelper.core import utils, cymruwhois, bot

AUTOSHUN_CSV_URL = "https://www.autoshun.org/files/shunlist.csv"


class AutoshunBot(bot.PollingBot):
    COLUMNS = ["ip", "time", "info"]
    time_offset = 5

    feed_url = bot.Param(default=AUTOSHUN_CSV_URL)
    use_cymru_whois = bot.BoolParam()

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

        # Grab time offset from first line of the CSV
        header = fileobj.readline()
        # Source file header row may sometimes be empty
        if header.startswith("Shunlist as of"):
            offset = -1 * int(header[-5:]) / 100  # ex: -0500 to 5
            self.time_offset = offset if -12 <= offset <= 12 else 5

        yield utils.csv_to_events(fileobj,
                                  columns=self.COLUMNS,
                                  charset=info.get_param("charset"))

    @idiokit.stream
    def _normalize(self):
        while True:
            event = yield idiokit.next()
            event.add("feed", "autoshun")
            event.add("feed url", self.feed_url)
            event.add("description", "This host has triggered an IDS alert.")

            for info in event.values("info"):
                event.add("additional information", info)
            event.clear("info")
            event.add("type", "ids alert")
            times = event.values("time")
            for time in times:
                try:
                    event.add("source time", self._normalize_time(time))
                except ValueError:
                    event.add("source time", self._normalize_date(time))
            event.clear("time")
            yield idiokit.send(event)

    def _normalize_time(self, time):
        try:
            parsed = _time.strptime(time, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            parsed = _time.strptime(time, "%Y-%m-%d %H:%M:")

        seconds = calendar.timegm(parsed)
        seconds += self.time_offset * 3600  # UTC-5 to UTC
        time_tuple = _time.gmtime(seconds)
        return _time.strftime("%Y-%m-%d %H:%M:%SZ", time_tuple)

    def _normalize_date(self, time):
        parsed = _time.strptime(time, "%Y-%m-%d")
        return _time.strftime("%Y-%m-%d", parsed)  # No UTC-5 to UTC conversion

if __name__ == "__main__":
    AutoshunBot.from_command_line().execute()
