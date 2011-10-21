from idiokit.xmlcore import Element
from abusehelper.core import serialize

import operator
import functools
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
        return self.__class__.__name__ + ("(%r, %r)" % (self.key, self.value))

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

    def match(self, obj, cache):
        return True
    match_with_cache = match
ANYTHING.serialize_register()

import struct
from socket import inet_aton, inet_pton, AF_INET6, error

_ACCEPTABLE_ERRORS = (error, UnicodeEncodeError, TypeError)

_unpack_ipv4 = struct.Struct("!I").unpack
def _parse_ipv4(string):
    try:
        packed = inet_aton(string)
        return _unpack_ipv4(packed)[0]
    except _ACCEPTABLE_ERRORS:
        return None

_unpack_ipv6 = struct.Struct("!QQ").unpack
def _parse_ipv6(string):
    try:
        packed = inet_pton(AF_INET6, string)
    except _ACCEPTABLE_ERRORS:
        return None
    hi, lo = _unpack_ipv6(packed)
    return ((hi << 64) | lo)

class NETBLOCKError(RuleError):
    pass

class NETBLOCK(_Rule):
    @classmethod
    def dump_rule(cls, dump, name, rule):
        element = Element(name, ip=rule.ip, bits=rule.bits)
        if rule.keys is not None:
            element.add(serialize.dump_list(dump, "keys", rule.keys))
        return element

    @classmethod
    def load_rule(cls, load, element):
        ip = element.get_attr("ip", None)
        bits = element.get_attr("bits", None)
        if None in (ip, bits):
            raise RuleError(element)
        try:
            bits = int(bits)
        except ValueError:
            raise RuleError(element)

        keys = None
        for child in element.children():
            keys = serialize.load_list(load, child)
        return cls(ip, bits, keys)

    def __init__(self, ip, bits, keys=None):
        if keys is not None:
            keys = frozenset(keys)
        self.keys = keys
        self.ip = ip
        self.bits = bits

        for (parser, size) in ((_parse_ipv4, 32), (_parse_ipv6, 128)):
            ip_num = parser(ip)
            if ip_num is not None:
                self.parser = parser
                self.mask = ((1 << size) - 1) ^ ((1 << (size-bits)) - 1)
                self.ip_num = ip_num & self.mask
                break
        else:
            raise NETBLOCKError("could not parse IP %r" % ip)

        _Rule.__init__(self, (self.parser, self.ip_num, self.bits, self.keys))

    def __repr__(self):
        keys = self.keys
        if keys is not None:
            keys = tuple(keys)
        args = ", ".join(map(repr, (self.ip, self.bits, keys)))
        return self.__class__.__name__ + "(" + args + ")"

    def _filter(self, value):
        return value is not None and value & self.mask == self.ip_num

    def match_with_cache(self, event, cache):
        if self.keys is None:
            keys = event.keys()
        else:
            keys = self.keys

        for key in keys:
            if event.contains(key, parser=self.parser, filter=self._filter):
                return True
        return False
NETBLOCK.serialize_register()

if __name__ == "__main__":
    import unittest
    from abusehelper.core import events

    class MockEvent(events.Event):
        def __init__(self, **keys):
            events.Event.__init__(self)
            for key, values in keys.iteritems():
                self.update(key, values)

    class RuleClassifierTests(unittest.TestCase):
        def test_inc(self):
            c = RuleClassifier()
            c.inc(MATCH("a", "b"), "c")
            assert set(c.classify(MockEvent(a=["b"]))) == set(["c"])
            assert not c.is_empty()

            c.inc(MATCH("a"), "d")
            assert set(c.classify(MockEvent(a=["b"]))) == set(["c", "d"])
            assert set(c.classify(MockEvent(a=["x"]))) == set(["d"])
            assert not c.is_empty()

        def test_dec(self):
            c = RuleClassifier()
            c.inc(MATCH("a", "b"), "c")
            c.inc(MATCH("a", "b"), "d")

            c.dec(MATCH("a", "b"), "c")
            assert set(c.classify(MockEvent(a=["b"]))) == set(["d"])
            assert not c.is_empty()

            c.dec(MATCH("a", "b"), "d")
            assert set(c.classify(MockEvent(a=["b"]))) == set([])
            assert c.is_empty()

    class MatchTests(unittest.TestCase):
        def test_init(self):
            self.assertRaises(MATCHError, MATCH, "key", re.compile("."))
            self.assertRaises(MATCHError, MATCH, "key", re.compile(".", re.L))

        def test_match(self):
            rule = MATCH()
            assert not rule.match(MockEvent())
            assert rule.match(MockEvent(a=["b"]))
            assert rule.match(MockEvent(x=["y"]))

            rule = MATCH("a")
            assert not rule.match(MockEvent())
            assert rule.match(MockEvent(a=["b"]))
            assert not rule.match(MockEvent(x=["y"]))

            rule = MATCH("a", "b")
            assert not rule.match(MockEvent())
            assert rule.match(MockEvent(a=["b"]))
            assert not rule.match(MockEvent(a=["a"]))

            rule = MATCH("a", re.compile("b", re.U))
            assert not rule.match(MockEvent())
            assert rule.match(MockEvent(a=["abba"]))
            assert not rule.match(MockEvent(a=["aaaa"]))

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
        def test_bad_data(self):
            rule = NETBLOCK("0.0.0.0", 0)
            assert not rule.match(MockEvent(ip=[u"not valid"]))
            assert not rule.match(MockEvent(ip=[u"\xe4 not convertible to ascii"]))

        def test_eq(self):
            assert NETBLOCK("0.0.0.0", 16) == NETBLOCK("0.0.0.0", 16)
            assert NETBLOCK("0.0.0.0", 16) == NETBLOCK("0.0.255.255", 16)
            assert NETBLOCK("0.0.0.0", 24) != NETBLOCK("0.0.255.255", 24)
            assert NETBLOCK("::", 24) != NETBLOCK("0.0.0.0", 24)

        def test_match_ipv6(self):
            rule = NETBLOCK("2001:0db8:ac10:fe01::", 32)
            assert rule.match(MockEvent(ip=["2001:0db8:aaaa:bbbb:cccc::"]))

        def test_non_match_ipv6(self):
            rule = NETBLOCK("2001:0db8:ac10:fe01::", 32)
            assert not rule.match(MockEvent(ip=["::1"]))

        def test_match_arbitrary_key(self):
            rule = NETBLOCK("1.2.3.4", 24)
            assert rule.match(MockEvent(somekey=["1.2.3.255"]))

        def test_non_match_arbitrary_key(self):
            rule = NETBLOCK("1.2.3.4", 24)
            assert not rule.match(MockEvent(somekey=["1.2.4.255"]))

        def test_match_ip_key(self):
            rule = NETBLOCK("1.2.3.4", 24, keys=["ip"])
            assert rule.match(MockEvent(somekey=["4.5.6.255"], ip=["1.2.3.255"]))

        def test_nonmatch_ip_key(self):
            rule = NETBLOCK("1.2.3.4", 24, keys=["ip"])
            assert not rule.match(MockEvent(somekey=["1.2.3.4"], ip=["1.2.4.255"]))

        def test_non_match_non_ip_data(self):
            rule = NETBLOCK("1.2.3.4", 24)
            assert not rule.match(MockEvent(ip=["this is just some data"]))

    unittest.main()
