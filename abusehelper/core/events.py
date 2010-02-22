import os
import gzip
from cStringIO import StringIO
from idiokit import threado
from idiokit.xmlcore import Element

EVENT_NS = "abusehelper#event"
_NO_VALUE = object()

class _Parsed(object):
    __slots__ = "attrs", "parser", "ignore"

    def __init__(self, attrs, parser, ignore):
        self.attrs = attrs
        self.parser = parser
        self.ignore = ignore

    def get(self, key, default):
        values = list()
        for value in self.attrs.get(key, ()):
            try:
                parsed = self.parser(value)
            except self.ignore:
                pass
            else:
                values.append(parsed)

        if values:
            try:
                return set(values)
            except TypeError:
                return values
        return default

    def keys(self):
        return list(self.iterkeys())

    def iterkeys(self):
        for key, values in self.attrs.iteritems():
            for value in values:
                try:
                    self.parser(value)
                except self.ignore:
                    pass
                else:
                    yield key
                    break

    def itervalues(self):
        for key, values in self.attrs.iteritems():
            parsed_values = list()
            append = parsed_values.append

            for value in values:
                try:
                    parsed_value = self.parser(value)
                except self.ignore:
                    pass
                else:
                    append(parsed_value)
                
            try:
                yield set(parsed_values)
            except TypeError:
                yield parsed_values

    def values(self):
        return list(self.itervalues())

    def __nonzero__(self):
        for key in self.iterkeys():
            return True
        return False

    def __contains__(self, key):
        for value in self.attrs.get(key, ()):
            try:
                self.parser(value)
            except self.ignore:
                pass
            else:
                return True
        return False

class Event(object):
    __slots__ = "attrs", "_element"

    @classmethod
    def from_element(self, element):
        if len(element) != 1:
            return None
        if not element.named("event", EVENT_NS):
            return None

        event = Event()
        event._element = element
        for attr in element.children("attr").with_attrs("key", "value"):
            event.add(attr.get_attr("key"), attr.get_attr("value"))
        return event

    def __init__(self, *events):
        self.attrs = dict()

        for event in events:
            for key in event.keys():
                self.update(key, event.values())
                
        self._element = None

    def add(self, key, value, *values):
        self._element = None
        if key not in self.attrs:
            self.attrs[key] = set()
        self.attrs[key].add(value)
        self.attrs[key].update(values)

    def update(self, key, values):
        self._element = None
        if key not in self.attrs:
            self.attrs[key] = set()
        self.attrs[key].update(values)

    def discard(self, key, value, *values):
        self._element = None
        value_set = self.attrs.get(key, set())
        value_set.discard(value)
        value_set.difference_update(values)
        if not value_set:
            self.attrs.pop(key, None)

    def clear(self, key):
        self._element = None
        self.attrs.pop(key, None)

    def values(self, key=_NO_VALUE, parser=None, ignore=Exception):
        attrs = _Parsed(self.attrs, parser, ignore) if parser else self.attrs
        if key is not _NO_VALUE:
            return attrs.get(key, set())

        result = list()
        for values in attrs.values():
            result.extend(values)

        try:
            return set(result)
        except TypeError:
            return result

    def value(self, key=_NO_VALUE, default=_NO_VALUE, 
              parser=None, ignore=Exception):
        attrs = _Parsed(self.attrs, parser, ignore) if parser else self.attrs
        if key is _NO_VALUE:
            for value in attrs.itervalues():
                return value
        else:
            for value in attrs.get(key, ()):
                return value

        if default is _NO_VALUE:
            if key is _NO_VALUE:
                raise KeyError("no value available")
            raise KeyError(key)
        return default

    def contains(self, key=_NO_VALUE, value=_NO_VALUE, 
                 parser=None, ignore=Exception):
        attrs = _Parsed(self.attrs, parser, ignore) if parser else self.attrs
        if key is not _NO_VALUE:
            if value is _NO_VALUE:
                return key in attrs
            return value in attrs.get(key, ())

        if value is _NO_VALUE:
            return not not attrs

        for value_set in attrs.itervalues():
            if value in value_set:
                return True
        return False

    def keys(self, parser=None, ignore=Exception):
        attrs = _Parsed(self.attrs, parser, ignore) if parser else self.attrs
        return attrs.keys()

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
        self.compresslevel = compresslevel
        self.gz = gzip.GzipFile(None, "w", compresslevel, self.stringio)

    def __setstate__(self, (compresslevel, data)):
        self.stringio = StringIO()
        self.stringio.write(data)
        self.compresslevel = compresslevel
        self.gz = gzip.GzipFile(None, "a", compresslevel, self.stringio)

    def __getstate__(self):
        self.gz.flush()
        self.gz.close()
        state = self.compresslevel, self.stringio.getvalue()
        self.stringio.close()
        self.__setstate__(state)
        return state
        
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
