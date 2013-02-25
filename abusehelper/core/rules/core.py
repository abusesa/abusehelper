import weakref
import threading


class Matcher(object):
    _lock = threading.Lock()
    _refs = weakref.WeakValueDictionary()

    def __new__(cls, *args, **keys):
        instance = object.__new__(cls)
        instance.init(*args, **keys)

        key = cls, instance.unique_key()

        with cls._lock:
            return cls._refs.setdefault(key, instance)

    def init(self):
        pass

    def unique_key(self):
        return None

    def arguments(self):
        return [], []

    def __repr__(self):
        args, keys = self.arguments()

        arg_info = []
        arg_info.extend(repr(x) for x in args)
        arg_info.extend(key + "=" + repr(value) for key, value in keys)
        return self.__class__.__name__ + "(" + ", ".join(arg_info) + ")"
