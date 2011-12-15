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
    def _poll(self, 
             url="http://danger.rulez.sk/projects/bruteforceblocker/blist.php"):
        self.log.info("Downloading %s" % url)
        try:
            info, fileobj = yield utils.fetch_url(url)
        except utils.FetchUrlFailed, fuf:
            self.log.error("Download failed: %r", asn, fuf)
            idiokit.stop(False)
        self.log.info("Downloaded")

        # Crappy human-readable output does not lend itself well for
        # csv parsing without modification
        data = fileobj.read()
        data = re.sub('\t+', '\t', data)
        data = re.sub('\n', '\t%s\n' % (url), data)
        data = data.replace('# ', '')
        fileobj = cStringIO.StringIO(data)

        charset = info.get_param("charset")
        if charset is None:
            decode = util.guess_encoding
        else:
            decode = lambda x: x.decode(charset)

        filtered = (x for x in fileobj if x.strip() and not x.startswith("#"))
        rows = list()

        yield utils.csv_to_events(filtered,
                                  delimiter="\t",
                                  columns=self.COLUMNS,
                                  charset=charset)

if __name__ == "__main__":
    BruteForceBlockerBot.from_command_line().execute()
