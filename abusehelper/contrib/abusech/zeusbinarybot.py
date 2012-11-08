"""
abuse.ch Zeus Binary RSS feed bot.

Maintainer: Lari Huttunen <mit-code@huttu.net>
"""

import re
import urlparse
from abusehelper.core import bot, events
from abusehelper.contrib.rssbot.rssbot import RSSBot

from . import is_ip


class ZeusBinaryBot(RSSBot):
    feeds = bot.ListParam(default=["https://zeustracker.abuse.ch/monitor.php?urlfeed=binaries"])

    def create_event(self, **keys):
        event = events.Event()
        # handle link data
        link = keys.get("link", None)
        if link:
            event.add("description url", link)
        # handle title data
        br = re.compile('[()]')
        title = keys.get("title")
        parts = []
        parts = title.split()
        tstamp = parts[1]
        tstamp = br.sub('', tstamp)
        event.add("source time", tstamp)
        # handle description data
        description = keys.get("description", None)
        if description:
            for part in description.split(","):
                pair = part.split(":", 1)
                if len(pair) < 2:
                    continue

                key = pair[0].strip()
                value = pair[1].strip()
                if not key or not value:
                    continue
                if key == "URL":
                    proto = re.compile('^http:\/\/')
                    url = proto.sub('hxxp://', value)
                    event.add("url", url)
                    parsed = urlparse.urlparse(value)
                    host = parsed.netloc
                    if is_ip(host):
                        event.add("ip", host)
                    else:
                        event.add("host", host)
                if key in ["Virustotal", "Status"]:
                    event.add(key.lower(), value)
                if key == "MD5 hash":
                    event.add("md5", value)
        event.add("feed", "abuse.ch")
        event.add("malware", "ZeuS")
        event.add("type", "malware")
        return event

if __name__ == "__main__":
    ZeusBinaryBot.from_command_line().execute()
