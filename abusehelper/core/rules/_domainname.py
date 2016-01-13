from itertools import izip


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
