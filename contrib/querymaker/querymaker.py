#!/usr/bin/env python
from idiokit import threado, timer, muc
from idiokit.jid import JID
from abusehelper.core import bot, events, services

class Querymaker(bot.XMPPBot):
    xmpp_room = bot.Param("room to write")
    query = bot.ListParam("command in form key=value[,key=value]")
    
    @threado.stream
    def main(inner, self):
        self.xmpp = yield inner.sub(self.xmpp_connect())
        room = yield inner.sub(self.xmpp.muc.join(self.xmpp_room, self.bot_name))
        self.make_request(room)

        yield inner.sub(room
                        | self.xmpp_to_log(room.nick_jid, room)
                        | threado.dev_null()
                        )

    def make_request(self, room):
        event = events.Event()
        for attr in self.query:
            k, v = attr.split("=")
            event.add(k, v)
        room.send(event.to_element())

    @threado.stream
    def xmpp_to_log(inner, self, own_jid, room):
        while True:
            elements = yield inner
            for message in elements.with_attrs("from"):
                print message.serialize()
                sender = JID(elements.get_attr("from"))
                if sender == own_jid:
                    continue
                if sender.resource is None:
                    continue

                resource = sender.resource.encode("unicode-escape")
                bare = unicode(sender.bare()).encode("unicode-escape")

                for event in message.children("event"):
                    event = events.Event.from_element(event)
                    self.log.info("<%s> %s",
                                  unicode(sender).encode("unicode-escape"),
                                  event)

if __name__ == "__main__":
    Querymaker.from_command_line().run()
