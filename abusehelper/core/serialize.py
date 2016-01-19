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


class Serializer(object):
    def __init__(self, register_common=True):
        self._lock = threading.Lock()
        self._types = []
        self._names = dict()
        self._cache = weakref.WeakKeyDictionary()

        if register_common:
            self.register("d", Dict(dict))
            self.register("l", List(list, tuple, set, frozenset))
            self.register("i", Int(int, long))
            self.register("f", Float(float))
            self.register("n", Nil(type(None)))
            self.register("s", Str(unicode))
            self.register("b", Bytes(str))
            self.register("t", Bool(bool))

            self.register("ra", Rule(rules.And))
            self.register("ro", Rule(rules.Or))
            self.register("rn", Rule(rules.No))
            self.register("rm", Rule(rules.Match))
            self.register("rc", Rule(rules.NonMatch))
            self.register("rf", Rule(rules.Fuzzy))
            self.register("ry", Rule(rules.Anything))

            self.register("rx", Rule(rules.RegExp))
            self.register("rs", Rule(rules.String))
            self.register("ri", Rule(rules.IP))
            self.register("rd", Rule(rules.DomainName))

    def register(self, name, serializer):
        with self._lock:
            if name in self._names:
                raise NameAlreadyRegistered(name)

            self._types.append((name, serializer))
            self._names[name] = serializer
            self._cache.clear()

    def _find_serializer(self, obj):
        obj_type = type(obj)

        with self._lock:
            if obj_type not in self._cache:
                info = None
                for name, serializer in reversed(self._types):
                    if serializer.isinstance(obj):
                        info = name, serializer
                        break
                self._cache[obj_type] = info

        info = self._cache[obj_type]
        if info is None:
            raise UnregisteredType(obj_type)

        return info

    def dump(self, obj):
        name, serializer = self._find_serializer(obj)
        return serializer.dump(obj, name, self)

    def normalize(self, obj):
        _, serializer = self._find_serializer(obj)
        return serializer.normalize(obj, self)

    def load(self, element):
        name = element.name

        with self._lock:
            if name not in self._names:
                raise UnregisteredName(name)
            serializer = self._names[name]

        return serializer.load(element, self)


class SubSerializer(object):
    def __init__(self, *types):
        self._types = types

    def isinstance(self, obj):
        return isinstance(obj, self._types)

    def dump(self, obj, name, context):
        raise NotImplementedError()

    def load(self, obj, context):
        raise NotImplementedError()

    def normalize(self, obj, context):
        return self.load(self.dump(obj, context), context)


class List(SubSerializer):
    def dump(self, obj, name, context):
        element = Element(name)
        for item in obj:
            element.add(context.dump(item))
        return element

    def load(self, element, context):
        return tuple(load(item) for item in element.children())

    def normalize(self, obj, context):
        return tuple(context.normalize(x) for x in obj)


class Dict(SubSerializer):
    _list = List()

    def dump(self, obj, name, context):
        return self._list.dump(obj.items(), name, context)

    def load(self, element, context):
        items = self._list.load(element, context)
        if all(isinstance(x, tuple) and len(x) == 2 for x in items):
            return dict(items)
        return dict(zip(items[::2], items[1::2]))

    def normalize(self, obj, context):
        return dict(self._list.normalize(obj.items(), context))


class Int(SubSerializer):
    def dump(self, obj, name, context):
        return Element(name, _text=unicode(obj))

    def load(self, element, context):
        return int(element.text)

    def normalize(self, obj, context):
        return obj


class Float(SubSerializer):
    def dump(self, obj, name, context):
        return Element(name, _text=repr(obj))

    def load(self, element, context):
        return float(element.text)

    def normalize(self, obj, context):
        return obj


class Nil(SubSerializer):
    def dump(self, obj, name, context):
        return Element(name)

    def load(self, element, context):
        return None

    def normalize(self, obj, context):
        return None


class Str(SubSerializer):
    def dump(self, obj, name, context):
        return Element(name, _text=b64encode(obj.encode("utf-8")))

    def load(self, element, context):
        return b64decode(element.text).decode("utf-8")

    def normalize(self, obj, context):
        return obj


class Bytes(SubSerializer):
    def dump(self, obj, name, context):
        return Element(name, _text=b64encode(obj))

    def load(self, element, context):
        return b64decode(element.text)

    def normalize(self, obj, context):
        return obj


class Bool(SubSerializer):
    def dump(self, obj, name, context):
        return Element(name, _text=unicode(int(bool(obj))))

    def load(self, element, context):
        return bool(int(element.text))

    def normalize(self, obj, context):
        return obj


class Rule(SubSerializer):
    def __init__(self, rule_type):
        SubSerializer.__init__(self, rule_type)

        self._rule_type = rule_type

    def dump(self, obj, name, context):
        element = Element(name)
        element.add(context.dump(obj.dump()))
        return element

    def load(self, element, context):
        for child in element.children():
            return self._rule_type.load(context.load(child))
        raise ValueError("element has no child elements")

    def normalize(self, obj, context):
        return obj.load(context.normalize(obj.dump()))


global_serializer = Serializer()
register = global_serializer.register
dump = global_serializer.dump
load = global_serializer.load
normalize = global_serializer.normalize
