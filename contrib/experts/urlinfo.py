import hashlib
import urlparse

from idiokit import threado
from abusehelper.core import events, utils
from combiner import Expert

class URLInfoEvent(events.Event):
    def __init__(self, url, info, fileobj):
        events.Event.__init__(self)

        self.url = url

        self.filename = filename = info.get_filename(None)
        if self.filename is not None:
            self.add("payload filename", self.filename)
        
        self.hash = hashlib.sha1(fileobj.read()).hexdigest()
        self.add("payload sha-1", self.hash)

    def __unicode__(self):
        result = "URL " + self.url + " payload"
        if self.filename is not None:
            result += " filename " + self.filename
        if self.hash is not None:
            result += " SHA-1 " + self.hash
        return result

class URLInfoExpert(Expert):
    def augment(self):
        channel = threado.Channel()

        @threado.stream
        def _collect(inner):
            while True:
                eid, event = yield inner

                for value in event.values():
                    parsed = urlparse.urlparse(value)
                    if parsed.scheme.lower() in ("http", "https"):
                        channel.send(eid, value)

        @threado.stream
        def _fetch(inner):
            while True:
                eid, url = yield inner, channel
                
                self.log.info("Fetching URL %r", url)
                try:
                    info, fileobj = yield inner.sub(utils.fetch_url(url))
                except utils.FetchUrlFailed, fail:
                    self.log.error("Fetching URL %r failed: %r", url, fail)
                else:
                    self.log.info("Fetched URL %r", url)
                    augment = URLInfoEvent(url, info, fileobj)
                    inner.send(eid, augment)

        return _collect() | _fetch()

if __name__ == "__main__":
    URLInfoExpert.from_command_line().execute()
