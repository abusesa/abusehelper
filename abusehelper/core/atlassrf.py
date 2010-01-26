import re
import cgi
import sys
import time
import urllib2
import urlparse
import cStringIO as StringIO
import xml.etree.cElementTree as etree

from idiokit import threado
from abusehelper.core import utils, bot, events, cymru

TABLE_REX = re.compile("</h3>\s*(<table>.*?</table>)", re.I | re.S)

@threado.stream
def fetch_extras(inner, opener, url):
    try:
        _, fileobj = yield inner.sub(utils.fetch_url(url, opener))
    except utils.FetchUrlFailed:
        inner.finish(list())

    data = yield inner.thread(fileobj.read)
    match = TABLE_REX.search(data)
    if match is None:
        inner.finish(list())

    table = etree.XML(match.group(1))
    keys = [th.text or "" for th in table.findall("thead/tr/th")]
    keys = map(str.strip, keys)
    values = [th.text or "" for th in table.findall("tbody/tr/td")]
    values = map(str.strip, values)
    items = [item for item in zip(keys, values) if all(item)]
    inner.finish(items)

ATOM_NS = "http://www.w3.org/2005/Atom"
DC_NS = "http://purl.org/dc/elements/1.1"

class AtlasSRFBot(bot.PollingBot):
    feed_url = bot.Param()
    no_extras = bot.BoolParam()

    def augment(self):
        return cymru.CymruWhois()

    def room_key(self, asn, **keys):
        return asn

    def event_keys(self, event):
        return event.attrs.get("asn", list())

    @threado.stream
    def poll(inner, self, _):
        self.log.info("Downloading the report")
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
        try:
            _, fileobj = yield inner.sub(utils.fetch_url(self.feed_url, opener))
        except utils.FetchUrlFailed, fuf:
            self.log.error("Failed to download the report: %s", fuf)
            return
        self.log.info("Downloaded the report")

        for _, elem in etree.iterparse(fileobj):
            if elem.tag != etree.QName(ATOM_NS, "entry"):
                continue

            event = events.Event()
            event.add("feed", "atlassrf")

            updated = elem.find(str(etree.QName(ATOM_NS, "updated")))
            if updated is not None:
                event.add("updated", updated.text)

            subject = elem.find(str(etree.QName(DC_NS, "subject")))
            if subject is not None:
                event.add("ip", subject.text)

            for link in elem.findall(str(etree.QName(ATOM_NS, "link"))):
                if link.attrib.get("rel", None) != "detail":
                    continue
                url = link.attrib.get("href", None)
                if not url:
                    continue

                event.add("url", url)

                if not self.no_extras:
                    extras = yield inner.sub(fetch_extras(opener, url))
                    for key, value in extras:
                        event.add(key, value)

                parsed = urlparse.urlparse(url)
                for key, value in cgi.parse_qsl(parsed.query):
                    event.add(key, value)

            inner.send(event)
            yield
            list(inner)

if __name__ == "__main__":
    AtlasSRFBot.from_command_line().run()
