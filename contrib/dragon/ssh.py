import idiokit
from idiokit import util
from abusehelper.core import utils, cymru, bot, events

class DragonSshBot(bot.PollingBot):
    COLUMNS = ["asn","as name", "ip", "time", "category"]
    use_cymru_whois = bot.BoolParam(default=False)

    def __init__(self, *args, **keys):
        bot.PollingBot.__init__(self, *args, **keys)
        self.whois = cymru.CymruWhoisAugmenter()

    def poll(self, asn):
        if self.use_cymru_whois:
            return self._poll() | self.whois.augment()
        return self._poll()

    @idiokit.stream
    def _poll(self, url="http://dragonresearchgroup.org/insight/sshpwauth.txt"):
        self.log.info("Downloading %s" % url)
        try:
            info, fileobj = yield utils.fetch_url(url)
        except utils.FetchUrlFailed, fuf:
            self.log.error("Download failed: %r", fuf)
            idiokit.stop(False)
        self.log.info("Downloaded")

        charset = info.get_param("charset")
        if charset is None:
            decode = util.guess_encoding
        else:
            decode = lambda x: x.decode(charset)

        filtered = (x for x in fileobj if x.strip() and not x.startswith("#"))
        rows = list()
        yield utils.csv_to_events(filtered,
                                  delimiter="|",
                                  columns=self.COLUMNS,
                                  charset=charset)

if __name__ == "__main__":
    DragonSshBot.from_command_line().execute()
