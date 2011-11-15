import uuid
import random
import functools

import idiokit
from idiokit.xmpp.core import XMPPError
from idiokit.xmpp.jid import JID
from idiokit.xmlcore import Element
from abusehelper.core import serialize

SERVICE_NS = "abusehelper#service"

class SessionError(Exception):
    pass

class Stop(Exception):
    pass

class Unavailable(Stop):
    pass

class Lobby(idiokit.Proxy):
    def __init__(self, xmpp, room):
        self.xmpp = xmpp
        self.room = room

        self.jids = dict()
        self.services = dict()
        self.catalogue = dict()
        self.waiters = dict()
        self.guarded = dict()

        for participant in self.room.participants:
            self._update_catalogue(participant.name, participant.payload)

        self.xmpp.core.add_iq_handler(self.handle_iq, "start", SERVICE_NS)

        idiokit.Proxy.__init__(self, self.room | self._run())

    @idiokit.stream
    def session(self, service_id, *path, **conf):
        while True:
            matches = list()
            for jid, service_ids in self.catalogue.items():
                if service_id in service_ids:
                    matches.append(jid)

            if not matches:
                event = idiokit.Event()
                self.waiters.setdefault(service_id, set()).add(event)
                try:
                    yield event
                finally:
                    self.waiters.get(service_id, set()).discard(event)
                    if not self.waiters.get(service_id, None):
                        self.waiters.pop(service_id, None)
                continue

            jid = random.choice(matches)
            task = self._establish_session(jid, service_id, path, conf)
            self.guarded.setdefault((jid, service_id), set()).add(task)
            try:
                session = yield task
            finally:
                self.guarded.get((jid, service_id), set()).discard(task)

            if session is not None:
                idiokit.stop(session)

    @idiokit.stream
    def _establish_session(self, jid, service_id, path, conf):
        start = Element("start", xmlns=SERVICE_NS, id=service_id)
        if path:
            path_element = Element("path")
            path_element.add(serialize.dump(path))
            start.add(path_element)
        conf_element = Element("config")
        conf_element.add(serialize.dump(conf))
        start.add(conf_element)

        try:
            result = yield self.xmpp.core.iq_set(start, to=jid)
        except XMPPError, error:
            if error.type != "cancel":
                raise
            if error.condition == "session-failure":
                raise SessionError(error.text)
            idiokit.stop()
        except Unavailable:
            idiokit.stop()

        for start in result.children("start", SERVICE_NS).with_attrs("id"):
            session_id = start.get_attr("id")
            session = self._catch(jid, session_id)
            idiokit.pipe(self.fork(), session)

            sessions = self.jids.setdefault(jid, dict())
            sessions[session_id] = session
            idiokit.stop(session)
        else:
            raise SessionError("No session ID received")

    def _update_catalogue(self, jid, payload=None):
        previous = self.catalogue.pop(jid, set())

        if payload:
            self.catalogue[jid] = set()
            for services in payload.named("services", SERVICE_NS):
                for service in services.children("service").with_attrs("id"):
                    service_id = service.get_attr("id")
                    self.catalogue[jid].add(service_id)

                    for event in self.waiters.pop(service_id, ()):
                        event.succeed()

        for service_id in previous - self.catalogue.get(jid, set()):
            for task in self.guarded.pop((jid, service_id), ()):
                task.signal(Unavailable())

    def handle_iq(self, iq, payload):
        if not iq.with_attrs("from", type="set"):
            return False
        jid = JID(iq.get_attr("from"))
        if jid.bare() != self.room.jid.bare():
            return False
        if not payload.named("start").with_attrs("id"):
            return False

        service_id = payload.get_attr("id")
        self._start(iq, jid, service_id, payload)
        return True

    @idiokit.stream
    def _start(self, iq, jid, service_id, element):
        try:
            service = self.services.get(service_id, None)
            if service is None:
                raise SessionError("Service '%s' not available" % service_id)

            path = None
            for child in element.children("path").children():
                path = serialize.load(child)
                break

            for child in element.children("config").children():
                conf = serialize.load(child)
                break
            else:
                raise SessionError("Did not get session configuration")

            session = yield service.open_session(path, conf)
            session_id = uuid.uuid4().hex

            sessions = self.jids.setdefault(jid, dict())
            sessions[session_id] = session
            session | self._catch(jid, session_id)
        except SessionError, se:
            msg = se.args[0]
            error = self.xmpp.core.build_error("cancel", "session-failure", msg)
            self.xmpp.core.iq_error(iq, error)
        except BaseException, exc:
            msg = "Session handling failed: %r" % exc
            error = self.xmpp.core.build_error("cancel", "session-failure", msg)
            self.xmpp.core.iq_error(iq, error)
        else:
            result = Element("start", xmlns=SERVICE_NS, id=session_id)
            self.xmpp.core.iq_result(iq, result)

    @idiokit.stream
    def _run(self):
        while True:
            elements = yield idiokit.next()

            for message in elements.named("message").with_attrs("from"):
                for end in message.children("end", SERVICE_NS).with_attrs("id"):
                    jid = JID(message.get_attr("from"))
                    session_id = end.get_attr("id")
                    self._discard_session(jid, session_id)

            presences = elements.named("presence").with_attrs("from")
            for presence in presences:
                jid = JID(presence.get_attr("from"))
                if presence.with_attrs(type="unavailable"):
                    self._discard_jid(jid, Unavailable())
                else:
                    self._update_catalogue(jid, presence.children())

    def _discard_session(self, jid, session_id, reason=Stop()):
        if jid in self.jids:
            sessions = self.jids[jid]
            if session_id in sessions:
                session = sessions.pop(session_id)
                session.signal(reason)
            if not sessions:
                del self.jids[jid]

    def _discard_jid(self, jid, reason=Stop()):
        if jid in self.jids:
            sessions = self.jids[jid]
            for session_id in list(sessions):
                self._discard_session(jid, session_id, reason)
        self._update_catalogue(jid, None)

    def _update_presence(self):
        services = Element("services", xmlns=SERVICE_NS)
        for service_id, service in self.services.items():
            element = Element("service", id=service_id)
            services.add(element)
        self.xmpp.core.presence(services, to=self.room.jid)

    @idiokit.stream
    def offer(self, service_id, service):
        self.services[service_id] = service

        self._update_presence()
        try:
            yield self.fork() | service.run()
        finally:
            if self.services.get(service_id, None) is service:
                self.services.pop(service_id, None)
            self._update_presence()

    @idiokit.stream
    def _catch(self, jid, session_id):
        try:
            yield idiokit.consume()
        finally:
            end = Element("end", xmlns=SERVICE_NS, id=session_id)
            self.xmpp.core.message(jid, end)
            self._discard_session(jid, session_id)

