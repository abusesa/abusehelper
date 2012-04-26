"""
PhishTank feed handler. Requires a PhishTank application key.

Maintainer: Jussi Eronen <exec@iki.fi>
"""

import bz2
import urllib2
from datetime import datetime
import xml.etree.cElementTree as etree

import idiokit
from abusehelper.core import bot, events, utils


class BZ2Reader(object):
    def __init__(self, fileobj):
        self.fileobj = fileobj

        self.bz2 = bz2.BZ2Decompressor()
        self.pending = ""
        self.index = 0

    def read(self, amount):
        result = list()

        while amount > 0:
            if self.index >= len(self.pending):
                data = self.fileobj.read(2 ** 16)
                if not data:
                    break
                self.pending = self.bz2.decompress(data)
                self.index = 0
            else:
                piece = self.pending[self.index:self.index + amount]
                self.index += len(piece)
                amount -= len(piece)
                result.append(piece)

        return "".join(result)


class HeadRequest(urllib2.Request):
    def get_method(self):
        return "HEAD"


class PhishTankBot(bot.PollingBot):
    application_key = bot.Param("registered application key for PhishTank")
    feed_url = bot.Param(default="http://data.phishtank.com/data/%s/online-valid.xml.bz2")

    def __init__(self, *args, **keys):
        bot.PollingBot.__init__(self, *args, **keys)
        self.fileobj = None
        self.etag = None

    @idiokit.stream
    def _handle_entry(self, entry, sites):
        url = entry.find("url")
        if url is None:
            return
        if not isinstance(url, basestring):
            url = url.text

        verification = entry.find("verification")
        if verification is None:
            return

        verified = verification.find("verified")
        if verified is None or verified.text != "yes":
            return

        ts = verification.find("verification_time")
        if ts != None and ts.text:
            try:
                ts = datetime.strptime(ts.text, "%Y-%m-%dT%H:%M:%S+00:00")
                ts = ts.strftime("%Y-%m-%d %H:%M:%S UTC")
            except ValueError:
                ts = None

        status = entry.find("status")
        if status is None:
            return
        online = status.find("online")
        if online is None or online.text != "yes":
            return

        target = entry.find("target")

        details = entry.find("details")
        if details is None:
            return
        for detail in details.findall("detail"):
            ip = detail.find("ip_address")
            if ip is None:
                continue

            announcer = detail.find("announcing_network")
            if announcer is None or announcer.text == None:
                continue

            ip = ip.text
            announcer = announcer.text

            url_data = sites.setdefault(url, set())
            if (ip, announcer) in url_data:
                continue
            url_data.add((ip, announcer))

            event = events.Event()
            event.add("feed", "phishtank")
            event.add("url", url)
            event.add("host", "/".join(url.split("/")[:3]) + "/")
            event.add("ip", ip)
            event.add("asn", announcer)
            if ts:
                event.add("time", ts)
            if target is not None:
                event.add("target", target.text)
            yield idiokit.send(event)

    @idiokit.stream
    def poll(self):
        url = self.feed_url % self.application_key
        try:
            self.log.info("Checking if %r has new data" % url)
            info, _ = yield utils.fetch_url(HeadRequest(url))

            etag = info.get("etag", None)
            if etag is None or self.etag != etag:
                self.log.info("Downloading new data from %r", url)
                _, self.fileobj = yield utils.fetch_url(url)
            self.etag = etag
        except utils.FetchUrlFailed, error:
            self.log.error("Failed to download %r: %r", url, error)
            return

        self.fileobj.seek(0)
        reader = BZ2Reader(self.fileobj)
        try:
            depth = 0
            sites = dict()

            for event, element in etree.iterparse(reader, events=("start", "end")):
                if event == "start" and element.tag == "entry":
                    depth += 1

                if event == "end" and element.tag == "entry":
                    yield self._handle_entry(element, sites)
                    depth -= 1

                if event == "end" and depth == 0:
                    element.clear()
        except SyntaxError, error:
            self.log.error("Syntax error in report %r: %r", url, error)

if __name__ == "__main__":
    PhishTankBot.from_command_line().execute()
