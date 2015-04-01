"""
Read '/repr key=val, key2=val2' style messages from body and throw
back similar message which includes machine readable idiokit
namespace.
"""

import idiokit
from idiokit.xmpp import jid
from abusehelper.core import bot, events, taskfarm


def _collect_text(element):
    yield element.text

    for child in element.children():
        for text in _collect_text(child):
            yield text

    yield element.tail


def get_message_text(message):
    html = message.children(
        "html", ns="http://jabber.org/protocol/xhtml-im"
    ).children(
        "body", ns="http://www.w3.org/1999/xhtml"
    )
    for body in html:
        pieces = list(_collect_text(body))
        return u"".join(pieces)

    for body in message.children("body"):
        return body.text

    return None


class ReprBot(bot.ServiceBot):
    def __init__(self, *args, **keys):
        bot.ServiceBot.__init__(self, *args, **keys)
        self.rooms = taskfarm.TaskFarm(self.handle_room)

    @idiokit.stream
    def session(self, _, src_room, dst_room=None, **keys):
        if not dst_room:
            dst_room = src_room
        yield self.rooms.inc(src_room) | self.rooms.inc(dst_room)

    @idiokit.stream
    def handle_room(self, name):
        self.log.info("Joining room %r", name)
        room = yield self.xmpp.muc.join(name, self.bot_name)
        self.log.info("Joined room %r", name)

        try:
            yield idiokit.pipe(
                room,
                self.reply(room.jid),
                events.events_to_elements())
        finally:
            self.log.info("Left room %r", name)

    @idiokit.stream
    def reply(self, own_jid):
        while True:
            element = yield idiokit.next()

            sender = jid.JID(element.get_attr("from"))
            if sender == own_jid:
                continue

            for message in element.named("message"):
                text = get_message_text(message)
                if text is None:
                    continue

                pieces = text.split(None, 1)
                if len(pieces) < 2 or pieces[0].lower() not in (u"/repr", u"!repr"):
                    continue

                try:
                    event = events.Event.from_unicode(pieces[1].strip())
                except ValueError:
                    continue

                yield idiokit.send(event)


if __name__ == "__main__":
    ReprBot.from_command_line().execute()
