"""
abuse.ch Palevo C&C feed RSS bot.

Maintainer: Lari Huttunen <mit-code@huttu.net>
"""
import socket
from abusehelper.core import bot, events
from abusehelper.contrib.rssbot.rssbot import RSSBot


class PalevoCcBot(RSSBot):
    feeds = bot.ListParam(default=["https://palevotracker.abuse.ch/?rssfeed"])
    # If treat_as_dns_source is set, the feed ip is dropped.
    treat_as_dns_source = bot.BoolParam()

    def is_ip(self, string):
        for addr_type in (socket.AF_INET, socket.AF_INET6):
            try:
                socket.inet_pton(addr_type, string)
            except (ValueError, socket.error):
                pass
            else:
                return True
        return False

    def create_event(self, **keys):
        event = events.Event()
        # handle link data
        link = keys.get("link", None)
        if link:
            event.add("description url", link)
        # handle title data
        title = keys.get("title", None)
        if title:
            host, date = title.split()
            if self.is_ip(host):
                event.add("ip", host)
            else:
                event.add("host", host)
            event.add("source time", date)
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
                elif key == "SBL" and value != "Not listed":
                    key = key.lower() + " id"
                    event.add(key, value)
                elif key == "IP address":
                    if not self.treat_as_dns_source:
                        event.add("ip", value)
        event.add("feed", "abuse.ch")
        event.add("malware", "Palevo")
        event.add("type", "c&c")
        return event

if __name__ == "__main__":
    PalevoCcBot.from_command_line().execute()
