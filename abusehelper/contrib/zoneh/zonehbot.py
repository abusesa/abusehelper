"""
Zone-H RSS feedbot based on abuse.ch bot and RSSbot.

Maintainer: Lari Huttunen <mit-code@huttu.net>
"""
import socket
import urlparse
from abusehelper.core import events
from abusehelper.contrib.rssbot.rssbot import RSSBot


def is_ip(string):
    for addr_type in (socket.AF_INET, socket.AF_INET6):
        try:
            socket.inet_pton(addr_type, string)
        except (ValueError, socket.error):
            pass
        else:
            return True
    return False


def parse_pubDate(pubdate):
    yield "time", pubdate


def parse_title(title):
    yield "url", title
    parsed = urlparse.urlparse(title)
    host = parsed.netloc
    if is_ip(host):
        yield "ip", host
    else:
        yield "host", host


def parse_link(link):
    yield "more info", link


def parse_description(description):
    parts = []
    parts = description.split()
    if len(parts) > 3:
        notifier = " ".join(parts[3:])
        yield "notified by", notifier


class ZoneHBot(RSSBot):
    feeds = ["http://www.zone-h.org/rss/defacements"]

    def parse_pubDate(self, string):
        return parse_pubDate(string)

    def parse_title(self, string):
        return parse_title(string)

    def parse_link(self, string):
        return parse_link(string)

    def parse_description(self, string):
        return parse_description(string)

    def create_event(self, source=None, **keys):
        event = events.Event()
        okeys = []
        for name, string in keys.iteritems():
            parse = getattr(self, "parse_" + name, None)
            if parse is None:
                continue

            for key, value in parse(string):
                event.add(key, value)
                okeys.append(key)

        if not event.contains():
            return None

        event.add("type", "defacement")
        event.add("feed", "zone-h")
        event.add("feed keys", ",".join(okeys))
        return event

if __name__ == "__main__":
    ZoneHBot.from_command_line().run()
