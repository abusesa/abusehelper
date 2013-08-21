import idiokit
import time as _time
import calendar
from abusehelper.core import utils, cymruwhois, bot

AUTOSHUN_CSV_URL = "http://www.autoshun.org/files/shunlist.csv"

# Based on analysis in VSRoom for the most common types.
CLASSIFICATION = (
    ("ZeroAccess", "malware", "zeroaccess"),
    ("Sipvicious", "protocol", "sip"),
    ("SSH", "protocol", "ssh"),
    ("Tomcat", "protocol", "http"),
    ("WEB Proxy", "protocol", "http"),
    ("Double HTTP", "protocol", "http"),
    ("Wordpress", "protocol", "http"),
    ("DHL Spambot", "type", "spam"),
    ("Spam Bot", "type", "spam"),
    ("Teminal Server", "protocol", "rdp"),
    ("TDSS", "malware", "tdss")
)


class AutoshunBot(bot.PollingBot):
    COLUMNS = ["ip", "time", "info"]

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
        offset = -1 * int(header[-6::].strip()) / 100  # ex: -0500 to 5
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
            event.add("description", "This host has triggered an AutoShun alert.")
            for info in event.values("info"):
                for name, key, value in CLASSIFICATION:
                    if info.startswith(name):
                        event.add(key, value)
                        if key in ["malware", "spam"]:
                            event.add("type", "botnet drone")
                        elif key == "protocol":
                            event.add("type", "brute-force")
                event.add("anecdotal information", info)
            event.clear("info")
            if not event.contains("type"):
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
        parsed = _time.strptime(time, "%Y-%m-%d %H:%M:%S")
        seconds = calendar.timegm(parsed)
        seconds += self.time_offset * 3600  # UTC-5 to UTC
        time_tuple = _time.gmtime(seconds)
        return _time.strftime("%Y-%m-%d %H:%M:%S UTC", time_tuple)

    def _normalize_date(self, time):
        parsed = _time.strptime(time, "%Y-%m-%d")
        return _time.strftime("%Y-%m-%d", parsed)  # No UTC-5 to UTC conversion

if __name__ == "__main__":
    AutoshunBot.from_command_line().execute()
