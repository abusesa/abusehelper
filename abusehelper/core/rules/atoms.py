from __future__ import absolute_import, unicode_literals

import re

from . import core
from . import iprange
from . import _domainname


class Atom(core.Matcher):
    def match(self, value):
        return False


class String(Atom):
    def init(self, value):
        Atom.init(self)

        self._value = unicode(value)

    def unique_key(self):
        return self._value

    def __repr__(self):
        return Atom.__repr__(self, self._value)

    @property
    def value(self):
        return self._value

    def match(self, value):
        return self._value == value

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
    def from_string(cls, string, ignore_case=False):
        return cls(re.escape(string), ignore_case=ignore_case)

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
        return self._regexp.flags & re.IGNORECASE != 0

    def init(self, pattern, ignore_case=False):
        Atom.init(self)

        flags = re.U | re.S | (re.I if ignore_case else 0)
        try:
            self._regexp = re.compile(pattern, flags)
        except re.error as error:
            raise ValueError(error)

    def unique_key(self):
        return self._regexp.pattern, bool(self._regexp.flags & re.I)

    def __repr__(self):
        pattern = self._regexp.pattern
        if self._regexp.flags & re.IGNORECASE == re.I:
            return Atom.__repr__(self, pattern, ignore_case=True)
        return Atom.__repr__(self, pattern)

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

    def __repr__(self):
        return Atom.__repr__(self, unicode(self._range))

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


class DomainName(Atom):
    @property
    def pattern(self):
        return self._pattern

    def init(self, pattern):
        Atom.init(self)

        if not isinstance(pattern, _domainname.Pattern):
            pattern = _domainname.Pattern.from_string(pattern)
        self._pattern = pattern

    def unique_key(self):
        return self._pattern

    def __repr__(self):
        return Atom.__repr__(self, unicode(self._pattern))

    def __unicode__(self):
        return unicode(self._pattern)

    def match(self, value):
        name = _domainname.parse_name(value)
        if name is None:
            return False
        return self._pattern.contains(name)

    def dump(self):
        return unicode(self._pattern)

    @classmethod
    def load(cls, value):
        return cls(value)
