import sys
import math
import unittest

from idiokit.xmlcore import Element

from .. import serialize
from .. import rules


class TestSerialize(unittest.TestCase):
    def test_dumping_unkown_types_raises_an_error(self):
        self.assertRaises(serialize.UnregisteredType, serialize.dump, object())

    def test_bool_roundtrip(self):
        self.assertEqual(True, serialize.load(serialize.dump(True)))
        self.assertEqual(False, serialize.load(serialize.dump(False)))

    def test_none_roundtrip(self):
        self.assertTrue(serialize.load(serialize.dump(None)) is None)

    def test_bytes_roundtrip(self):
        self.assertEqual(
            b"\x00test\xff",
            serialize.load(serialize.dump(b"\x00test\xff")))

    def test_unicode_roundtrip(self):
        self.assertEqual(
            u"\u0000test\uffff",
            serialize.load(serialize.dump(u"\u0000test\uffff")))

    def test_int_roundtrip(self):
        self.assertEqual(1, serialize.load(serialize.dump(1)))
        self.assertEqual(-1, serialize.load(serialize.dump(-1)))
        self.assertEqual(2 ** 129, serialize.load(serialize.dump(2 ** 129)))

    def test_float_roundtrip(self):
        info = sys.float_info
        inf = float("inf")
        nan = float("nan")

        self.assertEqual(1.0, serialize.load(serialize.dump(1.0)))
        self.assertEqual(-1.0, serialize.load(serialize.dump(-1.0)))
        self.assertEqual(info.min, serialize.load(serialize.dump(info.min)))
        self.assertEqual(info.max, serialize.load(serialize.dump(info.max)))
        self.assertEqual(inf, serialize.load(serialize.dump(inf)))
        self.assertEqual(-inf, serialize.load(serialize.dump(-inf)))
        self.assertTrue(math.isnan(serialize.load(serialize.dump(nan))))

    def test_sequence_roundtrip(self):
        self.assertEqual((), serialize.load(serialize.dump(())))
        self.assertEqual((), serialize.load(serialize.dump([])))
        self.assertEqual((), serialize.load(serialize.dump(frozenset())))
        self.assertEqual((), serialize.load(serialize.dump(set())))
        self.assertEqual(
            (1, 2, 3),
            serialize.load(serialize.dump([1, 2, 3])))

    def test_dict_roundtrip(self):
        self.assertEqual({}, serialize.load(serialize.dump({})))
        self.assertEqual({"a": 1}, serialize.load(serialize.dump({"a": 1})))

    def test_dict_backwards_compatibility(self):
        element = Element("d")
        element.add(serialize.dump(["a", "b"]).children())
        self.assertEqual(serialize.load(element), {"a": "b"})

    def test_rule_roundtrip(self):
        rule = rules.And(
            rules.Match(u"a", rules.String(u"a")),
            rules.Match(u"b", rules.RegExp(u"b")),
            rules.Match(u"c", rules.IP(u"192.0.2.0"))
        )
        self.assertEqual(serialize.load(serialize.dump(rule)), rule)
