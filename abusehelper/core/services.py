import sys
import uuid
import random
from idiokit import threado
from idiokit.core import XMPPError
from idiokit.jid import JID
from idiokit.xmlcore import Element
from abusehelper.core import serialize

SERVICE_NS = "abusehelper#service"

def bind(parent, child):
    def _bind(source):
        try:
            result = source.result()
            if source is parent:
                child.throw(threado.Finished())
        except:
            if source is parent:
                child.rethrow()
            else:
                parent.rethrow()
    parent.add_finish_callback(_bind)
    child.add_finish_callback(_bind)

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

        for participant in self.room.participants:
            self._update_catalogue(participant.name, participant.payload)

        self.xmpp.core.add_iq_handler(self.handle_iq, "start", SERVICE_NS)
        self.start()

    @threado.stream
    def _try_session(inner, self, service_id, *path, **conf):
        matches = list()
        for jid, service_ids in self.catalogue.items():
            if service_id in service_ids:
                matches.append(jid)
                
        if matches:
            jid = random.choice(matches)
        else:
            channel = threado.Channel()
            self.waiters.setdefault(service_id, set()).add(channel)

            try:
                while not channel.was_source:
                    jid = yield inner, channel
            finally:
                waiters = self.waiters.get(service_id, set())
                waiters.discard(channel)
                if not waiters:
                    self.waiters.pop(service_id, None)

        start = Element("start", xmlns=SERVICE_NS, id=service_id)
        if path:
            path_element = Element("path")
            path_element.add(serialize.dump(path))
            start.add(path_element)
        conf_element = Element("config")
        conf_element.add(serialize.dump(conf))
        start.add(conf_element)

        try:
            result = yield inner.sub(self.xmpp.core.iq_set(start, to=jid))
        except XMPPError, error:
            if error.type != "cancel":
                raise
            inner.finish()
        inner.finish(jid, result)

    @threado.stream
    def session(inner, self, service_id, *path, **conf):
        jid, result = yield inner.sub(self._try_session(service_id, *path, **conf))

        for start in result.children("start", SERVICE_NS).with_attrs("id"):
            session_id = start.get_attr("id")
            session = self._catch(jid, session_id)
            bind(self, session | mask_errors())

            sessions = self.jids.setdefault(jid, dict())
            sessions[session_id] = session
            inner.finish(session)
        else:
            raise SessionError("No session ID received")

    def _update_catalogue(self, jid, payload):
        self.catalogue.setdefault(jid, set())
        for services in payload.named("services", SERVICE_NS):
            for service in services.children("service").with_attrs("id"):
                service_id = service.get_attr("id")
                self.catalogue[jid].add(service_id)

                waiters = self.waiters.get(service_id, set())
                for channel in waiters:
                    channel.send(jid)

    def handle_iq(self, iq, payload):
        if not iq.with_attrs("from", type="set"):
            return False
        jid = JID(iq.get_attr("from"))
        if jid.bare() != self.room.room_jid:
            return False
        if not payload.named("start").with_attrs("id"):
            return False

        service_id = payload.get_attr("id")
        try:
            try:
                result = self._start(jid, service_id, payload)
            except SessionError:
                raise
            except:
                _, exc, tb = sys.exc_info()
                raise SessionError("Session handling failed: " + repr(exc))
        except SessionError, se:
            msg = se.args[0]
            error = self.xmpp.core.build_error("cancel", "session-failure", msg)
            self.xmpp.core.iq_error(iq, error)
        else:
            self.xmpp.core.iq_result(iq, result)
        return True

    def run(self):
        yield self.inner.sub(self.room | self._run())

    @threado.stream_fast
    def _run(inner, self):
        while True:
            yield inner

            for elements in inner:
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
        self.catalogue.pop(jid, None)
        if jid in self.jids:
            sessions = self.jids[jid]
            for session_id in list(sessions):
                self._discard_session(jid, session_id, reason)
                
    def _update_presence(self):
        services = Element("services", xmlns=SERVICE_NS)
        for service_id, service in self.services.items():
            element = Element("service", id=service_id)
            services.add(element)
        self.xmpp.core.presence(services, to=self.room.nick_jid)

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

    def _start(self, jid, service_id, element):
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

        session_id = uuid.uuid4().hex
        session = service.open_session(path, conf)

        sessions = self.jids.setdefault(jid, dict())
        sessions[session_id] = session
        session | self._catch(jid, session_id)
        return Element("start", xmlns=SERVICE_NS, id=session_id)

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

    def run(self):
        state = self._get(self.root_key)
        self._put(self.root_key, None)
        try:
            state = yield self.inner.sub(self.kill_sessions()
                                         | self.main(state))

            self._put(self.root_key, state)

            for path, session in self.sessions.iteritems():
                try:
                    state = session.result()
                except:
                    pass
                else:
                    key = self.path_key(path)
                    self._put(key, state)
            for key, session in self.sessions.iteritems():
                session.result()
        finally:
            self.db.commit()
            self.db.close()

    @threado.stream
    def kill_sessions(inner, self):
        try:
            while True:
                item = yield inner
                inner.send(item)
        except:
            self.shutting_down = True
            type, exc, tb = sys.exc_info()

            for session in self.sessions.values():
                session.throw(Stop())
            for session in self.sessions.values():
                while not session.has_result():
                    try:
                        yield session
                    except:
                        pass
            raise type, exc, tb

    def open_session(self, path, conf):
        assert not self.shutting_down

        if path is None:
            session = self.session(None, **conf)
        elif path in self.sessions:
            old_session = self.sessions.pop(path)
            old_session.throw(Stop())
            session = self.wait(old_session, conf)
            self.sessions[path] = session
        else:
            key = self.path_key(path)
            session = self.session(self._get(key), **conf)
            self._put(key, None)
            self.sessions[path] = session
        bind(self, session)
        return session

    @threado.stream
    def wait(inner, self, session, conf):
        state = yield session
        state = yield inner.sub(self.session(state, **conf))
        inner.finish(state)

    def delete_session(self, path):
        assert not self.shutting_down

        if path is None:
            return
        if path not in self.sessions:
            return
        old_session = self.sessions.pop(path)
        session = self.scrap(old_session)
        self.sessions[path] = session
        return session

    @threado.stream
    def scrap(inner, self, session):
        yield session
        del session
        inner.finish()

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
