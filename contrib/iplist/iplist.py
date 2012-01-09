# -*- coding: utf-8 -*-
"""
    Generic feed handler for lists of IPv4 addresses and netblocks. TODO: IPv6!
"""
__authors__ = "Jussi Eronen"
__copyright__ = "Copyright 2011, The AbuseHelper Project"
__license__ = "MIT <http://www.opensource.org/licenses/mit-license.php>"
__maintainer__ = "Jussi Eronen"
__email__ = "exec@iki.fi"

import re
import idiokit
from abusehelper.core import utils, cymru, bot, events

class IPListBot(bot.PollingBot):
    use_cymru_whois = bot.BoolParam(default=True)
    url = bot.Param("IPlist URL")
    source = bot.Param("Source name")

    def __init__(self, *args, **keys):
        bot.PollingBot.__init__(self, *args, **keys)
        self.log.info("%r %r", args, keys)
        self.whois = cymru.CymruWhoisAugmenter()

    def poll(self, _):
        if self.use_cymru_whois:
            return self._poll() | self.whois.augment()
        return self._poll()

    @idiokit.stream
    def _poll(self):
        if not self.url:
            self.log.error("URL not specified!")
            idiokit.stop(False)

        self.log.info("Downloading %s" % self.url)
        try:
            info, fileobj = yield utils.fetch_url(self.url)
        except utils.FetchUrlFailed, fuf:
            self.log.error("Download failed: %r", fuf)
            idiokit.stop(False)
        self.log.info("Downloaded")

        data = fileobj.read()
        for ip in re.findall('\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}(?!/)', data):
            new = events.Event()
            new.add('ip', ip)
            new.add('url', self.url)
            if self.source:
                new.add('source', self.source)

            yield idiokit.send(new)
        for netblock in re.findall('\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d+',
                                   data):
            new = events.Event()
            ip = netblock.split('/')[0]
            new.add('ip', ip)
            new.add('netblock', netblock)
            new.add('url', self.url)
            if self.source:
                new.add('source', self.source)

            yield idiokit.send(new)

if __name__ == "__main__":
    IPListBot.from_command_line().execute()
