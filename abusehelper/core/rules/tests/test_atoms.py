from __future__ import unicode_literals

import re
import pickle
import unittest

from ..atoms import String, RegExp, IP, DomainName


class TestString(unittest.TestCase):
    def test_matching(self):
        self.assertTrue(String("atom").match("atom"))
        self.assertFalse(String("atom").match("ATOM"))

    _options = [
        String("atom")
    ]

    def test_pickling_and_unpickling(self):
        for option in self._options:
            self.assertEqual(option, pickle.loads(pickle.dumps(option)))

    def test_repr(self):
        for option in self._options:
            self.assertEqual(option, eval(repr(option)))


class TestRegExp(unittest.TestCase):
    def test_from_string(self):
        self.assertEqual(
            RegExp.from_string("www.example.com", ignore_case=False),
            RegExp("www\\.example\\.com", ignore_case=False))
        self.assertEqual(
            RegExp.from_string("www.example.com", ignore_case=True),
            RegExp("www\\.example\\.com", ignore_case=True))

    def test_from_re(self):
        # re.U and re.S flags are implicitly set
        self.assertEqual(RegExp.from_re(re.compile("a", re.U)), RegExp("a"))
        self.assertEqual(RegExp.from_re(re.compile("a", re.S)), RegExp("a"))

        # re.I flag can be set explicitly
        self.assertEqual(
            RegExp.from_re(re.compile("a", re.I)),
            RegExp("a", ignore_case=True))

        # re.M, re.L and re.X are forbidden
        for flag in [re.M, re.L, re.X]:
            self.assertRaises(ValueError, RegExp.from_re, re.compile("a", flag))

    def test_matching(self):
        self.assertTrue(RegExp("a").match("a"))

        # Matching only to the beginning of the string must be explicitly defined
        self.assertTrue(RegExp("a").match("ba"))
        self.assertFalse(RegExp("^a").match("ba"))

        # Matches are case sensitive by default
        self.assertFalse(RegExp("a").match("A"))
        self.assertTrue(RegExp("a", ignore_case=True).match("A"))

    _options = [
        RegExp("a"),
        RegExp("a", ignore_case=True)
    ]

    def test_pickling_and_unpickling(self):
        for option in self._options:
            self.assertEqual(option, pickle.loads(pickle.dumps(option)))

    def test_repr(self):
        for option in self._options:
            self.assertEqual(option, eval(repr(option)))


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

    def test_range_constructor_accepts_reverse_ranges(self):
        self.assertEqual(IP("192.0.2.255 - 192.0.2.0"), IP("192.0.2.0 - 192.0.2.255"))
        self.assertEqual(IP("2001:db8::ffff - 2001:db8::"), IP("2001:db8:: - 2001:db8::ffff"))

    _options = [
        IP("192.0.2.0"),
        IP("192.0.2.0/24"),
        IP("192.0.2.0-192.0.2.1"),
        IP("2001:db8::"),
        IP("2001:db8::/24"),
        IP("2001:db8::-2001:db8::1")
    ]

    def test_pickling_and_unpickling(self):
        for option in self._options:
            self.assertEqual(option, pickle.loads(pickle.dumps(option)))

    def test_repr(self):
        for option in self._options:
            self.assertEqual(option, eval(repr(option)))


class TestDomainName(unittest.TestCase):
    def test_non_wildcard_label_should_(self):
        self.assertTrue(DomainName("domain.example").match("domain.example"))
        self.assertFalse(DomainName("domain.example").match("domain.test"))

    def test_subdomains_should_match_to_their_parent_domains(self):
        self.assertTrue(DomainName("domain.example").match("sub.domain.example"))
        self.assertTrue(DomainName("domain.example").match("deep.sub.domain.example"))

    def test_constructor_should_handle_names_case_insensitively(self):
        self.assertEqual(DomainName("domain.example"), DomainName("domain.EXAMPLE"))

    def test_match_should_handle_names_case_insensitively(self):
        self.assertTrue(DomainName("domain.example").match("domain.example"))
        self.assertTrue(DomainName("domain.example").match("domain.EXAMPLE"))

    def test_wildcard_should_match_to_any_label(self):
        self.assertTrue(DomainName("*.example").match("domain.example"))
        self.assertTrue(DomainName("*.example").match("sub.domain.example"))

    def test_wildcard_should_demand_a_label_to_match_to(self):
        self.assertFalse(DomainName("*.*.example").match("domain.example"))
        self.assertTrue(DomainName("*.*.example").match("sub.domain.example"))

    def test_constructor_should_normalize_internationalized_names(self):
        self.assertEqual(DomainName("\xe4.example"), DomainName("xn--4ca.example"))
        self.assertEqual(DomainName("\xe4.example"), DomainName("\xc4.example"))

    def test_match_should_normalize_internationalized_names(self):
        self.assertTrue(DomainName("\xe4.example").match("\xe4.example"))
        self.assertTrue(DomainName("\xe4.example").match("xn--4ca.example"))
        self.assertTrue(DomainName("\xe4.example").match("\xc4.example"))

    _options = [
        DomainName("domain.example"),
        DomainName("*.example"),
        DomainName("\xe4.example"),
        DomainName("xn--4ca.example")
    ]

    def test_pickling_and_unpickling(self):
        for option in self._options:
            self.assertEqual(option, pickle.loads(pickle.dumps(option)))

    def test_repr(self):
        for option in self._options:
            self.assertEqual(option, eval(repr(option)))
