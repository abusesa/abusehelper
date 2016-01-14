import re
from itertools import izip
from encodings import idna

from . import parsing


# A regular expression for checking a validity of a ASCII domain name label.
_LABEL_REX = re.compile(r"^[a-z0-9](?:[\-a-z0-9]{0,61}[a-z0-9])?$")


def _parse_labels(string):
    try:
        # Note: idna.ToASCII also enforces the minimum and maximum label length.
        labels = tuple(idna.ToASCII(x).lower() for x in string.split(u"."))
    except UnicodeError:
        return None

    if len(labels) + sum(len(x) for x in labels) > 253:
        return None

    if labels[-1].isdigit():
        return None
    if not all(_LABEL_REX.match(x) for x in labels):
        return None

    return tuple(idna.ToUnicode(x) for x in labels)


def parse_name(string):
    r"""
    Return domain name as a tuple of unicode labels parsed from the given
    unicode string.

    >>> parse_name(u"domain.example")
    (u'domain', u'example')

    Internationalized domain names are supported. To normalize the labels they
    are run through idna.ToASCII and lowercased.

    >>> parse_name(u"DOMAIN.example")
    (u'domain', u'example')
    >>> parse_name(u"\xe4.example")
    (u'\xe4', u'example')
    >>> parse_name(u"\xc4.example")
    (u'\xe4', u'example')
    >>> parse_name(u"xn--4ca.example")
    (u'\xe4', u'example')

    Return None if the string is not a well-formed domain name. For example the
    name must honor the maximum name length (253 characters, including periods)
    and label length limits (1-63 characters).

    >>> parse_name(u"a." * 128 + u"example")
    >>> parse_name(u"a" * 64 + u".example")
    >>> parse_name(u"domain..example")

    After unicode labels have been run through the IDNA ToASCII transformation
    additional restrictions outlined in RFC 3696, section 2 are applied:

      * Labels must consist only of ASCII alphabetic characters

        >>> parse_name(u"a domain.example")

      * A hyphen is not permitted to appear at either the beginning or end of a label.

        >>> parse_name(u"-domain.example")
        >>> parse_name(u"domain-.example")

      * The a top-level domain should not be all-numeric.

        >>> parse_name(u"domain.example.123")

    As a special limitation plain top-level domains are not accepted.

    >>> parse_name(u"example")
    """

    # Don't accept plain top-level domains.
    if "." not in string:
        return None
    return _parse_labels(string)


def _issubdomain(name, pattern_labels):
    r"""
    _issubdomain(["a", "b", "c"], ["b", "c"])
    True
    _issubdomain(["a", "x", "c"], ["b", "c"])
    True
    _issubdomain(["a", "b", "c"], ["b", "x"])
    False
    _issubdomain(["b", "c"], ["a", "b", "c"])
    False

    Every name matches the empty pattern.

    _issubdomain(["a", "b", "c"], [])
    True
    _issubdomain([], [])
    True

    Empty name matches to nothing but the empty pattern.

    _issubdomain([], ["b", "c"])
    False
    """

    if len(pattern_labels) > len(name):
        return False

    for left, right in izip(reversed(name), reversed(pattern_labels)):
        if left != right:
            return False

    return True


class _PatternParser(parsing.Parser):
    r"""
    A parser for domain name patterns.

    >>> parser = _PatternParser()
    >>> parser.parse("domain.example") == (Pattern(0, ["domain", "example"]), "")
    True
    >>> parser.parse("*.domain.example") == (Pattern(1, ["domain", "example"]), "")
    True

    Only the matching prefix should be consumed.

    >>> parser.parse("domain.example test") == (Pattern(0, ["domain", "example"]), " test")
    True

    To same rules and normalizations apply to the non-wildcard labels as with
    parse_name, with one exception: A plain top-level domain is allowed when it
    follows at least one wildcard label.

    >>> parser.parse("*.example") == (Pattern(1, ["example"]), "")
    True

    Wildcards are only accepted in the beginning of the pattern and the pattern has
    to end with a non-wildcard part.

    >>> parser.parse("domain.*.example")
    >>> parser.parse("*.*")
    """

    _PATTERN_REX = re.compile(r"(?:[^\.\*\s]+\.)*[^\.\*\s]+")

    def parse_gen(self, (string, start, end)):
        free = 0
        while string.startswith("*.", start, end):
            free += 1
            start += 2

        match = self._PATTERN_REX.match(string, start, end)
        if not match:
            yield None, None

        labels = _parse_labels(match.group(0))
        if labels is None or free + len(labels) < 2:
            yield None, None

        yield None, (Pattern(free, labels), (string, match.end(), end))


