import re
import socket
import opencollab.wiki

from idiokit import threado, timer
from abusehelper.core import bot, rules, events
from abusehelper.core.runtime import RuntimeBot, Room, Session

room_prefix = ""

sources_room = Room(room_prefix + "sources")

def raw_room(name):
    return Room(room_prefix + "raw." + name)

def sanitized_room(name):
    return Room(room_prefix + "sanitized." + name)

def customer_room(customer):
    return Room(room_prefix + "customer." + customer)

def fallback_room(name):
    return Room(room_prefix + "fallback." + name)

def parse_asn(string):
    try:
        return unicode(int(string))
    except ValueError:
        return None

def map_asn(asn):
    return rules.MATCH(u"asn", unicode(int(asn)))

def map_netblock(netblock):
    split = netblock.split("/", 1)
    ip = split[0]

    try:
        socket.inet_pton(socket.AF_INET, ip)
    except socket.error:
        try:
            socket.inet_pton(socket.AF_INET6, ip)
        except socket.error:
            return None
        bits = 128
    else:
        bits = 32

    if len(split) == 2:
        try:
            bits = int(split[1])
        except ValueError:
            return None
    return rules.NETBLOCK(ip, bits)

def map_alias_rule((alias, ruleset)):
    return rules.AND(rules.MATCH("feed", alias),
                     combine_rules(rules.OR, ruleset))

def filter_value(string):
    return string.strip() not in ("", "-")

def filter_email(string):
    return "@" in string

def combine_rules(base, ruleset):
    if not ruleset:
        return None
    if len(ruleset) == 1:
        return list(ruleset)[0]
    return base(*ruleset)

class Source(object):
    def __init__(self, wiki_name, bot_name, alias, **attrs):
        self.wiki_name = wiki_name
        self.bot_name = bot_name
        self.alias = alias
        self.attrs = attrs

    def __iter__(self):
        yield (Session(self.bot_name, **self.attrs)
               | raw_room(self.alias)
               | Session(self.bot_name + ".sanitizer")
               | sanitized_room(self.alias)
               | sources_room)
        yield raw_room(self.alias) | Session("archive")
        yield sanitized_room(self.alias) | Session("archive")

class Customer(object):
    mail_to = []
    mail_cc = []
    mail_times = [5*3600]

    def __init__(self, name, template, rule, **attrs):
        self.name = name
        self.template = template
        self.rule = rule

        for key, value in attrs.items():
            setattr(self, key, value)

    def __iter__(self):
        template = "Subject: AbuseHelper report for " + self.name + "\n\n"
        template += self.template

        yield (sources_room
               | Session("roomgraph", rule=self.rule)
               | customer_room(self.name)
               | Session("mailer",
                         self.name,
                         to=self.mail_to,
                         cc=self.mail_cc,
                         template=template,
                         times=self.mail_times))
        yield customer_room(self.name) | Session("archive")

class Fallback(object):
    def __init__(self, name, rule=None):
        self.name = name
        self.rule = rule
        self.customer_rules = None

    def set_customer_rules(self, customer_rules):
        self.customer_rules = customer_rules

    def __iter__(self):
        ruleset = list()
        if self.customer_rules:
            ruleset.append(rules.NOT(combine_rules(rules.OR,
                                                   self.customer_rules)))
        if self.rule is not None:
            ruleset.append(self.rule)
        rule = combine_rules(rules.AND, ruleset)

        yield (sources_room
               | Session("roomgraph", rule=rule)
               | fallback_room(self.name))

