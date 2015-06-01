"""
An expert to work as a Cymru whois service from a Quagga router.

Optionally, you can download IANA address space assignments and asnames,
and give their filesystem parts as parameters

http://www.iana.org/assignments/ipv4-address-space/ipv4-address-space.csv
http://bgp.potaroo.net/as2.0/asnames.txt

FIXME: IPv6 support.
FIXME: Does not include data about allocation date on more
fine-grained subnets due to a lack of known good data feeds on this.

Maintainer: "Juhani Eronen" <exec@iki.fi>
"""
import struct
import sys
import socket
import csv

from subprocess import Popen, PIPE, STDOUT

import idiokit

from abusehelper.core import bot, events, utils
from abusehelper.contrib.experts.bgpexpert import BgpBaseExpert

def run_command(cmd):
    p = Popen(cmd, stdout=PIPE, stderr=STDOUT,
              shell=True, close_fds=True)
    return p.stdout.read(), p.returncode

class BgpQuaggaExpert(BgpBaseExpert):
    def __init__(self, *args, **keys):
        BgpBaseExpert.__init__(self, *args, **keys)

    def make_result(self, result):
        augmentation = events.Event()
        for route in result:
            augmentation.update('asn', result[route]['asn'])
            augmentation.add('bgp prefix', route)
            for asn in result[route]['asn']:
                asname = self.asnamedata.get(asn, ('', ''))
                if asname[0]:
                    augmentation.add('as name', asname[0])
                if asname[1]:
                    augmentation.add('cc', asname[1])
            if result[route].get('date', ''):
                augmentation.add('allocated', 
                                 result[route]['date'])
            if result[route].get('reg', ''):
                augmentation.add('registry', 
                                 result[route]['reg'])
        return augmentation

    def parse_bgpquery(self, data):
        paths = set()
        ipasns = set()
        lines = data.split('\n')

        head, lines = lines[0], lines[1:]
        cidr = head.split()[-1]
        ipasns.add(cidr)

        for line in lines:
            if not len(line) > 2:
                continue

            spaces, path = line[:2], line[2:]
            if not path[0].isdigit():
                continue

            paths.add((cidr, path))
            ipasns.update('AS%s' % x for x in path.split())

        return paths, ipasns

    @idiokit.stream
    def _run_command(self, cmd, *args):
        out, s = yield idiokit.thread(run_command, cmd % args)
        if s:
            self.log.error(out)
            raise Continue()
        idiokit.stop(out)

    @idiokit.stream
    def lookup(self, query):
        try:
            q = query.split('/')
        
            ip_num, = struct.unpack("!I", socket.inet_aton(q[0]))
            if len(q) > 2:
                raise ValueError('Too many parts')
            elif len(q) == 2:
                int(q[1])
        except (socket.error, ValueError):
            self.log.info("Not a valid ip/cidr: %r", query)
            idiokit.stop()

        data = yield self._run_command('vtysh -c "sh ip bgp %s"', (query))

        paths, ipasns = self.parse_bgpquery(data)
        result = dict()
        for ip in ipasns:
            if not '.' in ip:
                continue
            result.setdefault(ip, dict())

            ip_num, = struct.unpack("!I", socket.inet_aton(ip.split('/')[0]))

            for topblock in self.assign_data:
                start, end = topblock
                if start < ip_num < end:
                    date, reg = self.assign_data[topblock]
                    result[ip]['date'] = date
                    result[ip]['reg'] = reg
                    break

        for cidr, path in paths:
            path = path.split()
            result[cidr].setdefault('asn', set()).add(path[-1])
        idiokit.stop(self.make_result(result))

    @idiokit.stream
    def augment(self):
        while True:
            eid, event = yield idiokit.next()

            for ip in event.values(self.ip_key):
                augmentation = yield self.lookup(ip)
                yield idiokit.send(eid, augmentation)

if __name__ == "__main__":
    BgpQuaggaExpert.from_command_line().execute()
