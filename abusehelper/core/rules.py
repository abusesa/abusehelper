from idiokit.xmlcore import Element
from abusehelper.core import serialize

import operator
import functools
import math
import re


class RuleError(Exception):
    pass


class RuleClassifier(object):
    def __init__(self):
        self._rules = dict()

    def inc(self, rule, class_id):
        classes = self._rules.get(rule, None)
        if classes is None:
            classes = dict()
            self._rules[rule] = classes
        classes[class_id] = classes.get(class_id, 0) + 1

    def dec(self, rule, class_id):
        classes = self._rules.get(rule, None)
        if classes is None:
            return

        count = classes.get(class_id, 0) - 1
        if count > 0:
            classes[class_id] = count
        else:
            classes.pop(class_id, None)
            if not classes:
                self._rules.pop(rule, None)

    def classify(self, obj):
        cache = dict()
        result = set()

        for rule, classes in self._rules.iteritems():
            if rule.match(obj, cache):
                result.update(classes)

        return result

    def is_empty(self):
        return not self._rules


class _Rule(object):
    @classmethod
    def serialize_register(cls):
        name = "rule-" + cls.__name__.lower()
        serialize.register(cls.dump_rule, cls.load_rule, cls, name)

    def __init__(self, identity):
        self._hash = None
        self._identity = identity

    def __eq__(self, other):
        if other.__class__ is not self.__class__:
            return NotImplemented
        return self._identity == other._identity

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __hash__(self):
        if self._hash is None:
            self._hash = hash(self.__class__) ^ hash(self._identity)
        return self._hash

    def match(self, obj, cache=None):
        if cache is None:
            cache = dict()
        elif self in cache:
            return cache[self]
        result = self.match_with_cache(obj, cache)
        cache[self] = result
        return result

    def match_with_cache(self, obj, cache):
        return False


class MATCHError(RuleError):
    pass


class MATCH(_Rule):
    _flags = dict(I=re.I, X=re.X, M=re.M, S=re.S)

    @classmethod
    def dump_rule(cls, dump, name, rule):
        flags = rule.flags
        if flags is not None:
            flags = "".join(x for x in cls._flags if flags & cls._flags[x])
        return serialize.dump_list(dump, name, [rule.key, rule.pattern, flags])

    @classmethod
    def load_rule(cls, load, element):
        key, pattern, flag_string = serialize.load_list(load, element)
        if flag_string is not None:
            flags = re.UNICODE
            for flag in flag_string:
                flags |= cls._flags.get(flag, 0)
            pattern = re.compile(pattern, flags)
        return cls(key, pattern)

    def __init__(self, key=None, value=None):
        if value is None:
            filter = None
            pattern = None
            flags = None
        elif isinstance(value, basestring):
            filter = functools.partial(operator.eq, value)
            pattern = value
            flags = None
        else:
            filter = value.search
            pattern = value.pattern
            flags = value.flags

            if (flags & re.LOCALE) != 0:
                raise MATCHError("re.LOCALE regexp flag is not supported")
            if (flags & re.UNICODE) == 0:
                raise MATCHError("re.UNICODE regexp flag is required")

        _Rule.__init__(self, (key, value))
        self.key = key
        self.value = value
        self.filter = filter
        self.pattern = pattern
        self.flags = flags

    def __repr__(self):
        return self.__class__.__name__ + repr((self.key, self.value))

    def match_with_cache(self, event, cache):
        if self.key is None:
            return event.contains(filter=self.filter)
        return event.contains(self.key, filter=self.filter)
MATCH.serialize_register()


class NOT(_Rule):
    @classmethod
    def dump_rule(cls, dump, name, rule):
        element = Element(name)
        element.add(dump(rule.child))
        return element

    @classmethod
    def load_rule(cls, load, element):
        children = list(element.children())
        if len(children) != 1:
            raise RuleError(element)
        return cls(load(children[0]))

    def __init__(self, child):
        _Rule.__init__(self, child)
        self.child = child

    def __repr__(self):
        return self.__class__.__name__ + "(" + repr(self.child) + ")"

    def match_with_cache(self, obj, cache):
        return not self.child.match(obj, cache)
