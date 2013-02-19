from __future__ import unicode_literals

import sys
import unittest

from .. import parser


class TestParserBasics(unittest.TestCase):
    def test_take(self):
        rex = parser.RegExp("(a)(b)(c)")
        self.assertEqual(rex.parse("abc"), (('a', 'b', 'c'), ''))
        self.assertEqual(rex.take(1).parse("abc"), ('b', ''))
        self.assertEqual(rex.take(1, 2).parse("abc"), (('b', 'c'), ''))

    def test_allow_recursion_deeper_than_the_recursion_limit(self):
        expr = parser.ForwardRef()
        expr.set(
            parser.OneOf(
                parser.Sequence(
                    parser.RegExp(r"\("),
                    expr,
                    parser.RegExp(r"\)")
                ).take(1),
                parser.RegExp(r"(\w+)").take(0)
            )
        )

        limit = sys.getrecursionlimit()
        string = (limit * "(") + "test" + (limit * ")")
        self.assertEqual(expr.parse(string), ('test', ''))


class TestTransform(unittest.TestCase):
    pass


class TestForwardRef(unittest.TestCase):
    def test_ref_has_to_be_set_before_parsing(self):
        ref = parser.ForwardRef()
        self.assertRaises(parser.ParserError, ref.parse, "a")

    def test_ref_can_only_be_set_once(self):
        ref = parser.ForwardRef()
        ref.set(parser.RegExp("a"))
        self.assertRaises(parser.ParserError, ref.set, parser.RegExp("b"))


class TestRegExp(unittest.TestCase):
    pass


class TestSequence(unittest.TestCase):
    pass


class TestOneOf(unittest.TestCase):
    pass
