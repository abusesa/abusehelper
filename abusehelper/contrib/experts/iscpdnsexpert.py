"""
Looks up results from the ISC Passive DNS service.
https://sie.isc.org/wiki/Passive_DNS

Maintainer: "Juhani Eronen" <exec@iki.fi>
"""
import re
import idiokit
import urllib2
import simplejson as json

from abusehelper.core import bot, events
from abusehelper.contrib.experts.combiner import Expert
import abusehelper.core.utils as utils

FORMAT = "%Y-%m-%d %H:%M:%SZ"

from time import strftime, gmtime

"""
Important notice:

This bot is deprecated and will not be maintained. Maintained
version will be moved under ahcommunity repository. 

abusehelper.contrib package will be removed after 2016-01-01.
During the migration period, you can already update your 
references to the bot.
"""

def ipv4_addr_reverse(ipv4):
    return '.'.join(reversed(ipv4.split('.')[:4]))

def ipv6_addr_reverse(ipv6):
    ipv6 = ipv6.rstrip('.')
    if ipv6.endswith('.ip6.arpa'):
        ipv6 = ipv6.split('.ip6.arpa')[0]
    ipv6 = ipv6.replace('.', '')
    ipv6 = ''.join(reversed(ipv6))
    return ':'.join(re.findall('(....)', ''.join(ipv6)))

class ISCPDNSExpert(Expert):
    server = bot.Param("Passive DNS server URL",
                       default="https://api.dnsdb.info")
    apikey = bot.Param("Service API key")

    def __init__(self, *args, **keys):
        cache_time = keys.get('cache_time', 3600.0)
        Expert.__init__(self, *args, **keys)
        self.cache = utils.TimedCache(cache_time)
        self.log.error("This bot is deprecated. It will move permanently under ahcommunity repository after 2016-01-01. Please update your references to the bot.")

    def json_to_event(self, event, name, typ='host'):
        pred = event.get('rrtype', '').lower()
        subj = event.get('rrname', '').lower()

        # A/AAAA responses
        if pred in ['a', 'aaaa']:
            # Handle IP queries
            if typ == 'ip':
                pred = 'host'
                if not ',' in name:
                    subj, name = name, subj
                else:
                    # IP network ranges
                    name = subj
                    subj = event.get('rdata', '').lower()
            # Host queries
            else:
                pred = 'ip'

        # NS responses, implementation derived from examples
        elif pred == 'ns':
            if subj.endswith('arpa.'):
                typ = 'ip'
                if subj.endswith("in-addr.arpa."):
                    subj = ipv4_addr_reverse(subj)
                    if '-' in subj:
                        typ = 'network'
                        subj = subj.replace('-', '/')
                else:
                    subj = ipv6_addr_reverse(subj)

        # PTR responses
        elif pred == 'ptr':
            pred = 'ptr'
            typ = 'ip'
            if subj.endswith("in-addr.arpa."):
                subj = ipv4_addr_reverse(subj)
            else:
                subj = ipv6_addr_reverse(subj)

        # MX responses
        elif pred == 'mx':
            pred = 'mx'
            typ = 'host'
            name = event.get('rdata', '').lower().split()[-1]

        # No reply
        if not (pred and subj):
            return events.Event()
        subj = subj.rstrip('.')
        new = events.Event({pred: name})
        new.add(typ, subj)
        cnt = event.get('count', '')
        lastseen = event.get('time_last', '')
        if cnt:
            new.add('count', str(cnt))
        if lastseen:
            new.add('last seen', strftime(FORMAT, gmtime(lastseen)))
        return new

    def augment_keys(self, *args, **keys):
        yield (keys.get("resolve", ("host",)))

    @idiokit.stream
    def augment(self, *keys):
        while True:
            eid, event = yield idiokit.next()

            for key in keys:
                qkey = key
                if qkey != 'ip':
                    qkey = 'name'

                for item in event.values(key):
                    # Network ranges
                    if key in ['ip', 'network'] and '/' in item:
                        item = item.replace('/', ',')

                    data = self.cache.get(item, None)

                    if not data:
                        url = "%s/lookup/rdata/%s/%s" % (self.server, 
                                                         qkey, item)
                        req = urllib2.Request(url)
                        req.add_header('Accept', 'application/json')
                        req.add_header('X-Api-Key', self.apikey)

                        try:
                            info, fileobj = yield utils.fetch_url(req)
                            data = fileobj.read()
                            self.cache.set(item, data)
                            fileobj.close()
                        except utils.HTTPError as he:
                            self.log.info("%r", he)
                            data = ''

                    for line in data.split('\n'):
                        line = line.strip()
                        if not line:
                            continue
                        report = json.loads(line)
                        new = self.json_to_event(report, item, qkey)

                        if new:
                            yield idiokit.send(eid, new)

if __name__ == "__main__":
    ISCPDNSExpert.from_command_line().execute()
