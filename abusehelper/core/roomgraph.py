import uuid

import idiokit
from idiokit import timer
from abusehelper.core import events, rules, taskfarm, bot


class SessionLogger(object):
    def __init__(self, id, logger, *args, **keys):
        self._defaults = events.Event(*args, **keys)
        self._logger = logger

        self._id = id
        self._latest = None

    def open(self, msg, *args, **keys):
        event = self._defaults.union({"id:open": self._id}, *args, **keys)
        self._log(msg, event)
        self._latest = msg, event

    def close(self, msg, *args, **keys):
        event = self._defaults.union({"id:close": self._id}, *args, **keys)
        self._log(msg, event)
        self._latest = None

    def _log(self, msg, event):
        event_dict = dict((x, event.values(x)) for x in event.keys())
        self._logger.info(msg, **event_dict)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        if self._latest is not None:
            msg, event = self._latest
            self._log(msg, event)
            self._latest = None
        return False


class RoomGraphBot(bot.ServiceBot):
    def __init__(self, *args, **keys):
        bot.ServiceBot.__init__(self, *args, **keys)
        self.rooms = taskfarm.TaskFarm(self.handle_room)
        self.srcs = dict()

    def session_logger(self, _id=None, *args, **keys):
        if _id is None:
            _id = uuid.uuid4().hex
        logger = SessionLogger(_id, self.log, {"service": self.bot_name}, *args, **keys)
        return logger

    @idiokit.stream
    def _alert(self, interval=15.0):
        while True:
            yield timer.sleep(interval)
            yield idiokit.send(None)

    @idiokit.stream
    def distribute(self, name):
        count = 0
        waiters = dict()

        while True:
            elements = yield idiokit.next()

            if elements is None:
                for waiter in waiters.values():
                    yield waiter
                waiters.clear()

                if count > 0:
                    self.log.info("Seen {0} events in room {1!r}".format(count, name))
                    count = 0
                continue

            classifier = self.srcs.get(name, None)
            if classifier is None:
                continue

            for event in events.Event.from_elements(elements):
                count += 1

                for dst_room in classifier.classify(event):
                    dst = self.rooms.get(dst_room)

                    if dst_room in waiters:
                        yield waiters.pop(dst_room)

                    if dst is not None:
                        waiters[dst_room] = dst.send(event.to_elements())

    @idiokit.stream
    def handle_room(self, name):
        msg = "room {0!r}".format(name)

        with self.session_logger(_id="room:"+name, type="roominfo", room=name) as logger:
            logger.open("Joining " + msg, status="joining")
            room = yield self.xmpp.muc.join(name, self.bot_name)
            logger.open("Joined " + msg, status="joined")

            try:
                distribute = self.distribute(name)
                idiokit.pipe(self._alert() | distribute)

                def check(elements):
                    if name in self.srcs:
                        yield elements

                yield room | idiokit.map(check) | distribute
            finally:
                logger.close("Left " + msg, status="left")

    @idiokit.stream
    def session(self, _, src_room, dst_room, rule=rules.ANYTHING(), **keys):
        classifier = self.srcs.setdefault(src_room, rules.RuleClassifier())
        classifier.inc(rule, dst_room)

        if rule == rules.ANYTHING():
            msg = "session {0} -> {1}".format(src_room, dst_room)
        else:
            msg = "session {0} -[{1}]-> {2}".format(src_room, rule, dst_room)

        with self.session_logger(type="session", src_room=src_room, dst_room=dst_room, rule=repr(rule)) as logger:
            logger.open("Opened " + msg, status="open")
            try:
                yield self.rooms.inc(src_room) | self.rooms.inc(dst_room)
            finally:
                logger.close("Closed " + msg, status="closed")

                classifier.dec(rule, dst_room)
                if classifier.is_empty():
                    self.srcs.pop(src_room, None)

if __name__ == "__main__":
    RoomGraphBot.from_command_line().execute()
