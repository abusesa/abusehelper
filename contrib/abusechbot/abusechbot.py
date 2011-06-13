import xml.etree.cElementTree as etree
from idiokit import threado
from abusehelper.core import bot, events, utils

class RSSBot(bot.PollingBot):
    feeds = bot.ListParam("a list of RSS feed URLs")

    def feed_keys(self, **_):
        for feed in self.feeds:
            yield (feed,)

    @threado.stream
    def poll(inner, self, url):
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
                for _ in inner: pass

                keys = ["title", "link", "description", "pubdate"]
                args = [item.findtext(key) for key in keys]
                args.append(url)

                event = self.create_event(*args)
                if event:
                    inner.send(event)

    def create_event(self, title, link, description, pubdate, url):
        keys = dict(title=title, link=link, description=description, 
                    pubdate=pubdate, url=url)

        event = events.Event()
        for key, value in keys.iteritems():
            if value:
                event.add(key, value)
        return event

class AbuseCHBot(RSSBot):
    feeds = bot.ListParam(
        default=["https://spyeyetracker.abuse.ch/monitor.php?rssfeed=tracker", 
                 "https://zeustracker.abuse.ch/rss.php"])

    def create_event(self, title, link, description, pubdate, url):
        if description is None:
            return None

        event = events.Event()
        event.add("feed", "abuse.ch")
        if url:
            event.add("source",url)

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
                event.add("as", value)
            elif key == "IP address":
                event.add("ip", value)
            elif key == "Country":
                event.add("country", value)
            elif key == "Host":
                event.add("host", value)

        if not event.contains("as") or not event.contains("ip"):
            return None
        return event

if __name__ == "__main__":
    AbuseCHBot.from_command_line().run()
