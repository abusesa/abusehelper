"""
Handles the abuse.ch AMaDa service

Maintainer: Jussi Eronen <exec@iki.fi>
"""

import socket
import idiokit
from idiokit import threadpool
from abusehelper.core import bot, cymruwhois, utils, events

class AmadaBot(bot.PollingBot):
    url = bot.Param()
    use_cymru_whois = bot.BoolParam(default=True)

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
            idiokit.stop()
        self.log.info("Downloaded")

        for line in (x for x in fileobj if not x.startswith("#")):
            pieces = line.split()
            if len(pieces) != 3:
                continue

            host, _, malware = pieces
            try:
                addrinfo = yield threadpool.thread(socket.getaddrinfo, host, None)
            except socket.error, error:
                self.log.info("Could not resolve host %r: %r", host, error)
                continue

            ips = set()
            for family, _, _, _, sockaddr in addrinfo:
                if family not in (socket.AF_INET, socket.AF_INET6):
                    continue
                ips.add(sockaddr[0])

            for ip in ips:
                new = events.Event()

                new.add("ip", ip)
                if host not in ips:
                    new.add("domain", host)
                new.add("url", self.url)
                new.add("cc type", malware)

                yield idiokit.send(new)

if __name__ == "__main__":
    AmadaBot.from_command_line().execute()
