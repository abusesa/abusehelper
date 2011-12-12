import urllib2
import xml.etree.cElementTree as etree
import idiokit
from abusehelper.core import bot, events, utils

class RSSBot(bot.PollingBot):
    feeds = bot.ListParam("URLs to the RSS feeds")

    @idiokit.stream
    def poll(self, _):
        for url in self.feeds:
            try:
                self.log.info('Downloading feed from: "%s"', url)
                _, fileobj = yield utils.fetch_url(url)
            except utils.FetchUrlFailed, e:
                self.log.error('Failed to download feed "%s": %r', url, e)
                return

            try:
                for _, elem in etree.iterparse(fileobj):
                    items = elem.findall("item")
                    if not items:
                        continue

                    for item in items:
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
                        if not pubdate:
                            pubdate = item.find("pubDate")
                            if pubdate is not None:
                                pubdate = pubdate.text

                        event = self.create_event(title,link,
                                                  description,pubdate,url)
                        if event:
                            yield idiokit.send(event)
            except SyntaxError, e:
                self.log.error('Syntax error in feed "%s": %r', url, e)
                continue

    def create_event(self, title, link, description, pubdate, url=''):
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
    feeds = bot.ListParam(default=[
            "https://spyeyetracker.abuse.ch/monitor.php?rssfeed=tracker",
            "https://zeustracker.abuse.ch/rss.php",
            "http://amada.abuse.ch/palevotracker.php?rssfeed"])

    def create_event(self, title, link, description, pubdate, url=''):
        if description is None:
            return None

        event = events.Event()

        for part in description.split(","):
            pair = part.split(":")
            if len(pair) < 2:
                continue
            key = pair[0].strip()
            value = pair[1].strip()

            if not value:
                continue
            elif key == "AS":
                if value.startswith("AS"):
                    value = value[2:]
                event.add("asn", value)
            elif key == "IP address":
                event.add("ip", value)
            elif key == "Country":
                event.add("country", value)
            elif key == "Host":
                event.add("host", value)
            elif key == "Status":
                event.add("status", value)
            if "zeus" in url:
                event.add("malware", "zeus")
            elif "spyeye" in url:
                event.add("malware", "spyeye")
            elif "palevo" in url:
                event.add("malware", "palevo")

        if not event.contains("asn") or not event.contains("ip"):
            return None

        return event

if __name__ == "__main__":
    AbuseCHBot.from_command_line().run()

