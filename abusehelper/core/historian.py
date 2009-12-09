import string
from random import Random
import time
import sqlite3
from idiokit.xmpp import connect, Element
from idiokit.jid import JID
from idiokit import threado, util
from abusehelper.core import roomfarm, events, services

def open_db(path=':memory:'):
    conn = sqlite3.connect(path)

    c = conn.cursor()
    c.execute('create table if not exists events (id TEXT, date TEXT, room TEXT)')
    c.execute('create table if not exists attrs (key TEXT, value TEXT, event TEXT)')
    conn.commit()
    return conn

def save_event(conn, room, event):
    id = ''.join(Random().sample(string.letters+string.digits, 10))

    c = conn.cursor()
    c.execute('select * from events where id="%s"' % (id))

    event_time = unicode(time.strftime("%Y-%m-%d %H:%M:%S"))
    room_id = unicode(room.room_jid)

    c.execute("insert into events values ('%s', '%s','%s')" % (id, event_time, room_id))

    for key, values in event.attrs.items():
        for value in values:
            c.execute("insert into attrs values ('%s', '%s','%s')" % (key, value, id))

    print "collected:", room.room_jid, time.time()

    conn.commit()

def events_from_db(conn, room_id=None):
    c = conn.cursor()

    if room_id:
        c.execute('select * from events where room="%s"' % room_id)
    else:
        c.execute('select * from events')

    for id, time, room in c:
        attrs = dict()

        d = conn.cursor()
        d.execute('select key, value from attrs where event="%s"' % id)
        for key, value in d:
            attrs.setdefault(key, list())
            attrs[key].append(value)

        yield time, room, attrs

def parse_command(message):
    parts = message.text.split()
    if not len(parts) >= 2:
        return None, dict(), set()

    command = parts[0][1:]

    keyed = dict()
    values = set()
    for part in parts[1:]:
        pair = part.split("=")
        if len(pair) >= 2:
            keyed.setdefault(pair[0], set())
            keyed[pair[0]].add(pair[1])
        elif len(pair) == 1:
            values.add(pair[0])

    return command, keyed, values


class HistorianSession(services.Session):
    def __init__(self, service):
        services.Session.__init__(self)
        self.service = service

    @threado.stream
    def config(inner, self, conf):
        if conf:
            self.service.rooms(self, *conf['rooms'])

        yield
        inner.finish(conf)

class HistorianService(roomfarm.RoomFarm):
    def __init__(self, xmpp, db_file):
        roomfarm.RoomFarm.__init__(self, xmpp)

        self.xmpp = xmpp
        self.conn = open_db(db_file)

    @threado.stream
    def handle_room(inner, self, name):
        room = yield inner.sub(self.xmpp.muc.join(name))

        yield inner.sub(room
                        | self.command_parser(room)
                        | events.stanzas_to_events()
                        | self.collect()
                        | threado.throws())

    def session(self):
        return HistorianSession(self)

    @threado.stream
    def collect(inner, self):
        while True:
            event = yield inner

            save_event(self.conn, self.room, event)
            inner.send(event)

    @threado.stream
    def command_parser(inner, self, room):
        while True:
            elements = yield inner

            for message in elements.named("message").with_attrs("from"):
                sender = JID(message.get_attr("from"))
                if sender == room.nick_jid:
                    continue

                for body in message.children("body"):
                    command, keyed, values = parse_command(body)
                    if not command or command != "historian":
                        continue

                    room_jid = unicode(room.room_jid)

                    for event_time, event_room, attrs in events_from_db(self.conn): #, room_jid):
                        send = False

                        #simple OR
                        for event_key, event_values in attrs.items():
                            for value in values:
                                if value in event_values:
                                    send = True
                                    break

                            for value in keys.get(event_key, set()):
                                if value in event_values:
                                    send = True
                                    break

                            if send:
                                break

                        if send:
                            body = Element("body")
                            body.text = "%s\n" % event_time
                            for event_key, event_values in attrs.items():
                                body.text += "%s: %s\n" % (event_key, ", ".join(event_values))
                            room.send(body)
                            yield

            inner.send(elements)

def main(xmpp_jid, service_room, db_file, xmpp_password=None):
    import getpass

    if not xmpp_password:
        xmpp_password = getpass.getpass("XMPP password: ")

    @threado.stream
    def bot(inner):
        print "Connecting XMPP server with JID", xmpp_jid
        xmpp = yield connect(xmpp_jid, xmpp_password)
        xmpp.core.presence()

        print "Joining lobby", service_room
        lobby = yield services.join_lobby(xmpp, service_room, "historian")

        yield inner.sub(lobby.offer("historian", HistorianService(xmpp, db_file)))
    return bot()
main.service_room_help = "the room where the services are collected"
main.xmpp_jid_help = "the XMPP username (e.g. user@xmpp.example.com)"
main.xmpp_password_help = "the XMPP password"

if __name__ == "__main__":
    from abusehelper.core import opts
    threado.run(opts.optparse(main))
