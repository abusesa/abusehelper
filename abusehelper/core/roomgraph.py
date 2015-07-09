from __future__ import absolute_import

import idiokit
from . import events, rules, taskfarm, bot


class RoomGraphBot(bot.ServiceBot):
    def __init__(self, *args, **keys):
        bot.ServiceBot.__init__(self, *args, **keys)

        self._rooms = taskfarm.TaskFarm(self._handle_room)
        self._srcs = dict()
        self._stats = dict()

    def _inc_stats(self, room, seen=0, sent=0):
        seen_count, sent_count = self._stats.get(room, (0, 0))
        self._stats[room] = seen_count + seen, sent_count + sent

    @idiokit.stream
    def _log_stats(self, interval=15.0):
        while True:
            yield idiokit.sleep(interval)

            for room, (seen, sent) in self._stats.iteritems():
                self.log.info(
                    "Room {0!r}: seen {1}, sent {2} events".format(room, seen, sent),
                    event=events.Event({
                        "type": "room",
                        "service": self.bot_name,
                        "seen events": unicode(seen),
                        "sent events": unicode(sent),
                        "room": room
                    })
                )
            self._stats.clear()

    def main(self, *args, **keys):
        return self._log_stats() | bot.ServiceBot.main(self, *args, **keys)

    @idiokit.stream
    def _distribute(self, name):
        waiters = dict()

        while True:
            elements = yield idiokit.next()

            classifier = self._srcs.get(name, None)

            for event in events.Event.from_elements(elements):
                self._inc_stats(name, seen=1)
                if classifier is None:
                    continue

                for dst_room in classifier.classify(event):
                    dst = self._rooms.get(dst_room)

                    if dst_room in waiters:
                        yield waiters.pop(dst_room)

                    if dst is not None:
                        waiters[dst_room] = dst.send(event.to_elements())
                        self._inc_stats(dst_room, sent=1)

    @idiokit.stream
    def _handle_room(self, name):
        msg = "room {0!r}".format(name)
        attrs = events.Event({
            "type": "room",
            "service": self.bot_name,
            "seen events": "0",
            "sent events": "0",
            "room": name
        })

        def check(elements):
            if name in self._srcs:
                yield elements

        with self.log.stateful(repr(self.xmpp.jid), "room", repr(name)) as log:
            log.open("Joining " + msg, attrs, status="joining")
            room = yield self.xmpp.muc.join(name, self.bot_name)

            log.open("Joined " + msg, attrs, status="joined")
            try:
                yield room | idiokit.map(check) | self._distribute(name)
            finally:
                log.close("Left " + msg, attrs, status="left")

    @idiokit.stream
    def session(self, _, src_room, dst_room, rule=None, **keys):
        if rule is None:
            rule = rules.Anything()
        rule = rules.rule(rule)

        classifier = self._srcs.setdefault(src_room, rules.Classifier())
        classifier.inc(rule, dst_room)

        try:
            yield self._rooms.inc(src_room) | self._rooms.inc(dst_room)
        finally:
            classifier.dec(rule, dst_room)
            if classifier.is_empty():
                self._srcs.pop(src_room, None)


if __name__ == "__main__":
    RoomGraphBot.from_command_line().execute()
