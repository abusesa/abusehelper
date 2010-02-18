from abusehelper.core import rules
from abusehelper.core.config import *
from abusehelper.core.runtime import *

def parse_netblock(string):
    split = string.split("/", 1)
    if len(split) == 1:
        return split[0], 32
    return split[0], int(split[1])

def netblock_rule(parsed_netblocks):
    return rules.OR(*[rules.NETBLOCK(*x) for x in parsed_netblocks])

def configs():
    customers = [x for x in default_configs(globals()) if isinstance(x, Customer)]
    netblocks = dict()

    for customer in customers:
        if customer.netblocks:
            parsed = map(parse_netblock, customer.netblocks)
            netblocks.setdefault(customer.asn, set()).update(parsed)

    for customer in customers:
        rule = rules.CONTAINS(asn=str(customer.asn))

        if customer.netblocks:
            rule = rules.AND(rule,
                             netblock_rule(map(parse_netblock, customer.netblocks)))
        elif customer.asn not in netblocks:
            pass
        else:
            rule = rules.AND(rule, rules.NOT(netblock_rule(netblocks[customer.asn])))

        customer.filter_rule = rule
        yield customer

dshield_template = """
# This is a mail that is based on the DShield template.

# Here is the data:
%(attach_and_embed_csv, report.csv, |, asn, ip, timestamp=%(updated)s, ptr=, cc=, type=scanners, ticket=0, info=firstseen: %(firstseen)s lastseen: %(lastseen)s)s

# Regards,
# Generic Abuse Handling Organization
"""

class Customer(Runtime):
    room_prefix = ""
    filter_rule = rules.CONTAINS()

    # AS info
    asn = None
    netblocks = []

    # Mailer options
    to = []
    cc = []
    subject = dynamic("Report for AS%(asn)s")
    template = dshield_template
    times = ["08:00"]
    
    @dynamic
    def dshield(self):
        return (Session("dshield", asns=[self.asn])
                | Room("%(room_prefix)sasn%(asn)s")
                | Session("roomgraph", rule=self.filter_rule)
                | Room("%(room_prefix)scustomer.%(name)s")
                | Session("mailer",
                          "customer", "%(name)s",
                          to=self.to,
                          cc=self.cc,
                          times=self.times,
                          template=self.template,
                          subject=self.subject))

customer1 = Customer(asn=123)
customer2 = Customer(asn=123, netblocks=["128.0.0.0/1"])
