import os
import sys
import json
import logging
import inspect
import optparse

import idiokit
from .. import handlers, utils
from .message import message_from_string


def _event_to_dict(event):
    event_dict = {}
    for key in event.keys():
        event_dict[key] = list(event.values(key))
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


def handle(handler_spec, msg_data):
    r"""
    Return a list of event dictionaries collected by handling
    msg_data using handler_spec.

    >>> from abusehelper.core.events import Event
    >>> from abusehelper.core.mail import Handler
    >>>
    >>> class MyHandler(Handler):
    ...     @idiokit.stream
    ...     def handle_text_plain(self, msg):
    ...         yield idiokit.send(Event(a="test"))
    ...
    >>> handle(MyHandler, "From: test@email.example\n\nThis is the payload.")
    [{u'a': [u'test']}]

    Note that to simplify testing the output is a list of dictionaries
    instead of abusehelper.core.events.Event objects.

    msg_data will be cleaned using inspect.cleandoc, so the previous example
    can be expressed with triple quotes:

    >>> handle(MyHandler, '''
    ...     From: test@email.example
    ...
    ...     This is the payload.
    ... ''')
    [{u'a': [u'test']}]
    """

    handler_type = handlers.load_handler(handler_spec)

    msg = message_from_string(inspect.cleandoc(msg_data))

    log = logging.getLogger("Null")
    log_handler = _NullHandler()
    log.addHandler(log_handler)
    try:
        handler = handler_type(log=log)
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
    parser.set_usage("usage: %prog [options] handler [path ...]")

    options, args = parser.parse_args()
    if len(args) < 1:
        parser.error("expected handler")

    try:
        handler_spec = json.loads(args[0])
    except ValueError:
        handler_spec = args[0]
    handler_type = handlers.load_handler(handler_spec)

    def handle_msg(msg):
        handler = handler_type(log=logging)
        idiokit.main_loop(handler.handle(msg) | _print_events())

    def handle_stdin():
        logging.info("Handling stdin")
        msg = message_from_string(sys.stdin.read())
        handle_msg(msg)
        logging.info("Done with stdin")

    def handle_file(filepath):
        try:
            with open(filepath, "rb") as fp:
                msg = message_from_string(fp.read())
        except IOError as ioe:
            logging.info("Skipped '{0}' ({1})".format(filepath, utils.format_exception(ioe)))
        else:
            logging.info("Handling '{0}'".format(filepath))
            handle_msg(msg)
            logging.info("Done with '{0}'".format(filepath))

    paths = args[1:]
    if not paths:
        handle_stdin()
    else:
        for path in paths:
            if path == "-":
                handle_stdin()
            elif os.path.isdir(path):
                for filename in os.listdir(path):
                    handle_file(os.path.join(path, filename))
            else:
                handle_file(path)

if __name__ == "__main__":
    main()
