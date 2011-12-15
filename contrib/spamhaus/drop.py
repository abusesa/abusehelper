import re
import cStringIO

import idiokit
from idiokit import util
from abusehelper.core import utils, cymru, bot, events

class BruteForceBlockerBot(bot.PollingBot):
    COLUMNS = ["ip", "lastseen", "count", "id", "url"]
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
            self.log.error("Download failed: %r", asn, fuf)
            idiokit.stop(False)
        self.log.info("Downloaded")

        for line in fileobj.xreadlines():
            if line.startswith(';'):
                continue
            data = line.split(';')
            if not data:
                continue
            netblock, sbl = [x.strip() for x in data]
            if not len(netblock.split('/')) == 2:
                continue
            ip = netblock.split('/')[0]
            new = events.Event()
            # Adding the bogus IP so that Cymru whois can do its magic
            new.add('ip', ip)
            new.add('netblock', netblock)
            new.add('url', 
                    "http://www.spamhaus.org/sbl/sbl.lasso?query=" % (url))
            new.add('source', 'Spamhaus DROP')

            yield idiokit.send(new)

if __name__ == "__main__":
    BruteForceBlockerBot.from_command_line().execute()
