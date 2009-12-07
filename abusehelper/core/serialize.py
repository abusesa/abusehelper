from base64 import b64encode, b64decode
from idiokit import threado
from idiokit.xmlcore import Element

class AlreadyRegistered(Exception): pass
class AlreadyRegisteredType(AlreadyRegistered): pass
class AlreadyRegisteredName(AlreadyRegistered): pass

class UnregisteredType(Exception): pass
class UnregisteredName(Exception): pass

class Marshal(object):
    def __init__(self, register_common=True):
        self.types = dict()
        self.names = dict()

        if register_common:
            self.register(dump_dict, load_dict, dict, "dict")
            self.register(dump_list, load_list, 
                          (list, tuple, set, frozenset), "list")
            self.register(dump_int, load_int, int, "int")
            self.register(dump_float, load_float, float, "float")
            self.register(dump_nil, load_nil, type(None), "nil")
            self.register(dump_str, load_str, unicode, "str")
            self.register(dump_b64, load_b64, str, "b64")

    def register(self, dump, load, types, name, overwrite=False):
        if isinstance(types, type):
            types = [types]

        for obj_type in types:
            if obj_type in self.types and not overwrite:
                raise TypeAlreadyRegistered(obj_type)
            self.types[obj_type] = dump, name

        if name in self.names and not overwrite:
            raise NameAlreadyRegistered(name)
        self.names[name] = load

    def dump(self, obj):
        obj_type = type(obj)
        if obj_type not in self.types:
            raise UnregisteredType(obj_type)
        dump, name = self.types[obj_type]
        return dump(self.dump, name, obj)

    def load(self, element):
        name = element.name
        if name not in self.names:
            raise UnregisteredName(name)
        load = self.names[name]
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
    element.text = obj
    return element
def load_str(load, element):
    return element.text

def dump_b64(dump, name, obj):
    element = Element(name)
    element.text = b64encode(obj)
    return element
def load_b64(load, element):
    return b64decode(element.text)

global_marshal = Marshal()
register = global_marshal.register
dump = global_marshal.dump
load = global_marshal.load
