import re
import os
import gzip
import codecs
import inspect
from cStringIO import StringIO

import idiokit
from idiokit.xmlcore import Element

_ESCAPE = re.compile(u"&(?=#)|[\x00-\x08\x0B\x0C\x0E-\x1F\uD800-\uDFFF\uFFFF\uFFFE]",
                     re.U)

def _escape_sub(match):
    return "&#x%X;" % ord(match.group())

def _escape(string):
    """Return a string where forbidden XML characters (and & in some
    cases) have been escaped using XML character references.

    >>> _escape(u"\u0000\uffff")
    u'&#x0;&#xFFFF;'

    & should only be escaped when it is potentially a part of an escape
    sequence starting with &#.

    >>> _escape(u"& &#x26;")
    u'& &#x26;#x26;'

    Other characters are not affected.
    """
    return _ESCAPE.sub(_escape_sub, string)

_UNESCAPE = re.compile(u"&#x([0-9a-f]+);", re.I)

def _unescape_sub(match):
    value = match.group(1)
    try:
        return unichr(int(value, 16))
    except ValueError:
        return match.group(1)

def _unescape(string):
    """Return a string where XML character references have been
    substituted with the corresponding unicode characters.

    >>> _unescape(u"&#x0;&#xFFFF;")
    u'\\x00\\uffff'
    """

    return _UNESCAPE.sub(_unescape_sub, string)

def _normalize(value):
    """Return the value converted to unicode. Raise a TypeError if the
    value is not a string.

    >>> _normalize("a")
    u'a'
    >>> _normalize(u"b")
    u'b'
    >>> _normalize(1)
    Traceback (most recent call last):
    ...
    TypeError: expected a string value, got the value 1 of type int

    When converting str objects the default encoding is tried, and an
    UnicodeDecodeError is raised if the value can not bot converted.

    >>> _normalize("\xe4") #doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
    ...
    UnicodeDecodeError: <the error goes here>
    """

    if isinstance(value, basestring):
        return unicode(value)

    name = type(value).__name__
    module = inspect.getmodule(value)
    if module is not None and module.__name__ != "__builtin__":
        name = module.__name__ + "." + name
    msg = "expected a string value, got the value %r of type %s" % (value, name)
    raise TypeError(msg)

_ENCODING = "utf-8"
_encoder = codecs.getencoder(_ENCODING)
_decoder = codecs.getdecoder(_ENCODING)

def _internal(string):
    return _encoder(string)[0]

def _external(string):
    return _decoder(string)[0]

EVENT_NS = "abusehelper#event"

def _bisect(items, key, value):
    """
    >>> _bisect([], "a", "b")
    0
    >>> _bisect(["a", "b"], "a", "b")
    0
    >>> _bisect(["a", "a", "a", "c"], "a", "b")
    2
    """

    lo = 0
    hi = len(items) // 2

    while lo < hi:
        mid = (lo + hi) // 2
        mid2 = 2 * mid
        mid_key = items[mid2]

        if mid_key < key:
            lo = mid + 1
        elif mid_key > key:
            hi = mid
        elif items[mid2 + 1] < value:
            lo = mid + 1
        else:
            hi = mid

    return 2 * lo

def _zip(items, start=0):
    """
    >>> list(_zip([1, 2, 3, 4]))
    [(1, 2), (3, 4)]
    >>> list(_zip([1, 2, 3, 4], 2))
    [(3, 4)]
    """

    for idx in xrange(start, len(items), 2):
        yield items[idx], items[idx+1]

def _unzip(items):
    """
    >>> list(_unzip([(1, 2), (3, 4)]))
    [1, 2, 3, 4]
    """

    for left, right in items:
        yield left
        yield right

_UNICODE_QUOTE_CHECK = re.compile(r'[\s"\\,=]', re.U)
_UNICODE_QUOTE = re.compile(r'["\\]', re.U)
def _unicode_quote(string):
    r"""
    >>> _unicode_quote(u"a")
    u'a'
    >>> _unicode_quote(u"=")
    u'"="'
    >>> _unicode_quote(u"\n")
    u'"\n"'
    """

    if _UNICODE_QUOTE_CHECK.search(string):
        return u'"' + _UNICODE_QUOTE.sub(r'\\\g<0>', string) + u'"'
    return string

