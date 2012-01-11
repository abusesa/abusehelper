# -*- coding: utf-8 -*-
"""
    Generic feed handler for lists of IPv4 addresses and netblocks. TODO: IPv6!
"""
__authors__ = "Jussi Eronen"
__copyright__ = "Copyright 2011, The AbuseHelper Project"
__license__ = "MIT <http://www.opensource.org/licenses/mit-license.php>"
__maintainer__ = "Jussi Eronen"
__email__ = "exec@iki.fi"

import re
import socket
import idiokit
from abusehelper.core import utils, cymru, bot, events

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

    def poll(self, _):
        if self.use_cymru_whois:
            return self._poll() | cymru.CymruWhois()
        return self._poll()

    @idiokit.stream
    def _poll(self):
        self.log.info("Downloading %s" % self.url)
        try:
            info, fileobj = yield utils.fetch_url(self.url)
        except utils.FetchUrlFailed, fuf:
            self.log.error("Download failed: %r", fuf)
            idiokit.stop(False)
        self.log.info("Downloaded")

        for line in fileobj:
            for candidate in rex.finditer(line):
                ip, netblock = candidate.groups()
                ip = as_ip(ip)
                if ip is None:
                    continue

                new = events.Event()
                new.add("ip", ip)
                new.add("netblock", netblock)
                new.add("url", self.url)
                if self.source:
                    new.add("source", self.source)
                yield idiokit.send(new)

if __name__ == "__main__":
    IPListBot.from_command_line().execute()
