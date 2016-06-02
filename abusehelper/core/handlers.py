import json
import collections

from . import bot, utils


class HandlerParam(bot.Param):
    def parse(self, value):
        try:
            return json.loads(value)
        except ValueError:
            return value


def load_handler(handler_spec):
    """
    >>> import logging
    >>> log = logging.getLogger("dummy")
    >>> handler = load_handler({
    ...     "type": "abusehelper.core.mail.Handler"
    ... })
    >>> type(handler(log=log))
    <class 'abusehelper.core.mail.Handler'>
    >>> handler(log=log).log is log
    True

    Extra keys in aside from "type" will be given as keyword arguments when
    instantiating the handler. The arguments given to load_handler take priority
    over overlapping keyword arguments given at instantiation.

    >>> handler = load_handler({
    ...     "type": "abusehelper.core.mail.Handler",
    ...     "log": log
    ... })
    >>> handler().log is log
    True
    >>> other_log = logging.getLogger("other")
    >>> other_log is not log
    True
    >>> handler(log=other_log).log is log
    True

    Instead of a string the "type" key can contain a Handler type object.

    >>> from abusehelper.core.mail import Handler
    >>> handler = load_handler({
    ...     "type": Handler,
    ...     "log": log
    ... })
    >>> type(handler())
    <class 'abusehelper.core.mail.Handler'>

    A plain string is a shorthand for {"type": <string>}, and a plain
    Handler type object is a shorthand for {"type": <object>}.

    >>> handler = load_handler("abusehelper.core.mail.Handler")
    >>> type(handler(log=log))
    <class 'abusehelper.core.mail.Handler'>

    >>> handler = load_handler(Handler)
    >>> type(handler(log=log))
    <class 'abusehelper.core.mail.Handler'>

    ValueError will be raised when there is no "type" key and the argument is
    not a shorthand.

    >>> load_handler({})
    Traceback (most recent call last):
        ...
    ValueError: missing key 'type'
    """

    if isinstance(handler_spec, collections.Mapping):
        handler_dict = dict(handler_spec)
        try:
            type_path = handler_dict.pop("type")
        except KeyError:
            raise ValueError("missing key 'type'")
        type_ = _load_callable(type_path)
        return _wrap_handler(type_, **handler_dict)

    # Wrap with anyway to force all arguments to be given as keyword arguments.
    type_ = _load_callable(handler_spec)
    return _wrap_handler(type_)


def _wrap_handler(type_, **fixed):
    def _wrapper(**defaults):
        kwargs = dict(defaults)
        kwargs.update(fixed)
        return type_(**kwargs)
    return _wrapper


def _load_callable(value):
    r"""
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
    TypeError: expected a string or a callable, got int

    If the value is a string but points to a non-callable then raise TypeError.

    >>> _load_callable("uuid.NAMESPACE_DNS")
    Traceback (most recent call last):
        ...
    TypeError: expected a string or a callable, got uuid.UUID

    Raise ValueError if the path is not valid.

    >>> _load_callable("SomeClass")
    Traceback (most recent call last):
        ...
    ValueError: missing module name

    Raise ImportError if the callable cannot be loaded.

    >>> _load_callable("abusehelper.nonexisting.SomeClass")
    Traceback (most recent call last):
        ...
    ImportError: no module named 'abusehelper.nonexisting'

    >>> _load_callable("abusehelper.NonExistingClass")
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
