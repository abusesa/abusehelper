import idiokit

from .. import handlers
from . import Transformation


class TransformationBot(Transformation):
    handler = handlers.HandlerParam()

    def __init__(self, *args, **keys):
        Transformation.__init__(self, *args, **keys)

        self.handler = handlers.load_handler(self.handler)

    @idiokit.stream
    def transform_keys(self, **keys):
        yield idiokit.send((self.handler(log=self.log),))

    def transform(self, handler):
        return handler.transform()


if __name__ == "__main__":
    TransformationBot.from_command_line().execute()
