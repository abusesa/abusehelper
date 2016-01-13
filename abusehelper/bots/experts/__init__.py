import idiokit
from hashlib import sha1
from ...core import bot, events, taskfarm


__all__ = ["Expert", "AUGMENT_KEY"]


class _RoomBot(bot.ServiceBot):
    def __init__(self, *args, **keys):
        bot.ServiceBot.__init__(self, *args, **keys)
        self.room_handlers = taskfarm.TaskFarm(self._handle_room)

    @idiokit.stream
    def _handle_room(self, name):
        msg = "room {0!r}".format(name)
        attrs = events.Event(type="room", service=self.bot_name, room=name)

        with self.log.stateful(repr(self.xmpp.jid), "room", repr(name)) as log:
            log.open("Joining " + msg, attrs, status="joining")
            room = yield self.xmpp.muc.join(name, self.bot_name)

            log.open("Joined " + msg, attrs, status="joined")
            try:
                yield room
            finally:
                log.close("Left " + msg, attrs, status="left")

    def to_room(self, name):
        return self.room_handlers.inc(name) | idiokit.consume()

    def from_room(self, name):
        return idiokit.consume() | self.room_handlers.inc(name)


AUGMENT_KEY = "augment sha-1"


@idiokit.stream
def _ignore_augmentations(ignore):
    while True:
        event = yield idiokit.next()
        if ignore and event.contains(AUGMENT_KEY):
            continue
        yield idiokit.send(event)


@idiokit.stream
def _create_eids():
    while True:
        event = yield idiokit.next()
        yield idiokit.send(events.hexdigest(event, sha1), event)


@idiokit.stream
def _embed_eids():
    while True:
        eid, event = yield idiokit.next()
        yield idiokit.send(event.union({AUGMENT_KEY: eid}))


class Expert(_RoomBot):
    def __init__(self, *args, **keys):
        _RoomBot.__init__(self, *args, **keys)
        self._augments = taskfarm.TaskFarm(self._handle_augment)

    def _handle_augment(self, src_room, dst_room, args):
        return idiokit.pipe(
            self.from_room(src_room),
            events.stanzas_to_events(),
            _ignore_augmentations(src_room == dst_room),
            _create_eids(),
            self.augment(*args),
            _embed_eids(),
            events.events_to_elements(),
            self.to_room(dst_room)
        )

    @idiokit.stream
    def session(self, state, src_room, dst_room=None, **keys):
        if dst_room is None:
            dst_room = src_room

        augments = list()
        for args in self.augment_keys(src_room=src_room,
                                      dst_room=dst_room,
                                      **keys):
            augments.append(self._augments.inc(src_room, dst_room, args))
        yield idiokit.pipe(*augments)

    def augment_keys(self, *args, **keys):
        yield ()

    @idiokit.stream
    def augment(self):
        while True:
            eid, event = yield idiokit.next()
            # Skip augmenting by default.
            # Implement yield idiokit.send(eid, augmentation).
