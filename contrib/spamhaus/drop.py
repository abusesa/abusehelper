# -*- coding: utf-8 -*-
"""
    Spamhaus DROP list handler
"""
__authors__ = "Jussi Eronen"
__copyright__ = "Copyright 2011, The AbuseHelper Project"
__license__ = "MIT <http://www.opensource.org/licenses/mit-license.php>"
__maintainer__ = "Jussi Eronen"
__email__ = "exec@iki.fi"

import idiokit
from idiokit import util
from abusehelper.core import utils, cymru, bot, events

class SpamhausDropBot(bot.PollingBot):
    use_cymru_whois = bot.BoolParam(default=True)

    def __init__(self, *args, **keys):
        bot.PollingBot.__init__(self, *args, **keys)
        self.whois = cymru.CymruWhoisAugmenter()

    def poll(self,_):
        if self.use_cymru_whois:
            return self._poll() | self.whois.augment()
        return self._poll()

    @idiokit.stream
    def _poll(self, url="http://www.spamhaus.org/drop/drop.lasso"):
        self.log.info("Downloading %s" % url)
        try:
            info, fileobj = yield utils.fetch_url(url)
        except utils.FetchUrlFailed, fuf:
            self.log.error("Download failed: %r", fuf)
            idiokit.stop(False)
        self.log.info("Downloaded")

        for line in fileobj.readlines():
            if line.startswith(';'):
                continue
            data = line.split(';')
            if not data:
                continue

            netblock_sbl = [x.strip() for x in data]
            if len(netblock_sbl) != 2:
                continue

            netblock, sbl = netblock_sbl
            if not len(netblock.split('/')) == 2:
                continue
            ip = netblock.split('/')[0]
            new = events.Event()
            # Adding the bogus IP so that Cymru whois can do its magic
            new.add('ip', ip)
            new.add('netblock', netblock)
            new.add('url', 
                    "http://www.spamhaus.org/sbl/sbl.lasso?query=%s" % (sbl))
            new.add('source', 'Spamhaus DROP')

            yield idiokit.send(new)

if __name__ == "__main__":
    SpamhausDropBot.from_command_line().execute()
