#!/usr/bin/env python

"""
Receive alerts via prowl to your iPhone when some of your bots leave
certain XMPP rooms.  This bot watches room presence instead of user's
presence, as AbuseHelper is build on assumption that user presence is
sometimes unavailable. (E.g, you would need to be buddy, or the bots would
need to be on a globally shared roster.)

Example ini:
------
[ahalert]
rooms=blah@conference.ah.cert.ee,cert-ee@conference.ah.cert.ee
xmpp_jid=<user@ah.example.com>
xmpp_password=<yourpass>
watch_room_jids=<lobby>@conference.ah.example.com/config
apikeys = <your api key from http://prowl.weks.net>
message=Bot in your watchlist AbuseHelper left the room
------
See also: http://prowl.weks.net/
"""

from idiokit import threado, jid
from abusehelper.core import bot
from abusehelper.year3000.prowl import ProwlConnection

class AHAlert(bot.XMPPBot):
    rooms = bot.ListParam("comma separated list of XMPP rooms "+
                          "roomreader should watch "+
                          "(e.g. room@conference.example.com, "+ 
                          "room2@conference.example.com)")
    watch_room_jids = bot.ListParam("comma separated watchlist in a "+
                                    "format of <room>/<resource> (e.g. "+
                                    "room@conference.example.com/mybot)")
    message = bot.Param("message to be send as alert")
    apikeys = bot.ListParam("Prowl apikey, which you need to aquire "+
                            "from https://prowl.weks.net/")

    @threado.stream
    def watch(inner, self, alerter):
        watched = set(map(jid.JID, self.watch_room_jids))

        while True:
            elements = yield inner

            for presence in elements.named("presence").with_attrs("from"):
                sender = jid.JID(presence.get_attr("from"))
                type = presence.get_attr("type", None)

                if type != "unavailable":
                    continue

                if sender in watched:
                    application = 'prowlbot'
                    event = 'event'
                    message = self.message.encode('utf-8')
                    result = alerter.add(application, event, message, 0)
                    self.log.info(result)

            for element in elements:
                self.log.debug(repr(elements.serialize()))

    @threado.stream
    def handle_room(inner, self, xmpp, name, alerter):
        self.log.info("Joining room %r", name)
        room = yield inner.sub(xmpp.muc.join(name, self.bot_name))
        self.log.info("Joined room %r", name)

        try:
            yield inner.sub(room 
                            | self.watch(alerter) 
                            | threado.dev_null())
        finally:
            self.log.info("Left room %r", name)

    @threado.stream
    def main(inner, self):
        xmpp = yield inner.sub(self.xmpp_connect())
        alerter = ProwlConnection(",".join(self.apikeys))

        rooms = [self.handle_room(xmpp, name, alerter) for name in self.rooms]
        yield inner.sub(threado.pipe(*rooms))

if __name__ == "__main__":
    AHAlert.from_command_line().run()
