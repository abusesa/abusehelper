import os
import json
import email
import logging
import inspect
import optparse

import idiokit
from ..utils import format_exception
from ._utils import load_callable


def _event_to_dict(event):
    event_dict = {}
    for key in event.keys():
        values = event.values(key)
        if len(values) == 1:
            event_dict[key] = values[0]
        else:
            event_dict[key] = list(values)
    return event_dict


@idiokit.stream
def _collect_events():
    results = []
    while True:
        try:
            event = yield idiokit.next()
        except StopIteration:
            idiokit.stop(results)
        else:
            results.append(_event_to_dict(event))


@idiokit.stream
def _print_events():
    while True:
        event = yield idiokit.next()
        print json.dumps(_event_to_dict(event))


class _NullHandler(logging.Handler):
    r"""
    A dummy logging handler that just scraps the log messages.

    Needed because of Python 2.6, as the Python 2.7 standard library
    contains logging.handlers.NullHandler.
    """

    def emit(self, record):
        pass


def handle(handler_class, msg_data):
    r"""
    Return a list of event dictionaries collected by handling
    msg_data using handler_class.

    >>> from abusehelper.core.events import Event
    >>> from abusehelper.core.mail import Handler
    >>>
    >>> class MyHandler(Handler):
    ...     @idiokit.stream
    ...     def handle_text_plain(self, msg):
    ...         yield idiokit.send(Event(a="test"))
    ...
    >>> handle(MyHandler, "From: test@email.example\n\nThis is the payload.")
    [{u'a': u'test'}]

    Note that to simplify testing the output is a list of dictionaries
    instead of abusehelper.core.events.Event objects.

    msg_data will be cleaned using inspect.cleandoc, so the previous example
    can be expressed with triple quotes:

    >>> handle(MyHandler, '''
    ...     From: test@email.example
    ...
    ...     This is the payload.
    ... ''')
    [{u'a': u'test'}]
    """

    msg = email.message_from_string(inspect.cleandoc(msg_data))

    log = logging.getLogger("Null")
    log_handler = _NullHandler()
    log.addHandler(log_handler)
    try:
        handler = handler_class(log)
        return idiokit.main_loop(handler.handle(msg) | _collect_events())
    finally:
        log.removeHandler(log_handler)


def main():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%SZ"
    )

    parser = optparse.OptionParser()
    parser.set_usage("usage: %prog [options] handler [dirname ...]")

    options, args = parser.parse_args()
    if len(args) < 1:
        parser.error("expected handler")
    handler_class = load_callable(args[0])

    for dirname in args[1:]:
        for filename in os.listdir(dirname):
            orig_name = os.path.join(dirname, filename)
            try:
                with open(orig_name, "rb") as fp:
                    msg = email.message_from_file(fp)
            except IOError as ioe:
                logging.info("skipped '{0}' ({1})".format(orig_name, format_exception(ioe)))
                continue

            logging.info("handling '{0}'".format(orig_name))
            handler = handler_class(logging)
            idiokit.main_loop(handler.handle(msg) | _print_events())
            logging.info("done with '{0}'".format(orig_name))


if __name__ == "__main__":
    main()
