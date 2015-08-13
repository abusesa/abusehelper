from __future__ import absolute_import

import idiokit
from . import events, bot, taskfarm


@idiokit.stream
def _collect_set():
    result_set = set()

    while True:
        try:
            value = yield idiokit.next()
        except StopIteration:
            break
        result_set.add(value)

    idiokit.stop(result_set)


class Transformation(bot.ServiceBot):
    def __init__(self, *args, **keys):
        bot.ServiceBot.__init__(self, *args, **keys)

        self._rooms = taskfarm.TaskFarm(self._room)
        self._srcs = taskfarm.TaskFarm(self._src)
        self._dsts = taskfarm.TaskFarm(self._dst)
        self._pipes = taskfarm.TaskFarm(self._pipe, grace_period=0.0)

    def _pipe(self, src, dst, key):
        return idiokit.pipe(
            self._srcs.inc(src),
            self.transform(*key),
            events.events_to_elements(),
            self._dsts.inc(dst))

    def _src(self, src):
        return idiokit.pipe(
            self._rooms.inc(src),
            events.stanzas_to_events())

    def _dst(self, dst):
        return idiokit.pipe(
            self._rooms.inc(dst),
            idiokit.consume())

    @idiokit.stream
    def _room(self, name):
        room = yield idiokit.pipe(
            self._delayed_log("Joining room " + repr(name)),
            self.xmpp.muc.join(name, self.bot_name))

        self.log.info("Joined room " + repr(name))
        try:
            yield room
        finally:
            self.log.info("Left room " + repr(name))

    @idiokit.stream
    def _delayed_log(self, logline, delay=1.0):
        yield idiokit.sleep(delay)
        self.log.info(logline)
        yield idiokit.Event()

    @idiokit.stream
    def session(self, _, src_room, dst_room, **keys):
        keyset = yield idiokit.pipe(
            self.transform_keys(src_room=src_room, dst_room=dst_room, **keys),
            _collect_set())

        pipes = [self._pipes.inc(src_room, dst_room, key) for key in keyset]
        yield idiokit.pipe(*pipes)

    @idiokit.stream
    def transform_keys(self, **keys):
        yield idiokit.send(())

    @idiokit.stream
    def transform(self):
        while True:
            event = yield idiokit.next()
            yield idiokit.send(event)


if __name__ == "__main__":
    Transformation.from_command_line().execute()
