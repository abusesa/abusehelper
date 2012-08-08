import os
import sys
import imp
import hashlib
import collections

import idiokit
from idiokit import timer


def relative_path(*path):
    return os.path.abspath(os.path.join(os.getcwd(), *path))


def load_module(module_name, relative_to_cwd=True):
    path, name = os.path.split(module_name)
    if not path:
        if relative_to_cwd:
            paths = [os.getcwd()]
        else:
            paths = None
        found = imp.find_module(name, paths)
        sys.modules.pop(name, None)
        return imp.load_module(name, *found)

    if relative_to_cwd:
        module_name = os.path.join(os.getcwd(), module_name)

    module_file = open(module_name, "r")
    try:
        name = hashlib.md5(module_name).hexdigest()
        sys.modules.pop(name, None)
        return imp.load_source(name, module_name, module_file)
    finally:
        module_file.close()


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


def load_configs(path, name="configs"):
    abspath = os.path.abspath(path)
    dirname, filename = os.path.split(abspath)

    cwd = os.getcwd()
    try:
        os.chdir(dirname)

        module = load_module(abspath, False)
        if not hasattr(module, name):
            raise ImportError("no {0!r} defined in module {1!r}".format(name, filename))

        config_attr = getattr(module, name)
        return tuple(flatten(config_attr))
    finally:
        os.chdir(cwd)


@idiokit.stream
def follow_config(path, poll_interval=1.0):
    last_mtime = None
    last_error_msg = None

    abspath = os.path.abspath(path)
    while True:
        try:
            mtime = os.path.getmtime(abspath)
            if last_mtime != mtime:
                configs = load_configs(abspath)
                yield idiokit.send(True, tuple(flatten(configs)))

                last_error_msg = None
                last_mtime = mtime
        except Exception as exc:
            error_msg = "Could not load module {0!r}: {1}".format(abspath, exc)
            if error_msg != last_error_msg:
                yield idiokit.send(False, error_msg)

                last_error_msg = error_msg
                last_mtime = None

        yield timer.sleep(poll_interval)
