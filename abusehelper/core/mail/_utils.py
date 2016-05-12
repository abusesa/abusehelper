from .. import utils


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
    TypeError: expected a string or a callable, got int

    If the value is a string but points to a non-callable then raise TypeError.

    >>> load_callable("uuid.NAMESPACE_DNS")
    Traceback (most recent call last):
        ...
    TypeError: expected a string or a callable, got uuid.UUID

    Raise ValueError if the path is not valid.

    >>> load_callable("SomeClass")
    Traceback (most recent call last):
        ...
    ValueError: missing module name

    Raise ImportError if the callable cannot be loaded.

    >>> load_callable("abusehelper.nonexisting.SomeClass")
    Traceback (most recent call last):
        ...
    ImportError: no module named 'abusehelper.nonexisting'

    >>> load_callable("abusehelper.NonExistingClass")
    Traceback (most recent call last):
        ...
    ImportError: module 'abusehelper' has no attribute 'NonExistingClass'
    """

    if isinstance(value, basestring):
        module, _, name = value.rpartition(".")
        if not module:
            raise ValueError("missing module name")

        try:
            mod = __import__(module, fromlist=[name])
        except ImportError:
            raise ImportError("no module named '{0}'".format(module))

        try:
            value = getattr(mod, name)
        except AttributeError:
            raise ImportError("module '{0}' has no attribute '{1}'".format(module, name))

    if not callable(value):
        raise TypeError("expected a string or a callable, got {0}".format(utils.format_type(value)))

    return value