NOT.serialize_register()


class OR(_Rule):
    @classmethod
    def dump_rule(cls, dump, name, rule):
        return serialize.dump_list(dump, name, rule.children)

    @classmethod
    def load_rule(cls, load, element):
        children = serialize.load_list(load, element)
        if len(children) < 1:
            raise RuleError(element)
        return cls(*children)

    def __init__(self, first, *rest):
        self.children = (first,) + rest
        _Rule.__init__(self, frozenset(self.children))

    def __repr__(self):
        children = ", ".join(map(repr, self.children))
        return self.__class__.__name__ + "(" + children + ")"

    def match_with_cache(self, obj, cache):
        for child in self.children:
            if child.match(obj, cache):
                return True
        return False
OR.serialize_register()


class AND(_Rule):
    @classmethod
    def dump_rule(cls, dump, name, rule):
        return serialize.dump_list(dump, name, rule.children)

    @classmethod
    def load_rule(cls, load, element):
        children = serialize.load_list(load, element)
        if len(children) < 1:
            raise RuleError(element)
        return cls(*children)

    def __init__(self, first, *rest):
        self.children = (first,) + rest
        _Rule.__init__(self, frozenset(self.children))

    def __repr__(self):
        children = ", ".join(map(repr, self.children))
        return self.__class__.__name__ + "(" + children + ")"

    def match_with_cache(self, obj, cache):
        for child in self.children:
            if not child.match(obj, cache):
                return False
        return True
AND.serialize_register()


class ANYTHING(_Rule):
    @classmethod
    def dump_rule(cls, dump, name, rule):
        element = Element(name)
        return element

    @classmethod
    def load_rule(cls, load, element):
        return ANYTHING()

    def __init__(self):
        _Rule.__init__(self, None)

    def __repr__(self):
        return self.__class__.__name__ + "()"

    def match(self, obj, cache=None):
        return True
    match_with_cache = match
ANYTHING.serialize_register()


import struct
from socket import inet_ntop, inet_pton, AF_INET, AF_INET6, error


class NETBLOCKError(RuleError):
    pass


class IPRangeError(NETBLOCKError):
    pass


def _parse_ipv4(ip):
    try:
        packed = inet_pton(AF_INET, ip.strip())
    except (error, UnicodeEncodeError):
        return None

    ip_num, = struct.unpack("!I", packed)
    return ip_num


def _format_ipv4(ip_num):
    return inet_ntop(AF_INET, struct.pack("!I", ip_num))


def _parse_ipv6(ip):
    try:
        packed = inet_pton(AF_INET6, ip.strip())
    except (error, UnicodeEncodeError):
        return None

    hi, lo = struct.unpack("!QQ", packed)
    return (hi << 64) | lo


def _format_ipv6(ip_num):
    hi = ip_num >> 64
    lo = ip_num & 0xffffffffffffffff
    return inet_ntop(AF_INET6, struct.pack("!QQ", hi, lo))


