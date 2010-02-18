import os
import uuid
from idiokit import jid
from abusehelper.core import serialize, config

class Runtime(config.Config):
    def runtime(self):
        for key, value in self.member_diff(Runtime):
            if not isinstance(value, Pipeable):
                continue
            yield value

class Pipeable(object):
    def sessions(self, runtime):
        return [self]

    def collect(self):
        return [self]

    def __or__(self, other):
        if not isinstance(other, Pipeable):
            raise TypeError("%r is not pipeable" % other)
        return Pipe(self, other)

class Pipe(Pipeable):
    def __init__(self, *pieces):
        self.pieces = pieces

    def collect(self, pieces=None):
        result = list()
        for piece in self.pieces:
            result.extend(piece.collect())
        return result

    def sessions(self, runtime):
        prev = None
        sessions = list()

        for piece in self.collect():
            if prev is None:
                if isinstance(piece, Session):
                    sessions.append(piece)
            else:
                if isinstance(piece, Room) and isinstance(prev, Room):
                    sessions.append(Session("roomgraph",
                                            src_room=prev.format(runtime),
                                            dst_room=piece.format(runtime)))
                elif isinstance(prev, Room):
                    sessions.append(piece.updated(src_room=prev.format(runtime)))
                elif isinstance(piece, Room):
                    if sessions:
                        room = piece.format(runtime)
                        sessions[-1] = sessions[-1].updated(dst_room=room)
                else:
                    room = Room().format(runtime)
                    sessions[-1] = sessions[-1].updated(dst_room=room)
                    sessions.append(piece.updated(src_room=room))

            prev = piece
        return sessions

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
                raise SessionError("can not serialize key %r value %r" % (key, value))
            conf[key] = value
        self.__dict__["_conf"] = frozenset(conf.items())

    def format_path(self, runtime):
        formatter = config.Formatter(runtime)
        return tuple(bite % formatter for bite in self.path)

    def updated(self, **conf):
        new_conf = dict(self._conf)
        new_conf.update(conf)
        return Session(self.service, *self.path, **new_conf)

    def __setitem__(self, key, value):
        raise AttributeError("%r instances are immutable" % self.__class__)

    def __delitem__(self, key):
        raise AttributeError("%r instances are immutable" % self.__class__)

    def __hash__(self):
        return hash(self.service) ^ hash(self._conf)

    def __eq__(self, other):
        if not isinstance(other, Session):
            return NotImplemented
        if self.service != other.service:
            return False
        return self._conf == other._conf

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return result
        return not result

class Room(Pipeable):
    def __init__(self, name=u"%(random)s"):
        if not isinstance(name, unicode):
            name = unicode(name)

        self.name = name
        self.random = uuid.uuid4().hex

    def sessions(self, runtime):
        return []

    def format(self, other):
        formatter = config.Formatter(other)
        formatter["random"] = self.random

        name = self.name % formatter
        try:
            jid.nodeprep(name)
        except jid.JIDError:
            jid.JID(name)

        return name

from idiokit import threado, timer
from abusehelper.core import bot, services, log

class Cancel(Exception):
    pass

class RuntimeBot(bot.XMPPBot):
    DISCARD = 0
    UPDATE = 1
    SET = 2

    service_room = bot.Param()

    @threado.stream
    def configs(inner, self):
        while True:
            yield inner

    @threado.stream
    def _handle_updates(inner, self, lobby):
        sessions = dict()
        current = dict()

        try:
            while True:
                mode, configs = yield inner

                removed = set()
                if mode == self.SET:
                    current = dict()
                    removed.update(sessions)
                elif mode in (self.UPDATE, self.DISCARD):
                    for config, sessions in configs:
                        removed.update(current.pop(config, set()))

                added = set()
                if mode in (self.UPDATE, self.SET):
                    for config in configs:
                        config_runtime = getattr(config, "runtime", None)
                        if config_runtime is None:
                            continue

                        current.setdefault(config, set())
                        for container in config_runtime():
                            for session in container.sessions(config):
                                path = session.format_path(config)
                                added.add((path, session))
                                current[config].add((path, session))

                removed.difference_update(added)
                for key in removed:
                    stream = sessions.pop(key)
                    stream.throw(Cancel())

                added.difference_update(sessions)
                for path, session in added:
                    sessions[(path, session)] = self.session(lobby, path, session)
        finally:
            for stream in sessions.values():
                stream.throw(Cancel())        

    @threado.stream
    def main(inner, self):
        xmpp = yield inner.sub(self.xmpp_connect())

        self.log.info("Joining lobby %r", self.service_room)
        lobby = yield inner.sub(services.join_lobby(xmpp, 
                                                    self.service_room,
                                                    self.bot_name))
        self.log.addHandler(log.RoomHandler(lobby.room))
        yield inner.sub(self.configs() | self._handle_updates(lobby))

    @threado.stream
    def session(inner, self, lobby, path, session):
        name = session.service
        if path:
            name += "(" + ".".join(path) + ")"
        
        while True:
            self.log.info("Waiting for %r", name)
            try:
                stream = yield inner.sub(lobby.session(session.service, *path, 
                                                       **session.conf))
            except Cancel:
                self.log.info("Stopped waiting for %r", name)
                break

            conf_str = "\n".join(" %r=%r" % item for item in session.conf.items())
            self.log.info("Sent %r conf:\n%s", name, conf_str)
                
            try:
                yield inner.sub(stream)
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

    @threado.stream
    def configs(inner, self):
        error_msg = None
        while True:
            try:
                configs = config.load_configs(os.path.abspath(self.config))
            except BaseException, exception:
                if error_msg != str(exception):
                    error_msg = str(exception)
                    self.log.error("Couldn't load module %r: %s", self.config, error_msg)
            else:
                error_msg = None
                inner.send(self.SET, configs)

            yield inner, timer.sleep(self.poll_interval)

if __name__ == "__main__":
    DefaultRuntimeBot.from_command_line().execute()
