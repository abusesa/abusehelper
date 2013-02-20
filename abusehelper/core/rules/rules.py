from __future__ import absolute_import

import re

from .core import Matcher
from . import atoms
from .parser import Parser, RegExp, Sequence, OneOf, ForwardRef, transform


__all__ = [
    "Rule",
    "And", "Or", "No",
    "Match", "NonMatch",
    "Fuzzy",
    "parse", "rule"
]


def parens(parser):
    return Sequence(
        RegExp(r"\(\s*"),
        parser,
        RegExp(r"\s*\)")
    ).take(1)


class Rule(Matcher):
    precedence = float("inf")

    @classmethod
    def parser(self, rule_parser):
        raise NotImplementedError()

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


class RuleParser(Parser):
    def __init__(self, *rules):
        refs = {}
        for rule in set(rules):
            refs[rule] = ForwardRef()

        self._rules = []
        for rule in sorted(rules, key=lambda x: x.precedence):
            self._rules.append((rule, refs[rule]))

        self._expr = ForwardRef()
        parsers = [ref for (_, ref) in self._rules] + [parens(self._expr)]
        self._expr.set(OneOf(*parsers))

        for rule, ref in self._rules:
            ref.set(rule.parser(self))

    def expr(self, filter=None):
        if filter is None:
            return self._expr

        filtered = []
        for rule, parser in self._rules:
            if filter(rule):
                filtered.append(parser)
        filtered.append(parens(self._expr))

        return OneOf(*filtered)

    def parse(self, string):
        return self._expr.parse(string.strip())


class BinaryRule(Rule):
    precedence = 0

    name = "binary"

    @classmethod
    def parser(cls, rule_parser):
        whitespace = RegExp(r"\s+")
        higher = rule_parser.expr(lambda x: x.precedence > cls.precedence)

        pattern = Sequence(
            OneOf(
                Sequence(higher, whitespace).take(0),
                parens(rule_parser.expr())
            ),

            RegExp(re.escape(cls.name), re.I),

            OneOf(
                Sequence(
                    whitespace,
                    rule_parser.expr(lambda x: x.precedence >= cls.precedence)
                ).take(1),
                parens(rule_parser.expr())
            )
        ).take(0, 2)

        @transform(pattern)
        def create((left, right)):
            return cls(left, right)
        return create

    def __init__(self, first, *rest):
        self._rules = (first,) + rest

        Rule.__init__(self, frozenset(self._rules))

    def __unicode__(self):
        texts = []
        for rule in self._rules:
            text = unicode(rule)
            if type(rule) != type(self):
                if rule.precedence <= self.precedence:
                    text = "(" + text + ")"
            texts.append(text)
        return (u" " + self.name + u" ").join(texts)


class And(BinaryRule):
    name = "and"

    def match_with_cache(self, obj, cache):
        for rule in self._rules:
            if not rule.match(obj, cache):
                return False
        return True


class Or(BinaryRule):
    name = "or"

    def match_with_cache(self, obj, cache):
        for rule in self._rules:
            if rule.match(obj, cache):
                return True
        return False


class No(Rule):
    precedence = 1

    @classmethod
    def parser(cls, rule_parser):
        pattern = Sequence(
            RegExp(r"no", re.I),
            OneOf(
                parens(rule_parser.expr()),
                Sequence(
                    RegExp(r"\s+"),
                    rule_parser.expr(lambda x: x.precedence >= cls.precedence)
                ).take(1)
            )
        ).take(1)

        @transform(pattern)
        def create(rule):
            return cls(rule)
        return create

    def __init__(self, rule):
        Rule.__init__(self, (rule,))

        self._rule = rule

    def match_with_cache(self, obj, cache):
        return not self._rule.match(obj, cache)

    def __unicode__(self):
        text = unicode(self._rule)
        if self._rule.precedence < self.precedence:
            text = u"(" + text + u")"
        return u"no " + text


