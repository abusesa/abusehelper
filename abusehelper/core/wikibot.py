import xmlrpclib
from idiokit import threado, timer
from abusehelper.core import events, taskfarm, bot, services

class Wiki:
    def __init__(self, url, user, password, type):
        self.type = type
        if self.type == "opencollab":
            self.separator = "/"
            import opencollab.wiki
            self.wiki = opencollab.wiki.CLIWiki(url, user, password)
        elif self.type == "doku":
            self.separator = ":"
            fullurl = "%s/lib/exe/xmlrpc.php?%s" % (url, 
                                                    urlencode({'u':user,
                                                               'p':password}))
            self.wiki = xmlrpclib.ServerProxy(fullurl).wiki

    def putEvents(self, pagename, events, parents=list()):
        if parents:
            parts = parents + [pagename]
            pagename = self.separator.join(parts)

        try:
            body = self.wiki.getPage(pagename)
        except:
            body = unicode()

        if self.type == "opencollab":
            body += "\n\n" + "\n\n".join(events)

            try:
                success = self.wiki.putPage(pagename, body)
            except:
                success = False

            if not success:
                return False

        elif self.type == "doku":
            body += "\\\\ \n" + "\\\\ \n".join(events)

            try:
                self.wiki.putPage(pagename, body, {})
            except:
                return False

        return True

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
from urllib import urlencode

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
        try:
            wiki = Wiki(url, user, password, type)
        except:
            self.log.info("Failed connecting to wiki")
            return
        self.log.info("Connected to wiki")

        content = dict()
        for event in events:
            asns = event.attrs.get("asn", None)
            for asn in asns:
                content.setdefault(asn, dict())

                types = list(event.attrs.get("type", list()))
                if not types:
                    continue

                type = types[0]
                content[asn].setdefault(type, list())
                line = unicode()

                for key, values in event.attrs.iteritems():
                    line += "%s=%s " % (key, ",".join(values))

                content[asn][type].append(line)

        time = strftime("%Y%m%d")
        for asn in content:
            parents = list()
            if parent:
                parents.append(parent)

            parents.append("as"+asn)

            for type in content[asn]:
                parents.append(time)

                self.log.info("Writing as%s events to wiki" % asn)
                success = wiki.putEvents(type, content[asn][type], parents)

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
    def session(inner, self, state, src_room, wiki_url, wiki_user,
                wiki_password, wiki_type="opencollab", parent="", **keys):

        self.rooms.inc(src_room)
        self.wikis[src_room] = (wiki_url, wiki_user, wiki_password, 
                                wiki_type, parent)

        self.events.setdefault(src_room, list())

        try:
            while True:
                yield inner
        except services.Stop:
            inner.finish()
        finally:
            self.rooms.dec(src_room)
            del self.wikis[src_room]
            del self.events[src_room]

if __name__ == "__main__":
    WikiBot.from_command_line().execute()

