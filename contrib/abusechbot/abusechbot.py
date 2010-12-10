import urllib2
import xml.etree.cElementTree as etree
from idiokit import threado
from abusehelper.core import bot, events, utils

class RSSBot(bot.PollingBot):
    feeds = bot.ListParam("Urls to the RSS feeds.")

    @threado.stream
    def poll(inner, self, _):
        yield

        for url in self.feeds:
            yield
            try:
                self.log.info('Downloading feed from: "%s"', url)
                _, fileobj = yield inner.sub(utils.fetch_url(url))
            except utils.FetchUrlFailed, e:
                self.log.error('Failed to download feed "%s": %r', url, e)
                return

            for _, elem in etree.iterparse(fileobj):
                items = elem.findall("item")
                if not items:
                    continue

                for item in items:
                    yield
                    title = item.find("title")
                    if title is not None:
                        title = title.text

                    link = item.find("link")
                    if link is not None:
                        link = link.text

                    description = item.find("description")
                    if description is not None:
                        description = description.text

                    pubdate = item.find("pubdate")
                    if pubdate is not None:
                        pubdate = pubdate.text

                    event = self.create_event(title,link,description,pubdate)
                    if event:
                        inner.send(event)

    def create_event(self, title, link, description, pubdate):
        event = events.Event()
        if title:
            event.add("title", title)
        if link:
            event.add("link", link)
        if description:
            event.add("description", description)
        if pubdate:
            event.add("pubdate", pubdate)
        return event

class AbuseCHBot(RSSBot):
    feeds = bot.ListParam(default=["https://spyeyetracker.abuse.ch/monitor.php?rssfeed=tracker", "https://zeustracker.abuse.ch/rss.php"])

    def create_event(self, title, link, description, pubdate):
        if description is None:
            return

        event = events.Event()
        event.add("feed", "abuse.ch")

        for part in description.split(","):
            pair = part.split(":")
            if len(pair) < 2:
                continue
            key = pair[0].strip()
            value = pair[1].strip()

            if key == "Status" and value != "online":
                return
            elif not value:
                continue
            elif key == "AS":
                if value.startswith("AS"):
                    value = value[2:]
                event.add("as", value)
            elif key == "IP address":
                event.add("ip", value)
            elif key == "Country":
                event.add("country", value)
            elif key == "Host":
                event.add("host", value)

        if not event.contains("as") or not event.contains("ip"):
            return

        return event

if __name__ == "__main__":
    AbuseCHBot.from_command_line().run()

