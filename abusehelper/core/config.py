import os
import re
import sys
import hashlib

from idiokit import threado, timer
from abusehelper.core import rules, bot, services

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

class CustomerDBError(Exception):
    pass

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
            config = bot.ConfigParser(self.filename)
        except IOError, ioe:
            if self.was_opened:
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

from abusehelper.core import log

class ConfigBot(bot.XMPPBot):
    service_room = bot.Param("the room where the services are collected")
    customer_file = bot.Param("the customer database file")
    template_dir = bot.Param("")

    @threado.stream
    def main(inner, self, interval=1.0):
        xmpp = yield inner.sub(self.xmpp_connect())

        self.log.info("Joining lobby %r", self.service_room)
        lobby = yield inner.sub(services.join_lobby(xmpp, 
                                                    self.service_room,
                                                    self.bot_name))
        self.log.addHandler(log.RoomHandler(lobby.room))

        confs = dict()
        db = CustomerDB(self.customer_file)

        try:
            while True:
                if db.update():
                    new_confs = frozenset(self.generate_conf(db, self.service_room))
                    for key in new_confs - set(confs):
                        confs[key] = self.setup(lobby, *key)
                    for key in set(confs) - new_confs:
                        confs.pop(key).throw(threado.Finished())

                yield inner, timer.sleep(interval)
        finally:
            for setup in confs.values():
                setup.throw(threado.Finished())

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
        
    def generate_conf(self, db, room_prefix):
        templates = dict()
        asn_defaults = dict()
        asn_non_defaults = dict()

        for customer in db.customers:
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
                        self.log.error("Couldn't open template %r", template)
                        continue

                    path = self.bot_name, customer.name, feed
                    asn_room = room_prefix + "." + feed + ".as" + unicode(asn)
                    mail_room = asn_room + "." + name

                    yield "historian", path, frozendict(rooms=(asn_room, mail_room))
                    yield "roomgraph", path, frozendict(src=asn_room,
                                                        dst=mail_room,
                                                        rule=rule)
                    yield "mailer", path, frozendict(to=emails, 
                                                     room=mail_room,
                                                     subject=("Report for AS" + 
                                                              unicode(asn)),
                                                     template=template,
                                                     times=times)
                    yield feed, path, frozendict(asn=asn, room=asn_room)

    @threado.stream
    def setup(inner, self, lobby, service, path, conf):
        while True:
            self.log.info("Waiting for %r session %r", service, path)
            session = yield inner.sub(lobby.session(service, *path, **conf))
            if session is None:
                break

            conf_str = "\n".join(" %r=%r" % item for item in conf.items())
            self.log.info("Sent %r session %r conf:\n%s", service, path, conf_str)
                
            try:
                yield inner.sub(session)
            except services.Stop:
                self.log.info("Lost connection to %r session %r", service, path)
            else:
                self.log.info("Ended connection to %r session %r", service, path)
                break

if __name__ == "__main__":
    ConfigBot.from_command_line().run()
