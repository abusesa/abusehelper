"""
Generic feed handler for lists of IPv4/6 addresses and netblocks.

Maintainer: Jussi Eronen <exec@iki.fi>


Important notice:

This bot is deprecated and will not be maintained. Maintained
version will be moved under ahcommunity repository. 

abusehelper.contrib package will be removed after 2016-01-01.
During the migration period, you can already update your 
references to the bot.
"""

import re
import socket
import idiokit
from abusehelper.core import utils, cymruwhois, bot, events

rex = re.compile(r"((?:[\d\.]|[a-z\d\:])+)(?:/(\d+))?", re.I)

def as_ip(string):
    for addr_type in (socket.AF_INET, socket.AF_INET6):
        try:
            value = socket.inet_pton(addr_type, string)
        except (ValueError, socket.error):
            pass
        else:
            return socket.inet_ntop(addr_type, value)
    return None

class IPListBot(bot.PollingBot):
    url = bot.Param("IP list URL")
    source = bot.Param("source name", default=None)
    use_cymru_whois = bot.BoolParam()

    def __init__(self, *args, **keys):
        bot.PollingBot.__init__(self, *args, **keys)
        self.log.error("This bot is deprecated. It will move permanently under ahcommunity repository after 2016-01-01. Please update your references to the bot.")

    def poll(self):
        if self.use_cymru_whois:
            return self._poll() | cymruwhois.augment("ip")
        return self._poll()

    @idiokit.stream
    def _poll(self):
        self.log.info("Downloading %s" % self.url)
        try:
            info, fileobj = yield utils.fetch_url(self.url)
        except utils.FetchUrlFailed, fuf:
            self.log.error("Download failed: %r", fuf)
            return
        self.log.info("Downloaded")

        for line in fileobj:
            for candidate in rex.finditer(line):
                ip, netblock = candidate.groups()
                ip = as_ip(ip)
                if ip is None:
                    continue

                new = events.Event()
                new.add("ip", ip)
                if netblock:
                    new.add("netblock", netblock)
                new.add("url", self.url)
                if self.source:
                    new.add("source", self.source)
                yield idiokit.send(new)

if __name__ == "__main__":
    IPListBot.from_command_line().execute()
