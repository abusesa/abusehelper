from abusehelper.core import rules
from abusehelper.core.config import *
from abusehelper.core.runtime import *

startup = load_module("startup")
prefix = startup.Bot.service_room + "."

class Base(Config):
    @classmethod
    def class_name(cls):
        return cls.__name__.lower()
    
    @classmethod
    def class_room(cls):
        return Room(prefix+cls.class_name()+"s")

    def room(self):
        return Room(prefix+self.class_name()+"."+self.name)

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

template_cache = dict()

def load_template(name):
    if name not in template_cache:
        template_file = open(startup.locate("template", name))
        try:
            template_cache[name] = template_file.read()
        finally:
            template_file.close()
    return template_cache[name]

class Mail(Session):
    def __init__(self, to=[], cc=[], template="default", times=["08:00"]):
        template = load_template(template)
        Session.__init__(self, "mailer", to=to, cc=cc, template=template, times=times)

class Wiki(Session):
    def __init__(self, url, user, password, type="opencollab", parent=""):
        Session.__init__(self, "wikibot", 
                         wiki_url=url, wiki_user=user, wiki_password=password,
                         wiki_type=type, parent=parent)

class Customer(Base):
    asns = [] # Default: no asns
    types = None # Default: all types
    reports = [] # Default: no reporting

    def main(self):
        if self.asns:
            rule = rules.OR(*[rules.CONTAINS(asn=str(asn)) for asn in self.asns])
            if self.types is None:
                yield Type.class_room() | Session("roomgraph", rule=rule) | self.room()
            else:
                for type in self.types:
                    yield Type(name=type).room() | Session("roomgraph", rule=rule) | self.room()

        for report in self.reports:
            yield self.room() | report

# Source definitions

dshield = Source(asns=[1, 2, 3, 4])

# Type definitions

malware = Type()
spam = Type()
ufo = Type()

# Customer definitions

malware_to_mail = Customer(asns=[1, 2, 3], 
                                 reports=[Mail()], 
                                 types=["malware"])
all_to_wiki = Customer(asns=[1, 2, 3], 
                       reports=[Wiki("https://wiki.example.com",
                                     "wikiuser", "wikipassword")])
