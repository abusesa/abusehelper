from __future__ import unicode_literals

import re
import unittest

from ..atoms import String, RegExp, IP


class TestString(unittest.TestCase):
    def test_matching(self):
        self.assertTrue(String('atom').match('atom'))
        self.assertTrue(String('atom').match('ATOM'))


class TestRegExp(unittest.TestCase):
    def test_from_re(self):
        # re.U and re.S flags are implicitly set
        self.assertEqual(RegExp.from_re(re.compile('a', re.U)), RegExp('a'))
        self.assertEqual(RegExp.from_re(re.compile('a', re.S)), RegExp('a'))

        # re.I flag can be set explicitly
        self.assertEqual(
            RegExp.from_re(re.compile('a', re.I)),
            RegExp('a', ignore_case=True))

        # re.M, re.L and re.X are forbidden
        for flag in [re.M, re.L, re.X]:
            self.assertRaises(ValueError, RegExp.from_re, re.compile('a', flag))

    def test_matching(self):
        self.assertTrue(RegExp('a').match('a'))

        # Matching only to the beginning of the string must be explicitly defined
        self.assertTrue(RegExp('a').match('ba'))
        self.assertFalse(RegExp('^a').match('ba'))

        # Matches are case sensitive by default
        self.assertFalse(RegExp('a').match('A'))
        self.assertTrue(RegExp('a', ignore_case=True).match('A'))


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
        self.assertEqual(IP("192.0.2.1-192.0.2.2"), IP("192.0.2.2-192.0.2.1"))
        self.assertEqual(IP("192.0.2.0"), IP("192.0.2.0-192.0.2.0"))
        self.assertEqual(IP("192.0.2.0"), IP("192.0.2.0/32"))

        self.assertEqual(IP("192.0.2.0/24"), IP("192.0.2.0", 24))
        self.assertEqual(IP("192.0.2.0-192.0.2.255"), IP("192.0.2.0", "192.0.2.255"))
        self.assertEqual(IP("192.0.2.0/24"), IP("192.0.2.0-192.0.2.255"))
