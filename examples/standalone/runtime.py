import re
import socket
from abusehelper.core import rules
from abusehelper.core.config import *
from abusehelper.core.runtime import *

startup = load_module("startup")

class Base(Config):
    prefix = startup.Bot.service_room

    @classmethod
    def class_name(cls):
        return cls.__name__.lower()
    
    @classmethod
    def class_room(cls):
        return Room(cls.prefix+"."+cls.class_name()+"s")

    def room(self):
        return Room(self.prefix+"."+self.class_name()+"."+self.name)

    # The session pipes yielded here are collected and then run.
    def runtime(self):
        yield self.room() | Session("historian")
        for item in self.main():
            yield item

    def main(self):
        return []

class Source(Base):
    def main(self):
        # Harvest the instance attributes that the class (Source)
        # doesn't already have.
        attrs = dict(self.member_diff())
        attrs.pop("name", None)

        yield (Session(self.name, **attrs) 
               | self.room() 
               | Session(self.name + ".sanitizer")
               | self.class_room())

class Type(Base):
    def main(self):
        rule = rules.CONTAINS(type=self.name)
        yield (Source.class_room() 
               | Session("roomgraph", rule=rule) 
               | self.room() 
               | self.class_room())

def parse_netblock(netblock):
    split = netblock.split("/", 1)
    ip = split[0]

    try:
        socket.inet_pton(socket.AF_INET, ip)
    except socket.error:
        try:
            socket.inet_pton(socket.AF_INET6, ip)
        except socket.error:
            raise ValueError("not a valid IP address %r" % ip)
        bits = 128
    else:
        bits = 32

    if len(split) == 2:
        bits = int(split[1])
    return rules.NETBLOCK(ip, bits)

def parse_asn_netblock(item):
    string = str(item)

    plus_asn = list()
    minus_asn = list()
    plus_netblock = list()
    minus_netblock = list()

    rex = re.compile("^\s*([+-])?\s*([^-+\s]+)\s*")
    while string:
        match = rex.search(string)
        if not match:
            raise ValueError("invalid asn/netblock rule %r" % item)

        prefix, data = match.groups()
        string = string[match.end():]

        if data.isdigit():
            rule = rules.CONTAINS(asn=str(int(data)))
            if prefix == "-":
                minus_asn.append(rule)
            else:
                plus_asn.append(rule)
        else:
            rule = parse_netblock(data)
            if prefix == "-":
                minus_netblock.append(rule)
            else:
                plus_netblock.append(rule)

    total = list()
    if plus_asn:
        total.append(rules.OR(*plus_asn))
    if minus_asn:
        total.append(rules.NOT(rules.OR(*minus_asn)))
    if plus_netblock:
        total.append(rules.OR(*plus_netblock))
    if minus_netblock:
        total.append(rules.NOT(rules.OR(*minus_netblock)))

    if not total:
        raise ValueError("empty asn/netblock rule")
    return rules.AND(*total)

template_cache = dict()

def load_template(name):
    if name not in template_cache:
        template_file = open(startup.locate("template", name))
        try:
            template_cache[name] = template_file.read()
        finally:
            template_file.close()
    return template_cache[name]

def wiki(customer):
    return Session("wikibot", 
                   "%(prefix)s", "%(name)s",
                   wiki_url=customer.wiki_url, 
                   wiki_user=customer.wiki_user, 
                   wiki_password=customer.wiki_password,
                   wiki_type=customer.wiki_type,
                   parent=customer.wiki_parent)

def mail(customer):
    template = load_template(customer.mail_template)
    return Session("mailer",
                   "%(prefix)s", "%(name)s",
                   to=customer.mail_to, 
                   cc=customer.mail_cc, 
                   template=template,
                   times=customer.mail_times)

class Customer(Base):
    asns = [] # Default: no asns
    types = None # Default: all types
    reports = [] # Default: no reporting

    wiki_url = "https://wiki.example.com"
    wiki_user = "wikiuser"
    wiki_password = "wikipassword"
    wiki_type = "opencollab"
    wiki_parent = dynamic("%(name)s")

    mail_to = []
    mail_cc = []
    mail_template = "default"
    mail_times = ["08:00"]

    def main(self):
        if self.asns:
            asns = map(parse_asn_netblock, self.asns)
            if asns:
                rule = rules.OR(*asns)

                if self.types is None:
                    yield (Type.class_room() 
                           | Session("roomgraph", rule=rule) 
                           | self.room())
                else:
                    for type in self.types:
                        yield (Type(name=type).room() 
                               | Session("roomgraph", rule=rule) 
                               | self.room())

        for report in self.reports:
            yield self.room() | report(self)

# Source definitions

dshield = Source(asns=[1, 2, 3])
ircfeed = Source()

# Type definitions

malware = Type()
spam = Type()
unknown = Type()

# Customer definitions

unknown_to_mail = Customer(asns=["3 +127.0.0.1/16"],
                           reports=[mail, wiki], 
                           types=["unknown"])
all_to_wiki = Customer(asns=[1, 2, 3], 
                       reports=[wiki])
