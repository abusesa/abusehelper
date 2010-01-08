import urllib2
import httplib
import socket
from idiokit import threado

class FetchUrlFailed(Exception):
    pass

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

        inner.finish(fileobj.info(), reader.result())
    except (urllib2.URLError, httplib.HTTPException, socket.error), error:
        raise FetchUrlFailed, error