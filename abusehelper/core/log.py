import hashlib
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


class _StatefulLogger(object):
    def __init__(self, eid, logger):
        self._logger = logger
        self._id = eid
        self._latest = None

    def open(self, msg, *args, **keys):
        event = events.Event({"id:open": self._id}, *args, **keys)
        self._log(msg, event)
        self._latest = msg, event

    def close(self, msg, *args, **keys):
        event = events.Event({"id:close": self._id}, *args, **keys)
        self._log(msg, event)
        self._latest = None

    def _log(self, msg, event):
        event_dict = dict((x, event.values(x)) for x in event.keys())
        self._logger.info(msg, **event_dict)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        if self._latest is not None:
            msg, event = self._latest
            self._log(msg, event)
            self._latest = None


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
        return self._logger.log(lvl, msg, **{"extra": {"event": event}})

    def stateful(self, *ids):
        hashed = hashlib.sha1()
        for piece in ids:
            hashed.update(hashlib.sha1(piece).digest())
        logger = _StatefulLogger(hashed.hexdigest(), self)
        return logger
