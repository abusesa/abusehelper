import collections
from idiokit import threado, timer
from abusehelper.core import events, rules, taskfarm, bot, services

class CollectorBot(bot.ServiceBot):
    def __init__(self, *args, **keys):
        bot.ServiceBot.__init__(self, *args, **keys)
        self.rooms = taskfarm.TaskFarm(self.handle_room)
        self.events = dict()       

    @threado.stream_fast
    def collect(inner, self, name):
        while True:
            yield inner

            for event in inner:
                self.events[name].append(event)

    @threado.stream
    def handle_room(inner, self, name):
        self.log.info("Joining room %r", name)
        room = yield inner.sub(self.xmpp.muc.join(name, self.bot_name))
        self.log.info("Joined room %r", name)

        try:
            yield inner.sub(room 
                            | events.stanzas_to_events()
                            | self.collect(name))
        finally:
            self.log.info("Left room %r", name)

import xmlrpclib
from time import strftime

class WikiBot(CollectorBot):
    write_interval = bot.IntParam("write interval", default=1800)

    def __init__(self, *args, **keys):
        CollectorBot.__init__(self, *args, **keys)
        self.wikis = dict()

    def write_to_wiki(self, room, events):
        wiki_params = self.wikis.get(room, None)
        if not wiki_params or not events:
            return

        url, user, password, type, parent = wiki_params

        self.log.info("Connecting to wiki %s" % url)
        wiki = None
        if type == "opencollab":
            try:
                import opencollab.wiki    
                wiki = opencollab.wiki.CLIWiki(url, user, password)
            except:
                wiki = None

#dokuwiki not tested
#        elif type == "doku":
#            full = url+"/lib/exe/xmlrpc.php?"+urlencode({'u':user,'p':password})
#            try:
#                wiki = xmlrpclib.ServerProxy(full).wiki
#            except:
#                wiki = None

        if not wiki:
            self.log.info("Failed connecting to wiki")
            return

        self.log.info("Connected to wiki")

        content = dict()
        for event in events:
            asns = event.attrs.get("asn", None)
            for asn in asns:
                content.setdefault(asn, list())
                line = unicode()

                for key, values in event.attrs.iteritems():
                    line += "%s=%s " % (key, ",".join(values))

                content[asn].append(line)

        date = strftime("%Y-%m-%d")
        for asn in content:
            pagename = "%s/%s/%s" % (parent, asn, date)

            try:
                body = wiki.getPage(pagename)
            except:
                body = unicode()

            body += "\n\n" + "\n\n".join(content[asn])
            self.log.info("Writing asn%s events to wiki" % asn)

            success = wiki.putPage(pagename, body)
            if success:
                self.log.info("Events written to wiki")
            else:
                self.log.info("Could not write events to wiki")            

    @threado.stream
    def timed(inner, self, interval):
        sleeper = timer.sleep(interval)
        while True:
            for room, events in self.events.iteritems():
                self.write_to_wiki(room, events)
                self.events[room] = list()

            item = yield inner, sleeper
            if sleeper.was_source:
                inner.finish()

    @threado.stream
    def main(inner, self, state):
        try:
            while True:
                yield inner.sub(self.timed(self.write_interval) 
                                | threado.dev_null())
        except services.Stop:
            inner.finish()

    @threado.stream
    def session(inner, self, state, room, wiki_url, wiki_user, wiki_password, 
                wiki_type="opencollab", parent="", **keys):

        self.rooms.inc(room)
        self.wikis[room] = (wiki_url, wiki_user, wiki_password, 
                            wiki_type, parent)

        self.events.setdefault(room, list())

        try:
            while True:
                yield inner
        except services.Stop:
            inner.finish()
        finally:
            self.rooms.dec(room)
            del self.wikis[room]
            del self.events[room]

if __name__ == "__main__":
    WikiBot.from_command_line().run()