class Match(Rule):
    precedence = 2

    atom_conversions = [
        (type(None), lambda x: atoms.Star()),
        (basestring, atoms.String),
        (type(re.compile(".")), atoms.Rex.from_re)
    ]

    atom_types = tuple([
        atoms.Star,
        atoms.Rex,
        atoms.String,
        atoms.IP
    ])

    atom_info = {
        atoms.Star: ("=", RegExp(r"\s*==?\s*")),
        atoms.Rex: ("=", RegExp(r"\s*==?\s*")),
        atoms.String: ("=", RegExp(r"\s*==?\s*")),
        atoms.IP: (" in ", RegExp(r"\s+in\s+", re.I))
    }

    star = atoms.Star()

    @classmethod
    def parser(cls, _):
        @transform(atoms.Star.parser())
        def key_star(_):
            return None

        @transform(atoms.String.parser())
        def key_string(string):
            return string.value

        atom_patterns = []
        for atom_type in cls.atom_types:
            _, atom_pattern = cls.atom_info[atom_type]
            atom_patterns.append(Sequence(
                atom_pattern, atom_type.parser()
            ).take(1))

        pattern = Sequence(
            OneOf(key_star, key_string),
            OneOf(*atom_patterns)
        )

        @transform(pattern)
        def create((key, value)):
            return cls(key, value)
        return create

    def __init__(self, key=None, value=None):
        for converted_type, conversion_func in self.atom_conversions:
            if isinstance(value, converted_type):
                value = conversion_func(value)

        if not isinstance(value, self.atom_types):
            raise TypeError("unexpected value " + repr(value))

        if key is None and value == self.star:
            Rule.__init__(self)
        elif key is None:
            Rule.__init__(self, (), (("value", value),))
        elif value == self.star:
            Rule.__init__(self, (key,))
        else:
            Rule.__init__(self, (key, value))

        self._key = key
        self._value = value

    def __unicode__(self):
        if self._key is None:
            key = "*"
        else:
            key = self._key
        op, _ = self.atom_info[type(self._value)]
        return key + unicode(op) + unicode(self._value)

    def match_with_cache(self, event, cache):
        if self._key is None:
            return event.contains(filter=self.filter)
        return event.contains(self._key, filter=self.filter)

    def filter(self, value):
        return self._value.match(value)


class NonMatch(Match):
    atom_info = {
        atoms.Star: ("!=", RegExp(r"\s*!=\s*")),
        atoms.Rex: ("!=", RegExp(r"\s*!=\s*")),
        atoms.String: ("!=", RegExp(r"\s*!=\s*")),
        atoms.IP: (" not in ", RegExp(r"\s+not\s+in\s+", re.I))
    }

    def filter(self, value):
        return not self._value.match(value)


class Fuzzy(Rule):
    precedence = 3

    atom_types = tuple([
        atoms.IP,
        atoms.Rex,
        atoms.String
    ])

    @classmethod
    def parser(cls, _):
        @transform(OneOf(*[x.parser() for x in cls.atom_types]))
        def create(result):
            return cls(result)
        return create

    def __init__(self, atom):
        Rule.__init__(self, (atom,))

        self._atom = atom
        self._is_key_type = isinstance(atom, atoms.String)
        self._is_value_type = isinstance(atom, self.atom_types)

    def match_with_cache(self, event, cache):
        if self._is_key_type:
            if any(self._atom.match, event.keys()):
                return True
        if self._is_atom_type:
            if event.contains(filter=self._atom.match):
                return True
        return False

    def __unicode__(self):
        return unicode(self._atom)


_rule_parser = RuleParser(
    And,
    Or,
    No,
    Match,
    NonMatch,
    Fuzzy
)


def parse(string):
    string = unicode(string)

    parsed = _rule_parser.parse(string)
    if parsed and not parsed[1]:
        return parsed[0]
    raise ValueError("can not parse rule " + repr(string))


def rule(obj):
    if isinstance(obj, basestring):
        return parse(obj)
    return obj
