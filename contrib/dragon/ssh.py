from idiokit import threado,util
from abusehelper.core import utils, cymru, bot, events
import re
class DragonSshBot(bot.PollingBot):
    COLUMNS = ["asn","as name", "ip", "time", "category"]
    use_cymru_whois = bot.BoolParam(default=False)

    def __init__(self, *args, **keys):
        bot.PollingBot.__init__(self, *args, **keys)
        self.whois = cymru.CymruWhoisAugmenter()

    def poll(self,_):
        if self.use_cymru_whois:
            return self._poll() | self.whois.augment()
        return self._poll()

    @threado.stream
    def _poll(inner, self, url="http://dragonresearchgroup.org/insight/sshpwauth.txt"):

        self.log.info("Downloading %s" % url)
        try:
            info, fileobj = yield inner.sub(utils.fetch_url(url))
        except utils.FetchUrlFailed, fuf:
            self.log.error("Download failed: %r", fuf)
            return
        self.log.info("Downloaded")

        charset = info.get_param("charset")
        if charset is None:
            decode = util.guess_encoding
        else:
            decode = lambda x: x.decode(charset)

        filtered = (x for x in fileobj if x.strip() and not x.startswith("#"))
        rows = list()

        yield inner.sub(utils.csv_to_events(filtered,
                                            delimiter="|",
                                            columns=self.COLUMNS,
                                            charset=charset))


if __name__ == "__main__":
    DragonSshBot.from_command_line().execute()
