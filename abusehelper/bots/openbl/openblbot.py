"""
OpenBL bot

Maintainer: Codenomicon <clarified@codenomicon.com>
"""

import idiokit
import time as _time

from abusehelper.core import utils, cymruwhois, bot, events

OPENBL_FEED_URL = "https://www.openbl.org/lists/date_all.txt"


def _normalize_time(time):
    seconds = int(time) - 1 * 3600  # UTC+1 to UTC
    return _time.strftime("%Y-%m-%d %H:%M:%SZ", _time.gmtime(seconds))


def _parse_line(line):
    if line.startswith("#"):
        return None

    try:
        ip, time = line.split()
    except ValueError:
        return None

    time = _normalize_time(time)

    event = events.Event()
    event.add("ip", ip)
    event.add("source time", time)
    return event


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
            raise bot.PollSkipped("failed to download {0!r} ({1})".format(url, fuf))
        self.log.info("Downloaded")

        for line in fileobj:
            event = _parse_line(line)
            if event is None:
                continue

            event.add("feed", "openbl")
            event.add("description url", self.feed_url)
            event.add("type", "brute-force")
            event.add(
                "description",
                "This host has most likely been performing brute-force " +
                "attacks on one of the following services: FTP, SSH, POP3, " +
                "IMAP, IMAPS or POP3S."
            )
            yield idiokit.send(event)


if __name__ == "__main__":
    OpenBLBot.from_command_line().execute()
