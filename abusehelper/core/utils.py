import csv
import socket
import urllib2
import httplib
import email.parser
import re

from idiokit import threado, util
from abusehelper.core import events
from cStringIO import StringIO

class FetchUrlFailed(Exception):
    pass

@threado.stream
def arf_to_events(inner, fileobj, charset=None):
    if charset is None:
        decode = util.guess_encoding    
    else:
        decode = lambda x: x.decode(charset)
    
    event = events.Event()
    yield
    for row in fileobj:
        m = re.search('^(?P<key>[\w\-]+)\s*\:\s*(?P<val>.+)$', row)
        if m != None and m.lastindex == 2:
            key = m.group('key')
            val = m.group('val')
            if key != None and val != None:
                key = decode(key.lower().strip())
                val = decode(val.strip())
                event.add(key, val)
    inner.send(event)

@threado.stream
def fetch_url(inner, url, opener=None):
    if opener is None:
        opener = urllib2.build_opener()

    try:
        reader = inner.thread(opener.open, url)
        while not reader.has_result():
            yield inner, reader

        fileobj = reader.result()
        reader = inner.thread(fileobj.read)
        try:
            while not reader.has_result():
                yield inner, reader
        finally:
            fileobj.close()
            
        info = fileobj.info()
        info = email.parser.Parser().parsestr(str(info), headersonly=True)

        inner.finish(info, StringIO(reader.result()))
    except (urllib2.URLError, httplib.HTTPException, socket.error), error:
        raise FetchUrlFailed(*error.args)

@threado.stream
def csv_to_events(inner, fileobj, delimiter=",", columns=None, charset=None):
    if columns is None:
        reader = csv.DictReader(fileobj, delimiter=delimiter)
    else:
        reader = csv.reader(fileobj, delimiter=delimiter)

    if charset is None:
        decode = util.guess_encoding
    else:
        decode = lambda x: x.decode(charset)

    for row in reader:
        yield
        list(inner)

        if columns is not None:
            row = dict(zip(columns, row))
            
        event = events.Event()
        for key, value in row.items():
            if None in (key, value):
                continue
            key = decode(key.lower().strip())
            value = decode(value.strip())
            event.add(key, value)
                
        inner.send(event)