class IPRange(object):
    _ip_versions = {
        4: (_parse_ipv4, _format_ipv4, 32),
        6: (_parse_ipv6, _format_ipv6, 128)
    }

    @classmethod
    def _parse_ip(cls, ip):
        for version, (parser, _, max_bits) in cls._ip_versions.iteritems():
            num = parser(ip)
            if num is not None:
                return version, num
        raise IPRangeError("invalid IP address " + repr(ip))

    @classmethod
    def _max_bits(cls, version):
        parser, formatter, max_bits = cls._ip_versions[version]
        return max_bits

    @classmethod
    def _format_ip(cls, version, num):
        parser, formatter, max_bits = cls._ip_versions[version]
        return formatter(num)

    @classmethod
    def from_cidr(cls, cidr, bits=None):
        parts = cidr.split("/")
        if len(parts) == 1:
            ip = parts[0]
        elif len(parts) == 2:
            if bits is not None:
                raise IPRangeError(repr(cidr) + " already contains bits")
            ip, bits = parts
        else:
            raise IPRangeError("invalid CIDR " + repr(cidr))

        ip_version, ip_num = cls._parse_ip(ip)
        max_bits = cls._max_bits(ip_version)

        if bits is None:
            bits = max_bits
        else:
            try:
                bits = int(bits)
            except ValueError:
                raise IPRangeError("invalid bits " + repr(bits))

            if not 0 <= bits <= max_bits:
                raise IPRangeError("bits not in range " +
                    "(got {0!r}, expected 0-{1!r})".format(bits, max_bits))

        mask = ((1 << max_bits) - 1) ^ ((1 << (max_bits - bits)) - 1)
        first = ip_num & mask
        last = first + (1 << (max_bits - bits)) - 1
        return cls(ip_version, first, last)

    @classmethod
    def from_range(cls, first, last=None):
        parts = first.split("-")
        if len(parts) == 1:
            first = parts[0]
        elif len(parts) == 2:
            if last is not None:
                raise IPRangeError(repr(first) + " already contains an last IP")
            first, last = parts
        else:
            raise IPRangeError("invalid IP range " + repr(first))

        first_version, first_num = cls._parse_ip(first)
        if last is None:
            return cls(first_version, first_num, first_num + 1)

        last_version, last_num = cls._parse_ip(last)
        if first_version != last_version:
            raise IPRangeError("mismatching IPs " + repr(first) + " and " + repr(last))
        return cls(first_version, first_num, last_num)

    def __init__(self, version, first, last):
        self._version = version
        self._first = first
        self._last = last

    @property
    def first(self):
        return self._format_ip(self._version, self._first)

    @property
    def last(self):
        return self._format_ip(self._version, self._last)

    def contains(self, other):
        if self._version != other._version:
            return False
        return self._first <= other._first <= other._last <= self._last

    def as_minimal_string(self):
        count = self._last - self._first + 1
        if count == 1:
            return self.first

        bits = self._max_bits(self._version) - int(math.log(count, 2))
        if IPRange.from_cidr(self.first, bits).contains(self):
            return self.first + "/" + repr(bits)

        return self.first + "-" + self.last


class NETBLOCK(_Rule):
    @classmethod
    def dump_rule(cls, dump, name, rule):
        element = Element(
            name, first=rule.range.first, last=rule.range.first)
        if rule.keys is not None:
            element.add(serialize.dump_list(dump, "keys", rule.keys))
        return element

    @classmethod
    def load_rule(cls, load, element):
        if not element.with_attrs("first", "last"):
            raise RuleError(element)
        first = element.get_attr("first")
        last = element.get_attr("last")

        keys = None
        for child in element.children():
            keys = serialize.load_list(load, child)
        return cls.from_range(first, last, keys)

    def __init__(self, ip_or_cidr_or_range, bits_or_last=None, keys=None):
        try:
            self.range = IPRange.from_cidr(ip_or_cidr_or_range, bits_or_last)
        except IPRangeError:
            self.range = IPRange.from_range(ip_or_cidr_or_range, bits_or_last)

        self.keys = None if keys is None else frozenset(keys)
        _Rule.__init__(self, (self.range.first, self.range.last, self.keys))

    def __repr__(self):
        args = [repr(self.range.as_minimal_string())]
        if self.keys is not None:
            args.append("keys=" + repr(list(self.keys)))
        return self.__class__.__name__ + "(" + ", ".join(args) + ")"

    def _filter(self, value):
        try:
            range = IPRange.from_cidr(value)
        except IPRangeError:
            return False
        return self.range.contains(range)

    def match_with_cache(self, event, cache):
        if self.keys is None:
            keys = event.keys()
        else:
            keys = self.keys

        for key in keys:
            if event.contains(key, filter=self._filter):
                return True
        return False
NETBLOCK.serialize_register()


