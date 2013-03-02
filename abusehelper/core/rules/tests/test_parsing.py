from __future__ import unicode_literals

import sys
import unittest

from .. import parsing


class TestParserBasics(unittest.TestCase):
    def test_allow_recursion_deeper_than_the_recursion_limit(self):
        expr = parsing.forward_ref()
        expr.set(
            parsing.union(
                parsing.seq(parsing.txt("("), expr, parsing.txt(")"), pick=1),
                parsing.txt("a")
            )
        )

        limit = 2 * sys.getrecursionlimit()
        string = (limit * "(") + "a" + (limit * ")")
        self.assertEqual(expr.parse(string), ('a', ''))


class TestForwardRef(unittest.TestCase):
    def test_ref_has_to_be_set_before_parsing(self):
        ref = parsing.forward_ref()
        self.assertRaises(parsing.ParserError, ref.parse, "a")

    def test_ref_can_only_be_set_once(self):
        ref = parsing.forward_ref()
        ref.set(parsing.txt("a"))
        self.assertRaises(parsing.ParserError, ref.set, parsing.txt("b"))
