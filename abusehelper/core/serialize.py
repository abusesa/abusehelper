import weakref
import threading
from base64 import b64encode, b64decode
from idiokit.xmlcore import Element

from . import rules


class NameAlreadyRegistered(Exception):
    pass


class UnregisteredType(Exception):
    pass


class UnregisteredName(Exception):
    pass


class Marshal(object):
    def __init__(self, register_common=True):
        self._lock = threading.Lock()
        self._types = []
        self._names = dict()
        self._cache = weakref.WeakKeyDictionary()

        if register_common:
            self.register(dump_dict, load_dict, dict, "d")
            self.register(dump_list, load_list,
                (list, tuple, set, frozenset), "l")
            self.register(dump_int, load_int, (int, long), "i")
            self.register(dump_float, load_float, float, "f")
            self.register(dump_nil, load_nil, type(None), "n")
            self.register(dump_str, load_str, unicode, "s")
            self.register(dump_bytes, load_bytes, str, "b")
            self.register(dump_bool, load_bool, bool, "t")
            self.register(dump_rule, load_rule, rules.Rule, "r")

    def register(self, dump, load, types, name):
        with self._lock:
            if name in self._names:
                raise NameAlreadyRegistered(name)

            self._types.append((types, dump, name))
            self._names[name] = load
            self._cache.clear()

    def dump(self, obj):
        obj_type = type(obj)

        with self._lock:
            if obj_type not in self._cache:
                info = None
                for types, dump, name in reversed(self._types):
                    if issubclass(obj_type, types):
                        info = dump, name
                        break
                self._cache[obj_type] = info

        info = self._cache[obj_type]
        if info is None:
            raise UnregisteredType(obj_type)

        dump, name = info
        return dump(self.dump, name, obj)

    def load(self, element):
        name = element.name

        with self._lock:
            if name not in self._names:
                raise UnregisteredName(name)
            load = self._names[name]

        return load(self.load, element)


def dump_list(dump, name, obj):
    element = Element(name)
    for item in obj:
        element.add(dump(item))
    return element


def load_list(load, element):
    return tuple(load(item) for item in element.children())


def dump_dict(dump, name, obj):
    return dump_list(dump, name, list(obj.items()))


def load_dict(load, element):
    return dict(load_list(load, element))


def dump_int(dump, name, obj):
    element = Element(name)
    element.text = unicode(obj)
    return element


def load_int(load, element):
    return int(element.text)


def dump_float(dump, name, obj):
    element = Element(name)
    element.text = repr(obj)
    return element


def load_float(load, element):
    return float(element.text)


def dump_nil(dump, name, obj):
    return Element(name)


def load_nil(load, element):
    return None


def dump_str(dump, name, obj):
    element = Element(name)
    element.text = b64encode(obj.encode("utf-8"))
    return element


def load_str(load, element):
    return b64decode(element.text).decode("utf-8")


def dump_bytes(dump, name, obj):
    element = Element(name)
    element.text = b64encode(obj)
    return element


def load_bytes(load, element):
    return b64decode(element.text)


def dump_bool(dump, name, obj):
    return dump_int(dump, name, int(bool(obj)))


def load_bool(load, element):
    return bool(load_int(load, element))


def dump_rule(dump, name, rule):
    return dump_str(dump, name, rules.format(rule))


def load_rule(load, element):
    return rules.parse(load_str(load, element))


global_marshal = Marshal()
register = global_marshal.register
dump = global_marshal.dump
load = global_marshal.load