import sqlite3
from cPickle import loads, dumps, HIGHEST_PROTOCOL
from idiokit import timer

class Service(object):
    def __init__(self, state_file=None):
        self.sessions = dict()

        if state_file is None:
            self.db = sqlite3.connect(":memory:")
        else:
            self.db = sqlite3.connect(state_file)
        self.db.execute("CREATE TABLE IF NOT EXISTS states "+
                        "(key UNIQUE, state)")
        self.db.commit()

        self.root_key = ""
        self.errors = idiokit.consume()

    def _get(self, key):
        for state, in self.db.execute("SELECT state FROM states "+
                                      "WHERE key = ?", (key,)):
            return loads(str(state))
        return None

    def _put(self, key, state):
        self.db.execute("DELETE FROM states WHERE key = ?", (key,))
        if state is not None:
            state = sqlite3.Binary(dumps(state, HIGHEST_PROTOCOL))
            self.db.execute("INSERT INTO states(key, state) VALUES(?, ?)",
                            (key, state))

    def path_key(self, path):
        bites = list()
        for bite in path:
            bite = bite.encode("unicode-escape")
            bites.append(bite.replace("/", r"\/"))
        return "/" + "/".join(bites)

    @idiokit.stream
    def run(self):
        state = self._get(self.root_key)
        self._put(self.root_key, None)

        try:
            state = yield self.errors | self.kill_sessions() | self.main(state)
        finally:
            self._put(self.root_key, state)

            self.db.commit()
            self.db.close()

    @idiokit.stream
    def kill_sessions(self):
        try:
            yield idiokit.consume()
            raise Stop()
        finally:
            for session in self.sessions.itervalues():
                session.signal(Stop())

            while self.sessions:
                session = tuple(self.sessions.itervalues())[0]
                yield session

    @idiokit.stream
    def open_session(self, path, conf):
        @idiokit.stream
        def _guarded(path, key, session):
            try:
                state = yield session
            except:
                self.errors.signal()
                raise
            else:
                if key is not None:
                    self._put(key, state)
            finally:
                del self.sessions[path]

        if path is None:
            path = object()
            session = _guarded(path, None, self.session(None, **conf))
        else:
            while path in self.sessions:
                old_session = self.sessions[path]
                yield old_session.signal(Stop())
                yield old_session

            key = self.path_key(path)
            state = self._get(key)
            session = _guarded(path, key, self.session(state, **conf))
            self._put(key, None)

        self.sessions[path] = session
        idiokit.stop(self.errors.fork() | session)

    @idiokit.stream
    def main(self, state):
        try:
            yield idiokit.consume()
        except Stop:
            idiokit.stop()

    @idiokit.stream
    def session(self, state, **keys):
        try:
            yield idiokit.consume()
        except Stop:
            idiokit.stop()

@idiokit.stream
def join_lobby(xmpp, name, nick=None):
    room = yield xmpp.muc.join(name, nick)
    idiokit.stop(Lobby(xmpp, room))
