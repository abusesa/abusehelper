"""
Spamhaus DROP list handler.

Maintainer: Jussi Eronen <exec@iki.fi>
"""

import idiokit
from abusehelper.core import utils, cymruwhois, bot, events


class SpamhausDropBot(bot.PollingBot):
    use_cymru_whois = bot.BoolParam()

    @idiokit.stream
    def poll(self, url="http://www.spamhaus.org/drop/drop.lasso"):
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

            new = events.Event()
            new.add('netblock', netblock)
            new.add('description url', "http://www.spamhaus.org/sbl/query/" + sbl)
            new.add('feed', 'spamhaus drop list')
            new.add('type', 'hijacked network')

            if self.use_cymru_whois:
                values = yield cymruwhois.lookup(netblock.split('/')[0])
                for key, value in values:
                    new.add(key, value)

            yield idiokit.send(new)

if __name__ == "__main__":
    SpamhausDropBot.from_command_line().execute()
