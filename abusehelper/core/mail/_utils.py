import re
import email.header
from ..bot import Param, ParamError


def get_header(headers, key, default=None):
    value = headers.get(key, None)
    if value is None:
        return default

    bites = []
    for string, encoding in email.header.decode_header(value):
        if encoding is not None:
            string = string.decode(encoding, "replace")
        bites.append(string)

    return u" ".join(bites)


def escape_whitespace(unicode_string):
    r"""
    Return the given unicode string with the whitespace escaped
    using 'unicode-escape' encoding.

    >>> escape_whitespace(u"space is not escaped")
    u'space is not escaped'

    >>> escape_whitespace(u"multi\nline\nwith\ttabs")
    u'multi\\nline\\nwith\\ttabs'
    """

    return re.sub(r"\s", lambda x: unicode(x.group(0).encode("unicode-escape")), unicode_string, re.U)


def load_callable(value):
    r"""
    Load and return a callable.

    >>> import uuid
    >>> load_callable("uuid.UUID") == uuid.UUID
    True

    If the value is not a string but a callable object then return it as-is.

    >>> load_callable(uuid.UUID) == uuid.UUID
    True

    if the value is neither a string nor a callable then raise TypeError.

    >>> load_callable(2)
    Traceback (most recent call last):
        ...
    TypeError: expected a string or a callable

    If the value is a string but points to a non-callable then raise TypeError.

    >>> load_callable("uuid.NAMESPACE_DNS")
    Traceback (most recent call last):
        ...
    TypeError: expected a string or a callable

    Raise ValueError if the callable cannot be loaded.

    >>> load_callable("SomeClass")
    Traceback (most recent call last):
        ...
    ValueError: missing module name

    >>> load_callable("abusehelper.nonexisting.SomeClass")
    Traceback (most recent call last):
        ...
    ValueError: no module named 'abusehelper.nonexisting'

    >>> load_callable("abusehelper.NonExistingClass")
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


class CallableParam(Param):
    def parse(self, value):
        try:
            return load_callable(value)
        except ValueError as error:
            raise ParamError(*error.args)
