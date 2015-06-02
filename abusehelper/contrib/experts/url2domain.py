"""
A simple expert to parse a domain name from a URL.

Maintainer: "Juhani Eronen" <exec@iki.fi>


Important notice:

This bot is deprecated and will not be maintained. Maintained
version will be moved under ahcommunity repository. 

abusehelper.contrib package will be removed after 2016-01-01.
During the migration period, you can already update your 
references to the bot.
"""

import socket
import idiokit
from abusehelper.core import events
from abusehelper.contrib.urllistmailbot.urllistmailbot import get_hosts
from abusehelper.contrib.experts.combiner import Expert


def is_ipv4(ip):
    try:
        socket.inet_aton(ip)
    except (ValueError, socket.error):
        return False
    return True


def is_ipv6(ip):
    if socket.has_ipv6:
        try:
            socket.inet_pton(socket.AF_INET6, ip)
        except(ValueError, socket.error):
            return False
        return True
    else:
        return False


class URL2DomainExpert(Expert):

    def __init__(self, *args, **keys):
        Expert.__init__(self, *args, **keys)
        self.log.error("This bot is deprecated. It will move permanently under ahcommunity repository after 2016-01-01. Please update your references to the bot.")

    def augment_keys(self, *args, **keys):
        yield (keys.get("resolve", ("url",)))

    def domaingrab(self, event, key):
        for _, host in get_hosts(event.values(key)):
            augmentation = events.Event()
            if is_ipv4(host) or is_ipv6(host):
                augmentation.add("ip", host)
            else:
                augmentation.add("host", host)
            yield augmentation

    @idiokit.stream
    def augment(self, url_key):
        while True:
            eid, event = yield idiokit.next()
            for augmentation in self.domaingrab(event, url_key):
                yield idiokit.send(eid, augmentation)

if __name__ == "__main__":
    URL2DomainExpert.from_command_line().execute()
