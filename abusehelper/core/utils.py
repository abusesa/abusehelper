import csv
import time
import gzip
import socket
import urllib2
import httplib
import collections
import email.parser

import cPickle as pickle

import idiokit
from abusehelper.core import events
from cStringIO import StringIO


class FetchUrlFailed(Exception):
    pass


class FetchUrlTimeout(FetchUrlFailed):
    pass


class HTTPError(FetchUrlFailed):
    def __init__(self, code, msg, headers, fileobj):
        FetchUrlFailed.__init__(self, code, msg)

        self.code = code
        self.msg = msg
        self.headers = headers
        self.fileobj = fileobj

    def __str__(self):
        return "HTTP Error {0}: {1}".format(self.code, self.msg)


@idiokit.stream
def fetch_url(url, opener=None, timeout=60.0, chunk_size=16384):
    if opener is None:
        opener = urllib2.build_opener()

    try:
        output = StringIO()

        fileobj = yield idiokit.thread(opener.open, url, timeout=timeout)
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
    except urllib2.URLError as error:
        if isinstance(error.reason, socket.timeout):
            raise FetchUrlTimeout("fetching URL timed out")
        raise FetchUrlFailed(str(error))
    except (httplib.HTTPException, socket.error) as error:
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


class CompressedCollection(object):
    FORMAT = 1

    def __init__(self, iterable=(), _state=None):
        """
        A collection of objects, stored in memory in a
        pickled & compressed form.

        >>> c = CompressedCollection([1, 2, 3])
        >>> c.append("testing")

        >>> list(c)
        [1, 2, 3, 'testing']
        >>> len(c)
        4
        >>> bool(c)
        True
        """

        self._stringio = StringIO()
        self._count = 0
        self._gz = None

        if _state:
            _format, data, count = _state
            self._stringio.write(data)
            self._count = count

        for obj in iterable:
            self.append(obj)

    def _close(self):
        if self._gz is None:
            return

        self._gz.flush()
        self._gz.close()
        self._gz = None

    def __iter__(self):
        self._close()

        stringio = self._stringio

        out_pos = stringio.tell()
        stringio.seek(0)
        try:
            gz = gzip.GzipFile(fileobj=stringio)
        finally:
            in_pos = stringio.tell()
            stringio.seek(out_pos)

        try:
            while True:
                out_pos = stringio.tell()
                stringio.seek(in_pos)

                try:
                    obj = pickle.load(gz)
                except EOFError:
                    break
                else:
                    in_pos = stringio.tell()
                finally:
                    stringio.seek(out_pos)

                yield obj
        finally:
            gz.close()

    def __reduce__(self):
        self._close()
        data = self._stringio.getvalue()
        return self.__class__, ((), (self.FORMAT, data, self._count))

    def __len__(self):
        return self._count

    def append(self, obj):
        if self._gz is None:
            self._gz = gzip.GzipFile(None, "ab", fileobj=self._stringio)
        self._gz.write(pickle.dumps(obj))
        self._count += 1