class WikiRuntimeBot(RuntimeBot):
    url = bot.Param("wiki url")
    user = bot.Param("wiki user")
    password = bot.Param("wiki password")
    category = bot.Param("page category")
    mail_template = bot.Param("default mail template (%default)",
                              default="DefaultMailTemplate")
    poll_interval = bot.IntParam("how often (in seconds) the "+
                                 "configuration wiki is checked "+
                                 "for updates (default: %default)",
                                 default=60)

    def __init__(self, *args, **keys):
        RuntimeBot.__init__(self, *args, **keys)
        self.wiki = None
        self.template_cache = dict()

    def connect(self):
        try:
            self.wiki = opencollab.wiki.GraphingWiki(self.url)
        except socket.error, e:
            self.log.error("Failed connecting to %s" % self.url)

        try:
            success = self.wiki.authenticate(self.user, self.password)
        except opencollab.wiki.WikiFailure, e:
            self.log.error("Invalid path to wiki: %s" % self.url)
            raise opencollab.wiki.WikiFailure, e

        if not success:
            self.log.error("Failed to authenticate.")
            raise opencollab.wiki.HttpAuthenticationFailed

    def get_pages(self, category):
        try:
            pages = self.wiki.getMeta(category)
        except Exception:
            self.wiki = None

            self.log.info("Trying to reconnect to wiki")
            try:
                self.connect()
            except Exception, e:
                self.log.info("Could not reconnect to wiki: %r" % e)
                return dict()

            try:
                pages = self.wiki.getMeta(category)
            except Exception, e:
                self.log.info("Failed to get category %s: %r" % category, e)
                return dict()

        result = dict()
        for page, meta in pages.iteritems():
            event = events.Event()
            for key in meta.keys():
                event.update(key, meta[key])
            result[page] = event
        return result

    def load_template(self, page):
        if not self.template_cache.get(page, None):
            self.template_cache[page] = self.wiki.getPage(page)
        return self.template_cache[page]

    @threado.stream
    def configs(inner, self):
        while True:
            confs = list()

            pages = self.get_pages(self.category)
            self.log.info("Got %i config pages from wiki.", len(pages))

            sources = list(self.sources(pages))
            confs.extend(sources)

            customer_rules = set()
            for customer in self.customers(pages, sources):
                customer_rules.add(customer.rule)
                confs.append(customer)

            for fallback in self.fallbacks():
                fallback.set_customer_rules(customer_rules)
                confs.append(fallback)

            inner.send(confs)
            yield inner, timer.sleep(self.poll_interval)

    def customers(self, pages, sources):
        templates = dict()
        customers = dict()
        self.template_cache.clear()

        for event in pages.values():
            asn_rules = event.values("ASN1", parser=map_asn)
            if not asn_rules:
                continue
            rule = combine_rules(rules.OR, asn_rules)

            netblock_rules = event.values("IP range", parser=map_netblock)
            if netblock_rules:
                rule = rules.AND(rule, combine_rules(rules.OR, netblock_rules))

            default_emails = event.values("Abuse email", filter=filter_email)
            default_template = event.value("Mail template", self.mail_template)
            for source in sources:
                template = event.value("Mail template "+source.wiki_name,
                                       default_template,
                                       filter=filter_value)

                emails = event.values("Abuse email "+source.wiki_name,
                                      filter=filter_email)
                for email in (emails or default_emails):
                    try:
                        template_data = self.load_template(template)
                    except Exception:
                        self.log.info("Failed to get template %r", template)
                        continue
                    templates[email] = template_data

                    customers.setdefault(email, dict())
                    customers[email].setdefault(source.alias, set())
                    customers[email][source.alias].add(rule)

        for email, aliases in customers.items():
            name = "".join(map(lambda x: x if x.isalnum() else "_", email))
            template = templates[email]
            rule = combine_rules(rules.OR, map(map_alias_rule, aliases.items()))
            yield Customer(name, template, rule, mail_to=[email])

    def sources(self, pages):
        asns = set()
        for event in pages.values():
            asns.update(event.values("ASN1", parse_asn))

        yield Source("DShield", "dshield", "d", asns=asns)
        yield Source("Arbor", "arbor", "a")
        yield Source("Shadowserver", "shadowserver", "s")

    def fallbacks(self):
        yield Fallback("all-unhandled")
        yield Fallback("containing-a-keyword",
                       rules.MATCH("somekey", re.compile("keyword", re.U)))

if __name__ == "__main__":
    WikiRuntimeBot.from_command_line().execute()
