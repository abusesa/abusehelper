import sys
import uuid
import random
import contextlib
from idiokit import threado
from idiokit.jid import JID
from idiokit.xmlcore import Element
from abusehelper.core import serialize

SERVICE_NS = "abusehelper#service"

def bind(parent, child):
    def _bind(source):
        try:
            result = source.result()
            if source is parent:
                child.throw(threado.Finished(result))
        except:
            if source is parent:
                child.rethrow()
            else:
                parent.rethrow()
    parent.add_finish_callback(_bind)
    child.add_finish_callback(_bind)

class SessionError(Exception):
    pass

class Unavailable(threado.Finished):
    pass

@threado.stream
def iq_handler(inner, xmpp, element):
    try:
        try:
            result = yield inner
        except SessionError:
            raise
        except:
            _, exc, tb = sys.exc_info()
            raise SessionError("Session handling failed: " + repr(exc))
    except SessionError, se:
        msg = se.args[0]
        error = xmpp.core.build_error("cancel", "session-failure", msg)
        xmpp.core.iq_error(element, error)
    else:
        xmpp.core.iq_result(element, result)

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
        self.xmpp.core.add_iq_handler(self.handle_iq, "config", SERVICE_NS)
        self.start()

    @threado.stream
    def session(inner, self, service_id):
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
        result = yield inner.sub(self.xmpp.core.iq_set(start, to=jid))

        for start in result.children("start", SERVICE_NS).with_attrs("id"):
            session_id = start.get_attr("id")
            session = RemoteSession(self.xmpp, jid, session_id)
            session.start()
            bind(self, session)

            sessions = self.jids.setdefault(jid, dict())
            sessions[session_id] = session
            session | self._catch(jid, session_id)
            inner.finish(session)
        else:
            raise SessionError("No service ID received")

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

        if payload.named("start").with_attrs("id"):
            service_id = payload.get_attr("id")
            self._start(jid, service_id) | iq_handler(self.xmpp, iq)
        if payload.named("config").with_attrs("id"):
            session_id = payload.get_attr("id")
            self._config(jid, session_id, payload) | iq_handler(self.xmpp, iq)
        return True

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

    def _discard_session(self, jid, session_id, reason=threado.Finished()):
        if jid in self.jids:
            sessions = self.jids[jid]
            if session_id in sessions:
                session = sessions.pop(session_id)
                session.throw(reason)
            if not sessions:
                del self.jids[jid]

    def _discard_jid(self, jid, reason=threado.Finished()):
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
        print "Offering service '%s'" % service_id

        try:
            yield inner.sub(service)
        finally:
            print "Retired service '%s'" % service_id
            self._update_presence()

    @threado.stream
    def _start(inner, self, jid, service_id):
        service = self.services.get(service_id, None)
        if service is None:
            raise SessionError("Service '%s' not available" % service_id)

        session_id = uuid.uuid4().hex
        session = service.session()
        session.start()
        bind(service, session)

        sessions = self.jids.setdefault(jid, dict())
        sessions[session_id] = session
        session | self._catch(jid, session_id)

        inner.send(Element("start", xmlns=SERVICE_NS, id=session_id))
        yield

    @threado.stream
    def _config(inner, self, jid, session_id, config):
        if jid not in self.jids:
            raise SessionError("Invalid session ID")        
        sessions = self.jids[jid]
        if session_id not in sessions:
            raise SessionError("Invalid session ID")
        session = sessions[session_id]

        for child in config.children():
            try:
                result = yield inner.sub(session.config(serialize.load(child)))
            except:
                session.rethrow()
                raise
            break
        else:
            raise SessionError("Invalid config")

        element = Element("config", xmlns=SERVICE_NS, id=session_id)
        element.add(serialize.dump(result))
        inner.send(element)

    @threado.stream
    def _catch(inner, self, jid, session_id):
        try:
            while True:
                yield inner
        finally:
            end = Element("end", xmlns=SERVICE_NS, id=session_id)
            self.xmpp.core.message(jid, end)
            self._discard_session(jid, session_id)

class RemoteSession(threado.GeneratorStream):
    def __init__(self, xmpp, jid, session_id):
        threado.GeneratorStream.__init__(self)
        self.xmpp = xmpp
        self.jid = jid
        self.session_id = session_id

    @threado.stream
    def config(inner, self, **keys):
        config = Element("config", xmlns=SERVICE_NS, id=self.session_id)
        config.add(serialize.dump(dict(keys)))

        result = yield inner.sub(self.xmpp.core.iq_set(config, to=self.jid))
        for config in result.children("config", SERVICE_NS).with_attrs("id"):
            for child in config.children():
                inner.finish(serialize.load(child))
        raise SessionError("No config info received")       

class Session(threado.GeneratorStream):
    @threado.stream
    def config(inner, self, conf):
        yield
        inner.finish(conf)

class Service(threado.GeneratorStream):
    def session(self):
        return Session(self)

@threado.stream
def join_lobby(inner, xmpp, name, nick=None):
    room = yield inner.sub(xmpp.muc.join(name, nick))
    lobby = Lobby(xmpp, room)
    inner.finish(lobby)
