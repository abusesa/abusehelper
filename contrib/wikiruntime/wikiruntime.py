import re
import socket
import opencollab.wiki
from idiokit import threado, timer
from abusehelper.core import bot, rules
from abusehelper.core.config import relative_path, load_module
from abusehelper.core.runtime import RuntimeBot, Room, Session

startup = load_module("startup")
sources_room = Room("sources")

def source_room(source):
    return Room("source." + source)

def alias_room(alias):
    return Room("sanitized." + alias)

def customer_room(customer):
    return Room("customer." + customer)

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

class Source(object):
    def __init__(self, name, alias, **attrs):
        self.name = name
        self.alias = alias
        self.attrs = attrs

    def runtime(self):
        yield (Session(self.name, **self.attrs)
               | source_room(self.name)
               | Session(self.name + ".sanitizer")
               | alias_room(self.alias)
               | sources_room)
        yield source_room(self.name) | Session("historian")
        yield alias_room(self.alias) | Session("historian")

class Customer(object):
    mail_to = []
    mail_cc = []
    mail_times = [5*3600]

    def __init__(self, name, template, rules, **attrs):
        self.name = name
        self.mail_template = template
        self.rules = rules

        for key, value in attrs.items():
            setattr(self, key, value)

    def runtime(self):
        template = "Subject: AbuseHelper report for " + self.name + "\n"
        template += self.mail_template

        for alias, rule in self.rules:
            yield (alias_room(alias)
                   | Session("roomgraph", rule=rule)
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
        self.all_asns = set()
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

    def get_customers(self, pages, sources):
        self.all_asns = set()
        templates = dict()
        customers = dict()
        self.template_cache.clear()

        for asn_page, metas in pages.iteritems():
            try:
                asn = int(metas["ASN1"].single(None))
            except ValueError:
                continue

            self.all_asns.add(asn)
            ruleset = set()

            ip_ranges = metas["IP range"].single("any").strip()
            if ip_ranges != "any":
                for ip_range in map(str.strip, ip_ranges.split(",")):
                    try:
                        ruleset.add(parse_netblock(ip_range))
                    except ValueError:
                        pass

            default_emails = metas["Abuse email"].single("-")
            default_template =metas["Mail template"].single(self.mail_template)

            for name, source in sources:
                emails = metas["Abuse email "+name].single("-").strip()
                if emails == "-":
                    emails = default_emails
                elif "@" not in emails:
                    continue

                template = metas["Mail template "+name].single("-").strip()
                if template == "-":
                    template = default_template

                for email in map(str.strip, emails.split(",")):
                    if "@" not in email:
                        continue
                    rule = rules.AND(rules.CONTAINS(asn=str(asn)), *ruleset)
                    customers.setdefault(email, dict()).setdefault(source, set()).add(rule)

                    try:
                        templates.setdefault(email, self.load_template(template))
                    except:
                        self.log.info("Failed to get page %s" % template)
                        continue

        for email, aliases in customers.iteritems():
            alias_rules = list()
            for alias, ruleset in list(aliases.iteritems()):
                if not ruleset:
                    continue
                alias_rules.append((alias, rules.OR(*ruleset)))
            if not alias_rules:
                continue

            name = "".join(map(lambda x: x if x.isalnum() else "_", email))
            template = templates[email]
            yield name, template, alias_rules

    @threado.stream
    def configs(inner, self):
        #These keys should match with the contact pages source specific email
        #and template keys. example:
        # Abuse email Arbor:: arbor@example.com
        # Mail template Shadowserver:: ShadowMailTemplate
        #
        #Alias is used to match the keys with the sourcebots added below.
        sourcekeys = [("Arbor", "a"), ("Shadowserver", "s")]

        while True:
            confs = list()
            pages = self.get_pages(self.category)
            self.log.info("Got %i config pages from wiki.", len(pages.keys()))

            for name, template, rules in self.get_customers(pages, sourcekeys):
                confs.append(Customer(name, template, rules))

            # Source definitions
            confs.extend([Source("ircfeed", "i"),
                          Source("shadowservermail", 's'),
                          Source("atlassrf", "a")])

            inner.send(confs)
            yield inner, timer.sleep(self.poll_interval)

if __name__ == "__main__":
    WikiRuntimeBot.from_command_line().execute()
