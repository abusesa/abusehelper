from idiokit.xmlcore import Element
from abusehelper.core import serialize

import operator
import functools
import re

class RuleError(Exception):
    pass

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

class MATCH(_Rule):
    _flags = tuple(sorted("UIXLMS"))

    @classmethod
    def dump_rule(cls, dump, name, rule):
        flags = rule.flags
        if flags is not None:
            flags = "".join(x for x in cls._flags if flags & getattr(re, x, 0))
        return serialize.dump_list(dump, name, [rule.key, rule.pattern, flags])

    @classmethod
    def load_rule(cls, load, element):
        key, pattern, flags = serialize.load_list(load, element)
        if flags is not None:
            flags = reduce(lambda x, y: getattr(re, y, 0) | x, flags, 0)
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

        _Rule.__init__(self, (key, value))
        self.key = key
        self.value = value
        self.filter = filter
        self.pattern = pattern
        self.flags = flags

    def __repr__(self):
        return self.__class__.__name__ + ("(%r, %r)" % (self.key, self.value))

    def __call__(self, event):
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

    def __call__(self, *args, **keys):
        return not self.child(*args, **keys)
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

    def __call__(self, *args, **keys):
        for child in self.children:
            if child(*args, **keys):
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

    def __call__(self, *args, **keys):
        for child in self.children:
            if not child(*args, **keys):
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

    def __call__(self, *args, **keys):
        return self
ANYTHING.serialize_register()

import struct
from socket import inet_pton, AF_INET, AF_INET6, error

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

    _unpack_ipv4 = struct.Struct("!I").unpack
    _unpack_ipv6 = struct.Struct("!QQ").unpack
    def parse_ip(self, ip):
        try:
            packed = inet_pton(AF_INET, ip)
            return 4, self._unpack_ipv4(packed)[0]
        except error:
            try:
                packed = inet_pton(AF_INET6, ip)
                hi, lo = self._unpack_ipv6(packed)
                return 6, ((hi << 64) | lo)
            except error:
                return None

    def __init__(self, ip, bits, keys=None):
        if keys is not None:
            keys = frozenset(keys)

        self.ip = ip
        self.bits = bits
        self.keys = keys

        parsed = self.parse_ip(ip)
        if parsed is None:
            raise NETBLOCKError("could not parse IP %r" % ip)
        self.version, self.ip_num = parsed
        assert self.version in (4, 6)

        if self.version == 4:
            self.mask = ((1<<32)-1) ^ ((1<<(32-bits))-1)
        elif self.version == 6:
            self.mask = ((1<<128)-1) ^ ((1<<(128-bits))-1)
        self.ip_num &= self.mask

        _Rule.__init__(self, (self.ip_num, self.bits, self.keys))

    def __repr__(self):
        keys = self.keys
        if keys is not None:
            keys = tuple(keys)
        args = ", ".join(map(repr, (self.ip, self.bits, keys)))
        return self.__class__.__name__ + "(" + args + ")"

    def __call__(self, event):
        if self.keys is None:
            keys = event.keys()
        else:
            keys = self.keys

        for key in keys:
            for value in event.values(key):
                parsed = self.parse_ip(value)
                if parsed is None:
                    continue
                version, ip_num = parsed
                if version != self.version:
                    continue
                if ip_num & self.mask == self.ip_num:
                    return True
        return False
NETBLOCK.serialize_register()

# CONTAINS rule type is deprecated. The following compatibility code
# implements CONTAINS using the current supported rule types.

import warnings

def CONTAINS(*keys, **key_values):
    warnings.warn("abusehelper.core.rules.CONTAINS is deprecated. "+
                  "Use abusehelper.core.rules.MATCH instead.")
    return _CONTAINS(keys, key_values)

def _CONTAINS(keys, key_values):
    keys = [MATCH(key) for key in keys]
    key_values = [MATCH(key, value) for (key, value) in key_values.items()]

    children = keys + key_values
    if len(children) == 0:
        return ANYTHING()
    if len(children) == 1:
        return children[0]
    return AND(*children)

def _CONTAINS_load(load, element):
    children = list(element.children())
    if len(children) != 2:
        raise RuleError(element)

    keys = set(serialize.load_list(load, children[0]))
    key_values = serialize.load_dict(load, children[1])
    return _CONTAINS(keys, key_values)
serialize.register(None, _CONTAINS_load, [], "rule-contains")

