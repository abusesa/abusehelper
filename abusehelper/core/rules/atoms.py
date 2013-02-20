from __future__ import absolute_import, unicode_literals

import re
import json

from .core import Matcher
from .parser import RegExp, OneOf, transform
from .iprange import IPRange


__all__ = ["String", "Rex", "IP"]


class Atom(Matcher):
    @classmethod
    def parser(cls):
        return cls()

    def match(self, value):
        return False


class String(Atom):
    escapes = {
        "\f": "\\f",
        "\b": "\\b",
        "\n": "\\n",
        "\r": "\\r",
        "\t": "\\t",
        "\\": "\\\\",
        "\"": "\\\""
    }

    unquoted = RegExp(r"([^\s\\\(\)\"\*!=/]+)").take(0)

    @classmethod
    def parser(cls):
        @transform(RegExp(r'("(?:\\u[0-9a-f]{4}|\\[\\"/fbnrt]|[^\\"])*")', re.I))
        def quoted(groups):
            return json.loads(groups[0])

        @transform(OneOf(cls.unquoted, quoted))
        def create(string):
            return cls(string)
        return create

    def __init__(self, value):
        self._value = unicode(value)

        Atom.__init__(self, (self._value,))

    @property
    def value(self):
        return self._value

    def __unicode__(self):
        parsed = self.unquoted.parse(self._value)
        if parsed and parsed[1] == "":
            return self._value

        result = [self.escapes.get(ch, ch) for ch in self._value]
        return "\"" + "".join(result) + "\""

    def match(self, value):
        return self._value.lower() == value.lower()


class Rex(Atom):
    _forbidden_flags = [
        (re.X, "re.X / re.VERBOSE"),
        (re.M, "re.M / re.MULTILINE"),
        (re.L, "re.L / re.LOCALE")
    ]

    @classmethod
    def parser(cls):
        @transform(RegExp(r'/((?:\\.|[^\\/])*)/(i)?'))
        def create(groups):
            pattern = groups[0]
            ignore_case = groups[1] is not None

            try:
                return cls(pattern, ignore_case=ignore_case)
            except re.error:
                return None
        return create

    @classmethod
    def from_re(cls, re_obj):
        for flag, name in cls._forbidden_flags:
            if re_obj.flags & flag == flag:
                raise ValueError("forbidden regular expression flag " + name)

        ignore_case = (re_obj.flags & re.I) != 0
        return cls(re_obj.pattern, ignore_case=ignore_case)

    def __init__(self, pattern, ignore_case=False):
        flags = re.U | re.S | (re.I if ignore_case else 0)
        self._regexp = re.compile(pattern, flags)

        args = (self._regexp.pattern,)
        if not ignore_case:
            Atom.__init__(self, args)
        else:
            Atom.__init__(self, args, (("ignore_case", ignore_case,)))

    _escape_slash_rex = re.compile(r"((?:^|[^\\])(?:\\\\)*?)(\/)", re.U)

    def _escape_slash(self, match):
        return match.group(1) + "\\" + match.group(2)

    def __unicode__(self):
        pattern = self._regexp.pattern
        pattern = self._escape_slash_rex.sub(self._escape_slash, pattern)

        result = "/" + pattern + "/"
        if (self._regexp.flags & re.I) != 0:
            result += "i"
        return result

    def match(self, value):
        return self._regexp.search(value)


class Star(Atom):
    @classmethod
    def parser(cls):
        @transform(RegExp(r'\*'))
        def create(_):
            return cls()
        return create

    def __init__(self):
        Atom.__init__(self)

    def __unicode__(self):
        return u"*"

    def match(self, value):
        return True


class IP(Atom):
    @classmethod
    def parser(cls):
        @transform(IPRange.parser())
        def create(range):
            return cls(range)
        return create

    def __init__(self, range, extra=None):
        if isinstance(range, IPRange):
            if extra is not None:
                raise TypeError("unexpected second argument")
        else:
            range = IPRange.from_autodetected(range, extra)

        Atom.__init__(self, (unicode(range),))

        self._range = range

    def __unicode__(self):
        return unicode(self._range)

    def match(self, value):
        try:
            range = IPRange.from_autodetected(value)
        except ValueError:
            return False
        return self._range.contains(range)
