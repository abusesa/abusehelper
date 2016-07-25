"""
PhishTank feed handler. Requires a PhishTank application key.

Maintainer: Codenomicon <clarified@codenomicon.com>
"""

import re
import bz2
import socket
import urllib2
import urlparse
import collections
from datetime import datetime
import xml.etree.cElementTree as etree

import idiokit
from abusehelper.core import bot, events, utils


def _replace_non_xml_chars(unicode_obj, replacement=u"\uFFFD"):
    return _NON_XML.sub(replacement, unicode_obj)
_NON_XML = re.compile(u"[\x00-\x08\x0B\x0C\x0E-\x1F\uD800-\uDFFF\uFFFE\uFFFF]", re.U)


def parse_text(element, key):
    entry = element.find(key)
    if entry is None:
        return

    if not isinstance(entry, basestring):
        entry = entry.text

    if entry:
        return entry


def is_domain(string):
    for addr_type in (socket.AF_INET, socket.AF_INET6):
        try:
            socket.inet_ntop(addr_type, socket.inet_pton(addr_type, string))
        except (ValueError, socket.error):
            pass
        else:
            return False
    return True


class BZ2Reader(object):
    def __init__(self, fileobj):
        self._fileobj = fileobj
        self._bz2 = bz2.BZ2Decompressor()

        self._line_buffer = collections.deque([""])

        self._current_line = ""
        self._current_offset = 0

    def _read_raw(self, chunk_size=65536):
        while True:
            compressed = self._fileobj.read(chunk_size)
            if not compressed:
                return ""

            decompressed = self._bz2.decompress(compressed)
            if decompressed:
                return decompressed

    def _read_line(self):
        if not self._line_buffer:
            return ""

        while len(self._line_buffer) == 1:
            raw = self._read_raw()
            if not raw:
                return self._line_buffer.pop()

            last = self._line_buffer.pop()
            self._line_buffer.extend((last + raw).splitlines(True))

        return self._line_buffer.popleft()

    def _mangle_line(self, line, target="utf-8"):
        # Forcibly decode the bytes into an unicode object.
        try:
            decoded = line.decode("utf-8")
        except UnicodeDecodeError:
            decoded = line.decode("latin-1")

        # Remove characters that are not proper XML 1.0.
        sanitized = _replace_non_xml_chars(decoded)

        return sanitized.encode("utf-8")

    def _read(self, amount):
        while self._current_offset >= len(self._current_line):
            line = self._read_line()
            if not line:
                return ""

            self._current_line = self._mangle_line(line)
            self._current_offset = 0

        data = self._current_line[self._current_offset:self._current_offset + amount]
        self._current_offset += len(data)
        return data

    def read(self, amount):
        result = list()

        while amount > 0:
            data = self._read(amount)
            if not data:
                break
            amount -= len(data)
            result.append(data)

        return "".join(result)


class HeadRequest(urllib2.Request):
    def get_method(self):
        return "HEAD"


class PhishTankBot(bot.PollingBot):
    application_key = bot.Param("registered application key for PhishTank")
    feed_url = bot.Param(default="https://data.phishtank.com/data/%s/online-valid.xml.bz2")

    def __init__(self, *args, **keys):
        bot.PollingBot.__init__(self, *args, **keys)

        self._etag = None

    @idiokit.stream
    def _handle_entry(self, entry, sites):
        details = entry.find("details")
        if details is None:
            return

        verification = entry.find("verification")
        if verification is None or parse_text(verification, "verified") != "yes":
            return

        status = entry.find("status")
        if status is None or parse_text(status, "online") != "yes":
            return

        url = parse_text(entry, "url")
        if not url:
            return

        event = events.Event({"feed": "phishtank", "url": url})

        domain = urlparse.urlparse(url).netloc
        if is_domain(domain):
            event.add("domain name", domain)

        detail_url = parse_text(entry, "phish_detail_url")
        if detail_url:
            event.add("description url", detail_url)

        target = parse_text(entry, "target")
        if target:
            event.add("target", target)

        history = {}
        for detail in details.findall("detail"):
            ip = parse_text(detail, "ip_address")
            if not ip:
                continue

            announcer = parse_text(detail, "announcing_network")
            if not announcer:
                continue

            detail_time = parse_text(detail, "detail_time")
            try:
                ts = datetime.strptime(detail_time, "%Y-%m-%dT%H:%M:%S+00:00")
            except (ValueError, TypeError):
                continue

            history[ts] = (ip, announcer)

        if history:
            latest = sorted(history.keys())[-1]
            ip, announcer = history[latest]

            url_data = sites.setdefault(url, set())
            if (ip, announcer) in url_data:
                return
            url_data.add((ip, announcer))

            event.add("ip", ip)
            event.add("asn", announcer)
            event.add("source time", latest.strftime("%Y-%m-%d %H:%M:%SZ"))

            yield idiokit.send(event)

    @idiokit.stream
    def poll(self):
        url = self.feed_url % self.application_key

        try:
            self.log.info("Checking if {0!r} has new data".format(url))
            info, _ = yield utils.fetch_url(HeadRequest(url))

            etag = info.get("etag", None)
            if etag is not None and self._etag == etag:
                raise bot.PollSkipped("no new data detected (ETag stayed the same)")

            self.log.info("Downloading data from {0!r}".format(url))
            _, fileobj = yield utils.fetch_url(url)
        except utils.FetchUrlFailed as error:
            raise bot.PollSkipped("failed to download {0!r} ({1})".format(url, error))

        self.log.info("Downloaded data from {0!r}".format(url))

        reader = BZ2Reader(fileobj)
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
        except SyntaxError as error:
            raise bot.PollSkipped("syntax error in report {0!r} ({1})".format(url, error))
        else:
            self._etag = etag

    def main(self, state):
        if state is None:
            state = None, None
        self._etag, wrapped_state = state

        return bot.PollingBot.main(self, wrapped_state) | self._add_etag_to_result()

    @idiokit.stream
    def _add_etag_to_result(self):
        state = yield idiokit.consume()
        idiokit.stop(self._etag, state)


if __name__ == "__main__":
    PhishTankBot.from_command_line().execute()
