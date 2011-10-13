import hashlib
import urlparse

from idiokit import threado
from abusehelper.core import events, utils
from combiner import Expert

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
                    augment = events.Event()

                    filename = info.get_filename(None)
                    if filename is not None:
                        augment.add("payload filename", filename)

                    sha1 = hashlib.sha1(fileobj.read()).hexdigest()
                    augment.add("payload sha-1", sha1)

                    inner.send(eid, augment)

        return _collect() | _fetch()

if __name__ == "__main__":
    URLInfoExpert.from_command_line().execute()
