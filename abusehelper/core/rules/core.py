import weakref
import threading


def load_reduced(cls, dumped):
    return cls.load(dumped)


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

    def __repr__(self, *args, **keys):
        arg_info = []
        arg_info.extend(repr(x) for x in args)
        arg_info.extend(key + "=" + repr(value) for key, value in keys.iteritems())
        return self.__class__.__name__ + "(" + ", ".join(arg_info) + ")"

    def dump(self):
        return None

    @classmethod
    def load(cls, dumped):
        return cls()

    def __reduce__(self):
        return load_reduced, (type(self), self.dump())