pattern_parser = _PatternParser()


class Pattern(object):
    @classmethod
    def from_string(cls, string):
        r"""
        Return a pattern parsed from a string.

        >>> Pattern.from_string("*.example") == Pattern(1, ["example"])
        True

        Raise ValueError if the string is not a valid domain name pattern.

        >>> Pattern.from_string("this is not a pattern")
        Traceback (most recent call last):
            ...
        ValueError: ...

        Non-unicode strings will be decoded using the default "ascii" encoding.

        >>> Pattern.from_string("\xe4")
        Traceback (most recent call last):
            ...
        UnicodeDecodeError: ...
        """

        result = pattern_parser.parse(unicode(string).strip())
        if result is not None:
            pattern, suffix = result
            if not suffix:
                return pattern
        raise ValueError("not a valid domain name pattern")

    def __init__(self, free, labels):
        self._hash = None
        self._free = free
        self._labels = tuple(labels)
        self._length = self._free + len(self._labels)

    def __hash__(self):
        r"""
        >>> s = set([Pattern(0, ["a", "b"])])
        >>> Pattern(0, ["a", "b"]) in s
        True
        >>> Pattern(1, ["a", "b"]) in s
        False
        >>> Pattern(0, ["x", "y"]) in s
        False
        """

        if self._hash is None:
            self._hash = hash(Pattern) ^ hash(self._free) ^ hash(self._labels)
        return self._hash

    def __eq__(self, other):
        r"""
        >>> Pattern(0, ["a", "b"]) == Pattern(0, ["a", "b"])
        True
        >>> Pattern(0, ["a", "b"]) == Pattern(1, ["a", "b"])
        False
        >>> Pattern(0, ["a", "b"]) == Pattern(0, ["x", "y"])
        False
        """

        if not isinstance(other, Pattern):
            return NotImplemented
        return self._free == other._free and self._labels == other._labels

    def __ne__(self, other):
        eq = self.__eq__(other)
        if eq is NotImplemented:
            return NotImplemented
        return not eq

    def __unicode__(self):
        r"""
        Return the pattern formatted as an unicode object.

        >>> unicode(Pattern(1, ["example"]))
        u'*.example'
        >>> unicode(Pattern(0, ["domain", "example"]))
        u'domain.example'
        """

        return u"*." * self._free + ".".join(self._labels)

    def contains(self, name):
        r"""
        >>> p = Pattern(0, ["example"])
        >>> p.contains(["example"])
        True
        >>> p.contains(["domain", "example"])
        True
        >>> p.contains(["sub", "domain", "example"])
        True
        >>> p.contains(["other"])
        False

        >>> p = Pattern(1, ["example"])
        >>> p.contains(["example"])
        False
        >>> p.contains(["domain", "example"])
        True
        >>> p.contains(["sub", "domain", "example"])
        True
        """

        if len(name) < self._length:
            return False
        return _issubdomain(name, self._labels)

    def matches(self, name):
        r"""
        >>> p = Pattern(0, ["example"])
        >>> p.matches(["example"])
        True
        >>> p.matches(["domain", "example"])
        False
        >>> p.matches(["other"])
        False

        >>> p = Pattern(1, ["example"])
        >>> p.matches(["example"])
        False
        >>> p.matches(["domain", "example"])
        True
        >>> p.matches(["sub", "domain", "example"])
        False
        """

        if len(name) != self._length:
            return False
        return _issubdomain(name, self._labels)
