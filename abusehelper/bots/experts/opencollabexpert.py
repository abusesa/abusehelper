import socket
import idiokit
from opencollab import wiki
from ...core import bot, events
from . import Expert


class OpenCollabExpert(Expert):
    collab_url = bot.Param()
    collab_user = bot.Param()
    collab_password = bot.Param()
    collab_ignore_cert = bot.BoolParam()
    collab_extra_ca_certs = bot.Param(default=None)
    cache_query = bot.Param()
    page_keys = bot.ListParam("pagekey=wikikey[,pagekey=wikikey]")
    disable_join_keys = bot.BoolParam("Disable pagekey and wikikey joining on events")
    poll_interval = bot.IntParam("""
        wait at least the given amount of seconds before polling the collab again
        (default: %default seconds)
        """, default=600)

    def __init__(self, *args, **keys):
        Expert.__init__(self, *args, **keys)

        self.cache = dict()
        self.keys = dict()

        for pair in self.page_keys:
            parts = pair.split("=")
            if len(parts) < 2:
                continue

            wikikeys = self.keys.setdefault(parts[0], set())
            wikikeys.add("=".join(parts[1:]))

        self.collab = wiki.GraphingWiki(self.collab_url,
                                        ssl_verify_cert=not self.collab_ignore_cert,
                                        ssl_ca_certs=self.collab_extra_ca_certs)
        self.collab.authenticate(self.collab_user, self.collab_password)

    def main(self, *args, **keys):
        return self._manage_cache(self.cache_query) | Expert.main(self, *args, **keys)

    @idiokit.stream
    def _manage_cache(self, query):
        token = None
        wikikeys = set()
        for valueset in self.keys.values():
            wikikeys.update(valueset)

        while True:
            try:
                result = yield idiokit.thread(self.collab.request, "IncGetMeta", query, token)
            except (socket.error, wiki.WikiFailure) as exc:
                self.log.error("IncGetMeta failed: {0}".format(exc))
            else:
                incremental, token, (removed, updates) = result
                removed = set(removed)
                if not incremental:
                    removed.update(self.cache.keys())
                    self.cache.clear()

                for page, keys in updates.iteritems():
                    event = self.cache.setdefault(page, events.Event())
                    event.add("gwikipagename", page)
                    removed.discard(page)

                    for key, (discarded, added) in keys.iteritems():
                        for value in discarded:
                            event.discard(key, value)

                        for value in added:
                            if key in wikikeys:
                                event.add(key, value)

                for page in removed:
                    self.cache.pop(page, None)

                if removed or updates:
                    self.log.info("Updated {0} pages and removed {1} pages ({2} pages in cache)".format(
                        len(updates), len(removed), len(self.cache.keys())))

            yield idiokit.sleep(self.poll_interval)

    @idiokit.stream
    def augment(self):
        while True:
            eid, event = yield idiokit.next()
            augment = events.Event()

            for pagekey in self.keys:
                for pagename in event.values(pagekey):
                    page = self.cache.get(pagename, None)
                    if not page:
                        continue

                    for wikikey in self.keys[pagekey]:
                        if not self.disable_join_keys:
                            newkey = str(pagekey + "_" + wikikey)
                        else:
                            newkey = str(wikikey)

                        for value in page.values(wikikey):
                            augment.add(newkey, value.strip("[[]]"))

            if augment.contains():
                yield idiokit.send(eid, augment)


if __name__ == "__main__":
    OpenCollabExpert.from_command_line().execute()
