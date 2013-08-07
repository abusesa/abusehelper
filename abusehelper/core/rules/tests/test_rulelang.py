from __future__ import unicode_literals

import sys
import unittest

from ..atoms import String, RegExp, IP
from ..rules import And, Or, No, Match, NonMatch, Fuzzy, Anything
from ..rulelang import format, parse, rule


class TestRule(unittest.TestCase):
    def test_basic(self):
        a = Match("a", "a")
        self.assertEqual(a, rule(a))
        self.assertEqual(a, rule("a=a"))


class TestParse(unittest.TestCase):
    def test_ignore_extra_whitespace(self):
        self.assertEqual(parse("  a  "), parse("a"))
        self.assertEqual(parse("(  a  )"), parse("a"))

    def test_and(self):
        a = Match("a", "a")
        b = Match("b", "b")
        c = Match("c", "c")
        self.assertEqual(And(a, b, c), parse("a=a and b=b and c=c"))
        self.assertEqual(And(a, And(b, c)), parse("a=a and (b=b and c=c)"))
        self.assertEqual(And(And(a, b), c), parse("(a=a and b=b) and c=c"))

        self.assertEqual(And(a, b, c), parse("(a=a) and (b=b) and (c=c)"))
        self.assertEqual(And(a, b, c), parse("(a=a)and(b=b)and(c=c)"))

        self.assertEqual(And(a, b, Or(c, And(a, b))), parse("a=a and b=b and c=c or a=a and b=b"))

    def test_or(self):
        a = Match("a", "a")
        b = Match("b", "b")
        c = Match("c", "c")
        self.assertEqual(Or(a, b, c), parse("a=a or b=b or c=c"))
        self.assertEqual(Or(a, Or(b, c)), parse("a=a or (b=b or c=c)"))
        self.assertEqual(Or(Or(a, b), c), parse("(a=a or b=b) or c=c"))

        self.assertEqual(Or(a, b, c), parse("(a=a) or (b=b) or (c=c)"))
        self.assertEqual(Or(a, b, c), parse("(a=a)or(b=b)or(c=c)"))

        self.assertEqual(Or(a, b, And(c, Or(a, b))), parse("a=a or b=b or c=c and a=a or b=b"))

    def test_match(self):
        string = Match('a', 'b')
        self.assertEqual(string, parse('a=b'))
        self.assertEqual(string, parse('a = b'))
        self.assertEqual(string, parse('"\u0061"="\u0062"'))

        rex = Match('a', RegExp('b'))
        self.assertEqual(rex, parse('a=/b/'))

        self.assertEqual(Match("a"), parse("a=*"))
        self.assertEqual(Match(value="b"), parse("*=b"))
        self.assertEqual(Match(), parse("*=*"))

        self.assertEqual(Match("a", IP("1.2.3.4")), parse("a in 1.2.3.4"))
        self.assertEqual(Match("a", IP("1.2.3.4")), parse("a in 1.2.3.4/32"))

    def test_no(self):
        x = Fuzzy(String("x"))

        self.assertEqual(parse("no x"), No(x))
        self.assertEqual(parse("no no x"), No(No(x)))
        self.assertEqual(parse("no (no x)"), No(No(x)))

        a = Match("a", "a")
        b = NonMatch("b", "b")

        # NO has a lower precedence than =/!=.
        self.assertEqual(parse("no a=a"), No(a))
        self.assertEqual(parse("no b!=b"), No(b))

        # NO has a higher precedence than AND or OR.
        self.assertEqual(parse("no a=a and b!=b"), And(No(a), b))
        self.assertEqual(parse("no a=a or b!=b"), Or(No(a), b))
        self.assertEqual(parse("no (a=a and b!=b)"), No(And(a, b)))
        self.assertEqual(parse("no (a=a or b!=b)"), No(Or(a, b)))

    def test_non_match(self):
        string = NonMatch('a', 'b')
        self.assertEqual(string, parse('a!=b'))
        self.assertEqual(string, parse('a != b'))
        self.assertEqual(string, parse('"\u0061"!="\u0062"'))

        rex = NonMatch('a', RegExp('b'))
        self.assertEqual(rex, parse('a!=/b/'))

        self.assertEqual(NonMatch("a"), parse("a!=*"))
        self.assertEqual(NonMatch(value="b"), parse("*!=b"))
        self.assertEqual(NonMatch(), parse("*!=*"))

        self.assertEqual(NonMatch("a", IP("1.2.3.4")), parse("a not in 1.2.3.4"))
        self.assertEqual(NonMatch("a", IP("1.2.3.4")), parse("a not in 1.2.3.4/32"))

    def test_fuzzy(self):
        self.assertEqual(parse('a'), Fuzzy(String('a')))
        self.assertEqual(parse('" a "'), Fuzzy(String(' a ')))
        self.assertEqual(parse('/a/'), Fuzzy(RegExp('a')))

    def test_string(self):
        self.assertEqual(
            parse('"\\" \\/ \\r \\n \\b \\f \\uffff"'),
            Fuzzy(String('" / \r \n \b \f \uffff')))

        # Empty strings must to be quoted
        self.assertRaises(ValueError, parse, '')
        self.assertEqual(parse('""'), Fuzzy(String('')))

    def test_regexp(self):
        self.assertEqual(parse('/a/'), Fuzzy(RegExp('a')))
        self.assertEqual(parse('/a/i'), Fuzzy(RegExp('a', ignore_case=True)))
        self.assertEqual(parse(r'/\//'), Fuzzy(RegExp(r'\/')))

    def test_anything(self):
        self.assertEqual(parse('*'), Anything())


class TestFormat(unittest.TestCase):
    def test_star(self):
        self.assertEqual("*", format(Anything()))
        self.assertEqual("*=*", format(Match()))
        self.assertEqual("*!=*", format(NonMatch()))

    def test_string(self):
        self.assertEqual("a", format(Fuzzy(String("a"))))
        self.assertEqual("\"a \"", format(Fuzzy(String("a "))))

        # Empty strings get quoted
        self.assertEqual('""', format(Fuzzy(String(''))))

    def test_regexp(self):
        self.assertEqual("/a/", format(Fuzzy(RegExp("a"))))
        self.assertEqual("/a/i", format(Fuzzy(RegExp("a", ignore_case=True))))
        self.assertEqual("/a|b|c/", format(Fuzzy(RegExp(r"a|b|c"))))

        # Unescaped forward slashes have to be escaped, but already escaped
        # forward slashes must be left intact.
        self.assertEqual(r'/\\\/\//', format(Fuzzy(RegExp(r'\\\//'))))
        self.assertEqual(r'/^http:\/\//', format(Fuzzy(RegExp(r'^http://'))))

    def test_allow_recursion_deeper_than_the_recursion_limit(self):
        limit = 2 * sys.getrecursionlimit()

        rule = Match("a", "b")
        for _ in xrange(limit):
            rule = No(rule)
        self.assertEqual(format(rule), "no " * limit + "a=b")
