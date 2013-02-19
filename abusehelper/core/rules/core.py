class Matcher(object):
    def __init__(self, args=(), keys=()):
        self._hashable = args, keys
        self._hash = None

    def __hash__(self):
        if self._hash is None:
            self._hash = hash((type(self), self._hashable))
        return self._hash

    def __eq__(self, other):
        if type(other) != type(self):
            return NotImplemented
        return other._hashable == self._hashable

    def __ne__(self, other):
        eq = self.__eq__(other)
        if eq is NotImplemented:
            return NotImplemented
        return not eq

    def __repr__(self):
        args, keys = self._hashable
        arg_info = map(repr, args)
        arg_info.extend(key + "=" + repr(value) for (key, value) in keys)
        return self.__class__.__name__ + "(" + ", ".join(arg_info) + ")"
