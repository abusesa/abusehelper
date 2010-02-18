import os
import sys
import imp
import hashlib
import inspect
import weakref

class Formatter(dict):
    def __init__(self, config):
        dict.__init__(self)
        self.config = config

    def __getitem__(self, key):
        try:
            return dict.__getitem__(self, key)
        except KeyError:
            return getattr(self.config, key)

def dynamic(func_or_string):
    refs = weakref.WeakKeyDictionary()

    def getter(self):
        if self in refs:
            return refs[self]

        if callable(func_or_string):
            return func_or_string(self)
        return func_or_string % Formatter(self)

    def setter(self, value):
        refs[self] = value

    return property(getter, setter)

def load_module(module_name, relative_to_caller=True):
    calling_frame = inspect.stack()[1]
    calling_file = calling_frame[1]
    base_dir, _ = os.path.split(os.path.abspath(calling_file))
    
    path, name = os.path.split(module_name)
    if not path:
        paths = list(sys.path)
        if relative_to_caller:
            paths = [base_dir] + paths
        found = imp.find_module(name, paths)
        return imp.load_module(name, *found)
    
    if relative_to_caller:
        module_name = os.path.join(base_dir, module_name)
    module_file = open(module_name, "r")
    try:
        name = hashlib.md5(module_name).hexdigest()
        return imp.load_source(name, module_name, module_file)
    finally:
        module_file.close()

def default_configs(globals):
    for key, value in globals.items():
        if isinstance(value, Config):
            if not hasattr(value, "name"):
                setattr(value, "name", key)
            yield value

def load_configs(module_name):
    module = load_module(module_name, False)
    configs = getattr(module, "configs", None)

    if configs is None:
        iterator = default_configs(dict(inspect.getmembers(module)))
    else:
        iterator = configs()
        
    for value in iterator:
        yield value

class Config(object):
    def __init__(self, **keys):
        for key, value in keys.items():
            setattr(self, key, value)

    def member_diff(self, base_class=None):
        if base_class is None:
            base_class = self.__class__

        for key, value in inspect.getmembers(self):
            if not hasattr(base_class, key):
                yield key, value
