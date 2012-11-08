"""
abuse.ch Zeus dropzone RSS feed.

Maintainer: Lari Huttunen <mit-code@huttu.net>
"""

import re
import urlparse
from abusehelper.core import bot, events
from abusehelper.contrib.rssbot.rssbot import RSSBot

from . import is_ip

class ZeusDropzoneBot(RSSBot):
    feeds = bot.ListParam(default=["https://zeustracker.abuse.ch/monitor.php?urlfeed=dropzones"])
    # Please note that this feed does *not* report ips per se. They are derived
    # below from the URL if the URL is an ip URL. That is why the ip is never
    # dropped if it is present in the source even if the bool param
    # treat_as_dns_source is set below.
    treat_as_dns_source = bot.BoolParam()

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
                if key == "Status":
                    event.add(key.lower(), value)
                elif key == "URL":
                    event.add("url", value)
                    parsed = urlparse.urlparse(value)
                    host = parsed.netloc
                    if is_ip(host):
                        event.add("ip", host)
                    else:
                        event.add("host", host)
        event.add("feed", "abuse.ch")
        event.add("malware", "ZeuS")
        event.add("type", "dropzone")
        return event

if __name__ == "__main__":
    ZeusDropzoneBot.from_command_line().execute()
