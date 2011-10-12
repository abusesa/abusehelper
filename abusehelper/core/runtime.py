import os
import idiokit
from idiokit import timer
from idiokit.xmpp import jid
from abusehelper.core import serialize, config

def iter_runtimes(obj):
    for obj in config.flatten(obj):
        runtime = getattr(obj, "__runtime__", None)
        if callable(runtime):
            yield runtime()
            continue

        # Backwards compatibility
        runtime_method = getattr(obj, "runtime", None)
        if callable(runtime_method):
            for obj in config.flatten(runtime_method()):
                yield obj
            continue

class Pipeable(object):
    def _collect(self):
        return self

    def __or__(self, other):
        if not isinstance(other, Pipeable):
            raise TypeError("%r is not pipeable" % other)
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
                    raise PipeError("a Session instance has to be piped "+
                                    "directly after a Room instance")
            prev = piece

        if isinstance(prev, Session):
            yield prev

class SessionError(Exception):
    pass

class Session(Pipeable):
    @property
    def conf(self):
        return dict(self._conf)

    def __init__(self, service, *path, **conf):
        self.__dict__["service"] = service
        self.__dict__["path"] = tuple(path)

        for key, value in conf.items():
            try:
                value  = serialize.load(serialize.dump(value))
            except serialize.UnregisteredType:
                raise SessionError("can not serialize key %r value %r" %
                                   (key, value))
            conf[key] = value
        self.__dict__["_conf"] = frozenset(conf.items())
        self.__dict__["_hash"] = None

    def updated(self, **conf):
        new_conf = dict(self._conf)
        new_conf.update(conf)
        return Session(self.service, *self.path, **new_conf)

    def __setitem__(self, key, value):
        raise AttributeError("%r instances are immutable" % self.__class__)

    def __delitem__(self, key):
        raise AttributeError("%r instances are immutable" % self.__class__)

    def __hash__(self):
        if self._hash is None:
            self._hash = hash(self.service) ^ hash(self._conf) ^ hash(self.path)
        return self._hash

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
        if result is NotImplemented:
            return result
        return not result

    def __runtime__(self):
        return self

class Room(Pipeable):
    def __init__(self, name):
        name = unicode(name)
        try:
            jid.nodeprep(name)
        except jid.JIDError:
            jid.JID(name)
        self.name = name

import idiokit
from idiokit import timer
from abusehelper.core import bot, services, log

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
        sessions = dict()

        try:
            while True:
                configs = yield idiokit.next()

                added = set(iter_runtimes(config.flatten(configs)))

                for key in set(sessions) - added:
                    stream = sessions.pop(key)
                    stream.throw(Cancel())

                for session in added - set(sessions):
                    sessions[session] = self.session(lobby, session) | self._catch(errors)
        finally:
            for stream in sessions.values():
                stream.throw(Cancel())

    @idiokit.stream
    def main(self):
        xmpp = yield self.xmpp_connect()

        self.log.info("Joining lobby %r", self.service_room)
        lobby = yield services.join_lobby(xmpp, self.service_room, self.bot_name)

        self.log.addHandler(log.RoomHandler(lobby.room))

        errors = idiokit.consume()
        yield errors | self.configs() | self._handle_updates(lobby, errors) | lobby

    @idiokit.stream
    def session(self, lobby, session):
        name = session.service
        if session.path:
            name += "(" + ".".join(session.path) + ")"

        while True:
            self.log.info("Waiting for %r", name)
            try:
                stream = yield lobby.session(session.service,
                                             *session.path,
                                             **session.conf)
            except Cancel:
                self.log.info("Stopped waiting for %r", name)
                break

            conf_str = "\n".join(" %r=%r" % item for item
                                 in session.conf.items())
            self.log.info("Sent %r conf:\n%s", name, conf_str)

            try:
                yield stream
            except services.Stop:
                self.log.info("Lost connection to %r", name)
            except Cancel:
                self.log.info("Ended connection to %r", name)
                break

class DefaultRuntimeBot(RuntimeBot):
    config = bot.Param("configuration module")
    poll_interval = bot.IntParam("how often (in seconds) the "+
                                 "configuration module is checked "+
                                 "for updates (default: %default)",
                                 default=1)

    @idiokit.stream
    def configs(self):
        conf_path = os.path.abspath(self.config)
        last_mtime = None
        error_msg = None

        while True:
            try:
                mtime = os.path.getmtime(conf_path)
                if last_mtime != mtime:
                    last_mtime = mtime

                    yield idiokit.send(config.load_configs(conf_path))

                    error_msg = None
            except BaseException, exception:
                if error_msg != str(exception):
                    error_msg = str(exception)
                    self.log.error("Couldn't load module %r: %s",
                                   self.config, error_msg)

            yield timer.sleep(self.poll_interval)

if __name__ == "__main__":
    DefaultRuntimeBot.from_command_line().execute()
