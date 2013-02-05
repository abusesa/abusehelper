import idiokit
from abusehelper.core import utils, cymruwhois, bot, events


class ArborSSHBot(bot.PollingBot):
    use_cymru_whois = bot.BoolParam()

    COLUMNS = ["ip", "count"]

    def poll(self):
        if self.use_cymru_whois:
            return self._poll() | cymruwhois.augment("ip")
        return self._poll()

    @idiokit.stream
    def _poll(self, url="http://atlas-public.ec2.arbor.net/public/ssh_attackers"):
        self.log.info("Downloading %s" % url)
        try:
            info, fileobj = yield utils.fetch_url(url)
        except utils.FetchUrlFailed, fuf:
            self.log.error("Download failed: %r", fuf)
            return
        self.log.info("Downloaded")

        charset = info.get_param("charset")
        if charset is None:
            decode = utils.force_decode
        else:
            decode = lambda x: x.decode(charset)

        for row in fileobj:
            row = row.strip()
            if row.startswith("other"):
                continue

            row = decode(row).split()
            event = events.Event()
            for key, value in zip(self.COLUMNS, row):
                event.add(key, value)
            yield idiokit.send(event)


if __name__ == "__main__":
    ArborSSHBot.from_command_line().execute()