_UNICODE_UNQUOTE = re.compile(r'\\(.)', re.U)
_UNICODE_PART = re.compile(r'\s*(?:(?:"((?:\\"|[^"])*)")|([^\s"=,]+)|)\s*',
                           re.U)
def _unicode_parse_part(string, start):
    match = _UNICODE_PART.match(string, start)
    quoted, unquoted = match.groups()
    end = match.end()

    if quoted is not None:
        return _UNICODE_UNQUOTE.sub("\\1", quoted), end
    if unquoted is not None:
        return unquoted, end
    return u"", end

class Event(object):
    __slots__ = ["_items"]

    _UNDEFINED = object()

    @classmethod
    def from_unicode(cls, string):
        r"""
        >>> event = Event()
        >>> event.add(u"a", u"b")
        >>> Event.from_unicode(unicode(event)) == event
        True

        >>> event.add(u'=', u'"')
        >>> Event.from_unicode(unicode(event)) == event
        True
        """

        result = cls()

        string = string.strip()
        if not string:
            return result

        index = 0
        length = len(string)

        while True:
            key, index = _unicode_parse_part(string, index)
            if index >= length:
                raise ValueError("unexpected string end")
            if string[index] != u"=":
                raise ValueError("unexpected character %r at index %d" %
                                 (string[index], index))
            index += 1

            value, index = _unicode_parse_part(string, index)
            result.add(key, value)

            if index >= length:
                return result

            if string[index] != u",":
                raise ValueError("unexpected character %r at index %d" %
                                 (string[index], index))
            index += 1

    @classmethod
    def from_element(self, element):
        """Return an event parsed from an XML element (None if the
        element was not suitable).

        >>> element = Element("event", xmlns=EVENT_NS)
        >>> Event.from_element(element) == Event()
        True

        >>> event = Event()
        >>> event.add("key", "value")
        >>> event.add("\uffff", "\x05") # include some forbidden XML chars
        >>> Event.from_element(event.to_element()) == event
        True

        >>> element = Element("invalid")
        >>> Event.from_element(element) is None
        True
        """

        if len(element) != 1:
            return None
        if not element.named("event", EVENT_NS):
            return None

        event = Event()
        for attr in element.children("attr").with_attrs("key", "value"):
            key = _unescape(attr.get_attr("key"))
            value = _unescape(attr.get_attr("value"))
            event.add(key, value)
        return event

    def __init__(self, *events):
        """
        Regression test: Keep the the correct internal encoding in the
        copy/merge constructor.

        >>> e1 = Event()
        >>> e1.add(u"\xe4", u"\xe4")
        >>> e2 = Event(e1)
        >>> e2.items()
        ((u'\\xe4', u'\\xe4'),)
        """

        if events:
            items = set()
            for event in events:
                items.update(_zip(event._items))
            self._items = tuple(_unzip(sorted(items)))
        else:
            self._items = ()

    def add(self, key, value, *values):
        """Add value(s) for a key.

        >>> event = Event()
        >>> event.add("key", "1")
        >>> event.values("key")
        (u'1',)

        More than one value can be added with one call.

        >>> event = Event()
        >>> event.add("key", "1", "2")
        >>> sorted(event.values("key"))
        [u'1', u'2']

        Key-value pairs is already contained by the event are ignored.

        >>> event = Event()
        >>> event.add("key", "1")
        >>> event.values("key")
        (u'1',)
        >>> event.add("key", "1")
        >>> event.values("key")
        (u'1',)
        """

        self.update(key, (value,) + values)

    def update(self, key, values):
        """Update the values of a key.

        >>> event = Event()
        >>> event.update("key", ["1", "2"])
        >>> sorted(event.values("key"))
        [u'1', u'2']

        The event will not be modified if there are no values to add.

        >>> event = Event()
        >>> event.update("key", [])
        >>> event.contains("key")
        False
        """

        key = intern(_internal(_normalize(key)))
        items = self._items
        length = len(items)

        for value in values:
            value = _internal(_normalize(value))
            idx = _bisect(items, key, value)

            if idx >= length or items[idx] != key or items[idx+1] != value:
                items = items[:idx] + (key, value) + items[idx:]
                length += 2

        self._items = items

    def discard(self, key, value, *values):
        """Discard some value(s) of a key.

        >>> event = Event()
        >>> event.add("key", "1", "2", "3")
        >>> event.discard("key", "1", "3")
        >>> event.values("key")
        (u'2',)

        Values that don't exist for the given key are silently ignored.

        >>> event = Event()
        >>> event.add("key", "2")
        >>> event.discard("key", "1", "2")
        >>> event.values("key")
        ()
        """

        key = _internal(_normalize(key))
        items = self._items
        length = len(items)

        for value in (value,) + values:
            value = _internal(_normalize(value))
            idx = _bisect(items, key, value)

            if idx < length and items[idx] == key and items[idx+1] == value:
                items = items[:idx] + items[idx+2:]
                length -= 2

        self._items = items

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

        key = _internal(_normalize(key))
        items = self._items
        length = len(items)

        start = _bisect(items, key, "")
        end = start
        while end < length and items[end] == key:
            end += 2

        self._items = items[:start] + items[end:]

    def _iteritems(self, key, parser, filter):
        """Iterate through parsed and filtered values of either a
        specific key or all keys.

        Regression test, start iterating from the correct index when
        iterating through values for a given key:

        >>> event = Event()
        >>> event.add("a", "1")
        >>> event.add("b", "2")
        >>> list(event._iteritems("b", None, None))
        [(u'b', u'2')]
        """

        if key is self._UNDEFINED:
            for key, value in _zip(self._items):
                value = _external(value)
                if parser is not None:
                    value = parser(value)

                if filter is None and value is None:
                    continue
                if filter is not None and not filter(value):
                    continue
                yield _external(key), value
            return

        key = _normalize(key)
        internal_key = _internal(key)
        idx = _bisect(self._items, internal_key, "")
        for other_key, value in _zip(self._items, idx):
            if other_key != internal_key:
                break

            value = _external(value)
            if parser is not None:
                value = parser(value)

            if filter is None and value is None:
                continue
            if filter is not None and not filter(value):
                continue
            yield key, value

    def values(self, key=_UNDEFINED, parser=None, filter=None):
        """Return a tuple of event values (for a specific key, if
        given).

        >>> event = Event()
        >>> event.add("key", "1", "2")
        >>> event.add("other", "3", "4")
        >>> sorted(event.values())
        [u'1', u'2', u'3', u'4']
        >>> sorted(event.values("key"))
        [u'1', u'2']

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
        >>> event.values("key", parser=ipv4)
        ('1.2.3.4',)
        >>> sorted(event.values(parser=ipv4))
        ['1.2.3.4', '10.10.10.10']
        """

        return tuple(x[1] for x in self._iteritems(key, parser, filter))

    def value(self, key=_UNDEFINED, default=_UNDEFINED,
              parser=None, filter=None):
        """Return one event value (for a specific key, if given).

        The value can be picked either from the values of some
        specific key or amongst event values.

        >>> event = Event()
        >>> event.add("key", "1")
        >>> event.add("other", "2")
        >>> event.value("key")
        u'1'
        >>> event.value() in [u"1", u"2"]
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

        for _, value in self._iteritems(key, parser, filter):
            return value

        if default is self._UNDEFINED:
            if key is self._UNDEFINED:
                raise KeyError("no value available")
            raise KeyError(key)
        return default

    def contains(self, key=_UNDEFINED, value=_UNDEFINED,
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
        >>> event.contains(parser=int_parse) # Any int value for any key?
        True
        >>> event.contains("key", parser=int_parse)
        True
        >>> event.add("other", "x")
        >>> event.contains("other", parser=int_parse)
        False
        """

        undef = self._UNDEFINED

        for _, parsed in self._iteritems(key, parser, filter):
            if value is undef or parsed == value:
                return True
        return False

    def items(self, parser=None, filter=None):
        """Return a tuple of key-value pairs contained by the event.

        >>> event = Event()
        >>> event.items()
        ()
        >>> event.add("key", "1")
        >>> event.add("other", "x", "y")
        >>> sorted(event.items())
        [(u'key', u'1'), (u'other', u'x'), (u'other', u'y')]

        Parsing and filtering functions can be given to modify the results.

        >>> def int_parse(string):
        ...     try:
        ...         return int(string)
        ...     except ValueError:
        ...         return None
        >>> event.items(parser=int_parse)
        ((u'key', 1),)

        The order of the key-value pairs is undefined.
        """

        return tuple(self._iteritems(self._UNDEFINED, parser, filter))

    def keys(self, parser=None, filter=None):
        """Return a tuple of keys with at least one value.

        >>> event = Event()
        >>> event.keys()
        ()
        >>> event.add("key", "1")
        >>> event.add("other", "x", "y")
        >>> sorted(event.keys())
        [u'key', u'other']

        Parsing and filtering functions can be given to modify the
        results.

        >>> def int_parse(string):
        ...     try:
        ...         return int(string)
        ...     except ValueError:
        ...         return None
        >>> sorted(event.keys(parser=int_parse))
        [u'key']
        """

        keys = list()
        prev_key = None

        for key, value in _zip(self._items):
            if key == prev_key:
                continue
            prev_key = None

            value = _external(value)
            if parser is not None:
                value = parser(value)

            if filter is None and value is None:
                continue
            if filter is not None and not filter(value):
                continue
            keys.append(_external(key))
            prev_key = key

        return tuple(keys)

    def to_element(self):
        event = Element("event", xmlns=EVENT_NS)

        for key, value in self.items():
            key = _escape(key)
            value = _escape(value)
            attr = Element("attr", key=key, value=value)
            event.add(attr)

        return event

    def __eq__(self, other):
        if not isinstance(other, Event):
            return NotImplemented
        return other._items == self._items

    def __ne__(self, other):
        value = self.__eq__(other)
        if value is NotImplemented:
            return NotImplemented
        return not value

    def __unicode__(self):
        """Return an unicode representation of the event.

        >>> e = Event()
        >>> unicode(e)
        u''
        >>> e.add("a,", "b")
        >>> unicode(e)
        u'"a,"=b'

        The specific order of the key-value pairs is undefined.
        """

        return u", ".join(_unicode_quote(key) + u"=" + _unicode_quote(value)
                          for (key, value) in self.items())

    def __repr__(self):
        attrs = dict()
        for key, value in self.items():
            attrs.setdefault(key, list()).append(value)
        return self.__class__.__name__ + "(" + repr(attrs) + ")"

@idiokit.stream
def stanzas_to_events():
    while True:
        element = yield idiokit.next()

        for child in element.children():
            event = Event.from_element(child)
            if event is not None:
                yield idiokit.send(event)

@idiokit.stream
def events_to_elements(include_body=True):
    while True:
        event = yield idiokit.next()

        if include_body:
            body = Element("body")
            body.text = _escape(unicode(event))
            yield idiokit.send(body, event.to_element())
        else:
            yield idiokit.send(event.to_element())

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
        attrs = dict()
        for key, value in event.items():
            attrs.setdefault(key, list()).append(value)
        self.gz.write(repr(attrs) + os.linesep)

    def purge(self):
        """
        >>> collector = EventCollector()

        >>> event = Event()
        >>> event.add("1", "2")
        >>> collector.append(event)

        >>> event2 = Event()
        >>> event2.add("x", "y")
        >>> collector.append(event2)

        >>> collector.append(event)
        >>> list(collector.purge()) == [event, event2, event]
        True
        """

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
                        event.update(key, values)
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
