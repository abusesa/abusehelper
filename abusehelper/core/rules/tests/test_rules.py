from __future__ import unicode_literals

import re
import unittest

from .. import atoms
from ..rules import And, Or, Match, NonMatch, Fuzzy, parse


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

    def test_parsing(self):
        a = Match("a", "a")
        b = Match("b", "b")
        c = Match("c", "c")

        self.assertEqual(And(a, b, c), parse("a=a and b=b and c=c"))
        self.assertEqual(And(a, And(b, c)), parse("a=a and (b=b and c=c)"))
        self.assertEqual(And(And(a, b), c), parse("(a=a and b=b) and c=c"))

        ab = And(a, b)
        self.assertEqual(ab, parse("a=a and b=b"))
        self.assertEqual(ab, parse("(a=a) and (b=b)"))
        self.assertEqual(ab, parse("(a=a)and(b=b)"))


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

    def test_parsing(self):
        a = Match("a", "a")
        b = Match("b", "b")
        c = Match("c", "c")

        self.assertEqual(Or(a, b, c), parse("a=a or b=b or c=c"))
        self.assertEqual(Or(a, Or(b, c)), parse("a=a or (b=b or c=c)"))
        self.assertEqual(Or(Or(a, b), c), parse("(a=a or b=b) or c=c"))

        ab = Or(a, b)
        self.assertEqual(ab, parse("a=a or b=b"))
        self.assertEqual(ab, parse("(a=a) or (b=b)"))
        self.assertEqual(ab, parse("(a=a)or(b=b)"))


class TestNo(unittest.TestCase):
    pass


class TestMatch(unittest.TestCase):
    def test_init_conversions(self):
        self.assertEqual(
            Match('a', 'b'),
            Match('a', atoms.String('b')))
        self.assertEqual(
            Match('a', re.compile('b')),
            Match('a', atoms.Rex('b')))

    def test_parsing(self):
        string = Match('a', 'b')
        self.assertEqual(string, parse('a=b'))
        self.assertEqual(string, parse('a = b'))
        self.assertEqual(string, parse('"\u0061"="\u0062"'))

        rex = Match('a', atoms.Rex('b'))
        self.assertEqual(rex, parse('a=/b/'))

        self.assertEqual(Match("a"), parse("a=*"))
        self.assertEqual(Match(value="b"), parse("*=b"))
        self.assertEqual(Match(), parse("*=*"))

        self.assertEqual(Match("a", atoms.IP("1.2.3.4")), parse("a in 1.2.3.4"))
        self.assertEqual(Match("a", atoms.IP("1.2.3.4")), parse("a in 1.2.3.4/32"))

    def test_to_unicode(self):
        self.assertEqual(unicode(Match("a b", "c")), u'"a b"=c')


class TestNonMatch(unittest.TestCase):
    def test_init_conversions(self):
        self.assertEqual(
            NonMatch('a', 'b'),
            NonMatch('a', atoms.String('b')))
        self.assertEqual(
            NonMatch('a', re.compile('b')),
            NonMatch('a', atoms.Rex('b')))

    def test_parsing(self):
        string = NonMatch('a', 'b')
        self.assertEqual(string, parse('a!=b'))
        self.assertEqual(string, parse('a != b'))
        self.assertEqual(string, parse('"\u0061"!="\u0062"'))

        rex = NonMatch('a', atoms.Rex('b'))
        self.assertEqual(rex, parse('a!=/b/'))

        self.assertEqual(NonMatch("a"), parse("a!=*"))
        self.assertEqual(NonMatch(value="b"), parse("*!=b"))
        self.assertEqual(NonMatch(), parse("*!=*"))

        self.assertEqual(NonMatch("a", atoms.IP("1.2.3.4")), parse("a not in 1.2.3.4"))
        self.assertEqual(NonMatch("a", atoms.IP("1.2.3.4")), parse("a not in 1.2.3.4/32"))


class TestFuzzy(unittest.TestCase):
    def test_parsing(self):
        self.assertEqual(
            parse('a'),
            Fuzzy(atoms.String('a')))
        self.assertEqual(
            parse('" a "'),
            Fuzzy(atoms.String(' a ')))
        self.assertEqual(
            parse('/a/'),
            Fuzzy(atoms.Rex('a')))


class TestParse(unittest.TestCase):
    def test_and_or(self):
        self.assertEqual(
            parse("a=a and b=b and c=c or d=d"),
            parse("a=a and b=b and (c=c or d=d)"))

        self.assertEqual(
            parse("a=a and b=b or c=c and d=d"),
            parse("a=a and (b=b or (c=c and d=d))"))
