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

def meta_to_event(meta):
    event = events.Event()
    for key in meta.keys():
        event.update(key, meta[key])
    return event

def map_asn(string):
    try:
        return rules.MATCH(u"asn", unicode(int(string)))
    except ValueError:
        return None

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
    return rules.AND(rules.MATCH("feed", alias), combine_rules(rules.OR, ruleset))

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
    def __init__(self, name, alias, **attrs):
        self.name = name
        self.alias = alias
        self.attrs = attrs

    def runtime(self):
        yield (Session(self.name, **self.attrs)
               | raw_room(self.alias)
               | Session(self.name + ".sanitizer")
               | sanitized_room(self.alias)
               | sources_room)
        yield raw_room(self.alias) | Session("historian")
        yield sanitized_room(self.alias) | Session("historian")

class Fallback(object):
    def __init__(self, name, customer_rules, rule):
        self.name = name

        ruleset = list()
        if customer_rules:
            ruleset.append(rules.NOT(combine_rules(rules.OR, customer_rules)))
        if rule is not None:
            ruleset.append(rule)
        self.rule = combine_rules(rules.AND, ruleset)

    def runtime(self):
        yield (sources_room
               | Session("roomgraph", rule=self.rule)
               | fallback_room(self.name))

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

    def runtime(self):
        template = "Subject: AbuseHelper report for " + self.name + "\n"
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
        yield customer_room(self.name) | Session("historian")

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
            return self.wiki.getMeta(category)
        except:
            self.wiki = None
            self.log.info("Trying to reconnect to wiki")
            try:
                self.connect()
                try:
                    return self.wiki.getMeta(category)
                except:
                    self.info.log("Failed to get category %s" % category)
            except:
                return
 
    def load_template(self, page):
        if not self.template_cache.get(page, None):
            self.template_cache[page] = self.wiki.getPage(page)
        return self.template_cache[page]

    def get_customers(self, pages):
        templates = dict()
        customers = dict()
        self.template_cache.clear()

        for asn_page, meta in pages.items():
            event = meta_to_event(meta)

            asn_rules = event.values("ASN1", parser=map_asn)
            if not asn_rules:
                continue
            rule = combine_rules(rules.OR, asn_rules)

            netblock_rules = event.values("IP range", parser=map_netblock)
            if netblock_rules:
                rule = rules.AND(rule, combine_rules(rules.OR, netblock_rules))

            default_emails = event.values("Abuse email", filter=filter_email)
            default_template = event.value("Mail template", self.mail_template)
            for wiki_name, (_, alias) in self.sources.items():
                template = event.value("Mail template "+wiki_name, 
                                       default_template,
                                       filter=filter_value)

                emails = event.values("Abuse email "+wiki_name, 
                                      filter=filter_email)
                for email in (emails or default_emails):
                    try:
                        template_data = self.load_template(template)
                    except:
                        self.log.info("Failed to get mail template %r" % template)
                        continue
                    templates[email] = template_data

                    customers.setdefault(email, dict()).setdefault(alias, set())
                    customers[email][alias].add(rule)

        for email, aliases in customers.items():
            name = "".join(map(lambda x: x if x.isalnum() else "_", email))
            template = templates[email]
            rule = combine_rules(rules.OR, map(map_alias_rule, aliases.items()))
            yield name, template, rule

    @threado.stream
    def configs(inner, self):
        while True:
            confs = list()
            customer_rules = set()

            pages = self.get_pages(self.category)
            self.log.info("Got %i config pages from wiki.", len(pages.keys()))
            for name, template, rule in self.get_customers(pages):
                customer_rules.add(rule)
                confs.append(Customer(name, template, rule))

            for key, rule in self.fallbacks.items():
                confs.append(Fallback(key, customer_rules, rule))
            
            for wiki_name, (bot_name, alias) in self.sources.items():
                confs.append(Source(bot_name, alias))

            inner.send(confs)
            yield inner, timer.sleep(self.poll_interval)

    # These keys should match with the contact pages source specific email
    # and template keys. Example:
    #  Abuse email Arbor:: arbor@example.com
    #  Mail template Shadowserver:: ShadowMailTemplate
    sources = {
        "Arbor": ("arbor", "a"),
        "Shadowserver": ("shadowserver", "s"),
        }
    
    fallbacks = {
        "all-unhandled": None,
        "containing-a-keyword": rules.MATCH("somekey", re.compile("keyword"))
        }

if __name__ == "__main__":
    WikiRuntimeBot.from_command_line().execute()
