"""
Malc0de RSS bot.

Maintainer: Lari Huttunen <mit-code@huttu.net>
"""
import socket
from abusehelper.core import bot, events
from abusehelper.bots.rssbot.rssbot import RSSBot


class Malc0deBot(RSSBot):
    feeds = bot.ListParam(default=["http://malc0de.com/rss/"])

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
        description = keys.get("description", None)
        if description is None:
            return None

        event = events.Event()
        event.add("feeder", "malc0de.com")
        event.add("feed", "malc0de")
        event.add("type", "malware url")

        link = keys.get("link", None)
        if link:
            event.add("description url", link)

        for part in description.split(","):
            pair = part.split(":", 1)
            if len(pair) < 2:
                continue

            key = pair[0].strip()
            value = pair[1].strip()
            if not key or not value:
                continue

            if key in ["URL", "MD5"]:
                if key == "URL":
                    value = "hxxp://" + value
                event.add(key.lower(), value)
            elif key == "IP Address":
                event.add("ip", value)

        host = keys.get("title", None)
        if not self.is_ip(host):
            event.add("domain name", host)

        event.add("description", "This host is most likely hosting a malware URL.")

        return event

if __name__ == "__main__":
    Malc0deBot.from_command_line().execute()
