import idiokit
from idiokit import util
from abusehelper.core import utils, cymru, bot, events

class IPListBot(bot.PollingBot):
    use_cymru_whois = bot.BoolParam(default=True)
    url = bot.Param("IPlist URL")
    source = bot.Param("Source name")

    def __init__(self, *args, **keys):
        bot.PollingBot.__init__(self, *args, **keys)
        self.log.info("%r %r", args, keys)
        self.whois = cymru.CymruWhoisAugmenter()

    def poll(self, _):
        if self.use_cymru_whois:
            return self._poll() | self.whois.augment()
        return self._poll()

    @idiokit.stream
    def _poll(self):
        if not self.url:
            self.log.error("URL not specified!")
            idiokit.stop(False)
            
        self.log.info("Downloading %s" % self.url)
        try:
            info, fileobj = yield utils.fetch_url(self.url)
        except utils.FetchUrlFailed, fuf:
            self.log.error("Download failed: %r", fuf)
            idiokit.stop(False)
        self.log.info("Downloaded")

        for line in fileobj.readlines():
            line = line.strip()
            # Skip empty lines
            if not line:
                continue
            # If the line does not start with a number, skip. Checking
            # the validity of IP addresses is the job of sanitizers.
            if not line[0].isdigit():
                continue
            # Assuming that the lines can contain arbitrary crap after
            # a space, so only retain data before space and assume
            # that it is the IP address
            ip = line.split()[0]

            new = events.Event()
            new.add('ip', ip)
            new.add('url', self.url)
            if self.source:
                new.add('source', self.source)

            yield idiokit.send(new)

if __name__ == "__main__":
    IPListBot.from_command_line().execute()
