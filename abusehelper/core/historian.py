import sqlite3
import time
from idiokit.xmpp import connect, Element
from idiokit.jid import JID
from idiokit import threado
from abusehelper.core import roomfarm, events, services

def open_db(path=None):
    if path is None:
        path = ":memory:"
    conn = sqlite3.connect(path)

    c = conn.cursor()
    c.execute('create table if not exists events \
               (id integer primary key, timestamp integer, room text)')
    c.execute('create table if not exists attrs \
               (eventid integer, key text, value text)')
    conn.commit()
    return conn

def save_event(conn, room, event):
    c = conn.cursor()

    c.execute("insert into events(timestamp, room) values (?, ?)",
              (time.time(), unicode(room.room_jid)))
    eventid = c.lastrowid

    for key, values in event.attrs.items():
        for value in values:
            c.execute("insert into attrs(eventid, key, value) values (?, ?, ?)",
                      (eventid, key, value))

    conn.commit()

def events_from_db(conn, room_id=None):
    c = conn.cursor()

    if room_id:
        c.execute('select * from events where room=?', (room_id,))
    else:
        c.execute('select * from events')

    for eventid, timestamp, room in c:
        attrs = dict()

        d = conn.cursor()
        d.execute('select key, value from attrs where eventid=?', (eventid,))
        for key, value in d:
            attrs.setdefault(key, list())
            attrs[key].append(value)

        yield timestamp, room, attrs

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
                        | self.collect(room)
                        | threado.throws())

    def session(self):
        return HistorianSession(self)

    @threado.stream
    def collect(inner, self, room):
        while True:
            event = yield inner

            save_event(self.conn, room, event)
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

                    rjid = unicode(room.room_jid)

                    for etime, eroom, attrs in events_from_db(self.conn, rjid):
                        send = False

                        #simple OR
                        for event_key, event_values in attrs.items():
                            for value in values:
                                if value in event_values:
                                    send = True
                                    break

                            for value in keyed.get(event_key, set()):
                                if value in event_values:
                                    send = True
                                    break

                            if send:
                                break

                        if send:
                            ts = time.strftime("%Y-%m-%d %H:%M:%S", 
                                               time.localtime(etime))
                            body = Element("body")
                            body.text = "%s %s\n" % (ts, eroom)
                            for event_key, event_values in attrs.items():
                                vals = ", ".join(event_values)
                                body.text += "%s: %s\n" % (event_key, vals)
                            room.send(body)
                            yield

            inner.send(elements)

def main(xmpp_jid, service_room, 
         db_file=None, xmpp_password=None, log_file=None):
    import getpass
    from abusehelper.core import log

    if not xmpp_password:
        xmpp_password = getpass.getpass("XMPP password: ")

    logger = log.config_logger("historian", filename=log_file)

    @threado.stream
    def bot(inner):
        print "Connecting XMPP server with JID", xmpp_jid
        xmpp = yield connect(xmpp_jid, xmpp_password)
        xmpp.core.presence()

        print "Joining lobby", service_room
        lobby = yield services.join_lobby(xmpp, service_room, "historian")

        service = HistorianService(xmpp, db_file)
        yield inner.sub(lobby.offer("historian", service))
    return bot()
main.service_room_help = "the room where the services are collected"
main.xmpp_jid_help = "the XMPP username (e.g. user@xmpp.example.com)"
main.xmpp_password_help = "the XMPP password"
main.db_file_help = ("write the history data into the given file "+
                     "(default: keep the history only in memory)")
main.log_file_help = "log to the given file instead of the console"

if __name__ == "__main__":
    from abusehelper.core import opts
    threado.run(opts.optparse(main))
