import logging
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
