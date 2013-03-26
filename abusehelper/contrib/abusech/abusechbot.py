"""
Base AbuseCH feed handler. The specific AbuseCH RSS feeds bots
(ZeuS Tracker etc.) are built on this.

Maintainer: Jussi Eronen <exec@iki.fi>
"""

import re
import cgi
import time
import urlparse

from abusehelper.core import events
from abusehelper.contrib.rssbot.rssbot import RSSBot

from . import parse_ip


def parse_title(title):
    """
    ZeuS Tracker and SpyEye Tracker styles:

    >>> list(parse_title("1.2.3.4/badness.php (2012-01-01)"))
    [('time', '2012-01-01 00:00:00 UTC')]

    >>> list(parse_title("1.2.3.4/badness.php (2012-01-01 01:02:03)"))
    [('time', '2012-01-01 01:02:03 UTC')]

    Palevo tracker style:

    >>> list(parse_title("1.2.3.4/badness.php 2012-01-01"))
    [('time', '2012-01-01 00:00:00 UTC')]

    Ignore if can't be parsed:

    >>> list(parse_title("1.2.3.4/badness.php"))
    []
    """

    match = re.search(r"(\d{4}-\d\d-\d\d(?: \d\d\:\d\d:\d\d)?)\)?\s*$", title)
    if not match:
        return

    timestamp = match.group(1)
    for format in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            timestamp = time.strptime(timestamp, format)
        except ValueError:
            continue
        yield "time", time.strftime("%Y-%m-%d %H:%M:%S UTC", timestamp)
        break


def parse_link(link):
    """
    >>> sorted(parse_link("https://spyeyetracker.abuse.ch/monitor.php?host=www.example.com"))
    [('host', 'www.example.com'), ('more info', 'https://spyeyetracker.abuse.ch/monitor.php?host=www.example.com')]

    >>> sorted(parse_link("https://spyeyetracker.abuse.ch/monitor.php?host=1.2.3.4"))
    [('host', '1.2.3.4'), ('ip', '1.2.3.4'), ('more info', 'https://spyeyetracker.abuse.ch/monitor.php?host=1.2.3.4')]
    """

    yield "more info", link

    parsed = urlparse.urlparse(link)
    query = cgi.parse_qs(parsed[4])
    for host in query.get("host", []):
        yield "host", host

        if parse_ip(host):
            yield "ip", host


_levels = {
    "1": "bulletproof hosted",
    "2": "hacked webserver",
    "3": "free hosting service",
    "4": "unknown",
    "5": "hosted on a fastflux botnet"
}


_sbl_prefix = "http://www.spamhaus.org/sbl/sbl.lasso?query="


def parse_description(description):
    for part in description.split(","):
        pair = part.split(":", 1)
        if len(pair) < 2:
            continue
        key, value = pair

        value = value.strip()
        if not value:
            continue

        key = key.strip().lower()
        if key == "as":
            if value.lower().startswith("as"):
                value = value[2:]
            yield "asn", value
        elif key == "ip address":
            yield "ip", value
        elif key == "sbl":
            if value.lower() != "not listed":
                yield "sbl", _sbl_prefix + value
        elif key == "level":
            yield "level", _levels.get(value, value)
        else:
            yield key, value


class AbuseCHBot(RSSBot):
    feeds = None

    malwares = {
        "zeus": {
            "c&c": "https://zeustracker.abuse.ch/rss.php",
            "config": "https://zeustracker.abuse.ch/monitor.php?urlfeed=configs",
            "binary": "https://zeustracker.abuse.ch/monitor.php?urlfeed=binaries",
            "dropzone": "https://zeustracker.abuse.ch/monitor.php?urlfeed=dropzones"
        },
        "spyeye": {
            "c&c": "https://spyeyetracker.abuse.ch/monitor.php?rssfeed=tracker",
            "config": "https://spyeyetracker.abuse.ch/monitor.php?rssfeed=configurls",
            "binary": "https://spyeyetracker.abuse.ch/monitor.php?rssfeed=binaryurls",
            "dropzone": "https://spyeyetracker.abuse.ch/monitor.php?rssfeed=dropurls"
        },
        "palevo": {
            "c&c": "https://palevotracker.abuse.ch/?rssfeed"
        }
    }

    @property
    def urls(self):
        if self._urls is not None:
            return self._urls

        self._urls = dict()
        for malware, feed_types in self.malwares.iteritems():
            for feed_type, url in feed_types.iteritems():
                self._urls[url] = malware, feed_type
        return self._urls
    _urls = None

    def feed_keys(self, malwares=None, types=None, **_):
        if malwares is None:
            malwares = self.malwares

        for malware in malwares:
            if not malware in self.malwares:
                self.log.error("no support for malware %r" % malware)
                continue

            feed_types = self.malwares[malware]
            for feed_type in (feed_types if types is None else types):
                if feed_type not in feed_types:
                    self.log.error("no support for %r type %r" % (malware, feed_type))
                    continue
                yield (feed_types[feed_type],)

    def parse_title(self, string):
        return parse_title(string)

    def parse_link(self, string):
        return parse_link(string)

    def parse_description(self, string):
        return parse_description(string)

    def create_event(self, source=None, **keys):
        event = events.Event()

        for name, string in keys.iteritems():
            parse = getattr(self, "parse_" + name, None)
            if parse is None:
                continue

            for key, value in parse(string):
                event.add(key, value)

        if not event.contains():
            return None

        if source in self.urls:
            malware, feed_type = self.urls[source]

            # Provide a default malware name if the event doesn't have one
            malware_values = event.values("malware") or [malware]

            # Normalize the malware name(s) to lowercase
            event.clear("malware")
            event.update("malware", [x.lower() for x in malware_values])
            event.add("type", feed_type)
            event.add("feed", "abuse.ch")
        event.add("description url", source)

        return event

if __name__ == "__main__":
    AbuseCHBot.from_command_line().execute()
