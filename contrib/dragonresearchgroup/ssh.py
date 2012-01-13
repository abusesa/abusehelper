import idiokit
from idiokit import util
from abusehelper.core import utils, bot, events

class DragonSshBot(bot.PollingBot):
    COLUMNS = ["asn", "as name", "ip", "time", "category"]

    @idiokit.stream
    def poll(self, _, url="http://dragonresearchgroup.org/insight/sshpwauth.txt"):
        self.log.info("Downloading %s" % url)
        try:
            info, fileobj = yield utils.fetch_url(url)
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
        yield utils.csv_to_events(filtered,
                                  delimiter="|",
                                  columns=self.COLUMNS,
                                  charset=charset)

if __name__ == "__main__":
    DragonSshBot.from_command_line().execute()
