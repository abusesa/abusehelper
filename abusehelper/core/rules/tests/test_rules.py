from __future__ import unicode_literals

import re
import pickle
import unittest

from .. import atoms
from ..rules import And, Or, No, Match, NonMatch, Fuzzy

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

    def test_pickling_and_unpickling(self):
        a = And(Match("a"), Match("b"))
        self.assertEqual(a, pickle.loads(pickle.dumps(a)))


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

    def test_pickling_and_unpickling(self):
        a = Or(Match("a"), Match("b"))
        self.assertEqual(a, pickle.loads(pickle.dumps(a)))


class TestNo(unittest.TestCase):
    def test_pickling_and_unpickling(self):
        a = No(Match("a"))
        self.assertEqual(a, pickle.loads(pickle.dumps(a)))


class TestMatch(unittest.TestCase):
    def test_init_conversions(self):
        self.assertEqual(
            Match("a", "b"),
            Match("a", atoms.String("b")))
        self.assertEqual(
            Match("a", re.compile("b")),
            Match("a", atoms.RegExp("b")))

    def test_pickling_and_unpickling(self):
        options = [
            Match(),
            Match("a", "b"),
            Match("a", re.compile("b"))
        ]
        for option in options:
            self.assertEqual(option, pickle.loads(pickle.dumps(option)))


class TestNonMatch(unittest.TestCase):
    def test_init_conversions(self):
        self.assertEqual(
            NonMatch("a", "b"),
            NonMatch("a", atoms.String("b")))
        self.assertEqual(
            NonMatch("a", re.compile("b")),
            NonMatch("a", atoms.RegExp("b")))

    def test_pickling_and_unpickling(self):
        options = [
            NonMatch(),
            NonMatch("a", "b"),
            NonMatch("a", re.compile("b"))
        ]
        for option in options:
            self.assertEqual(option, pickle.loads(pickle.dumps(option)))


class TestFuzzy(unittest.TestCase):
    def test_base(self):
        rule = Fuzzy(atoms.String("a"))
        self.assertTrue(rule.match(Event({"a": "xy"})))
        self.assertTrue(rule.match(Event({"xy": "a"})))

        rule = Fuzzy(atoms.RegExp("a"))
        self.assertFalse(rule.match(Event({"a": "xy"})))
        self.assertTrue(rule.match(Event({"xy": "a"})))

    def test_pickling_and_unpickling(self):
        options = [
            Fuzzy(atoms.String("a")),
            Fuzzy(atoms.RegExp("a"))
        ]
        for option in options:
            self.assertEqual(option, pickle.loads(pickle.dumps(option)))

