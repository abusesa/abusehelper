import re
import email
import email.header
import functools
from email.message import Message

import idiokit


def _wrap(message_method):
    @functools.wraps(message_method)
    def _wrapper(self, *args, **keys):
        return message_method(self._message, *args, **keys)
    return _wrapper


class Message(object):
    def __init__(self, message):
        self._message = message

    @idiokit.stream
    def walk(self):
        for part in self._message.walk():
            yield idiokit.send(Message(part))

    @idiokit.stream
    def as_string(self, unixfrom=False):
        yield idiokit.sleep(0.0)

        idiokit.stop(self._message.as_string(unixfrom))

    @idiokit.stream
    def get_payload(self, i=None, decode=False):
        yield idiokit.sleep(0.0)

        if not self.is_multipart():
            idiokit.stop(self._message.get_payload(i, decode))
        elif i is not None:
            idiokit.stop(Message(self._message.get_payload(i, decode)))
        else:
            idiokit.stop(map(Message, self._message.get_payload(i, decode)))

    def get_unicode(self, key, failobj=None, errors="strict"):
        value = self.get(key, None)
        if value is None:
            return failobj

        header = email.header.Header()
        for string, encoding in email.header.decode_header(value):
            header.append(string, encoding, errors)
        return unicode(header)

    is_multipart = _wrap(Message.is_multipart)
    get_unixfrom = _wrap(Message.get_unixfrom)
    get_charset = _wrap(Message.get_charset)
    __len__ = _wrap(Message.__len__)
    __contains__ = _wrap(Message.__contains__)
    __getitem__ = _wrap(Message.__getitem__)
    has_key = _wrap(Message.has_key)
    keys = _wrap(Message.keys)
    values = _wrap(Message.values)
    items = _wrap(Message.items)
    get = _wrap(Message.get)
    get_all = _wrap(Message.get_all)
    get_content_type = _wrap(Message.get_content_type)
    get_content_maintype = _wrap(Message.get_content_maintype)
    get_content_subtype = _wrap(Message.get_content_subtype)
    get_default_type = _wrap(Message.get_default_type)
    get_filename = _wrap(Message.get_filename)
    get_content_charset = _wrap(Message.get_content_charset)


def message_from_string(s):
    return Message(email.message_from_string(s))


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
