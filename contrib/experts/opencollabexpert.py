from idiokit import threado, timer
from abusehelper.core import bot, events, taskfarm
from abusehelper.contrib.experts.combiner import Expert
from opencollab import wiki
import random, hashlib

class OpenCollabExpert(Expert):
    collab_url = bot.Param()
    collab_user = bot.Param()
    collab_password = bot.Param()
    collab_ignore_cert = bot.BoolParam()
    collab_extra_ca_certs = bot.Param(default=None)
    cache_query = bot.Param()
    page_keys = bot.ListParam()
    poll_interval = bot.IntParam("wait at least the given amount of seconds "+
                                 "before polling the collab again "+
                                 "(default: %default seconds)", default=600)

    def __init__(self, *args, **keys):
        Expert.__init__(self, *args, **keys)
        self.cache_handler = taskfarm.TaskFarm(self._manage_cache)
        self.cache = dict()

        self.collab = wiki.GraphingWiki(self.collab_url,
                                        ssl_verify_cert=not self.collab_ignore_cert,
                                        ssl_ca_certs=self.collab_extra_ca_certs)
        self.collab.authenticate(self.collab_user, self.collab_password)
        self.cache_handler.inc(self.cache_query)

    @threado.stream
    def _manage_cache(inner, self, query):
        token = None
        while True:
            try:
                result = yield inner.thread(self.collab.request, 
                                            "IncGetMeta", query, token)
            except Exception, exc:
                self.log.error("IncGetMeta failed: %s" % exc)
            else:

                incremental, token, (removed, updates) = result
                removed = set(removed)
                if not incremental:
                    removed.update(self.cache)
                    self.cache.clear()

                for page, keys in updates.iteritems():
                    event = self.cache.setdefault(page, events.Event())
                    event.add("gwikipagename", page)
                    removed.discard(page)

                    for key, (discarded, added) in keys.iteritems():
                        for value in discarded:
                            event.discard(key, value)

                        for value in added:
                            event.add(key, value)

                for page in removed:
                    self.cache.pop(page, None)

            self.log.info("%i pages in cache", len(self.cache))

            sleep = timer.sleep(self.poll_interval)
            while not sleep.has_result():
                yield inner, sleep

    @threado.stream
    def augment(inner, self):
        counter = 0

        while True:
            eid, event = yield inner

            for page_key in self.page_keys:
                for value in event.values(page_key):
                    page = self.cache.get(value, None)
                    if not page:
                        continue

                    for key, value in page.items():
                        event.add("%s_%s" % (page_key,key), value.lstrip("[[").rstrip("]]"))

            inner.send(eid, event)

if __name__ == "__main__":
    OpenCollabExpert.from_command_line().execute()
