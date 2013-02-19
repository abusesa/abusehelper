import re
import unittest
from abusehelper.core.events import Event

from ..compat import MATCHError, MATCH, AND, OR, NETBLOCK


class TestMATCH(unittest.TestCase):
    def test_init(self):
        self.assertRaises(MATCHError, MATCH, "key", re.compile(".", re.L))

    def test_match(self):
        rule = MATCH()
        self.assertFalse(rule.match(Event()))
        self.assertTrue(rule.match(Event(a="b")))
        self.assertTrue(rule.match(Event(x="y")))

        rule = MATCH("a")
        self.assertFalse(rule.match(Event()))
        self.assertTrue(rule.match(Event(a="b")))
        self.assertFalse(rule.match(Event(x="y")))

        rule = MATCH("a", "b")
        self.assertFalse(rule.match(Event()))
        self.assertTrue(rule.match(Event(a="b")))
        self.assertFalse(rule.match(Event(a="a")))

        rule = MATCH("a", re.compile("b", re.U))
        self.assertFalse(rule.match(Event()))
        self.assertTrue(rule.match(Event(a="abba")))
        self.assertFalse(rule.match(Event(a="aaaa")))

    def test_eq(self):
        self.assertEqual(MATCH(), MATCH())
        self.assertNotEqual(MATCH(), MATCH("a"))
        self.assertEqual(MATCH("a"), MATCH("a"))
        self.assertNotEqual(MATCH("a"), MATCH("x"))
        self.assertNotEqual(MATCH("a"), MATCH("a", "b"))
        self.assertEqual(MATCH("a", "b"), MATCH("a", "b"))
        self.assertNotEqual(MATCH("a", "b"), MATCH("x", "y"))
        self.assertEqual(MATCH("a", re.compile("b", re.U)), MATCH("a", re.compile("b", re.U)))
        self.assertNotEqual(MATCH("a", re.compile("b", re.U)), MATCH("x", re.compile("y", re.U)))
        self.assertNotEqual(MATCH("a", re.compile("b", re.U)), MATCH("a", "b"))
        self.assertNotEqual(MATCH("a", re.compile("b", re.I | re.U)), MATCH("a", re.compile("a", re.U)))
        self.assertNotEqual(MATCH("a", re.compile("b", re.I | re.U)), MATCH("a", re.compile("a", re.I | re.U)))


class TestOR(unittest.TestCase):
    def test_eq(self):
        a = MATCH("a")
        b = MATCH("b")
        self.assertEqual(OR(a, b), OR(a, b))
        self.assertEqual(OR(a, b), OR(b, a))
        self.assertNotEqual(OR(a, a), OR(b, b))


class TestAND(unittest.TestCase):
    def test_eq(self):
        a = MATCH("a")
        b = MATCH("b")
        self.assertEqual(AND(a, b), AND(a, b))
        self.assertEqual(AND(a, b), AND(b, a))
        self.assertNotEqual(AND(a, a), AND(b, b))


