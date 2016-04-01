from __future__ import absolute_import

import time
import hashlib
import logging

from idiokit.xmlcore import Element
from . import events


class RoomHandler(logging.Handler):
    def __init__(self, room):
        logging.Handler.__init__(self)

        self.room = room

        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s",
            "%Y-%m-%d %H:%M:%SZ")
        formatter.converter = time.gmtime

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
        self._logger._log(logging.INFO, msg, event=event)

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

    def log(self, level, msg, *args, **keys):
        if args:
            msg = msg % args
        return self._log(level, msg, **keys)

    def _log(self, level, msg, event=()):
        event = events.Event(event).union({
            "logtime": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
            "logmsg": msg,
            "loglevel": logging.getLevelName(level)
        })
        return self._logger.log(level, msg, **{"extra": {"event": event}})

    def stateful(self, *ids):
        hashed = hashlib.sha1()
        for piece in ids:
            hashed.update(hashlib.sha1(piece).digest())
        logger = _StatefulLogger(hashed.hexdigest(), self)
        return logger
