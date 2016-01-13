import re
from itertools import izip
from encodings import idna


# A regular expression for checking a validity of a ASCII domain name label.
_LABEL_REX = re.compile(r"^[a-z0-9](?:[\-a-z0-9]{0,61}[a-z0-9])?$")


def parse_name(string):
    r"""
    Return domain name as a tuple of unicode labels parsed from the given
    unicode string.

    >>> parse_name(u"domain.example")
    (u'domain', u'example')

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

    labels = string.split(".")

    # Don't accept plain top-level domains.
    if len(labels) < 2:
        return None

    try:
        # Note: idna.ToASCII also enforces the minimum and maximum label length.
        labels = map(idna.ToASCII, string.split("."))
    except UnicodeError:
        return None

    if len(labels) + sum(len(x) for x in labels) > 253:
        return None

    if labels[-1].isdigit():
        return None
    if not all(_LABEL_REX.match(x) for x in labels):
        return None

    return tuple(idna.ToUnicode(x) for x in labels)


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


class Pattern(object):
    def __init__(self, free, labels):
        self._hash = None
        self._labels = tuple(labels)
        self._length = free + len(self._labels)

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
            self._hash = hash(Pattern) ^ hash(self._length) ^ hash(self._labels)
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
        return self._length == other._length and self._labels == other._labels

    def __ne__(self, other):
        eq = self.__eq__(other)
        if eq is NotImplemented:
            return NotImplemented
        return not eq

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
