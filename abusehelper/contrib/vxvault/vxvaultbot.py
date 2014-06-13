import socket
import idiokit
import urlparse 
from abusehelper.core import utils, bot, events

FEED_URL = "http://vxvault.siri-urz.net/URL_List.php"

def i_am_a_name(string):
    for addr_type in (socket.AF_INET, socket.AF_INET6):
        try:
            socket.inet_ntop(addr_type, socket.inet_pton(addr_type, string))
        except (ValueError, socket.error):
            pass
        else:
            return False
    return True


def parseURL(line):
    parsed = urlparse.urlparse(line)
    if parsed.scheme and parsed.netloc:
        return line, parsed.netloc
    else:
        return None, None

class VxVaultBot(bot.PollingBot):
    feed_url = bot.Param(default=FEED_URL)

    def poll(self):
        pipe = self._poll(url=self.feed_url)
        return pipe

    @idiokit.stream
    def _poll(self, url):
        self.log.info("Downloading %s" % url)
        try:
            info, fileobj = yield utils.fetch_url(url)
        except utils.FetchUrlFailed, fuf:
            raise bot.PollSkipped("failed to download {0!r} ({1})".format(url, fuf))
        self.log.info("Downloaded")

        for line in fileobj:
            url, netloc = parseURL(line)
            if url is None:
                continue
            event = events.Event()
            event.add("url", url)
            if i_am_a_name(netloc):
                event.add("domain name", netloc)
            else:
                event.add("ip", netloc)
            event.add("feed", "vxvault")
            event.add("feed url", self.feed_url)
            event.add("type", "malware")
            event.add("description", "This host is most likely hosting a malware URL.") 
            yield idiokit.send(event)

if __name__ == "__main__":
    VxVaultBot.from_command_line().execute()

