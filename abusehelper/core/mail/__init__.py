import json
import idiokit
from .. import bot
from ._utils import load_callable
import collections


class Handler(object):
    def __init__(self, log):
        self.log = log

    @idiokit.stream
    def handle(self, msg):
        handle_default = getattr(self, "handle_default", None)

        stack = [msg]
        while stack:
            part = stack.pop()
            content_type = part.get_content_type()
            suffix = content_type.replace("-", "__").replace("/", "_")

            handler = getattr(self, "handle_" + suffix, handle_default)
            if handler is not None:
                skip_rest = yield handler(part)
                if skip_rest:
                    idiokit.stop(True)
                continue

            if part.is_multipart():
                parts = yield part.get_payload()
                stack.extend(reversed(parts))

        idiokit.stop(False)


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
        type_ = load_callable(type_path)
        return _wrap_handler(type_, **handler_dict)

    # Wrap with anyway to force all arguments to be given as keyword arguments.
    type_ = load_callable(handler_spec)
    return _wrap_handler(type_)


def _wrap_handler(type_, **fixed):
    def _wrapper(**defaults):
        kwargs = dict(defaults)
        kwargs.update(fixed)
        return type_(**kwargs)
    return _wrapper
