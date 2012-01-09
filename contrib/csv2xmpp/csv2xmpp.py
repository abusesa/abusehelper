import urlparse
import idiokit
from abusehelper.core import events, bot, utils

class CSV2XMPP(bot.XMPPBot):
    csv = bot.Param()
    csv_delimiter = bot.Param(default=",")
    csv_columns = bot.ListParam(default=None)
    xmpp_room = bot.Param()
    add_values = bot.ListParam("list of key/values to be added to every event" +
                               '(example: "key1=value1,key1=value2,key3=value3")',
                               default=dict())

    def __init__(self, **keys):
        bot.XMPPBot.__init__(self, **keys)

        if self.add_values:
            temp = dict()
            for pair in self.add_values:
                key_value = pair.split("=")
                if len(key_value) < 2:
                    continue
                values = temp.setdefault(key_value[0], set())
                values.add("=".join(key_value[1:]))
            self.add_values = temp

    @idiokit.stream
    def _add_values(self):
        while True:
            event = yield idiokit.next()
            for key, values in self.add_values.iteritems():
                event.update(key, values)
            yield idiokit.send(event)

    @idiokit.stream
    def main(self):
        if not urlparse.urlparse(self.csv)[0]:
            self.log.info("Opening file %r", self.csv)
            fileobj = open(self.csv, "rb")
            self.log.info("Opened file %r", self.csv)
        else:
            self.log.info("Opening URL %r", self.csv)
            _, fileobj = yield utils.fetch_url(self.csv)
            self.log.info("Opened URL %r", self.csv)

        xmpp = yield self.xmpp_connect()

        self.log.info("Joining room %r", self.xmpp_room)
        room = yield xmpp.muc.join(self.xmpp_room, self.bot_name)

        yield (utils.csv_to_events(fileobj, self.csv_delimiter, self.csv_columns)
               | self._add_values()
               | events.events_to_elements()
               | room)

if __name__ == "__main__":
    CSV2XMPP.from_command_line().execute()
