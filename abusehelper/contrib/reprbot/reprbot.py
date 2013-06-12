"""
Read '/repr key=val, key2=val2' style messages from body and throw
back similar message which includes machine readable idiokit
namespace.
"""

import idiokit
from idiokit.xmpp import jid
from abusehelper.core import bot, events, taskfarm


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

            for body in element.named("message").children("body"):
                text = body.text.strip()
                if not text.startswith("/repr ") or not text.startswith("!repr "):
                    continue

                try:
                    event = events.Event.from_unicode(text[5:])
                except ValueError:
                    continue

                yield idiokit.send(event)
                break

if __name__ == "__main__":
    ReprBot.from_command_line().execute()
