import os
import sys
import imp
import inspect
import hashlib
import collections


def base_dir(depth=1):
    calling_frame = inspect.stack()[depth]
    calling_file = calling_frame[1]
    return os.path.dirname(os.path.abspath(calling_file))


def relative_path(*path):
    return os.path.abspath(os.path.join(base_dir(depth=2), *path))


def load_module(module_name, relative_to_caller=True):
    base = base_dir(depth=2)

    path, name = os.path.split(module_name)
    if not path:
        if relative_to_caller:
            paths = [base]
        else:
            paths = None
        found = imp.find_module(name, paths)
        sys.modules.pop(name, None)
        return imp.load_module(name, *found)

    if relative_to_caller:
        module_name = os.path.join(base, module_name)

    module_file = open(module_name, "r")
    try:
        name = hashlib.md5(module_name).hexdigest()
        sys.modules.pop(name, None)
        return imp.load_source(name, module_name, module_file)
    finally:
        module_file.close()


def flatten(obj):
    """
    >>> list(flatten([1, 2]))
    [1, 2]
    >>> list(flatten([[1, [2, 3]], 4]))
    [1, 2, 3, 4]

    >>> list(flatten([xrange(1, 3), xrange(3, 5)]))
    [1, 2, 3, 4]

    >>> list(flatten(list))
    []
    """

    if callable(obj):
        for flattened in flatten(obj()):
            yield flattened
        return

    try:
        iterable = iter(obj)
    except TypeError:
        yield obj
        return

    for item in iterable:
        for flattened in flatten(item):
            yield flattened


def load_configs(module_name, config_name="configs"):
    module = load_module(module_name, False)
    if not hasattr(module, config_name):
        raise ImportError("no %r defined in module %r" %
                          (config_name, module_name))

    config_attr = getattr(module, config_name)
    return flatten(config_attr)


class HashableFrozenDict(collections.Mapping, collections.Hashable):
    _HASHABLE = object()

    def __init__(self, *args, **keys):
        self._dict = dict(*args, **keys)
        self._hash = None

    def __hash__(self):
        hashed = hash(type(self))
        for key, value in sorted(self._dict.iteritems()):
            hashed ^= hash(key)
            if hasattr(value, "__hash__") and callable(value.__hash__):
                hashed ^= hash(value)
            else:
                hashed ^= hash(self._HASHABLE)
        return hashed

    def __eq__(self, other):
        return self._dict == other

    def __getitem__(self, key):
        return self._dict[key]

    def __iter__(self):
        return iter(self._dict)

    def __len__(self):
        return len(self._dict)

    def __contains__(self, key):
        return key in self._dict

    def __reduce__(self):
        return type(self), (self._dict,)
