from __future__ import unicode_literals

import re
import unittest

from ..atoms import Star, String, Rex, IP


class TestStar(unittest.TestCase):
    def test_parsing(self):
        parser = Star.parser()
        self.assertEqual(parser.parse('* test'), (Star(), ' test'))

    def test_to_unicode(self):
        self.assertEqual('*', unicode(Star()))

    def test_matching(self):
        self.assertTrue(Star().match(''))
        self.assertTrue(Star().match('anything'))


class TestString(unittest.TestCase):
    def test_parsing(self):
        parser = String.parser()
        self.assertEqual(parser.parse('atom test'), (String('atom'), ' test'))
        self.assertEqual(
            parser.parse('"\\" \\/ \\r \\n \\b \\f \\uffff" test'),
            (String('" / \r \n \b \f \uffff'), ' test'))

        # Empty strings must to be quoted
        self.assertIs(parser.parse(''), None)
        self.assertEqual(parser.parse('""'), (String(''), ''))

        self.assertEqual(parser.parse("*"), None)

    def test_to_unicode(self):
        self.assertEqual('""', unicode(String('')))
        self.assertEqual('"*"', unicode(String('*')))

    def test_matching(self):
        self.assertTrue(String('atom').match('atom'))
        self.assertTrue(String('atom').match('ATOM'))


class TestRex(unittest.TestCase):
    def test_from_re(self):
        # re.U and re.S flags are implicitly set
        self.assertEqual(Rex.from_re(re.compile('a', re.U)), Rex('a'))
        self.assertEqual(Rex.from_re(re.compile('a', re.S)), Rex('a'))

        # re.I flag can be set explicitly
        self.assertEqual(Rex.from_re(re.compile('a', re.I)), Rex('a', ignore_case=True))

        # re.M, re.L and re.X are forbidden
        for flag in [re.M, re.L, re.X]:
            self.assertRaises(ValueError, Rex.from_re, re.compile('a', flag))

    def test_parsing(self):
        parser = Rex.parser()
        self.assertEqual(parser.parse('/a/'), (Rex('a'), ""))
        self.assertEqual(parser.parse('/a/i'), (Rex('a', ignore_case=True), ""))
        self.assertEqual(parser.parse(r'/\//'), (Rex(r'\/'), ""))

    def test_to_unicode(self):
        self.assertEqual(unicode(Rex('a')), '/a/')
        self.assertEqual(unicode(Rex('a', ignore_case=True)), '/a/i')
        self.assertEqual(unicode(Rex('/')), r'/\//')

    def test_matching(self):
        self.assertTrue(Rex('a').match('a'))

        # Matching only to the beginning of the string must be explicitly defined
        self.assertTrue(Rex('a').match('ba'))
        self.assertFalse(Rex('^a').match('ba'))

        # Matches are case sensitive by default
        self.assertFalse(Rex('a').match('A'))
        self.assertTrue(Rex('a', ignore_case=True).match('A'))


class TestIP(unittest.TestCase):
    def test_cidr_constructor_errors(self):
        self.assertRaises(ValueError, IP, "192.0.2.0", 33)
        self.assertRaises(ValueError, IP, "192.0.2.0/33")

        self.assertRaises(ValueError, IP, "2001:db8::", 129)
        self.assertRaises(ValueError, IP, "2001:db8::/129")

    def test_range_constructor_errors(self):
        self.assertRaises(ValueError, IP, "192.0.2.0", "2001:db8::")
        self.assertRaises(ValueError, IP, "192.0.2.0-2001:db8::")

        self.assertRaises(ValueError, IP, "2001:db8::", "192.0.2.0")
        self.assertRaises(ValueError, IP, "2001:db8::-192.0.2.0")

    def test_equality(self):
        self.assertEqual(IP("192.0.2.0"), IP("192.0.2.0-192.0.2.0"))
        self.assertEqual(IP("192.0.2.0"), IP("192.0.2.0/32"))

        self.assertEqual(IP("192.0.2.0/24"), IP("192.0.2.0", 24))
        self.assertEqual(IP("192.0.2.0-192.0.2.255"), IP("192.0.2.0", "192.0.2.255"))
        self.assertEqual(IP("192.0.2.0/24"), IP("192.0.2.0-192.0.2.255"))
