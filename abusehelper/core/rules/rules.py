from __future__ import absolute_import

import re

from . import core
from . import atoms


class Rule(core.Matcher):
    def match(self, obj, cache=None):
        if cache is None:
            cache = dict()

        result = cache.get(self, None)
        if result is None:
            result = self.match_with_cache(obj, cache)
            cache[self] = bool(result)
        return result

    def match_with_cache(self, obj, cache):
        return False


class And(Rule):
    def init(self, first, *rest):
        Rule.init(self)

        self._rules = frozenset((first,) + rest)

    def unique_key(self):
        return self._rules

    def arguments(self):
        return self._rules, []

    @property
    def subrules(self):
        return self._rules

    def match_with_cache(self, obj, cache):
        for rule in self.subrules:
            if not rule.match(obj, cache):
                return False
        return True

    def dump(self):
        return self._rules

    @classmethod
    def load(cls, subrules):
        return cls(*subrules)


class Or(And):
    def match_with_cache(self, obj, cache):
        for rule in self.subrules:
            if rule.match(obj, cache):
                return True
        return False


class No(Rule):
    def init(self, rule):
        Rule.init(self)

        self._rule = rule

    def unique_key(self):
        return self._rule

    def arguments(self):
        return [self._rule], []

    @property
    def subrule(self):
        return self._rule

    def match_with_cache(self, obj, cache):
        return not self._rule.match(obj, cache)

    def dump(self):
        return self._rule

    @classmethod
    def load(cls, rule):
        return cls(rule)


class Anything(Rule):
    def match_with_cache(self, obj, cache):
        return True


class Match(Rule):
    _to_atom = [
        (basestring, atoms.String),
        (type(re.compile(".")), atoms.RegExp.from_re)
    ]

    _from_atom = [
        (atoms.String, lambda x: x.value)
    ]

    def _convert(self, obj, conversions):
        for converted_type, conversion_func in conversions:
            if isinstance(obj, converted_type):
                return conversion_func(obj)
        return obj

    def init(self, key=None, value=None):
        Rule.init(self)

        self._key = self._convert(key, self._to_atom)
        self._value = self._convert(value, self._to_atom)

    def unique_key(self):
        return self._key, self._value

    def arguments(self):
        key = self._convert(self._key, self._from_atom)
        value = self._convert(self._value, self._from_atom)

        if key is None and value is None:
            return [], []
        if key is None:
            return [], [("value", value)]
        if value is None:
            return [], [("key", key)]
        return [key, value], []

    @property
    def key(self):
        return self._key

    @property
    def value(self):
        return self._value

    def match_with_cache(self, event, cache):
        if self._key is None:
            return event.contains(filter=self.filter)
        return event.contains(self._key.value, filter=self.filter)

    def filter(self, value):
        return self._value is None or self._value.match(value)

    def dump(self):
        return (self._key, self._value)

    @classmethod
    def load(cls, (key, value)):
        return cls(key, value)


class NonMatch(Match):
    def filter(self, value):
        return self._value is None or not self._value.match(value)


class Fuzzy(Rule):
    @property
    def atom(self):
        return self._atom

    def init(self, atom):
        Rule.init(self)

        self._atom = atom
        self._is_key_type = isinstance(atom, atoms.String)

    def unique_key(self):
        return self._atom

    def arguments(self):
        return [self._atom], []

    def match_with_cache(self, event, cache):
        if self._is_key_type:
            if any(self._atom.match(x) for x in event.keys()):
                return True
        if event.contains(filter=self._atom.match):
            return True
        return False

    def dump(self):
        return self._atom

    @classmethod
    def load(cls, dumped):
        return cls(dumped)

