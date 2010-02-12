import re

from idiokit import threado
from abusehelper.core import bot
from abusehelper.core import utils
from abusehelper.core import events

class ProjectHoneypotBot(bot.XMPPBot):
    xmpp_room = bot.Param("the destination room")
    url = bot.Param("the URL for the data")

    @threado.stream
    def main(inner, self):
        # Join the XMPP network using credentials given from the command line
        conn = yield self.xmpp_connect()

        # Join the XMPP room
        room = yield conn.muc.join(self.xmpp_room, self.bot_name)
        self.log.info("Joined room %r", self.xmpp_room)

        # Fetch the URL info and data as an file-like object.
        # Info contains e.g. the HTTP(S) headers, ignored for now.
        info, fileobj = yield utils.fetch_url(self.url)
        self.log.info("Opened URL %r", self.url)
        
        yield self.parse(fileobj) | events.events_to_elements() | room | threado.dev_null()

    @threado.stream
    def parse(inner, self, fileobj):
        data = yield inner.thread(fileobj.read)

        # Read all the data
        rex = re.compile(r"<title>(.*?)</title>\s*"+
                         "<link>(.*?)</link>\s*"+
                         "<description>(.*?)</description>\s*"+
                         "<pubDate>(.*?)</pubDate>")
        for match in rex.findall(data):
            title, link, desc, date = match

            event = events.Event()
            event.add("title", title)
            event.add("link", link)
            event.add("description", desc)
            event.add("date", date)
            inner.send(event)

            yield
            list(inner)

if __name__ == "__main__":        
    ProjectHoneypotBot.from_command_line().run()
