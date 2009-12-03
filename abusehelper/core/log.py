import sys
import logging
import contextlib
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
            body = Element("body")
            body.text = self.format(record)
            self.room.send(body)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

class LoggerStream(object):
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level
        self.buffer = ""

    def write(self, data):
        self.buffer += data
        lines = (self.buffer + " ").splitlines()

        self.buffer = lines.pop()[:-1]
        for line in lines:
            self.logger.log(self.level, line)

    def writelines(self, lines):
        self.write(lines.join("\n"))

    def flush(self):
        if self.buffer:
            self.logger.log(self.level, self.buffer)
            self.buffer = ""

def config_logger(name, *args, **keys):
    keys = dict(keys)
    keys.setdefault("format", "%(asctime)s %(name)s %(levelname)s %(message)s")
    keys.setdefault("datefmt", "%Y-%m-%d %H:%M:%S")
    keys.setdefault("level", logging.INFO)

    logging.basicConfig(*args, **keys)

    logger = logging.getLogger(name)
    sys.stdout = LoggerStream(logger, logging.INFO)
    sys.stderr = LoggerStream(logger, logging.ERROR)

    return logger
