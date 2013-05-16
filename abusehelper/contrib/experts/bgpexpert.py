"""
An expert to perform offline Cymru whois service from offline files,
for situations where whois server access is not available. 

The bot assumes the following files to be given to it as parameters:

http://bgp.potaroo.net/as2.0/asnames.txt
http://bgp.potaroo.net/as2.0/bgptable.txt

FIXME: Uses a lot of memory as it stores the routing table in-memory.
FIXME: Lookups are far from optimal.
FIXME: IPv6 support.
FIXME: Does not include data on country code or allocation date due to
a lack of known good data feeds on this.
FIXME: Could include registrar data from 
http://www.iana.org/assignments/ipv4-address-space/ipv4-address-space.txt

Maintainer: "Juhani Eronen" <exec@iki.fi>
"""
import struct
import sys
import socket

import idiokit

from abusehelper.core import bot, events, utils
from abusehelper.contrib.experts.combiner import Expert

class SubnetException(Exception):
    pass

class BgpExpert(Expert):
    bgptable = bot.Param("Path to bgptable.txt", default="bgptable.txt")
    asnames = bot.Param("Path to asnames.txt", default="asnames.txt")
    allroutes = bot.BoolParam("Give all routes instead of the most specific")
    ip_key = bot.Param("key which has IP address as value " +
                       "(default: %default)", default="ip")

    def __init__(self, *args, **keys):
        Expert.__init__(self, *args, **keys)
        self.initialize()

    def subnets(self, ip, original_bits):
        if not 0 <= original_bits <= 32:
            raise SubnetException, "subnet not correct: %r" % (original_bits)

        ip_num, = struct.unpack("!I", socket.inet_aton(ip))

        ip_start = ip_num & (((1 << 32) - 1) ^ \
                                 ((1 << (32-original_bits)) - 1))
        ip_end = ip_start + (1 << (32 - original_bits))

        return ip_start, ip_end

    def make_subnet(self, subnet):
        subnet, mask = subnet.split('/')
        try:
            mask = int(mask)
        except ValueError:
            raise SubnetException, "subnet not correct: %r" % (mask)

        return self.subnets(subnet, mask)

    def in_subnet(self, ip, subnet):
        ip_num, = struct.unpack("!I", socket.inet_aton(ip))
        start, end = self.make_subnet(subnet)
        return start < ip_num < end

    def initialize(self):
        data = file(self.asnames, 'r')
        self.asnames = dict()

        for line in data.xreadlines():
            asn = line.split()[0].lstrip('AS')
            self.asnames[asn] = ' '.join(line.split()[1:])

        self.routes = dict()

        data = file(self.bgptable, 'r')

        for line in data.xreadlines():
            if not line.startswith('*'):
                continue
            line = line.split()
            if not '/' in line[1]:
                mask = line[1].count('.0')
                if not mask in [1,2,3]:
                    continue
                if mask == 1: line[1] = line[1] + '/24'
                elif mask == 2: line[1] = line[1] + '/16'
                elif mask == 3: line[1] = line[1] + '/8'
            if len(line) < 5:
                continue
            try:
                self.routes.setdefault(
                    self.make_subnet(line[1]), set()).add((line[1], line[-2]))
            except:
                self.log.info("Illegal route: %r", (line))
                pass

    def make_result(self, result):
        augmentation = events.Event()
        asn, route, asname = result
        augmentation.add('asn', asn)
        augmentation.add('bgp prefix', route)
        augmentation.add('as name', asname)
        return augmentation

    def lookup(self, event):
        for ip in event.values(self.ip_key):
            try:
                ip_num, = struct.unpack("!I", socket.inet_aton(ip))
            except socket.error:
                sys.log.info("Illegal IP address: %r", ip)
                continue

            results = list()
            smallest = (0, 0)
            for route in self.routes:
                start, end = route
                if start < ip_num < end:
                    route, asn = list(self.routes[route])[0]
                    asname = self.asnames[asn]
                    results.append((asn, route, asname))
                    mask = int(route.split('/')[1])
                    if mask > smallest[0]:
                        smallest = (mask, len(results)-1)

            if not results:
                self.log.info("Route not found: %r", ip)
            if self.allroutes:
                for result in results:
                    yield self.make_result(result)
            else:
                if not results:
                    return
                else:
                    yield self.make_result(results[smallest[1]])

    @idiokit.stream
    def augment(self):
        while True:
            eid, event = yield idiokit.next()

            for augmentation in self.lookup(event):
                yield idiokit.send(eid, augmentation)

if __name__ == "__main__":
    BgpExpert.from_command_line().execute()
