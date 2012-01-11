from abusehelper.core import bot, events
from abusehelper.contrib.rssbot.rssbot import RSSBot

class Malc0deBot(RSSBot):
    feeds = bot.ListParam(default=["http://malc0de.com/rss/"])

    def create_event(self, **keys):
        description = keys.get("description", None)
        if description is None:
            return None

        event = events.Event()
        event.add("feed", "malc0de")

        link = keys.get("link", None)
        if link:
            event.add("link", link)

        for part in description.split(","):
            pair = part.split(":", 1)
            if len(pair) < 2:
                continue

            key = pair[0].strip()
            value = pair[1].strip()
            if not key or not value:
                continue

            if key in ["URL", "Country", "ASN", "MD5"]:
                event.add(key.lower(), value)
            elif key == "IP Address":
                event.add("ip", value)

        if not event.contains("ip"):
            return None
        return event

if __name__ == "__main__":
    Malc0deBot.from_command_line().run()
