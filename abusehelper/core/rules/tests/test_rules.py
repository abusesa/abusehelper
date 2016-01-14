from __future__ import unicode_literals

import re
import pickle
import unittest

from ..atoms import String, RegExp, IP, DomainName
from ..rules import And, Or, No, Match, NonMatch, Fuzzy

from ...events import Event


class TestRules(unittest.TestCase):
    def test_results_should_get_cached(self):
        rule = Match("a", "a")
        cache = {}
        rule.match(Event(), cache)
        self.assertTrue(rule in cache)
        self.assertFalse(cache[rule])

    def test_cached_results_should_get_used(self):
        rule = Match("a", "a")
        cache = {rule: True}
        self.assertTrue(rule.match(Event(), cache))


class TestAnd(unittest.TestCase):
    def test_can_not_be_initialized_with_zero_arguments(self):
        self.assertRaises(TypeError, And)

    def test_commutativity(self):
        a = Match("a", "a")
        b = Match("b", "b")
        self.assertEqual(And(a, b), And(b, a))

    def test_redundant_arguments_get_deduplicated(self):
        a = Match("a", "a")
        self.assertEqual(And(a, a), And(a))

    _options = [
        And(Match("a"), Match("b"))
    ]

    def test_pickling_and_unpickling(self):
        for option in self._options:
            self.assertEqual(option, pickle.loads(pickle.dumps(option)))

    def test_repr(self):
        for option in self._options:
            self.assertEqual(option, eval(repr(option)))


class TestOr(unittest.TestCase):
    def test_can_not_be_initialized_with_zero_arguments(self):
        self.assertRaises(TypeError, Or)

    def test_commutativity(self):
        a = Match("a", "a")
        b = Match("b", "b")
        self.assertEqual(Or(a, b), Or(b, a))

    def test_redundant_arguments_get_deduplicated(self):
        a = Match("a", "a")
        self.assertEqual(Or(a, a), Or(a))

    _options = [
        Or(Match("a"), Match("b"))
    ]

    def test_pickling_and_unpickling(self):
        for option in self._options:
            self.assertEqual(option, pickle.loads(pickle.dumps(option)))

    def test_repr(self):
        for option in self._options:
            self.assertEqual(option, eval(repr(option)))


class TestNo(unittest.TestCase):
    _options = [
        No(Match("a"))
    ]

    def test_pickling_and_unpickling(self):
        for option in self._options:
            self.assertEqual(option, pickle.loads(pickle.dumps(option)))

    def test_repr(self):
        for option in self._options:
            self.assertEqual(option, eval(repr(option)))


class TestMatch(unittest.TestCase):
    def test_init_conversions(self):
        self.assertEqual(
            Match("a", "b"),
            Match("a", String("b")))
        self.assertEqual(
            Match("a", re.compile("b")),
            Match("a", RegExp("b")))

    def test_domainname(self):
        matcher = Match("a", DomainName("*.example"))
        self.assertTrue(matcher.match(Event({"a": "domain.example"})))
        self.assertTrue(matcher.match(Event({"a": "sub.domain.example"})))
        self.assertFalse(matcher.match(Event({"a": "*.example"})))
        self.assertFalse(matcher.match(Event({"a": "*.domain.example"})))
        self.assertFalse(matcher.match(Event({"a": "domain.test"})))

    _options = [
        Match(),
        Match("a", String("b")),
        Match("a", RegExp("b")),
        Match("a", IP("192.0.2.0")),
        Match("a", DomainName("*.example"))
    ]

    def test_pickling_and_unpickling(self):
        for option in self._options:
            self.assertEqual(option, pickle.loads(pickle.dumps(option)))

    def test_repr(self):
        for option in self._options:
            self.assertEqual(option, eval(repr(option)))


class TestNonMatch(unittest.TestCase):
    def test_init_conversions(self):
        self.assertEqual(
            NonMatch("a", "b"),
            NonMatch("a", String("b")))
        self.assertEqual(
            NonMatch("a", re.compile("b")),
            NonMatch("a", RegExp("b")))

    def test_domainname(self):
        matcher = NonMatch("a", DomainName("*.example"))
        self.assertFalse(matcher.match(Event({"a": "domain.example"})))
        self.assertFalse(matcher.match(Event({"a": "sub.domain.example"})))
        self.assertTrue(matcher.match(Event({"a": "*.example"})))
        self.assertTrue(matcher.match(Event({"a": "*.domain.example"})))
        self.assertTrue(matcher.match(Event({"a": "domain.test"})))

    _options = [
        NonMatch(),
        NonMatch("a", String("b")),
        NonMatch("a", RegExp("b")),
        NonMatch("a", IP("192.0.2.0")),
        NonMatch("a", DomainName("*.example"))
    ]

    def test_pickling_and_unpickling(self):
        for option in self._options:
            self.assertEqual(option, pickle.loads(pickle.dumps(option)))

    def test_repr(self):
        for option in self._options:
            self.assertEqual(option, eval(repr(option)))


class TestFuzzy(unittest.TestCase):
    def test_base(self):
        rule = Fuzzy(String("a"))
        self.assertTrue(rule.match(Event({"a": "xy"})))
        self.assertTrue(rule.match(Event({"xy": "a"})))
        self.assertTrue(rule.match(Event({"ba": "xy"})))
        self.assertTrue(rule.match(Event({"xy": "ba"})))
        self.assertFalse(rule.match(Event({"xy": "xy"})))

        # Fuzzy String matching is case-insensitive
        self.assertTrue(rule.match(Event({"A": "xy"})))
        self.assertTrue(rule.match(Event({"xy": "A"})))

        rule = Fuzzy(RegExp("a"))
        self.assertTrue(rule.match(Event({"a": "xy"})))
        self.assertTrue(rule.match(Event({"xy": "a"})))
        self.assertTrue(rule.match(Event({"ba": "xy"})))
        self.assertTrue(rule.match(Event({"xy": "ba"})))
        self.assertFalse(rule.match(Event({"xy": "xy"})))

        # Fuzzy RegExp matching is not case-insensitive by default
        self.assertFalse(rule.match(Event({"A": "xy"})))
        self.assertFalse(rule.match(Event({"xy": "A"})))

    _options = [
        Fuzzy(String("a")),
        Fuzzy(RegExp("a")),
        Fuzzy(IP("192.0.2.0")),
        Fuzzy(DomainName("*.example"))
    ]

    def test_pickling_and_unpickling(self):
        for option in self._options:
            self.assertEqual(option, pickle.loads(pickle.dumps(option)))

    def test_repr(self):
        for option in self._options:
            self.assertEqual(option, eval(repr(option)))
