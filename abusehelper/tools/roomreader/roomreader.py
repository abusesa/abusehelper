"""
Roomreader is a simple client for reading messages in multiple rooms.
Roomreader can print messages to stdout (default) or to a log file.
"""

import idiokit
from idiokit.xmpp.jid import JID
from abusehelper.core import bot, events


class Roomreader(bot.XMPPBot):
    bot_name = "roomreader"
    xmpp_rooms = bot.ListParam("""
        comma separated list of XMPP rooms roomreader should watch.
        (e.g. room@conference.example.com, room2@conference.example.com)
        """)
    show_events = bot.BoolParam("print out events from channels")

    @idiokit.stream
    def main(self):
        try:
            xmpp = yield self.xmpp_connect()

            rooms = list()
            for name in self.xmpp_rooms:
                room = yield xmpp.muc.join(name, self.bot_name)
                rooms.append(
                    room | self.xmpp_to_log(room.jid, room.participants))
            yield idiokit.pipe(*rooms)
        except idiokit.Signal:
            pass

    @idiokit.stream
    def xmpp_to_log(self, own_jid, participants):
        in_room = set()
        for participant in participants:
            in_room.add(participant.name.resource)

        while True:
            elements = yield idiokit.next()

            for message in elements.with_attrs("from"):
                sender = JID(elements.get_attr("from"))
                if sender == own_jid or sender.resource is None:
                    continue

                resource = sender.resource.encode("unicode-escape")
                bare = unicode(sender.bare()).encode("unicode-escape")

                type_ = message.get_attr("type", None)
                if type_ == "unavailable":
                    if sender.resource in in_room:
                        in_room.discard(sender.resource)
                        self.log.info("* {0} left the room {1}.".format(
                            resource, bare))
                else:
                    if sender.resource not in in_room:
                        in_room.add(sender.resource)
                        self.log.info("* {0} entered the room {1}.".format(
                            resource, bare))

                for body in message.children("body"):
                    self.log.info("<{0}> {1}".format(
                        unicode(sender).encode("unicode-escape"),
                        body.text.encode("unicode-escape")))

                if self.show_events:
                    for event in events.Event.from_elements(message):
                        self.log.info("<{0}> {1}".format(
                            unicode(sender).encode("unicode-escape"),
                            event))
