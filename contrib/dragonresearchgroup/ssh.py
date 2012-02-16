import idiokit
from abusehelper.core import utils, cymruwhois, bot

class DragonSshBot(bot.PollingBot):
    # The first column values (ASN and AS name) are ignored.
    COLUMNS = [None, None, "ip", "time", "category"]

    def poll(self):
        return self._poll() | cymruwhois.augment("ip")

    @idiokit.stream
    def _poll(self, url="http://dragonresearchgroup.org/insight/sshpwauth.txt"):
        self.log.info("Downloading %s" % url)
        try:
            info, fileobj = yield utils.fetch_url(url)
        except utils.FetchUrlFailed, fuf:
            self.log.error("Download failed: %r", fuf)
            return
        self.log.info("Downloaded")

        charset = info.get_param("charset")
        filtered = (x for x in fileobj if x.strip() and not x.startswith("#"))
        yield utils.csv_to_events(filtered,
                                  delimiter="|",
                                  columns=self.COLUMNS,
                                  charset=charset)

if __name__ == "__main__":
    DragonSshBot.from_command_line().execute()
