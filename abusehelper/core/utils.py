import csv
import time
import socket
import urllib2
import httplib
import collections
import email.parser

import idiokit
from abusehelper.core import events
from cStringIO import StringIO


class FetchUrlFailed(Exception):
    pass


class HTTPError(FetchUrlFailed):
    def __init__(self, code, msg, headers, fileobj):
        FetchUrlFailed.__init__(self, code, msg)

        self.code = code
        self.msg = msg
        self.headers = headers
        self.fileobj = fileobj

    def __str__(self):
        return "HTTP Error %d: %s" % (self.code, self.msg)


@idiokit.stream
def fetch_url(url, opener=None, chunk_size=16384):
    if opener is None:
        opener = urllib2.build_opener()

    try:
        output = StringIO()

        fileobj = yield idiokit.thread(opener.open, url)
        try:
            while True:
                data = yield idiokit.thread(fileobj.read, chunk_size)
                if not data:
                    break
                output.write(data)
        finally:
            fileobj.close()

        info = fileobj.info()
        info = email.parser.Parser().parsestr(str(info), headersonly=True)

        output.seek(0)

        idiokit.stop(info, output)
    except urllib2.HTTPError as he:
        raise HTTPError(he.code, he.msg, he.hdrs, he.fp)
    except (urllib2.URLError, httplib.HTTPException, socket.error) as error:
        raise FetchUrlFailed(str(error))


def force_decode(string, encodings=["ascii", "utf-8"]):
    if isinstance(string, unicode):
        return string

    for encoding in encodings:
        try:
            return string.decode(encoding)
        except ValueError:
            pass
    return string.decode("latin-1", "replace")


def _csv_reader(fileobj, charset=None, **keys):
    if charset is None:
        decode = force_decode
    else:
        decode = lambda x: x.decode(charset)
    lines = (decode(line).encode("utf-8").replace("\x00", "\xc0") for line in fileobj)
    normalize = lambda x: x.replace("\xc0", "\x00").decode("utf-8").strip()

    for row in csv.reader(lines, **keys):
        yield map(normalize, row)


@idiokit.stream
def csv_to_events(fileobj, delimiter=",", columns=None, charset=None):
    for row in _csv_reader(fileobj, charset=charset, delimiter=delimiter):
        if columns is None:
            columns = row
            continue

        event = events.Event()
        for key, value in zip(columns, row):
            if key is None or not value:
                continue
            event.add(key, value)

        yield idiokit.send(event)


class TimedCache(object):
    def __init__(self, cache_time):
        self.cache = dict()
        self.queue = collections.deque()
        self.cache_time = cache_time

    def _expire(self):
        current_time = time.time()

        while self.queue:
            expire_time, key = self.queue[0]
            if expire_time > current_time:
                break
            self.queue.popleft()

            other_time, _ = self.cache[key]
            if other_time == expire_time:
                del self.cache[key]

    def get(self, key, default):
        self._expire()
        if key not in self.cache:
            return default
        _, value = self.cache[key]
        return value

    def set(self, key, value):
        self._expire()
        expire_time = time.time() + self.cache_time
        self.queue.append((expire_time, key))
        self.cache[key] = expire_time, value
