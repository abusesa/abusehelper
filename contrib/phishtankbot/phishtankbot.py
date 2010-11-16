import bz2
from idiokit import threado, timer
from abusehelper.core import bot, events, utils

try:
    import json
except ImportError:
    import simplejson as json

class PhishtankBot(bot.PollingBot):
    application_key = bot.Param("Registered application key for Phistank.")
    feed_url = bot.Param(default="http://data.phishtank.com/data/%s/online-valid.json.bz2")

    @threado.stream
    def poll(inner, self, _):
        while True:
            feed = self.feed_url % self.application_key

            try:
                _, fileobj = yield inner.sub(utils.fetch_url(feed))
            except utils.FetchUrlFailed, fu:
                self.log.error("Failed to download the report %s: %r", feed, fu)
                return

            data = json.loads(bz2.decompress(fileobj.read()))

            for site in data:
                url = site.get("url", None)     
                if not url:
                    continue

                verified = site.get("verified", "no")
                if verified != "yes":
                    continue

                online = site.get("online", "no")
                if online != "yes":
                    continue

                for detail in site.get("details", list()):
                    ip = detail.get("ip_address", None)
                    announcer = detail.get("announcing_network", None)

                    if not ip and not announcer:
                        continue

                    event = events.Event()
                    event.add("feed", "phishtank")
                    event.add("url", url)
                    event.add("host", "/".join(url.split("/")[:3])+"/")
                    event.add("ip", ip)
                    event.add("asn", announcer)

                    inner.send(event)

if __name__ == "__main__":
     PhishtankBot.from_command_line().execute()
