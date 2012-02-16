# -*- coding: utf-8 -*-

# In the runtime config:
# yield Source("cleanmxbot", csv_url="http://support.clean-mx.de/clean-mx/xmlphishing?response=alive&format=csv&domain=")
# yield Source("cleanmxbot", csv_url="http://support.clean-mx.de/clean-mx/xmlviruses?response=alive&format=csv&domain=", csv_name="xmlvirii")

import re
import idiokit
import urlparse
from xml.sax.saxutils import unescape as _unescape
from abusehelper.core import bot, events, utils

cdata = re.compile("(.*?)\<\!\[CDATA\[(.*?)\]\]\>")

def unescape(string):
    """
    >>> unescape("one&nbsp;<![CDATA[two&nbsp;]]>three")
    'one two&nbsp;three'
    """

    result = list()

    for index, data in enumerate(cdata.split(string)):
        if index % 3 != 2:
            data = _unescape(data, {"&nbsp;": " "})
        result.append(data)

    return "".join(result)

class CleanMXBot(bot.PollingBot):
    def feed_keys(self, csv_url, csv_name=None, **keys):
        if csv_name is None:
            csv_name = urlparse.urlparse(csv_url)[2].split("/")[-1]
        yield (csv_url, csv_name)

    @idiokit.stream
    def poll(self, url, name):
        try:
            self.log.info('Downloading page from: "%s"', url)
            info, fileobj = yield utils.fetch_url(url)
        except utils.FetchUrlFailed, e:
            self.log.error('Failed to download page "%s": %r', url, e)
            return

        charset = info.get_param("charset", None)
        lines = (line.strip() for line in fileobj if line.strip())
        yield utils.csv_to_events(lines, charset=charset) | self.normalize(name)

    @idiokit.stream
    def normalize(self, name):
        while True:
            event = yield idiokit.next()

            new = events.Event()
            for key, value in event.items():
                value = unescape(value).strip()
                if not value:
                    continue
                if key == "firsttime":
                    key = "time"
                new.add(key, value)

            if name:
                new.add("feed", name)

            yield idiokit.send(new)

if __name__ == "__main__":
    CleanMXBot.from_command_line().execute()
