#! /usr/bin/env python
# -*- coding: latin-1 -*-
"""
    Scraper for CVE vuln feed

    @copyright: 2009 Erno Kuusela
    @license: GPLv2
"""

import xml.etree.cElementTree as ET
from collections import defaultdict
import shelve

from abusehelper.thirdparty.couchbot import events_to_couchdb
from idiokit import threado, util
from abusehelper.core import events

def gen_text(obj):
    return obj.text.replace('\n', '').replace('\t', '').replace('\r', '')

@threado.stream
def parse_nvd_data(inner, fob):
    tree = ET.parse(fob)

    for entry in tree.getroot().getchildren():
        inner.send(entry)
        yield

@threado.stream
def do_nvd_entry(inner):
    while True:
        e = yield inner

        m = events.Event()
        m.add('feedsource', 'nvd')
        m.add('feedtype', 'Vulnerability')
        cveid = e.get('id')
        m._id = cveid

        for s in 'published-datetime', 'last-modified-datetime', 'security-protection', 'summary', 'severity':
            try:
                x = e.find('{http://scap.nist.gov/schema/vulnerability/0.4}' + s)
                m.add(s, gen_text(x))
                #print s, x.encode('ascii', 'replace')
            except AttributeError:
                pass

        try:
            vs = e.find('{http://scap.nist.gov/schema/vulnerability/0.4}vulnerable-software-list')
            if not vs:
                vs = []
        except AttributeError:
            vs = []

        for s in vs:
            m.add('vulnerable-software', gen_text(s))

        try:
            refs = e.findall('{http://scap.nist.gov/schema/vulnerability/0.4}references')
        except AttributeError:
            refs = []

        for r in refs:
            m.add(gen_text(r[0]), r[1].get('href'))

        metric = lambda x: e.find('{http://scap.nist.gov/schema/vulnerability/0.4}cvss').find('{http://scap.nist.gov/schema/cvss-v2/0.2}base_metrics').find('{http://scap.nist.gov/schema/cvss-v2/0.2}' + x)

        for mn in 'score', 'access-vector', 'access-complexity', 'availability-impact', 'confidentiality-impact', 'integrity-impact':
            try:
                z =  metric(mn)
                #print 'cvss-'+mn, z
            except AttributeError:
                pass
            else:
                m.add('cvss-' + mn, gen_text(z))

        try:
            cweid = e.find('{http://scap.nist.gov/schema/vulnerability/0.4}cwe').get("id")
        except AttributeError:
            pass
        else:
            if cweid:
                m.add("cwe-id", cweid)

        inner.send(m)

def main():
    
    for _ in parse_nvd_data(open('nvdcve-2.0-2009.xml')) | do_nvd_entry() | events_to_couchdb("http://localhost:5984", "vulndata"):
        pass

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print "Script interrupted via CTRL-C."

