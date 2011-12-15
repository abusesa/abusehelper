import idiokit
from idiokit import util
from abusehelper.core import utils, cymru, bot, events

class IPListBot(bot.PollingBot):
    use_cymru_whois = bot.BoolParam(default=True)

    def __init__(self, *args, **keys):
        bot.PollingBot.__init__(self, *args, **keys)
        self.whois = cymru.CymruWhoisAugmenter()

    def poll(self, _, url="", source=""):
        if self.use_cymru_whois:
            return self._poll(url, source) | self.whois.augment()
        return self._poll(url)

    @idiokit.stream
    def _poll(self, url="", source=""):
        if not url:
            self.log.error("URL not specified!")
            idiokit.stop(False)
            
        self.log.info("Downloading %s" % url)
        try:
            info, fileobj = yield utils.fetch_url(url)
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

            new.add('ip', ip)
            new.add('url', url)
            if source:
                new.add('source', source)

            yield idiokit.send(new)

if __name__ == "__main__":
    IPListBot.from_command_line().execute()
