import csv
import urllib2
from idiokit import threado
from abusehelper.core import events, bot, utils

class CSV2XMPP(bot.XMPPBot):
    csv_url = bot.Param()
    csv_delimiter = bot.Param(default=",")
    csv_columns = bot.ListParam(default=None)
    xmpp_room = bot.Param()

    @threado.stream
    def main(inner, self):
        self.log.info("Opening URL %r", self.csv_url)
        _, fileobj = yield inner.sub(utils.fetch_url(self.csv_url))
        self.log.info("Opened URL %r", self.csv_url)

        xmpp = yield inner.sub(self.xmpp_connect())

        self.log.info("Joining room %r", self.xmpp_room)
        room = yield xmpp.muc.join(self.xmpp_room, self.bot_name)

        yield inner.sub(utils.csv_to_events(fileobj, self.csv_delimiter, self.csv_columns)
                        | events.events_to_elements() 
                        | room)

if __name__ == "__main__":
    CSV2XMPP.from_command_line().run()
