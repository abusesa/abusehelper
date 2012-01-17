import re
import cgi
import urllib2
import urlparse
import xml.etree.cElementTree as etree

import idiokit
from idiokit import threadpool
from abusehelper.core import utils, bot, events, cymruwhois

TABLE_REX = re.compile("</h3>\s*(<table>.*?</table>)", re.I | re.S)

@idiokit.stream
def fetch_extras(opener, url):
    try:
        _, fileobj = yield utils.fetch_url(url, opener)
    except utils.FetchUrlFailed:
        idiokit.stop(list())

    data = yield threadpool.thread(fileobj.read)
    match = TABLE_REX.search(data)
    if match is None:
        idiokit.stop(list())

    table = etree.XML(match.group(1))
    keys = [th.text or "" for th in table.findall("thead/tr/th")]
    keys = map(str.strip, keys)

    def get_values(all):
        # Long urls are formatted in the following format, this code
        # is needed to get the full url
        #
        # <td><span class="long_hover_default"
        # onmouseout="MochiKit.DOM.setElementClass(this,
        # 'long_hover_default')">http://x<wbr />y</span><span
        # onmouseover="MochiKit.DOM.setElementClass(this.previousSibling,
        # 'long_hover_on')">http://x......</span></td>
        out = list()
        for th in all:
            val = ''
            if th.text:
                if not th.get('onmouseover'):
                    val = th.text
            if th.tail and th.tail.strip():
                val += th.tail
            if th.getchildren():
                val += ''.join(get_values(th))
            if not val:
                out.append('')
            else:
                out.append(val)

        return out

    values = get_values(table.findall("tbody/tr/td"))
    values = map(str.strip, values)
    # Keys and values do not match in the table
    if (len(values) % len(keys)):
        idiokit.stop(list())
    items = [item for item in zip((len(values) / len(keys)) * keys, values)]
    items = zip(*[items[i::len(keys)] for i in range(len(keys))])
    idiokit.stop(items)

ATOM_NS = "http://www.w3.org/2005/Atom"
DC_NS = "http://purl.org/dc/elements/1.1"

class AtlasSRFBot(bot.PollingBot):
    feed_url = bot.Param()
    no_extras = bot.BoolParam()

    def augment(self):
        return cymruwhois.augment("ip")

    def feed_keys(self, *args, **keys):
        yield (self.feed_url,)

    @idiokit.stream
    def poll(self, url):
        self.log.info("Downloading the report")
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor())
        try:
            _, fileobj = yield utils.fetch_url(url, opener)
        except utils.FetchUrlFailed, fuf:
            self.log.error("Failed to download the report: %r", fuf)
            return
        self.log.info("Downloaded the report")

        for _, elem in etree.iterparse(fileobj):
            if elem.tag != etree.QName(ATOM_NS, "entry"):
                continue

            all_events = list()

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

                parsed = urlparse.urlparse(url)
                for key, value in cgi.parse_qsl(parsed.query):
                    event.add(key, value)

                if not self.no_extras:
                    extras = yield fetch_extras(opener, url)
                    if not extras:
                        all_events.append(event)
                    for line in extras:
                        new_event = events.Event(event)
                        for key, value in line:
                            if value:
                                new_event.add(key, value)
                        all_events.append(new_event)
                else:
                    all_events.append(event)

            for cur in all_events:
                yield idiokit.send(cur)

if __name__ == "__main__":
    AtlasSRFBot.from_command_line().run()
