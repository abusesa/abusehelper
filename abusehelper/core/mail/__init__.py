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

        for part in msg.walk():
            content_type = part.get_content_type()
            suffix = content_type.replace("-", "__").replace("/", "_")

            handler = getattr(self, "handle_" + suffix, handle_default)
            if handler is None:
                continue

            skip_rest = yield handler(part)
            if skip_rest:
                idiokit.stop(True)

        idiokit.stop(False)


class HandlerParam(bot.Param):
    def parse(self, value):
        try:
            return json.loads(value)
        except ValueError:
            return value


def load_handler(handler_spec):
    """
    >>> from abusehelper.core.mail import Handler
    >>> handler = load_handler(Handler)
    >>> type(handler())
    <class 'abusehelper.core.mail.Handler'>
    >>> handler = load_handler("abusehelper.core.mail.Handler")
    >>> type(handler())
    <class 'abusehelper.core.mail.Handler'>

    >>> dummy_log = object()
    >>> handler = load_handler({
    ...     "class": "abusehelper.core.mail.Handler",
    ...     "log": dummy_log
    ... })
    >>> type(handler())
    <class 'abusehelper.core.mail.Handler'>
    >>> handler().log is dummy_log
    True
    >>> handler = load_handler({
    ...     "class": Handler,
    ...     "log": dummy_log
    ... })
    >>> type(handler())
    <class 'abusehelper.core.mail.Handler'>
    >>> handler().log is dummy_log
    True

    >>> load_handler({})
    Traceback (most recent call last):
        ...
    ValueError: missing key 'class'
    """

    if isinstance(handler_spec, collections.Mapping):
        handler_dict = dict(handler_spec)
        try:
            class_path = handler_dict.pop("class")
        except KeyError:
            raise ValueError("missing key 'class'")
        class_ = load_callable(class_path)
        return _wrap_handler(class_, **handler_dict)

    # Wrap with _load_handler_wrapper anyway to force all arguments to be given
    # as keyword arguments.
    class_ = load_callable(handler_spec)
    return _wrap_handler(class_)


def _wrap_handler(class_, **fixed):
    def _wrapper(**defaults):
        kwargs = dict(defaults)
        kwargs.update(fixed)
        return class_(**kwargs)
    return _wrapper
