from __future__ import absolute_import, unicode_literals

import re

from . import core
from . import iprange


class Atom(core.Matcher):
    def match(self, value):
        return False


class String(Atom):
    def init(self, value):
        Atom.init(self)

        self._value = unicode(value)

    def unique_key(self):
        return self._value

    def arguments(self):
        return [self._value], []

    @property
    def value(self):
        return self._value

    def match(self, value):
        return self._value.lower() == value.lower()

    def dump(self):
        return self._value

    @classmethod
    def load(cls, value):
        return cls(value)


class RegExp(Atom):
    _forbidden_flags = [
        (re.X, "re.X / re.VERBOSE"),
        (re.M, "re.M / re.MULTILINE"),
        (re.L, "re.L / re.LOCALE")
    ]

    @classmethod
    def from_re(cls, re_obj):
        for flag, name in cls._forbidden_flags:
            if re_obj.flags & flag == flag:
                raise ValueError("forbidden regular expression flag " + name)

        ignore_case = (re_obj.flags & re.I) != 0
        return cls(re_obj.pattern, ignore_case=ignore_case)

    @property
    def pattern(self):
        return self._regexp.pattern

    @property
    def ignore_case(self):
        return self._regexp.flags & re.I != 0

    def init(self, pattern, ignore_case=False):
        Atom.init(self)

        flags = re.U | re.S | (re.I if ignore_case else 0)
        self._regexp = re.compile(pattern, flags)

    def unique_key(self):
        return self._regexp.pattern, bool(self._regexp.flags & re.I)

    def arguments(self):
        keys = []
        if self._regexp.flags & re.I == re.I:
            keys.append(("ignore_case", True))
        return [self._regexp.pattern], keys

    def match(self, value):
        return self._regexp.search(value)

    def dump(self):
        return self._regexp.pattern, bool(self._regexp.flags & re.I)

    @classmethod
    def load(cls, (pattern, ignore_case)):
        return cls(pattern, ignore_case)


class IP(Atom):
    @property
    def range(self):
        return self._range

    def init(self, range, extra=None):
        Atom.init(self)

        if isinstance(range, iprange.IPRange):
            if extra is not None:
                raise TypeError("unexpected second argument")
        else:
            range = iprange.IPRange.from_autodetected(range, extra)
        self._range = range

    def unique_key(self):
        return self._range

    def arguments(self):
        return [unicode(self._range)], []

    def __unicode__(self):
        return unicode(self._range)

    def match(self, value):
        try:
            range = iprange.IPRange.from_autodetected(value)
        except ValueError:
            return False
        return self._range.contains(range)

    def dump(self):
        return unicode(self._range)

    @classmethod
    def load(cls, value):
        return cls(value)
