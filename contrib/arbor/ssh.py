from idiokit import threado,util
from abusehelper.core import utils, cymru, bot, events
import re
class ArborSshBot(bot.PollingBot):
    COLUMNS = ["ip", "count"]

    use_cymru_whois = bot.BoolParam(default=False)

    def __init__(self, *args, **keys):
        bot.PollingBot.__init__(self, *args, **keys)
        self.whois = cymru.CymruWhoisAugmenter()

    def poll(self,_):
        return self._poll() | self.whois.augment()

    @threado.stream
    def _poll(inner, self, url="http://atlas-public.ec2.arbor.net/public/ssh_attackers"):

        self.log.info("Downloading %s" % url)
        try:
            info, fileobj = yield inner.sub(utils.fetch_url(url))
        except utils.FetchUrlFailed, fuf:
            self.log.error("Download failed: %r", asn, fuf)
            return
        self.log.info("Downloaded")

        charset = info.get_param("charset")
        if charset is None:
            decode = util.guess_encoding
        else:
            decode = lambda x: x.decode(charset)

        filtered = (x for x in fileobj if x.strip() and not x.startswith("other"))
        rows = list()
        #sanitize delimiter
        for row in filtered:
            row = decode(row.strip())
            rows.append("\t".join(re.split("\s+",row)))
        yield inner.sub(utils.csv_to_events(rows,
                                            delimiter="\t",
                                            columns=self.COLUMNS,
                                            charset=charset))


if __name__ == "__main__":
    ArborSshBot.from_command_line().execute()
