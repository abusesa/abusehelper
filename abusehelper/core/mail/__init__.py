import idiokit
from ..bot import Param, ParamError


class Handler(object):
    def __init__(self, log):
        self.log = log

    @idiokit.stream
    def handle(self, msg):
        handle_default = getattr(self, "handle_default", None)

        for part in msg.walk():
            content_type = part.get_content_type()
            suffix = content_type.replace("-", "__").replace("/", "_")

            handler = getattr(self, "handle_" + suffix, handle_default)
            if handler is None:
                continue

            skip_rest = yield handler(part)
            if skip_rest:
                return


def _load_callable(value):
    """
    Load and return a callable.

    >>> import uuid
    >>> _load_callable("uuid.UUID") == uuid.UUID
    True

    If the value is not a string but a callable object then return it as-is.

    >>> _load_callable(uuid.UUID) == uuid.UUID
    True

    if the value is neither a string nor a callable then raise TypeError.

    >>> _load_callable(2)
    Traceback (most recent call last):
        ...
    TypeError: expected a string or a callable

    If the value is a string but points to a non-callable then raise TypeError.

    >>> _load_callable("uuid.NAMESPACE_DNS")
    Traceback (most recent call last):
        ...
    TypeError: expected a string or a callable

    Raise ValueError if the callable cannot be loaded.

    >>> _load_callable("SomeClass")
    Traceback (most recent call last):
        ...
    ValueError: missing module name

    >>> _load_callable("abusehelper.nonexisting.SomeClass")
    Traceback (most recent call last):
        ...
    ValueError: no module named 'abusehelper.nonexisting'

    >>> _load_callable("abusehelper.NonExistingClass")
    Traceback (most recent call last):
        ...
    ValueError: module 'abusehelper' has no attribute 'NonExistingClass'
    """

    if isinstance(value, basestring):
        module, _, classname = value.rpartition(".")
        if not module:
            raise ValueError("missing module name")

        try:
            mod = __import__(module, fromlist=[classname])
        except ImportError:
            raise ValueError("no module named '{0}'".format(module))

        try:
            value = getattr(mod, classname)
        except AttributeError:
            raise ValueError("module '{0}' has no attribute '{1}'".format(module, classname))

    if not callable(value):
        raise TypeError("expected a string or a callable")

    return value


class _CallableParam(Param):
    def parse(self, value):
        try:
            return _load_callable(value)
        except ValueError as error:
            raise ParamError(*error.args)
