from itertools import izip


class Name(object):
    def __init__(self, labels):
        self._hash = None
        self._labels = tuple(labels)

    def __hash__(self):
        r"""
        >>> s = set([Name(["a", "b", "c"])])
        >>> Name(["a", "b", "c"]) in s
        True
        >>> Name(["x", "y", "z"]) in s
        False
        """

        if self._hash is None:
            self._hash = hash(Name) ^ hash(self._labels)
        return self._hash

    def __eq__(self, other):
        if not isinstance(other, Name):
            return NotImplemented
        return self._labels == other._labels

    def __ne__(self, other):
        eq = self.__eq__(other)
        if eq is NotImplemented:
            return NotImplemented
        return not eq


def _issubdomain(name_labels, pattern_labels):
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

    if len(pattern_labels) > len(name_labels):
        return False

    for left, right in izip(reversed(name_labels), reversed(pattern_labels)):
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
        >>> p.contains(Name(["example"]))
        True
        >>> p.contains(Name(["domain", "example"]))
        True
        >>> p.contains(Name(["sub", "domain", "example"]))
        True
        >>> p.contains(Name(["other"]))
        False

        >>> p = Pattern(1, ["example"])
        >>> p.contains(Name(["example"]))
        False
        >>> p.contains(Name(["domain", "example"]))
        True
        >>> p.contains(Name(["sub", "domain", "example"]))
        True
        """

        if len(name._labels) < self._length:
            return False
        return _issubdomain(name._labels, self._labels)

    def matches(self, name):
        r"""
        >>> p = Pattern(0, ["example"])
        >>> p.matches(Name(["example"]))
        True
        >>> p.matches(Name(["domain", "example"]))
        False
        >>> p.matches(Name(["other"]))
        False

        >>> p = Pattern(1, ["example"])
        >>> p.matches(Name(["example"]))
        False
        >>> p.matches(Name(["domain", "example"]))
        True
        >>> p.matches(Name(["sub", "domain", "example"]))
        False
        """

        if len(name._labels) != self._length:
            return False
        return _issubdomain(name._labels, self._labels)
