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
    >>> import logging
    >>> log = logging.getLogger("dummy")
    >>> handler = load_handler({
    ...     "class": "abusehelper.core.mail.Handler"
    ... })
    >>> type(handler(log=log))
    <class 'abusehelper.core.mail.Handler'>
    >>> handler(log=log).log is log
    True

    Extra keys in aside from "class" will be given as keyword arguments when
    instantiating the class. The arguments given to load_handler take priority
    over overlapping keyword arguments given at instantiation.

    >>> handler = load_handler({
    ...     "class": "abusehelper.core.mail.Handler",
    ...     "log": log
    ... })
    >>> handler().log is log
    True
    >>> other_log = logging.getLogger("other")
    >>> other_log is not log
    True
    >>> handler(log=other_log).log is log
    True

    Instead of a string the "class" key can contain a Handler type object.

    >>> from abusehelper.core.mail import Handler
    >>> handler = load_handler({
    ...     "class": Handler,
    ...     "log": log
    ... })
    >>> type(handler())
    <class 'abusehelper.core.mail.Handler'>

    A plain string is a shorthand for {"class": <string>}, and a plain
    Handler type object is a shorthand for {"class": <object>}.

    >>> handler = load_handler("abusehelper.core.mail.Handler")
    >>> type(handler(log=log))
    <class 'abusehelper.core.mail.Handler'>

    >>> handler = load_handler(Handler)
    >>> type(handler(log=log))
    <class 'abusehelper.core.mail.Handler'>

    ValueError will be raised when there is no "class" key and the argument is
    not a shorthand.

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

    # Wrap with anyway to force all arguments to be given as keyword arguments.
    class_ = load_callable(handler_spec)
    return _wrap_handler(class_)


def _wrap_handler(class_, **fixed):
    def _wrapper(**defaults):
        kwargs = dict(defaults)
        kwargs.update(fixed)
        return class_(**kwargs)
    return _wrapper
