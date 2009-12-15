import os
import re
import sys
import hashlib
import traceback

from idiokit import threado, timer
from abusehelper.core import opts, rules, services

class frozendict(dict):
    def __init__(self, *args, **keys):
        dict.__init__(self, *args, **keys)
        self.frozenset = frozenset(self.items())

    def __hash__(self):
        return hash(self.frozenset)

def split(string, parser=unicode, split_rex=r"[\s,]+"):
    split = re.split(split_rex, string)
    split = filter(None, split)
    return tuple(map(parser, split))

def parse_netblock(string):
    split = string.split("/", 1)
    if len(split) == 1:
        return split[0], 32
    return split[0], int(split[1])

class CustomerDB(object):
    def __init__(self, filename):
        self.filename = os.path.abspath(filename)
        self.was_opened = True
        self.last_mod = None
        self.customers = list()

    def update(self):
        try:
            last_mod = os.path.getmtime(self.filename)
        except OSError, ose:
            last_mod = None

        if last_mod is not None and self.last_mod == last_mod:
            return False
        self.last_mod = last_mod

        try:
            config = opts.ConfigParser(self.filename)
        except IOError, ioe:
            if self.was_opened:
                print >> sys.stderr, "Couldn't open customer file %r" % self.filename
                self.was_opened = False
                self.customers = list()
                return True
            return False

        self.was_opened = True
        self.customers = list()
        for section_name in config.sections():
            self.customers.append(Customer(config, section_name))
        return True

class Customer(object):
    def __init__(self, config, section_name):
        section = dict(config.items(section_name))
        
        try:
            self.asn = int(section.get("info.asn", ""))
        except ValueError:
            self.asn = None
        self.name = section_name
        self.netblocks = split(section.get("info.netblocks", ""), 
                               parse_netblock)

        times = section.get("mail.times", "")
        emails = section.get("mail.addresses", "")
        pgp = section.get("mail.pgp", None)

        self.feeds = dict()
        for feed in split(section.get("feeds", "")):
            feed_template = section.get(feed + ".template", None)
            feed_times = split(section.get(feed + ".times", times))
            feed_emails = split(section.get(feed + ".addresses", emails))

            if not (feed_template and feed_times and feed_emails):
                continue

            feed_pgp = section.get(feed + "pgp", pgp)
            self.feeds[feed] = feed_template, feed_times, feed_emails, feed_pgp

class Config(threado.GeneratorStream):
    def __init__(self, name, lobby, filename, room_prefix, template_dir, 
                 interval=1.0):
        threado.GeneratorStream.__init__(self)

        self.name = name
        self.lobby = lobby
        self.interval = interval
        self.room_prefix = room_prefix
        self.template_dir = os.path.abspath(template_dir)

        self.db = CustomerDB(filename)
        self.confs = dict()

        self.start()

    def load_template(self, name, cache=None):
        if cache is not None and name in cache:
            return cache[name]

        filename = os.path.join(self.template_dir, name)
        opened = open(filename, "rb")
        try:
            data = opened.read()
        finally:
            opened.close()

        if cache is not None:
            cache[name] = data
        return data
        
    def run(self):
        while True:
            if self.db.update():
                confs = frozenset(self.generate_conf())
                for key in confs - set(self.confs):
                    self.confs[key] = self.setup(*key)
                    services.bind(self, self.confs[key])
                for key in set(self.confs) - confs:
                    self.confs.pop(key).throw(threado.Finished())

            yield self.inner, timer.sleep(self.interval)

    def generate_conf(self):
        templates = dict()
        asn_defaults = dict()
        asn_non_defaults = dict()

        for customer in self.db.customers:
            if customer.asn is None:
                continue
            if not customer.netblocks:
                asn_defaults.setdefault(customer.asn, set()).add(customer)
            else:
                asn_non_defaults.setdefault(customer.asn, set()).add(customer)

        for asn in set(asn_defaults) | set(asn_non_defaults):
            defaults = asn_defaults.get(asn, set())
            non_defaults = asn_non_defaults.get(asn, set())

            default_netblocks = set()
            for customer in non_defaults:
                default_netblocks.update(customer.netblocks)

            for customer in defaults | non_defaults:
                rule = rules.CONTAINS(asn=unicode(asn))

                netblocks = customer.netblocks or default_netblocks
                if netblocks:
                    netblock_rules = [rules.NETBLOCK(*x) for x in netblocks]
                    if len(netblock_rules) == 1:
                        netblock_rule = netblock_rules.pop()
                    else:
                        netblock_rule = rules.OR(*netblock_rules)
                    if not customer.netblocks:
                        netblock_rule = rules.NOT(netblock_rule)
                    rule = rules.AND(rule, netblock_rule)

                for feed, (template, times, emails, pgp) in customer.feeds.items():
                    name = hashlib.md5(customer.name).hexdigest()

                    try:
                        template = self.load_template(template, templates)
                    except IOError, ioe:
                        print >> sys.stderr, "Couldn't open template %r" % template
                        continue

                    path = self.name, customer.name, feed
                    asn_room = self.room_prefix + "." + feed + ".asn" + unicode(asn)
                    mail_room = asn_room + "." + name

                    yield "historian", path, frozendict(rooms=(asn_room, mail_room))
                    yield "roomgraph", path, frozendict(src=asn_room,
                                                        dst=mail_room,
                                                        rule=rule)
                    yield "mailer", path, frozendict(to=emails, 
                                                     room=mail_room,
                                                     subject=("Report for ASN" + 
                                                              unicode(asn)),
                                                     template=template,
                                                     times=times)
                    yield feed, path, frozendict(asn=asn, room=asn_room)

    @threado.stream
    def setup(inner, self, service, path, conf):
        while True:
            print "waiting for", repr(service), "session", repr(path)
            session = yield inner.sub(self.lobby.session(service, *path, **conf))
            if session is None:
                break

            print "sent", repr(service), "session", repr(path), "conf:"
            for key, value in conf.iteritems():
                print "", repr(key), "=", repr(value)
                
            try:
                yield inner.sub(session)
            except services.Stop:
                print "lost connection to", repr(service), "session", repr(path)
            else:
                print "ended connection to", repr(service), "session", repr(path)
                break

def main(name, xmpp_jid, service_room, customer_file, template_dir,
         service_name=None, xmpp_password=None, log_file=None):
    import getpass
    from idiokit.xmpp import connect
    from abusehelper.core import log
    
    if not xmpp_password:
        xmpp_password = getpass.getpass("XMPP password: ")

    logger = log.config_logger(name, filename=log_file)

    @threado.stream
    def bot(inner):
        print "Connecting XMPP server with JID", xmpp_jid
        xmpp = yield connect(xmpp_jid, xmpp_password)
        xmpp.core.presence()

        print "Joining lobby", service_room
        lobby = yield services.join_lobby(xmpp, service_room, name)
        logger.addHandler(log.RoomHandler(lobby.room))

        config = Config(name, lobby, customer_file, service_room, template_dir)
        yield inner.sub(lobby | config)
    return bot()
main.customer_file_help = "the customer database file"
main.service_room_help = "the room where the services are collected"
main.xmpp_jid_help = "the XMPP JID (e.g. xmppuser@xmpp.example.com)"
main.asn_room_prefix = "prefix for rooms created for each ASN"
main.xmpp_password_help = "the XMPP password"
main.log_file_help = "log to the given file instead of the console"

if __name__ == "__main__":
    from abusehelper.core import opts
    threado.run(opts.optparse(main))
