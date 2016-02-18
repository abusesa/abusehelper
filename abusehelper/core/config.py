import os
import sys
import imp
import time
import traceback
import contextlib
import collections

import idiokit
from . import utils


class HashableFrozenDict(collections.Mapping, collections.Hashable):
    _HASHABLE = object()

    @classmethod
    def _hashable_item(cls, item):
        key, value = item
        try:
            hash(value)
        except TypeError:
            return key, cls._HASHABLE
        return key, value

    def __init__(self, *args, **keys):
        self._dict = dict(*args, **keys)
        self._hash = None

    def __hash__(self):
        if self._hash is not None:
            return self._hash

        items = frozenset(map(self._hashable_item, self._dict.iteritems()))
        self._hash = hash(type(self)) ^ hash(items)
        return self._hash

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


@contextlib.contextmanager
def _workdir(workdir):
    cwd = os.getcwd()
    try:
        os.chdir(workdir)
        yield
    finally:
        os.chdir(cwd)


def _load_config_module(abspath, module_name="<config>"):
    with open(abspath, "r") as module_file:
        old_module = sys.modules.pop(module_name, None)
        try:
            module = imp.load_source(module_name, abspath, module_file)
        finally:
            if old_module is not None:
                sys.modules[module_name] = old_module
            else:
                sys.modules.pop(module_name, None)
    return module


def load_configs(path, name="configs"):
    abspath = os.path.abspath(path)
    dirname, filename = os.path.split(abspath)

    sys_path = list(sys.path)
    argv_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

    with _workdir(dirname):
        try:
            try:
                sys.path.remove(argv_dir)
            except ValueError:
                pass
            sys.path.insert(0, dirname)

            module = _load_config_module(abspath)
            if not hasattr(module, name):
                raise ImportError("no {0!r} defined in module {1!r}".format(name, filename))

            config_attr = getattr(module, name)
            return tuple(flatten(config_attr))
        finally:
            sys.path[:] = sys_path


@idiokit.stream
def follow_config(path, poll_interval=1.0, force_interval=30.0):
    last_reload = -float("inf")
    last_mtime = None
    last_error_msg = None

    abspath = os.path.abspath(path)
    while True:
        try:
            now = time.time()
            if now < last_reload:
                last_reload = now

            mtime = os.path.getmtime(abspath)
            if now > last_reload + force_interval or last_mtime != mtime:
                configs = load_configs(abspath)
                yield idiokit.send(True, tuple(flatten(configs)))

                last_error_msg = None
                last_mtime = mtime
                last_reload = now
        except Exception:
            _, exc_value, exc_tb = sys.exc_info()

            stack = traceback.extract_tb(exc_tb)
            error_msg = "Could not load {path!r} (most recent call last):\n{stack}\n{exception}".format(
                path=abspath,
                stack="".join(traceback.format_list(stack)).rstrip(),
                exception=utils.format_exception(exc_value)
            )

            if error_msg != last_error_msg:
                yield idiokit.send(False, error_msg)
                last_error_msg = error_msg
                last_mtime = None

        yield idiokit.sleep(poll_interval)