if __name__ == "__main__":
    import unittest
    from abusehelper.core.events import Event

    class RuleClassifierTests(unittest.TestCase):
        def test_inc(self):
            c = RuleClassifier()
            c.inc(MATCH("a", "b"), "c")
            assert set(c.classify(Event(a="b"))) == set(["c"])
            assert not c.is_empty()

            c.inc(MATCH("a"), "d")
            assert set(c.classify(Event(a="b"))) == set(["c", "d"])
            assert set(c.classify(Event(a="x"))) == set(["d"])
            assert not c.is_empty()

        def test_dec(self):
            c = RuleClassifier()
            c.inc(MATCH("a", "b"), "c")
            c.inc(MATCH("a", "b"), "d")

            c.dec(MATCH("a", "b"), "c")
            assert set(c.classify(Event(a="b"))) == set(["d"])
            assert not c.is_empty()

            c.dec(MATCH("a", "b"), "d")
            assert set(c.classify(Event(a="b"))) == set([])
            assert c.is_empty()

    class MatchTests(unittest.TestCase):
        def test_init(self):
            self.assertRaises(MATCHError, MATCH, "key", re.compile("."))
            self.assertRaises(MATCHError, MATCH, "key", re.compile(".", re.L))

        def test_match(self):
            rule = MATCH()
            assert not rule.match(Event())
            assert rule.match(Event(a="b"))
            assert rule.match(Event(x="y"))

            rule = MATCH("a")
            assert not rule.match(Event())
            assert rule.match(Event(a="b"))
            assert not rule.match(Event(x="y"))

            rule = MATCH("a", "b")
            assert not rule.match(Event())
            assert rule.match(Event(a="b"))
            assert not rule.match(Event(a="a"))

            rule = MATCH("a", re.compile("b", re.U))
            assert not rule.match(Event())
            assert rule.match(Event(a="abba"))
            assert not rule.match(Event(a="aaaa"))

        def test_eq(self):
            assert MATCH() == MATCH()
            assert MATCH() != MATCH("a")
            assert MATCH("a") == MATCH("a")
            assert MATCH("a") != MATCH("x")
            assert MATCH("a") != MATCH("a", "b")
            assert MATCH("a", "b") == MATCH("a", "b")
            assert MATCH("a", "b") != MATCH("x", "y")
            assert MATCH("a", re.compile("b", re.U)) == MATCH("a", re.compile("b", re.U))
            assert MATCH("a", re.compile("b", re.U)) != MATCH("x", re.compile("y", re.U))
            assert MATCH("a", re.compile("b", re.U)) != MATCH("a", "b")
            assert MATCH("a", re.compile("b", re.I | re.U)) != MATCH("a", re.compile("a", re.U))
            assert MATCH("a", re.compile("b", re.I | re.U)) != MATCH("a", re.compile("a", re.I | re.U))

        def test_serialize(self):
            rule = MATCH()
            assert serialize.load(serialize.dump(rule)) == rule

            rule = MATCH("a", "b")
            assert serialize.load(serialize.dump(rule)) == rule

            rule = MATCH("a", re.compile("b", re.I | re.U))
            assert serialize.load(serialize.dump(rule)) == rule

    class OrTests(unittest.TestCase):
        def test_eq(self):
            a = MATCH("a")
            b = MATCH("b")
            assert OR(a, b) == OR(a, b)
            assert OR(a, b) == OR(b, a)
            assert OR(a, a) != OR(b, b)

    class AndTests(unittest.TestCase):
        def test_eq(self):
            a = MATCH("a")
            b = MATCH("b")
            assert AND(a, b) == AND(a, b)
            assert AND(a, b) == AND(b, a)
            assert AND(a, a) != AND(b, b)

    class NetblockTests(unittest.TestCase):
        def test_eq(self):
            assert NETBLOCK("0.0.0.0", 16) == NETBLOCK("0.0.0.0", 16)
            assert NETBLOCK("0.0.0.0", 16) == NETBLOCK("0.0.255.255", 16)
            assert NETBLOCK("0.0.0.0", 24) != NETBLOCK("0.0.255.255", 24)
            assert NETBLOCK("::", 24) != NETBLOCK("0.0.0.0", 24)

        def test_cidr_constructor(self):
            assert NETBLOCK("1.2.3.4") == NETBLOCK("1.2.3.4/32")
            assert NETBLOCK("1.2.3.4", 32) == NETBLOCK("1.2.3.4/32")
            assert NETBLOCK("1.2.3.4", 16) == NETBLOCK("1.2.3.4/16")
            assert NETBLOCK("1.2.3.4", 16) != NETBLOCK("1.2.3.4")

            assert NETBLOCK("2001:0db8:ac10:fe01::") == NETBLOCK("2001:0db8:ac10:fe01::/128")
            assert NETBLOCK("2001:0db8:ac10:fe01::", 128) == NETBLOCK("2001:0db8:ac10:fe01::/128")
            assert NETBLOCK("2001:0db8:ac10:fe01::", 64) == NETBLOCK("2001:0db8:ac10:fe01::/64")
            assert NETBLOCK("2001:0db8:ac10:fe01::", 64) != NETBLOCK("2001:0db8:ac10:fe01::")

            self.assertRaises(NETBLOCKError, NETBLOCK, "1.2.3.4/16", 16)
            self.assertRaises(NETBLOCKError, NETBLOCK, "2001:0db8:ac10:fe01::/32", 32)

        def test_range_constructor(self):
            assert NETBLOCK("10.0.1.2") == NETBLOCK("10.0.1.2", "10.0.1.2")
            assert NETBLOCK("10.0.0.0/16") == NETBLOCK("10.0.0.0 - 10.0.255.255")
            assert NETBLOCK("10.0.0.0", "10.0.255.255") == NETBLOCK("10.0.0.0 - 10.0.255.255")
            assert NETBLOCK("10.0.0.0/16") != NETBLOCK("10.0.0.0 - 10.0.255.0")

            self.assertRaises(NETBLOCKError, NETBLOCK, "10.0.0.0 - 10.0.255.255", "10.0.255.255")

        def test_match_ipv4(self):
            rule = NETBLOCK("10.0.0.0", "10.0.0.254")
            assert rule.match(Event(ip="10.0.0.0"))
            assert rule.match(Event(ip="10.0.0.1"))
            assert not rule.match(Event(ip="10.0.0.255"))

        def test_match_ipv4_cidr(self):
            rule = NETBLOCK("1.2.3.4", 16)
            assert not rule.match(Event(cidr="1.2.3.4/0"))
            assert not rule.match(Event(cidr="1.2.3.4/8"))
            assert rule.match(Event(cidr="1.2.3.4/16"))
            assert rule.match(Event(cidr="1.2.3.4/24"))
            assert not rule.match(Event(cidr="0.0.0.0/16"))

        def test_match_ipv6(self):
            rule = NETBLOCK("2001:0db8:ac10:fe01::", 32)
            assert rule.match(Event(ip="2001:0db8:aaaa:bbbb:cccc::"))
            assert not rule.match(Event(ip="::1"))

        def test_match_ipv6_cidr(self):
            rule = NETBLOCK("2001:0db8:ac10:fe01::", 32)
            assert not rule.match(Event(cidr="2001:0db8:aaaa:bbbb:cccc::/0"))
            assert not rule.match(Event(cidr="2001:0db8:aaaa:bbbb:cccc::/16"))
            assert rule.match(Event(cidr="2001:0db8:aaaa:bbbb:cccc::/32"))
            assert rule.match(Event(cidr="2001:0db8:aaaa:bbbb:cccc::/64"))
            assert not rule.match(Event(cidr="::1/32"))

        def test_non_match_bad_data(self):
            rule = NETBLOCK("1.2.3.4", 24)
            assert not rule.match(Event(ip="1.2.3.4/-1"))
            assert not rule.match(Event(ip="1.2.3.4/33"))
            assert not rule.match(Event(ip=u"this is just some data"))
            assert not rule.match(Event(ip=u"\xe4 not convertible to ascii"))

        def test_match_arbitrary_key(self):
            rule = NETBLOCK("1.2.3.4", 24)
            assert rule.match(Event(somekey="1.2.3.255"))

            rule = NETBLOCK("1.2.3.4", 24)
            assert not rule.match(Event(somekey="1.2.4.255"))

        def test_match_ip_key(self):
            rule = NETBLOCK("1.2.3.4", 24, keys=["ip"])
            assert rule.match(Event(somekey="4.5.6.255", ip="1.2.3.255"))

            rule = NETBLOCK("1.2.3.4", 24, keys=["ip"])
            assert not rule.match(Event(somekey="1.2.3.4", ip="1.2.4.255"))

    unittest.main()
