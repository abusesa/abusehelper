from idiokit.xmlcore import Element
from abusehelper.core import serialize

class RuleError(Exception):
    pass

class _Rule(object):
    @classmethod
    def serialize_register(cls):
        name = "rule-" + cls.__name__.lower()
        serialize.register(cls.dump_rule, cls.load_rule, cls, name)
    
    def __init__(self, *args, **keys):
        self.arguments = tuple(args), frozenset(keys.items())

    def __eq__(self, other):
        if other.__class__ is not self.__class__:
            return NotImplemented
        return self.arguments == other.arguments

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

    def __hash__(self):
        return hash(self.__class__) ^ hash(self.arguments)

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
        _Rule.__init__(self, first, *rest)
        self.children = (first,) + rest

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
        _Rule.__init__(self, first, *rest)
        self.children = (first,) + rest

    def __call__(self, *args, **keys):
        for child in self.children:
            if not child(*args, **keys):
                return False
        return True
AND.serialize_register()

class CONTAINS(_Rule):
    @classmethod
    def dump_rule(cls, dump, name, rule):
        element = Element(name)
        element.add(serialize.dump_list(dump, "keys", rule.keys))
        element.add(serialize.dump_dict(dump, "key-values", rule.key_values))
        return element

    @classmethod
    def load_rule(cls, load, element):
        children = list(element.children())
        if len(children) != 2:
            raise RuleError(element)
        keys = set(serialize.load_list(load, children[0]))
        key_values = serialize.load_dict(load, children[1])
        return cls(*keys, **key_values)
                 
    def __init__(self, *keys, **key_values):
        _Rule.__init__(self, *keys, **key_values)
        self.keys = keys
        self.key_values = key_values

    def __call__(self, event):
        for key in self.keys:
            if not event.contains_key(key):
                return False
        for key, value in self.key_values.items():
            if not event.contains_key_value(key, value):
                return False
        return True
CONTAINS.serialize_register()

import struct
from socket import inet_aton, error

class NETBLOCK(_Rule):
    unpack_ip = struct.Struct("!I").unpack

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

    def ip_to_num(self, ip):
        try:
            packed = inet_aton(ip)
        except error:
            return None
        return self.unpack_ip(packed)[0]

    def __init__(self, ip, bits, keys=None):
        if keys is not None:
            keys = frozenset(keys)

        _Rule.__init__(self, ip, bits, keys)

        self.ip = ip
        self.bits = bits
        self.keys = keys

        self.mask = ((1<<32)-1) ^ ((1<<(32-bits))-1)
        self.ip_num = self.ip_to_num(ip) & self.mask

    def __call__(self, event):
        if self.keys is None:
            keys = event.attrs.keys()
        else:
            keys = self.keys

        for key in keys:
            values = event.attrs.get(key, ())
            for value in values:
                ip_num = self.ip_to_num(value)
                if ip_num is None:
                    continue
                if ip_num & self.mask == self.ip_num:
                    return True
        return False
NETBLOCK.serialize_register()

import unittest

class MockEvent(object):
    def __init__(self, **keys):
        self.attrs = dict(keys)

class NetblockTests(unittest.TestCase):
    def test_match_arbitrary_key(self):
        rule = NETBLOCK("1.2.3.4", 24)
        assert rule(MockEvent(somekey=["1.2.3.255"]))

    def test_non_match_arbitrary_key(self):
        rule = NETBLOCK("1.2.3.4", 24)
        assert not rule(MockEvent(somekey=["1.2.4.255"]))

    def test_match_given_key(self):
        rule = NETBLOCK("1.2.3.4", 24, keys=["ip"])
        assert rule(MockEvent(somekey=["4.5.6.255"], ip=["1.2.3.255"]))

    def test_nonmatch_given_key(self):
        rule = NETBLOCK("1.2.3.4", 24, keys=["ip"])
        assert not rule(MockEvent(somekey=["4.5.6.255"], ip=["1.2.4.255"]))

    def test_non_match_non_ip_data(self):
        rule = NETBLOCK("1.2.3.4", 24)
        assert not rule(MockEvent(somekey=["this is just some data"]))

if __name__ == "__main__":
    unittest.main()
