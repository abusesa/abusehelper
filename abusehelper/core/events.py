import os
import csv
import gzip
from cStringIO import StringIO
from idiokit import threado
from idiokit.xmlcore import Element

EVENT_NS = "abusehelper#event"

class Event(object):
    @classmethod
    def from_element(self, element):
        if len(element) != 1:
            return None
        if not element.named("event", EVENT_NS):
            return None

        event = Event(element)
        for attr in element.children("attr").with_attrs("key", "value"):
            event.add(attr.get_attr("key"), attr.get_attr("value"))
        return event

    def __init__(self, element=None):
        self.attrs = dict()
        self._element = None

    def add(self, key, value):
        self._element = None
        if key not in self.attrs:
            self.attrs[key] = set()
        self.attrs[key].add(value)

    def contains_key_value(self, key, value):
        return value in self.attrs.get(key, ())
        
    def contains_key(self, key):
        return key in self.attrs

    def to_element(self):
        if self._element is None:
            event = Element("event", xmlns=EVENT_NS)

            for key, values in self.attrs.items():
                for value in values:
                    attr = Element("attr", key=key, value=value)
                    event.add(attr)
            self._element = event
        return self._element

@threado.stream_fast
def stanzas_to_events(inner):
    while True:
        yield inner

        for element in inner:
            for child in element.children():
                event = Event.from_element(child)
                if event is not None:
                    inner.send(event)

@threado.stream_fast
def events_to_elements(inner, include_body=True):
    while True:
        yield inner

        for event in inner:
            if include_body:
                fields = list()
                for key, values in event.attrs.iteritems():
                    for value in values:
                        fields.append(key + "=" + value)
                body = Element("body")
                body.text = ", ".join(fields)
                inner.send(body, event.to_element())
            else:
                inner.send(event.to_element())

class EventCollector(object):
    def __init__(self, compresslevel=6):
        self.stringio = StringIO()
        self.gz = gzip.GzipFile(None, "w", compresslevel, self.stringio)
        
    def append(self, event):
        self.gz.write(repr(event.attrs) + os.linesep)

    def purge(self):
        stringio = self.stringio
        self.stringio = StringIO()

        self.gz.flush()
        self.gz.close()
        self.gz = gzip.GzipFile(None, "w", 6, self.stringio)

        return EventList(stringio)

class EventList(object):
    def __init__(self, stringio=None):
        self.stringio = stringio
        self.extensions = list()

    def __iter__(self):
        if self.stringio is not None:
            seek = self.stringio.seek
            tell = self.stringio.tell

            seek(0)
            gz = gzip.GzipFile(fileobj=self.stringio)
        
            try:
                for line in gz:
                    event = Event()
                    for key, values in eval(line).items():
                        for value in values:
                            event.add(key, value)
                    pos = tell()
                    yield event
                    seek(pos)
            finally:
                gz.close()

        for other in self.extensions:
            for event in other:
                yield event

    def extend(self, other):
        self.extensions.append(other)

    def __nonzero__(self):
        for _ in self:
            return True
        return False
