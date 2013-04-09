from __future__ import unicode_literals

import re
import unittest

from .. import atoms
from ..rules import And, Or, Match, NonMatch, Fuzzy

from ...events import Event


class TestRules(unittest.TestCase):
    def test_caching(self):
        cache = dict()
        rule = Match("a", "a")
        rule.match(Event(), cache)
        self.assertFalse(cache[rule])


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


class TestNo(unittest.TestCase):
    pass


class TestMatch(unittest.TestCase):
    def test_init_conversions(self):
        self.assertEqual(
            Match('a', 'b'),
            Match('a', atoms.String('b')))
        self.assertEqual(
            Match('a', re.compile('b')),
            Match('a', atoms.RegExp('b')))


class TestNonMatch(unittest.TestCase):
    def test_init_conversions(self):
        self.assertEqual(
            NonMatch('a', 'b'),
            NonMatch('a', atoms.String('b')))
        self.assertEqual(
            NonMatch('a', re.compile('b')),
            NonMatch('a', atoms.RegExp('b')))


class TestFuzzy(unittest.TestCase):
    def test_base(self):
        rule = Fuzzy(atoms.String('a'))
        self.assertTrue(rule.match(Event({"a": "xy"})))
        self.assertTrue(rule.match(Event({"xy": "a"})))

