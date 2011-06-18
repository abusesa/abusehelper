import getpass, opencollab.wiki
from idiokit import threado, timer
from abusehelper.core import events, taskfarm, bot, services
from combiner import Expert
from opencollab.wiki import WikiFailure
from opencollab.meta import Metas

class WikiIdentityExpert(Expert):
    wiki_url = bot.Param("wiki username")
    wiki_username = bot.Param("wiki username")
    wiki_password = bot.Param("wiki password", default=None)
    wiki_identity = bot.Param("identity to poll for", default="IPv4")
    expert_key = bot.Param("event key to look for", default="ip")
    metas = Metas()
    poll_interval = bot.IntParam("poll interval", default=60)

    def __init__(self, *args, **keys):
        Expert.__init__(self, *args, **keys)
        if self.wiki_password is None:
            self.wiki_password = getpass.getpass("Wiki password: ")
        self.wiki = opencollab.wiki.GraphingWiki(self.wiki_url)
        self.wiki.authenticate(self.wiki_username, self.wiki_password)
        self.log.info("Connected to wiki %s" % self.wiki_url)
        self.poll_from_wiki()
        self.log.info("Wiki poll interval is %d seconds." % self.poll_interval)

    @threado.stream
    def poll_from_wiki(inner, self):
	sleeper = timer.sleep(self.poll_interval)

        while True:
            yield sleeper, inner

	    if sleeper.was_source:
                self.log.info("Polling identity data from wiki.")
                try:
                    self.metas = yield inner.thread(self.wiki.getMeta, 
						    "TYPE=%s" % self.wiki_identity)
                except WikiFailure:
                    self.log.error("There was an error on the wiki side.")
            sleeper = timer.sleep(self.poll_interval)

    @threado.stream
    def augment(inner, self):
        while True:
            eid, event = yield inner
            ips = set(event.values(self.expert_key)) 
            for ip in ips:
                augment = events.Event()
                if ip in self.metas:
                    for k,v in self.metas[ip].iteritems():
                        augment.add(unicode(k),unicode(v.single()))
                if augment.contains():
                    inner.send(eid, augment)

if __name__ == "__main__":
    WikiIdentityExpert.from_command_line().execute()
