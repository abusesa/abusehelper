import os
import json
import email
import logging
import optparse

import idiokit
from ..utils import format_exception
from . import _load_callable


@idiokit.stream
def _print_events():
    while True:
        event = yield idiokit.next()

        json_dict = {}
        for key in event.keys():
            values = event.values(key)
            if len(values) == 1:
                json_dict[key] = values[0]
            else:
                json_dict[key] = list(values)
        print json.dumps(json_dict)


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
    handler_class = _load_callable(args[0])

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