if __name__ == "__main__":
    import unittest
    from abusehelper.core import events

    class MockEvent(events.Event):
        def __init__(self, **keys):
            events.Event.__init__(self)
            for key, values in keys.iteritems():
                self.update(key, values)

    class ContainsTests(unittest.TestCase):
        def test_match(self):
            rule = CONTAINS()
            assert rule(MockEvent())

            rule = CONTAINS("a")
            assert not rule(MockEvent())
            assert not rule(MockEvent(x=["y"]))
            assert rule(MockEvent(a=["b"]))

            rule = CONTAINS(a="b")
            assert not rule(MockEvent(a=["a"]))
            assert rule(MockEvent(a=["b"]))

            rule = CONTAINS(a="b", x="y")
            assert not rule(MockEvent(x=["y"]))
            assert not rule(MockEvent(a=["b"]))
            assert rule(MockEvent(a=["b"], x=["y"]))

        def test_serialize(self):
            rule = CONTAINS()
            assert serialize.load(serialize.dump(rule)) == rule

            rule = CONTAINS("a")
            assert serialize.load(serialize.dump(rule)) == rule

            rule = CONTAINS(a="a")
            assert serialize.load(serialize.dump(rule)) == rule

            rule = CONTAINS("key", a="a", x="y")
            assert serialize.load(serialize.dump(rule)) == rule

    class MatchTests(unittest.TestCase):
        def test_match(self):
            rule = MATCH()
            assert not rule(MockEvent())
            assert rule(MockEvent(a=["b"]))
            assert rule(MockEvent(x=["y"]))

            rule = MATCH("a")
            assert not rule(MockEvent())
            assert rule(MockEvent(a=["b"]))
            assert not rule(MockEvent(x=["y"]))

            rule = MATCH("a", "b")
            assert not rule(MockEvent())
            assert rule(MockEvent(a=["b"]))
            assert not rule(MockEvent(a=["a"]))

            rule = MATCH("a", re.compile("b"))
            assert not rule(MockEvent())
            assert rule(MockEvent(a=["abba"]))
            assert not rule(MockEvent(a=["aaaa"]))

        def test_eq(self):
            assert MATCH() == MATCH()
            assert MATCH() != MATCH("a")
            assert MATCH("a") == MATCH("a")
            assert MATCH("a") != MATCH("x")
            assert MATCH("a") != MATCH("a", "b")
            assert MATCH("a", "b") == MATCH("a", "b")
            assert MATCH("a", "b") != MATCH("x", "y")
            assert MATCH("a", re.compile("b")) == MATCH("a", re.compile("b"))
            assert MATCH("a", re.compile("b")) != MATCH("x", re.compile("y"))
            assert MATCH("a", re.compile("b")) != MATCH("a", "b")
            assert MATCH("a", re.compile("b", re.I)) != MATCH("a", re.compile("a"))
            assert MATCH("a", re.compile("b", re.I)) != MATCH("a", re.compile("a", re.I))

        def test_serialize(self):
            rule = MATCH()
            assert serialize.load(serialize.dump(rule)) == rule

            rule = MATCH("a", "b")
            assert serialize.load(serialize.dump(rule)) == rule

            rule = MATCH("a", re.compile("b", re.I))
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

        def test_match_ipv6(self):
            rule = NETBLOCK("2001:0db8:ac10:fe01::", 32)
            assert rule(MockEvent(ip=["2001:0db8:aaaa:bbbb:cccc::"]))

        def test_non_match_ipv6(self):
            rule = NETBLOCK("2001:0db8:ac10:fe01::", 32)
            assert not rule(MockEvent(ip=["::1"]))

        def test_match_arbitrary_key(self):
            rule = NETBLOCK("1.2.3.4", 24)
            assert rule(MockEvent(somekey=["1.2.3.255"]))

        def test_non_match_arbitrary_key(self):
            rule = NETBLOCK("1.2.3.4", 24)
            assert not rule(MockEvent(somekey=["1.2.4.255"]))

        def test_match_ip_key(self):
            rule = NETBLOCK("1.2.3.4", 24, keys=["ip"])
            assert rule(MockEvent(somekey=["4.5.6.255"], ip=["1.2.3.255"]))

        def test_nonmatch_ip_key(self):
            rule = NETBLOCK("1.2.3.4", 24, keys=["ip"])
            assert not rule(MockEvent(somekey=["1.2.3.4"], ip=["1.2.4.255"]))

        def test_non_match_non_ip_data(self):
            rule = NETBLOCK("1.2.3.4", 24)
            assert not rule(MockEvent(ip=["this is just some data"]))

    unittest.main()
