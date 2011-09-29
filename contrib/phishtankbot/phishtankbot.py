import bz2
import urllib2
from datetime import datetime
import xml.etree.cElementTree as etree

from idiokit import threado, timer
from abusehelper.core import bot, events, utils

class HeadRequest(urllib2.Request):
    def get_method(self):
        return "HEAD"

class PhishtankBot(bot.PollingBot):
    application_key = bot.Param("Registered application key for Phistank.")
    feed_url = bot.Param(default="http://data.phishtank.com/data/%s/online-valid.xml.bz2")

    def __init__(self, *args, **keys):
        bot.PollingBot.__init__(self, *args, **keys)
        self.full_feed = self.feed_url % self.application_key
        self.last_modified = None

    def urlIsModified(self, url):
        self.log.info("Checking if %s has new data." % url)
        info = urllib2.urlopen(HeadRequest(url)).info()

        etag = info.get("etag", '"Thu, 01 Jan 1970 00:00:00"')
        etag = datetime.strptime(etag, '"%a, %d %b %Y %H:%M:%S"')
        new = info.get("last-modified", 'Thu, 01 Jan 1970 00:00:00 GMT')
        new = datetime.strptime(new, "%a, %d %b %Y %H:%M:%S GMT")

        if etag > new:
            new = etag

        if self.last_modified and self.last_modified >= new:
            self.log.info("No new data since %s", self.last_modified)
            return False

        self.last_modified = new
        self.log.info("Data modified since last fetch.")
        return True

    @threado.stream
    def poll(inner, self, _):
        yield inner.flush()

        if not self.urlIsModified(self.full_feed):
            return

        try:
            self.log.info("Downloading data from: %s", self.full_feed)
            _, fileobj = yield inner.sub(utils.fetch_url(self.full_feed))
        except utils.FetchUrlFailed, e:
            self.log.error("Failed to download the report %s: %r", self.full_feed, e)
            return

        uncompressed = bz2.decompress(fileobj.read())
        sites = dict()
        for elem in etree.fromstring(uncompressed):
            entries = elem.findall("entry")
            if not entries:
                continue

            for entry in entries:
                yield inner.flush()
                url = entry.find("url")
                if url is None:
                    continue

                verification = entry.find("verification")
                if verification is None:
                    continue
                verified = verification.find("verified")
                if verified is None or verified.text != "yes":
                    continue

                status = entry.find("status")
                if status is None:
                    continue
                online = status.find("online")
                if online is None or online.text != "yes":
                    continue

                details = entry.find("details")
                if details is None:
                    continue
                for detail in details.findall("detail"):
                    ip = detail.find("ip_address")
                    if ip is None:
                        continue

                    announcer = detail.find("announcing_network")
                    if announcer is None or announcer.text == None:
                        continue

                    if type(url) not in [str, unicode]:
                        url = url.text
                    ip = ip.text
                    announcer = announcer.text

                    url_data = sites.setdefault(url, list())
                    if (ip, announcer) not in url_data:
                        url_data.append((ip, announcer))

                        event = events.Event()
                        event.add("feed", "phishtank")
                        event.add("url", url)
                        event.add("host", "/".join(url.split("/")[:3])+"/")
                        event.add("ip", ip)
                        event.add("asn", announcer)
                        inner.send(event)

if __name__ == "__main__":
     PhishtankBot.from_command_line().execute()
