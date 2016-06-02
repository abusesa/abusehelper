import json
import logging
import optparse
import fileinput
import itertools

import idiokit
from .. import events, handlers


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
def _feed(iterable):
    for obj in iterable:
        yield idiokit.send(obj)


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


def handle(handler_spec, input_events):
    r"""
    Return a list of event dictionaries collected by handling  input_events
    using handler_spec.

    >>> from abusehelper.core.events import Event
    >>> from abusehelper.core.transformation import Handler
    >>>
    >>> class MyHandler(Handler):
    ...     @idiokit.stream
    ...     def transform(self):
    ...         while True:
    ...             event = yield idiokit.next()
    ...             event.add("a", "b")
    ...             yield idiokit.send(event)
    ...
    >>> handle(MyHandler, [{}])
    [{u'a': [u'b']}]

    Note that to simplify testing the output is a list of dictionaries
    instead of abusehelper.core.events.Event objects.
    """

    handler_type = handlers.load_handler(handler_spec)

    log = logging.getLogger("Null")
    log_handler = _NullHandler()
    log.addHandler(log_handler)
    try:
        handler = handler_type(log=log)
        return idiokit.main_loop(idiokit.pipe(
            _feed(itertools.imap(events.Event, input_events)),
            handler.transform(),
            _collect_events()
        ))
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

    def generate_events():
        for line in fileinput.input(args[1:]):
            line = line.strip()
            if not line:
                continue
            yield events.Event(json.loads(line))

    idiokit.main_loop(idiokit.pipe(
        _feed(generate_events()),
        handler_type(log=logging).transform(),
        _print_events()
    ))


if __name__ == "__main__":
    main()
