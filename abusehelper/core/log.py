import logging

from abusehelper.core import events
from idiokit.xmlcore import Element


class RoomHandler(logging.Handler):
    def __init__(self, room):
        logging.Handler.__init__(self)

        self.room = room

        formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s",
                                      "%Y-%m-%d %H:%M:%S")
        self.setFormatter(formatter)

    def emit(self, record):
        try:
            event = getattr(record, "event", None)

            body = Element("body")
            body.text = self.format(record)

            if event is not None:
                self.room.send(event.to_elements(include_body=False), body)
            else:
                self.room.send(body)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)


def _level(lvl):
    def log(self, *args, **keys):
        return self.log(lvl, *args, **keys)
    return log


class EventLogger(object):
    def __init__(self, logger):
        self._logger = logger

    def __getattr__(self, key):
        return getattr(self._logger, key)

    debug = _level(logging.DEBUG)
    info = _level(logging.INFO)
    warning = _level(logging.WARNING)
    error = _level(logging.ERROR)
    critical = _level(logging.CRITICAL)

    def log(self, lvl, *args, **keys):
        if len(args) > 1 and keys:
            raise TypeError("mixed positional and keyword arguments")

        event = events.Event(keys)

        if not args:
            msg = unicode(event).encode("unicode-escape")
        elif len(args) > 1:
            msg = args[0] % args[1:]
        elif keys:
            msg = args[0] % keys
        else:
            msg = args[0]

        event = event.union(logmsg=msg, loglevel=logging.getLevelName(lvl))
        return self._logger.log(lvl, msg, **dict(extra=dict(event=event)))
