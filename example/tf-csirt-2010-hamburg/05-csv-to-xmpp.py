from idiokit import threado
from idiokit import jid
from abusehelper.core import bot
from abusehelper.core import utils
from abusehelper.core import events

class CSVBot(bot.XMPPBot):
    xmpp_room = bot.Param("the destination room")
    csv_url = bot.Param("the URL for the CSV data")

    # These are not a mandatory options, as they have defaults.
    csv_delimiter = bot.Param("delimiter used in the CSV data",
                              default=",")
    csv_columns = bot.ListParam("comma separated list of column names for the CSV data "+
                                "(default: use the first row as column names)",
                                default=None)

    @threado.stream
    def main(inner, self):
        # Join the XMPP network using credentials given from the command line
        conn = yield self.xmpp_connect()

        # Join the XMPP room
        room = yield conn.muc.join(self.xmpp_room, self.bot_name)
        self.log.info("Joined room %r", self.xmpp_room)

        # Fetch the URL info and data as an file-like object.
        # Info contains e.g. the HTTP(S) headers, ignored for now.
        info, fileobj = yield utils.fetch_url(self.csv_url)
        self.log.info("Opened URL %r", self.csv_url)

        # csv_to_events feeds out abusehelper.core.events.Event
        # objects, so convert them to XML elements before sending them
        # to the room.
        csv_feed = utils.csv_to_events(fileobj,
                                       delimiter=self.csv_delimiter,
                                       columns=self.csv_columns)
        yield csv_feed | events.events_to_elements() | room | threado.dev_null()

if __name__ == "__main__":        
    CSVBot.from_command_line().run()
