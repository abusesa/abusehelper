import xml.etree.cElementTree as etree
from idiokit import threado
from abusehelper.core import bot, events, utils
from abusehelper.contrib.rssbot.rssbot import RSSBot

class AbuseCHBot(RSSBot):
    feeds = bot.ListParam(
        default=["https://spyeyetracker.abuse.ch/monitor.php?rssfeed=tracker",
                 "https://zeustracker.abuse.ch/rss.php"])

    def create_event(self, **keys):
        description = keys.get("description", None)
        if description is None:
            return None

        event = events.Event()
        event.add("feed", "abuse.ch")

        url = keys.get("source", None)
        if url:
            event.add("source", url)

        title = keys.get("title", None)
        if title:
            parts = title.split("(")
            if len(parts) > 1:
                event.add("time", parts[1].rstrip(")"))

        for part in description.split(","):
            pair = part.split(":", 1)
            if len(pair) < 2:
                continue

            key = pair[0].strip()
            value = pair[1].strip()
            if key == "Status" and value != "online":
                return None
            if not value:
                continue

            if key == "AS":
                if value.startswith("AS"):
                    value = value[2:]
                event.add("asn", value)
            elif key == "IP address":
                event.add("ip", value)
            elif key == "Country":
                event.add("country", value)
            elif key == "Host":
                event.add("host", value)

        if not event.contains("asn") or not event.contains("ip"):
            return None
        return event

if __name__ == "__main__":
    AbuseCHBot.from_command_line().run()