class TestNETBLOCK(unittest.TestCase):
    def test_eq(self):
        self.assertEqual(NETBLOCK("0.0.0.0", 16), NETBLOCK("0.0.0.0", 16))
        self.assertEqual(NETBLOCK("0.0.0.0", 16), NETBLOCK("0.0.255.255", 16))
        self.assertNotEqual(NETBLOCK("0.0.0.0", 24), NETBLOCK("0.0.255.255", 24))
        self.assertNotEqual(NETBLOCK("::", 24), NETBLOCK("0.0.0.0", 24))

    def test_cidr_constructor(self):
        self.assertEqual(NETBLOCK("1.2.3.4"), NETBLOCK("1.2.3.4/32"))
        self.assertEqual(NETBLOCK("1.2.3.4", 32), NETBLOCK("1.2.3.4/32"))
        self.assertEqual(NETBLOCK("1.2.3.4", 16), NETBLOCK("1.2.3.4/16"))
        self.assertNotEqual(NETBLOCK("1.2.3.4", 16), NETBLOCK("1.2.3.4"))

        self.assertEqual(NETBLOCK("2001:0db8:ac10:fe01::"), NETBLOCK("2001:0db8:ac10:fe01::/128"))
        self.assertEqual(NETBLOCK("2001:0db8:ac10:fe01::", 128), NETBLOCK("2001:0db8:ac10:fe01::/128"))
        self.assertEqual(NETBLOCK("2001:0db8:ac10:fe01::", 64), NETBLOCK("2001:0db8:ac10:fe01::/64"))
        self.assertNotEqual(NETBLOCK("2001:0db8:ac10:fe01::", 64), NETBLOCK("2001:0db8:ac10:fe01::"))

        self.assertRaises(TypeError, NETBLOCK, "1.2.3.4/16", 16)
        self.assertRaises(TypeError, NETBLOCK, "2001:0db8:ac10:fe01::/32", 32)

    def test_range_constructor(self):
        self.assertEqual(NETBLOCK("10.0.1.2"), NETBLOCK("10.0.1.2", "10.0.1.2"))
        self.assertEqual(NETBLOCK("10.0.0.0/16"), NETBLOCK("10.0.0.0 - 10.0.255.255"))
        self.assertEqual(NETBLOCK("10.0.0.0", "10.0.255.255"), NETBLOCK("10.0.0.0 - 10.0.255.255"))
        self.assertNotEqual(NETBLOCK("10.0.0.0/16"), NETBLOCK("10.0.0.0 - 10.0.255.0"))

        self.assertRaises(TypeError, NETBLOCK, "10.0.0.0 - 10.0.255.255", "10.0.255.255")

    def test_match_ipv4(self):
        rule = NETBLOCK("10.0.0.0", "10.0.0.254")
        self.assertTrue(rule.match(Event(ip="10.0.0.0")))
        self.assertTrue(rule.match(Event(ip="10.0.0.1")))
        self.assertFalse(rule.match(Event(ip="10.0.0.255")))

    def test_match_ipv4_cidr(self):
        rule = NETBLOCK("1.2.3.4", 16)
        self.assertFalse(rule.match(Event(cidr="1.2.3.4/0")))
        self.assertFalse(rule.match(Event(cidr="1.2.3.4/8")))
        self.assertTrue(rule.match(Event(cidr="1.2.3.4/16")))
        self.assertTrue(rule.match(Event(cidr="1.2.3.4/24")))
        self.assertFalse(rule.match(Event(cidr="0.0.0.0/16")))

    def test_match_ipv6(self):
        rule = NETBLOCK("2001:0db8:ac10:fe01::", 32)
        self.assertTrue(rule.match(Event(ip="2001:0db8:aaaa:bbbb:cccc::")))
        self.assertFalse(rule.match(Event(ip="::1")))

    def test_match_ipv6_cidr(self):
        rule = NETBLOCK("2001:0db8:ac10:fe01::", 32)
        self.assertFalse(rule.match(Event(cidr="2001:0db8:aaaa:bbbb:cccc::/0")))
        self.assertFalse(rule.match(Event(cidr="2001:0db8:aaaa:bbbb:cccc::/16")))
        self.assertTrue(rule.match(Event(cidr="2001:0db8:aaaa:bbbb:cccc::/32")))
        self.assertTrue(rule.match(Event(cidr="2001:0db8:aaaa:bbbb:cccc::/64")))
        self.assertFalse(rule.match(Event(cidr="::1/32")))

    def test_non_match_bad_data(self):
        rule = NETBLOCK("1.2.3.4", 24)
        self.assertFalse(rule.match(Event(ip="1.2.3.4/-1")))
        self.assertFalse(rule.match(Event(ip="1.2.3.4/33")))
        self.assertFalse(rule.match(Event(ip=u"this is just some data")))
        self.assertFalse(rule.match(Event(ip=u"\xe4 not convertible to ascii")))

    def test_match_arbitrary_key(self):
        rule = NETBLOCK("1.2.3.4", 24)
        self.assertTrue(rule.match(Event(somekey="1.2.3.255")))

        rule = NETBLOCK("1.2.3.4", 24)
        self.assertFalse(rule.match(Event(somekey="1.2.4.255")))

    def test_match_ip_key(self):
        rule = NETBLOCK("1.2.3.4", 24, keys=["ip"])
        self.assertTrue(rule.match(Event(somekey="4.5.6.255", ip="1.2.3.255")))

        rule = NETBLOCK("1.2.3.4", 24, keys=["ip"])
        self.assertFalse(rule.match(Event(somekey="1.2.3.4", ip="1.2.4.255")))
