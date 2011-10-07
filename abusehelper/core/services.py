import sys
import uuid
import random
import functools
from idiokit import threado
from idiokit.xmpp.core import XMPPError
from idiokit.xmpp.jid import JID
from idiokit.xmlcore import Element
from abusehelper.core import serialize

SERVICE_NS = "abusehelper#service"

def bind(parent, child):
    def _bind(source, result):
        throw, args = result
        if not throw and source is parent:
            child.throw(threado.Finished())
        elif throw:
            if source is parent:
                child.throw(*args)
            else:
                parent.throw(*args)
    parent.result().listen(functools.partial(_bind, parent))
    child.result().listen(functools.partial(_bind, child))

@threado.stream
def mask_errors(inner):
    try:
        while True:
            yield inner
    except:
        pass

class SessionError(Exception):
    pass

class Stop(Exception):
    pass

class Unavailable(Stop):
    pass

class Lobby(threado.GeneratorStream):
    def __init__(self, xmpp, room):
        threado.GeneratorStream.__init__(self)

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
        self.start()

    @threado.stream
    def session(inner, self, service_id, *path, **conf):
        while True:
            matches = list()
            for jid, service_ids in self.catalogue.items():
                if service_id in service_ids:
                    matches.append(jid)

            if not matches:
                if service_id not in self.waiters:
                    channel = threado.Channel()
                    self.waiters[service_id] = channel
                channel = self.waiters[service_id]

                while not channel.has_result():
                    yield inner, channel
                continue

            jid = random.choice(matches)
            task = self._establish_session(jid, service_id, path, conf)
            self.guarded.setdefault((jid, service_id), set()).add(task)
            try:
                session = yield inner.sub(task)
            finally:
                self.guarded.get((jid, service_id), set()).discard(task)

            if session is not None:
                inner.finish(session)

    @threado.stream
    def _establish_session(inner, self, jid, service_id, path, conf):
        start = Element("start", xmlns=SERVICE_NS, id=service_id)
        if path:
            path_element = Element("path")
            path_element.add(serialize.dump(path))
            start.add(path_element)
        conf_element = Element("config")
        conf_element.add(serialize.dump(conf))
        start.add(conf_element)

        try:
            # Check that the service has not become unavailable.
            yield inner.flush()

            result = yield inner.sub(self.xmpp.core.iq_set(start, to=jid))

            # Check again that the service has not become unavailable.
            yield inner.flush()
        except XMPPError, error:
            if error.type != "cancel":
                raise
            if error.condition == "session-failure":
                raise SessionError(error.text)
            inner.finish()
        except Unavailable:
            inner.finish()

        for start in result.children("start", SERVICE_NS).with_attrs("id"):
            session_id = start.get_attr("id")
            session = self._catch(jid, session_id)
            bind(self, session | mask_errors())

            sessions = self.jids.setdefault(jid, dict())
            sessions[session_id] = session
            inner.finish(session)
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

                    if service_id in self.waiters:
                        self.waiters.pop(service_id).finish()

        for service_id in previous - self.catalogue.get(jid, set()):
            for task in self.guarded.pop((jid, service_id), ()):
                task.throw(Unavailable())

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

    @threado.stream
    def _start(inner, self, iq, jid, service_id, element):
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

            session = yield inner.sub(service.open_session(path, conf))
            session_id = uuid.uuid4().hex

            sessions = self.jids.setdefault(jid, dict())
            sessions[session_id] = session
            session | self._catch(jid, session_id)
        except SessionError, se:
            msg = se.args[0]
            error = self.xmpp.core.build_error("cancel", "session-failure", msg)
            self.xmpp.core.iq_error(iq, error)
        except:
            _, exc, _ = sys.exc_info()
            msg = "Session handling failed: %r" % exc
            error = self.xmpp.core.build_error("cancel", "session-failure", msg)
            self.xmpp.core.iq_error(iq, error)
        else:
            result = Element("start", xmlns=SERVICE_NS, id=session_id)
            self.xmpp.core.iq_result(iq, result)

    def run(self):
        yield self.inner.sub(self.room | self._run())

    @threado.stream
    def _run(inner, self):
        while True:
            elements = yield inner

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
                session.throw(reason)
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

    @threado.stream
    def offer(inner, self, service_id, service):
        service.start()
        self.services[service_id] = service
        bind(self, service)

        self._update_presence()
        try:
            yield inner.sub(service)
        finally:
            if self.services.get(service_id, None) is service:
                self.services.pop(service_id, None)
            self._update_presence()

    @threado.stream
    def _catch(inner, self, jid, session_id):
        try:
            while True:
                yield inner
        finally:
            end = Element("end", xmlns=SERVICE_NS, id=session_id)
            self.xmpp.core.message(jid, end)
            self._discard_session(jid, session_id)

import sqlite3
from cPickle import loads, dumps, HIGHEST_PROTOCOL
from idiokit import timer

class Service(threado.GeneratorStream):
    def __init__(self, state_file=None):
        threado.GeneratorStream.__init__(self)

        self.sessions = dict()
        self.shutting_down = False

        if state_file is None:
            self.db = sqlite3.connect(":memory:")
        else:
            self.db = sqlite3.connect(state_file)
        self.db.execute("CREATE TABLE IF NOT EXISTS states "+
                        "(key UNIQUE, state)")
        self.db.commit()

        self.root_key = ""

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

    @threado.stream
    def _wrapped_main(inner, self):
        state = self._get(self.root_key)
        self._put(self.root_key, None)

        state = yield inner.sub(self.main(state))

        self._put(self.root_key, state)

    def run(self):
        try:
            yield self.inner.sub(self.kill_sessions() | self._wrapped_main())
        finally:
            self.db.commit()
            self.db.close()

    @threado.stream
    def kill_sessions(inner, self):
        try:
            try:
                while True:
                    item = yield inner
                    inner.send(item)
            except threado.Finished:
                raise Stop()
        finally:
            self.shutting_down = True

            for session in self.sessions.itervalues():
                session.throw(Stop())

            while self.sessions:
                session = tuple(self.sessions.itervalues())[0]
                while not session.has_result():
                    yield inner, session

    @threado.stream
    def open_session(inner, self, path, conf):
        assert not self.shutting_down

        @threado.stream
        def _guarded(inner, path, key, session):
            try:
                state = yield inner.sub(session)
                if path is not None:
                    self._put(key, state)
            finally:
                del self.sessions[path]

        if path is None:
            path = object()
            session = _guarded(path, None, self.session(None, **conf))
        else:
            while path in self.sessions:
                old_session = self.sessions[path]
                old_session.throw(Stop())
                while not old_session.has_result():
                    yield inner, old_session

            key = self.path_key(path)
            state = self._get(key)
            session = _guarded(path, key, self.session(state, **conf))
            self._put(key, None)

        self.sessions[path] = session
        bind(self, session)
        inner.finish(session)

    @threado.stream
    def main(inner, self, state):
        try:
            while True:
                yield inner
        except Stop:
            inner.finish()

    @threado.stream
    def session(inner, self, state, **keys):
        try:
            while True:
                yield inner
        except Stop:
            inner.finish()

@threado.stream
def join_lobby(inner, xmpp, name, nick=None):
    room = yield inner.sub(xmpp.muc.join(name, nick))
    lobby = Lobby(xmpp, room)
    inner.finish(lobby)
