import os
import gzip
import operator
from functools import partial
from itertools import ifilter, imap
from cStringIO import StringIO
from idiokit import threado
from idiokit.xmlcore import Element

DEFAULT_PARSER = lambda x: x
DEFAULT_FILTER = partial(operator.is_not, None)

EVENT_NS = "abusehelper#event"
_NO_VALUE = object()

class _Parsed(object):
    __slots__ = "attrs", "parser", "filter"

    def __init__(self, attrs, parser, filter):
        self.attrs = attrs
        self.parser = parser
        self.filter = partial(ifilter, filter)

    def get(self, key, default):
        values = self.attrs.get(key, ())
        values = imap(self.parser, values)
        values = list(self.filter(values))

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
            for _ in self.filter(imap(self.parser, values)):
                yield key
                break

    def itervalues(self):
        for key, values in self.attrs.iteritems():
            values = imap(self.parser, values)
            values = list(self.filter(values))

            try:
                yield set(values)
            except TypeError:
                yield values

    def values(self):
        return list(self.itervalues())

    def __nonzero__(self):
        for key in self.iterkeys():
            return True
        return False

    def __contains__(self, key):
        values = self.attrs.get(key, ())
        values = imap(self.parser, values)
        return any(self.filter(imap(self.parser, values)))

class Event(object):
    __slots__ = "_attrs", "_element"
    
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
        self._attrs = dict()

        for event in events:
            for key in event.keys():
                self.update(key, event.values())
                
        self._element = None

    def _parsed(self, parser, filter):
        if parser or filter:
            parser = parser or DEFAULT_PARSER
            filter = filter or DEFAULT_FILTER
            return _Parsed(self._attrs, parser, filter)
        return self._attrs

    def add(self, key, value, *values):
        """Add value(s) for a key.

        >>> event = Event()
        >>> event.add("key", "1")
        >>> event.values("key")
        set(['1'])

        More than one value can be added with one call.

        >>> event = Event()
        >>> event.add("key", "1", "2")
        >>> event.values("key") == set(["1", "2"])
        True

        Key-value pairs is already contained by the event are ignored.

        >>> event = Event()
        >>> event.add("key", "1")
        >>> event.values("key")
        set(['1'])
        >>> event.add("key", "1")
        >>> event.values("key")
        set(['1'])
        """

        self._element = None
        if key not in self._attrs:
            self._attrs[key] = set()
        self._attrs[key].add(value)
        self._attrs[key].update(values)

    def update(self, key, values):
        """Update the values of a key.

        >>> event = Event()
        >>> event.update("key", ["1", "2"])
        >>> event.values("key") == set(["1", "2"])
        True

        The event will not be modified if there are no values to add.

        >>> event = Event()
        >>> event.update("key", [])
        >>> event.contains("key")
        False
        """

        if not values:
            return

        self._element = None
        if key not in self._attrs:
            self._attrs[key] = set()
        self._attrs[key].update(values)

    def discard(self, key, value, *values):
        """Discard some value(s) of a key.

        >>> event = Event()
        >>> event.add("key", "1", "2", "3")
        >>> event.discard("key", "1", "3")
        >>> event.values("key")
        set(['2'])

        Values that don't exist for the given key are silently ignored.

        >>> event = Event()
        >>> event.add("key", "2")
        >>> event.discard("key", "1", "2")
        >>> event.values("key")
        set([])
        """
        self._element = None
        value_set = self._attrs.get(key, set())
        value_set.discard(value)
        value_set.difference_update(values)
        if not value_set:
            self._attrs.pop(key, None)

    def clear(self, key):
        """Clear all values of a key.

        >>> event = Event()
        >>> event.add("key", "1")
        >>> event.clear("key")
        >>> event.contains("key")
        False
        
        Clearing keys that do not exist does nothing.

        >>> event = Event()
        >>> event.clear("key")
        """

        self._element = None
        self._attrs.pop(key, None)

    def values(self, key=_NO_VALUE, parser=None, filter=None):
        """Return event values (for a specific key, if given).

        >>> event = Event()
        >>> event.add("key", "1", "2")
        >>> event.add("other", "3", "4")
        >>> event.values() == set(["1", "2", "3", "4"])
        True
        >>> event.values("key") == set(["1", "2"])
        True

        Perform parsing, validation and filtering by passing in
        parsing and filtering functions (by default all None objects
        are filtered when a parsing function has been given).

        >>> import socket
        >>> def ipv4(string):
        ...     try:
        ...         return socket.inet_ntoa(socket.inet_aton(string))
        ...     except socket.error:
        ...         return None
        >>> event = Event()
        >>> event.add("key", "1.2.3.4", "abba")
        >>> event.add("other", "10.10.10.10")
        >>> event.values("key", parser=ipv4) == set(["1.2.3.4"])
        True
        >>> event.values(parser=ipv4) == set(["1.2.3.4", "10.10.10.10"])
        True

        The returned value collection is always a set unless the
        parsing function returns unhashable objects (e.g. lists):

        >>> event = Event()
        >>> event.add("key", "ab", "cd")
        >>> event.values(parser=list) == [["a", "b"], ["c", "d"]]
        True
        """

        attrs = self._parsed(parser, filter)
        if key is not _NO_VALUE:
            return attrs.get(key, set())

        result = list()
        for values in attrs.values():
            result.extend(values)

        try:
            return set(result)
        except TypeError:
            return result

    def value(self, key=_NO_VALUE, default=_NO_VALUE, parser=None, filter=None):
        """Return one event value (for a specific key, if given).

        The value can be picked either from the values of some
        specific key or amongst event values.

        >>> event = Event()
        >>> event.add("key", "1")
        >>> event.add("other", "2")
        >>> event.value("key")
        '1'
        >>> event.value() in ["1", "2"]
        True

        A default return value can be defined in case no suitable
        value is available:

        >>> event = Event()
        >>> event.value("key", "default value")
        'default value'
        >>> event.value(default="default value")
        'default value'

        KeyError is raised if no suitable values are available and no
        default is given.

        >>> event = Event()
        >>> event.value()
        Traceback (most recent call last):
        ...
        KeyError: 'no value available'
        >>> event.value("somekey")
        Traceback (most recent call last):
        ...
        KeyError: 'somekey'

        As with .values(...), parsing and filtering functions can be
        given, and they will be used to modify the results.

        >>> def int_parse(string):
        ...     try:
        ...         return int(string)
        ...     except ValueError:
        ...         return None
        >>> event = Event()
        >>> event.add("key", "1", "a")
        >>> event.value(parser=int_parse)
        1
        >>> event.value("key", parser=int_parse)
        1
        >>> event.value("other", parser=int_parse)
        Traceback (most recent call last):
        ...
        KeyError: 'other'
        """

        attrs = self._parsed(parser, filter)
        if key is _NO_VALUE:
            for values in attrs.itervalues():
                for value in values:
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
                 parser=None, filter=None):
        """Return whether the event contains a key-value pair (for
        specific key and/or value, if given).

        >>> event = Event()
        >>> event.contains() # Does the event contain any values at all?
        False

        >>> event.add("key", "1")
        >>> event.contains()
        True
        >>> event.contains("key") # Any value for key "key"?
        True
        >>> event.contains(value="1") # Value "1" for any key?
        True
        >>> event.contains("key", "1") # Value "1" for key "key"?
        True

        >>> event.contains("other", "2") # Value "2" for key "other"?
        False

        Parsing and filtering functions can be given to modify the results.

        >>> def int_parse(string):
        ...     try:
        ...         return int(string)
        ...     except ValueError:
        ...         return None
        >>> event = Event()
        >>> event.add("key", "1", "a")
        >>> event.contains(parser=int_parse) # Any int value for any key?
        True
        >>> event.contains("key", parser=int_parse)
        True
        """

        attrs = self._parsed(parser, filter)
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

    def keys(self, parser=None, filter=None):
        """Return a sequence of keys with at least one value.

        >>> event = Event()
        >>> set(event.keys()) == set()
        True
        >>> event.add("key", "1")
        >>> event.add("other", "2", "3")
        >>> set(event.keys()) == set(["key", "other"])
        True

        Parsing and filtering functions can be given to modify the
        results.

        >>> def int_parse(string):
        ...     try:
        ...         return int(string)
        ...     except ValueError:
        ...         return None
        >>> event = Event()
        >>> event.add("key", "1")
        >>> event.add("other", "a")
        >>> set(event.keys(parser=int_parse)) == set(["key"])
        True
        """

        attrs = self._parsed(parser, filter)
        return attrs.keys()

    def is_valid(self):
        """Return whether the event contains values for keys other than "id".

        >>> event = Event()
        >>> event.is_valid()
        False
        >>> event.add("id", "1")
        >>> event.is_valid()
        False
        >>> event.add("other", "2")
        >>> event.is_valid()
        True
        """

        if len(self._attrs) == 0:
            return False
        if "id" in self._attrs and len(self._attrs) == 1:
            return False
        return True

    def to_element(self):
        if self._element is None:
            event = Element("event", xmlns=EVENT_NS)

            for key, values in self._attrs.items():
                for value in values:
                    attr = Element("attr", key=key, value=value)
                    event.add(attr)
            self._element = event
        return self._element

    def __repr__(self):
        return self.__class__.__name__ + "(" + repr(self._attrs) + ")"

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
                for key, values in event._attrs.iteritems():
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
        self.gz.write(repr(event._attrs) + os.linesep)

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

if __name__ == "__main__":
    import doctest
    doctest.testmod()
