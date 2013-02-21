from __future__ import absolute_import

import re

from . import core
from . import atoms


class Rule(core.Matcher):
    def match(self, obj, cache=None):
        if cache is None:
            cache = dict()
        elif self in cache:
            return cache[self]

        result = self.match_with_cache(obj, cache)
        cache[obj] = result
        return result

    def match_with_cache(self, obj, cache):
        return False


class And(Rule):
    def __init__(self, first, *rest):
        self._rules = (first,) + rest

        Rule.__init__(self, frozenset(self._rules))

    @property
    def subrules(self):
        return self._rules

    def match_with_cache(self, obj, cache):
        for rule in self.subrules:
            if not rule.match(obj, cache):
                return False
        return True


class Or(And):
    def match_with_cache(self, obj, cache):
        for rule in self.subrules:
            if rule.match(obj, cache):
                return True
        return False


class No(Rule):
    def __init__(self, rule):
        Rule.__init__(self, (rule,))

        self._rule = rule

    @property
    def subrule(self):
        return self._rule

    def match_with_cache(self, obj, cache):
        return not self._rule.match(obj, cache)


class Match(Rule):
    atom_conversions = [
        (type(None), lambda x: atoms.Star()),
        (basestring, atoms.String),
        (type(re.compile(".")), atoms.RegExp.from_re)
    ]

    star = atoms.Star()

    def _convert(self, obj):
        for converted_type, conversion_func in self.atom_conversions:
            if isinstance(obj, converted_type):
                return conversion_func(obj)
        return obj

    def __init__(self, key=None, value=None):
        key = self._convert(key)
        value = self._convert(value)

        if key == self.star and value == self.star:
            Rule.__init__(self)
        elif key == self.star:
            Rule.__init__(self, (), (("value", value),))
        elif value == self.star:
            Rule.__init__(self, (key,))
        else:
            Rule.__init__(self, (key, value))

        self._key = key
        self._value = value

    @property
    def key(self):
        return self._key

    @property
    def value(self):
        return self._value

    def match_with_cache(self, event, cache):
        if self._key == self.star:
            return event.contains(filter=self.filter)
        return event.contains(self._key.value, filter=self.filter)

    def filter(self, value):
        return self.value.match(value)


class NonMatch(Match):
    def filter(self, value):
        return not self.value.match(value)


class Fuzzy(Rule):
    @property
    def atom(self):
        return self._atom

    def __init__(self, atom):
        Rule.__init__(self, (atom,))

        self._atom = atom
        self._is_key_type = isinstance(atom, atoms.String)

    def match_with_cache(self, event, cache):
        if self._is_key_type:
            if any(self._atom.match, event.keys()):
                return True
        if event.contains(filter=self._atom.match):
            return True
        return False
