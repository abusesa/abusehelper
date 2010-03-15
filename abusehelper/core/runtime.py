import os
import uuid
from idiokit import jid
from abusehelper.core import serialize, config

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
                                            src_room=prev.name,
                                            dst_room=piece.name))
                elif isinstance(prev, Room):
                    sessions.append(piece.updated(src_room=prev.name))
                elif isinstance(piece, Room):
                    if sessions:
                        sessions[-1] = sessions[-1].updated(dst_room=piece.name)
                else:
                    room = Room()
                    sessions[-1] = sessions[-1].updated(dst_room=room.name)
                    sessions.append(piece.updated(src_room=room.name))

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
                raise SessionError("can not serialize key %r value %r" % 
                                   (key, value))
            conf[key] = value
        self.__dict__["_conf"] = frozenset(conf.items())

    def updated(self, **conf):
        new_conf = dict(self._conf)
        new_conf.update(conf)
        return Session(self.service, *self.path, **new_conf)

    def __setitem__(self, key, value):
        raise AttributeError("%r instances are immutable" % self.__class__)

    def __delitem__(self, key):
        raise AttributeError("%r instances are immutable" % self.__class__)

    def __hash__(self):
        return hash(self.service) ^ hash(self._conf) ^ hash(self.path)

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
    def __init__(self, name=None):
        if name is None:
            name = uuid.uuid4().hex
        if not isinstance(name, unicode):
            name = unicode(name)

        try:
            jid.nodeprep(name)
        except jid.JIDError:
            jid.JID(name)

        self.name = name

    def sessions(self, runtime):
        return []

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
                                added.add(session)
                                current[config].add(session)

                removed.difference_update(added)
                for key in removed:
                    stream = sessions.pop(key)
                    stream.throw(Cancel())

                added.difference_update(sessions)
                for session in added:
                    sessions[session] = self.session(lobby, session)
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
    def session(inner, self, lobby, session):
        name = session.service
        if session.path:
            name += "(" + ".".join(session.path) + ")"
        
        while True:
            self.log.info("Waiting for %r", name)
            try:
                stream = yield inner.sub(lobby.session(session.service, 
                                                       *session.path, 
                                                       **session.conf))
            except Cancel:
                self.log.info("Stopped waiting for %r", name)
                break

            conf_str = "\n".join(" %r=%r" % item for item 
                                 in session.conf.items())
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
        conf_path = os.path.abspath(self.config)
        last_mtime = None
        error_msg = None

        while True:
            try:
                mtime = os.path.getmtime(conf_path)
                if last_mtime != mtime:
                    last_mtime = mtime
                    inner.send(self.SET, config.load_configs(conf_path))
                    error_msg = None
            except BaseException, exception:
                if error_msg != str(exception):
                    error_msg = str(exception)
                    self.log.error("Couldn't load module %r: %s", 
                                   self.config, error_msg)

            yield inner, timer.sleep(self.poll_interval)

if __name__ == "__main__":
    DefaultRuntimeBot.from_command_line().execute()
