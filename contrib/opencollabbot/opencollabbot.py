import opencollab.wiki
from idiokit import threado
from abusehelper.core import bot, events

class OpenCollabBot(bot.PollingBot):
    url = bot.Param("Open Collab wiki url.")
    user = bot.Param("Open Collab wiki user.")
    password = bot.Param("Open Collab wiki password.")
    query = bot.Param("Metatable query string.")

    def __init__(self, *args, **keys):
        bot.PollingBot.__init__(self, *args, **keys)
        self.wiki = None
        self.handle = None
        self.events = dict()

    def connect(self):
        try:
            self.wiki = opencollab.wiki.GraphingWiki(self.url)
        except socket.error, e:
            self.log.error("Failed connecting to %s" % self.url)
            return False

        try:
            success = self.wiki.authenticate(self.user, self.password)
        except opencollab.wiki.WikiFailure, e:
            self.log.error("Invalid path to wiki: %s" % self.url)
            return False

        if not success:
            self.log.error("Authentication failed.")

        return success

    def update_events(self, incremental, diff):
        updated = set()

        if not incremental:
            for page in self.events:
                event = events.Event()
                event.add("id", page)
                self.events[page] = event
            updated.update(self.events.keys())

        deleted = diff[0]
        for page in deleted:
            event = events.Event()
            event.add("id", page)
            self.events[page] = event
        updated.update(deleted)

        updates = diff[1]
        for page in updates:
            event = self.events.get(page, events.Event())
            if not event.contains("id"):
                event.add("id", page)

            for key in updates[page]:
                discard = updates[page][key][0]
                if discard:
                    event.discard(key, *discard)
                add = updates[page][key][1]
                if add:
                    event.add(key, *add)

            self.events[page] = event
        updated.update(updates.keys())

        return updated

    def get_events(self):
        response = list()

        self.log.info("Fetching pages from wiki.")
        try:
            response = self.wiki.request("IncGetMeta", self.query, self.handle)
        except:
            self.wiki = None
            self.log.info("Connecting to wiki..") 
            if self.connect():
                try:    
                    response = self.wiki.request("IncGetMeta", self.query, \
                        self.handle)
                except:
                    self.log.info("Failed to get category %s" % category)
                    return None, None

        if len(response) < 3 or len(response[2]) < 2:
            return None, None

        incremental, self.handle, diff = response
        return incremental, diff

    @threado.stream
    def poll(inner, self, _):
        yield

        incremental, diff = self.get_events()
        if len(diff) < 2 or (not diff[0] and not diff[1]):
            return

        updated = self.update_events(incremental, diff)
        self.log.info("%s updated events.", str(len(updated)))
        for page in updated:
            event = self.events.get(page, None)
            if event:
                if len(event.keys()) > 1 and event.contains("id"):
                    link = "%s%s" % (self.url, page)
                    event.add("source", link)
                inner.send(event)

if __name__ == "__main__":
    OpenCollabBot.from_command_line().run()

