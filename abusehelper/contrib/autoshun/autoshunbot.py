import idiokit
import time as _time
import calendar
from abusehelper.core import utils, cymruwhois, bot

AUTOSHUN_CSV_URL = "http://www.autoshun.org/files/shunlist.csv"

# Based on analysis in VSRoom for the most common types.
CLASSIFICATION = (
    ("ZeroAccess", "malware", "ZeroAccess"),
    ("Sipvicious", "protocol", "sip"),
    ("SSH", "protocol", "ssh"),
    ("Tomcat", "protocol", "http"),
    ("WEB Proxy", "protocol", "http"),
    ("Double HTTP", "protocol", "http"),
    ("Wordpress", "protocol", "http"),
    ("DHL Spambot", "type", "spambot"),
    ("Spam Bot", "type", "spambot"),
    ("Terminal Server", "protocol", "rdp"),
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
            event.add("description url", self.feed_url)
            for d in event.values("info"):
                event.add("description", d)
                for name, key, value in CLASSIFICATION:
                    if d.startswith(name):
                        event.add(key, value)
                        if key == "malware":
                            event.add("type", "botnet drone")
                        elif key == "protocol":
                            event.add("type", "brute-force")
                        if value == "spambot":
                            event.add("type", "botnet drone")
            event.clear("info")
            if not event.contains("type"):
                event.add("type", "ids alert")
            times = event.values("time")
            event.clear("time")
            for time in times:
                event.add("source time", self._normalize_time(time))
            yield idiokit.send(event)

    def _normalize_time(self, time):
        parsed = _time.strptime(time, "%Y-%m-%d %H:%M:%S")
        seconds = calendar.timegm(parsed)
        seconds += 5 * 3600  # UTC-5 to UTC
        time_tuple = _time.gmtime(seconds)
        return _time.strftime("%Y-%m-%d %H:%M:%S UTC", time_tuple)

if __name__ == "__main__":
    AutoshunBot.from_command_line().execute()
