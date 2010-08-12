import re

from idiokit import threado, util
from abusehelper.core import events

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
