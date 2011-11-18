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
        event = getattr(record, "event", None)

        try:
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

def _format(msg, formats, keys):
    if not formats:
        return msg

    keys = dict(keys)
    keys["_"] = _format(msg, formats[1:], keys)
    return formats[0] % keys

class EventLogger(object):
    def __init__(self, logger, *formats, **keys):
        self._logger = logger
        self._formats = formats
        self._keys = dict(keys)

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

        all_keys = dict(self._keys)
        all_keys.update(keys)

        event = events.Event()
        for key, value in all_keys.iteritems():
            event.add(key, unicode(value))

        if not args:
            msg = unicode(event).encode("unicode-escape")
        elif len(args) > 1:
            msg = args[0] % args[1:]
        elif all_keys:
            msg = args[0] % all_keys
        else:
            msg = args[0]

        msg = _format(msg, self._formats, all_keys)
        event.add("logmsg", msg)
        event.add("loglevel", unicode(logging.getLevelName(lvl)))
        return self._logger.log(lvl, msg, **dict(extra=dict(event=event)))

    def derive(self, *formats, **keys):
        default_keys = dict(self._keys)
        default_keys.update(keys)
        return self.__class__(self._logger, *(self._formats + formats), **default_keys)
