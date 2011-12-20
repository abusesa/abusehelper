# -*- coding: utf-8 -*-
"""
    Handles the abuse.ch AMaDa service
"""
__authors__ = "Jussi Eronen"
__copyright__ = "Copyright 2011, The AbuseHelper Project"
__license__ = "MIT <http://www.opensource.org/licenses/mit-license.php>"
__maintainer__ = "Jussi Eronen"
__email__ = "exec@iki.fi"

import socket
import idiokit
from idiokit import threadpool

from abusehelper.core import utils, cymru, bot, events
from abusehelper.contrib.iplist.iplist import IPListBot

class AmadaBot(IPListBot):
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
            if line.startswith('#'):
                continue
            line = line.split(' # ')
            if not len(line) == 2:
                continue

            host, malware = line
            ips = set()
            if not host.replace('.', '').isdigit():
                try:
                    addrinfo = yield threadpool.thread(socket.getaddrinfo, 
                                                       host, None)
                except socket.error, error:
                    self.log.info("Could not resolve host %r: %r", host, error)
                    continue

                for family, _, _, _, sockaddr in addrinfo:
                    if family not in (socket.AF_INET, socket.AF_INET6):
                        continue
                    ips.add(sockaddr[0])
            else:
                ips.add(host)
                host = ''

            for ip in ips:
                new = events.Event()

                new.add('ip', ip)
                if host:
                    new.add('domain', host)
                new.add('url', self.url)
                new.add('Cc type', malware)

                yield idiokit.send(new)

if __name__ == "__main__":
    AmadaBot.from_command_line().execute()
