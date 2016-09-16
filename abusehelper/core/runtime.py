from __future__ import absolute_import

import uuid
import idiokit
from idiokit import timer
from idiokit.xmpp import jid
from . import serialize, events, config, bot, services, log
from .. import __version__


def iter_runtimes(obj):
    for obj in config.flatten(obj):
        runtime = getattr(obj, "__runtime__", None)
        if callable(runtime):
            yield runtime()
            continue


class Pipeable(object):
    def _collect(self):
        return self

    def __or__(self, other):
        if not isinstance(other, Pipeable):
            raise TypeError(repr(other) + " is not pipeable")
        return Pipe(self, other)


class PipeError(Exception):
    pass


class Pipe(Pipeable):
    def __init__(self, *pieces):
        self.pieces = pieces

    def _collect(self, pieces=None):
        for piece in self.pieces:
            yield piece._collect()

    def __iter__(self):
        prev = None

        for piece in config.flatten(self._collect()):
            if prev is not None:
                if isinstance(prev, Room) and isinstance(piece, Session):
                    piece = piece.updated(src_room=prev.name)
                elif isinstance(prev, Session) and isinstance(piece, Room):
                    yield prev.updated(dst_room=piece.name)
                elif isinstance(prev, Room) and isinstance(piece, Room):
                    yield Session("roomgraph",
                                  src_room=prev.name,
                                  dst_room=piece.name)
                elif isinstance(piece, Session):
                    raise PipeError("a Session instance has to be piped " +
                                    "directly after a Room instance")
            prev = piece

        if isinstance(prev, Session):
            yield prev


class SessionError(Exception):
    pass


class Session(Pipeable):
    __slots__ = "_conf", "_service", "_path"

    @property
    def conf(self):
        return dict(self._conf)

    @property
    def service(self):
        return self._service

    @property
    def path(self):
        return self._path

    def __init__(self, service, *path, **conf):
        self._service = service
        self._path = tuple(path)

        for key, value in conf.items():
            try:
                value = serialize.normalize(value)
            except serialize.UnregisteredType:
                raise SessionError("can not serialize key {0!r} value {1!r}".format(key, value))
            conf[key] = value
        self._conf = config.HashableFrozenDict(conf)

    def updated(self, **conf):
        new_conf = dict(self._conf)
        new_conf.update(conf)
        return Session(self.service, *self.path, **new_conf)

    def __hash__(self):
        return hash(self._service) ^ hash(self._path) ^ hash(self._conf)

    def __eq__(self, other):
        if not isinstance(other, Session):
            return NotImplemented
        if self.service != other.service:
            return False
        if self.path != self.path:
            return False
        return self._conf == other._conf

    def __ne__(self, other):
        result = self.__eq__(other)
        return result if result is NotImplemented else not result

    def __runtime__(self):
        return self

    def __repr__(self):
        args = [repr(self._service)] + map(repr, self._path)
        for key, value in self._conf.iteritems():
            args.append(key + "=" + repr(value))

        prefix = __name__ + "." + self.__class__.__name__
        return prefix + "(" + ", ".join(args) + ")"


class Room(Pipeable):
    def __init__(self, name):
        name = unicode(name)
        try:
            jid.nodeprep(name)
        except jid.JIDError:
            jid.JID(name)
        self.name = name


class Cancel(Exception):
    pass


class RuntimeBot(bot.XMPPBot):
    service_room = bot.Param()

    @idiokit.stream
    def configs(self):
        yield idiokit.consume()

    @idiokit.stream
    def _catch(self, errors):
        try:
            yield idiokit.consume()
        except:
            errors.throw()
            raise

    @idiokit.stream
    def _handle_updates(self, lobby, errors):
        queues = dict()
        sessions = dict()

        try:
            while True:
                configs = yield idiokit.next()

                added = set(iter_runtimes(config.flatten(configs)))

                for key in set(sessions) - added:
                    stream = sessions.pop(key)
                    stream.throw(Cancel())

                for session in added - set(sessions):
                    sessions[session] = self._session(lobby, session, queues) | self._catch(errors)
        finally:
            for stream in sessions.values():
                stream.throw(Cancel())

    @idiokit.stream
    def main(self):
        self.log.info("Starting bot {0!r} version {1}".format(self.bot_name, __version__))
        xmpp = yield self.xmpp_connect()

        self.log.info("Joining lobby {0!r}".format(self.service_room))
        lobby = yield services.join_lobby(xmpp, self.service_room, self.bot_name)

        self.log.addHandler(log.RoomHandler(lobby.room))

        errors = idiokit.consume()
        yield errors | self.configs() | self._handle_updates(lobby, errors) | lobby

    @idiokit.stream
    def _delayed_log(self, log, name, attrs, delay=1.0):
        try:
            result = yield timer.timeout(delay, idiokit.consume())
        except timer.Timeout:
            log.open("Waiting for {0!r}".format(name), attrs, status="waiting")
            try:
                result = yield idiokit.consume()
            except Cancel:
                log.close("Stopped waiting for {0!r}".format(name), attrs, status="removed")
                raise

        idiokit.stop(result)

    @idiokit.stream
    def _session(self, lobby, session, queues):
        name = session.service
        if session.path:
            name += u"(" + ".".join(session.path) + ")"

        conf = []
        for key, value in session.conf.iteritems():
            conf.append(repr(key) + "=" + repr(value))

        attrs = events.Event({
            "type": "session",
            "service": session.service,
            "path": u".".join(session.path) if session.path else [],
            "config": u", ".join(conf)
        })

        session_id = session.path or [uuid.uuid4().hex]
        with self.log.stateful(attrs.value("service").encode("utf-8"), *session_id) as log:
            while True:
                waiter = queues.pop(session.service, None)
                event = idiokit.Event()
                queues[session.service] = event

                try:
                    while waiter is not None:
                        waiter = yield waiter.fork()

                    stream = yield idiokit.pipe(
                        lobby.session(session.service, *session.path, **session.conf),
                        self._delayed_log(log, name, attrs))
                except Cancel:
                    return
                finally:
                    if queues.get(session.service, None) is event:
                        queues.pop(session.service)
                    event.succeed(waiter)

                conf_str = ", ".join(conf)
                log.open("Sent {0!r} conf {1}".format(name, conf_str), attrs, status="running")

                try:
                    yield stream
                except services.Stop:
                    log.close("Lost connection to {0!r}".format(name), attrs, status="lost")
                except Cancel:
                    log.close("Ended connection to {0!r}".format(name), attrs, status="removed")
                    return

    def run(self):
        try:
            return bot.XMPPBot.run(self)
        except idiokit.Signal:
            pass


class DefaultRuntimeBot(RuntimeBot):
    config = bot.Param("configuration module")

    def configs(self):
        return config.follow_config(self.config) | self._follow_config()

    @idiokit.stream
    def _follow_config(self):
        while True:
            ok, obj = yield idiokit.next()
            if not ok:
                self.log.error(obj)
                continue
            yield idiokit.send(set(obj))


if __name__ == "__main__":
    DefaultRuntimeBot.from_command_line().execute()
