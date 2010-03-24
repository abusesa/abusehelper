import time
import re
from datetime import datetime
import sqlite3
from idiokit.xmpp import Element
from idiokit.jid import JID
from idiokit import threado, timer
from abusehelper.core import taskfarm, events, bot, services

class HistoryDB(threado.GeneratorStream):
    def __init__(self, path=None, keeptime=None):
        threado.GeneratorStream.__init__(self)

        if path is None:
            path = ":memory:"
        self.conn = sqlite3.connect(path)

        cursor = self.conn.cursor()

        cursor.execute("CREATE TABLE IF NOT EXISTS events "+
                       "(id INTEGER PRIMARY KEY, timestamp INTEGER, room INTEGER)")
        cursor.execute("CREATE INDEX IF NOT EXISTS events_id_index ON events(id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS events_room_ts_index ON events(room, timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS events_room_index ON events(room)")
        cursor.execute("CREATE INDEX IF NOT EXISTS events_ts_index ON events(timestamp)")
        
        cursor.execute("CREATE TABLE IF NOT EXISTS attrs "+
                       "(eventid INTEGER, key TEXT, value TEXT)")
        cursor.execute("CREATE INDEX IF NOT EXISTS attrs_eventid_index ON attrs(eventid)")

        self.conn.commit()
        self.keeptime = keeptime
        self.cursor = self.conn.cursor()

        self.start()

    def collect(self, room_name):
        collect = self._collect(room_name)
        services.bind(self, collect)
        return collect

    @threado.stream_fast
    def _collect(inner, self, room_name):
        while True:
            yield inner
                
            for event in inner:
                if event.contains("action"):
                    continue
                
                self.cursor.execute("INSERT INTO events(timestamp, room) VALUES (?, ?)",
                                    (int(time.time()), room_name))
                eventid = self.cursor.lastrowid
                
                for key in event.keys():
                    values = event.values(key)
                    self.cursor.executemany("INSERT INTO attrs(eventid, key, value) VALUES (?, ?, ?)",
                                            [(eventid, key, value) for value in values])

    def run(self, interval=1.0):
        try:
            while True:
                yield self.inner.sub(timer.sleep(interval))
                list(self.inner)

                if self.keeptime is not None:
                    cutoff = int(time.time() - self.keeptime)
                    
                    max_id = self.cursor.execute("SELECT MAX(events.id) FROM events "+
                                                 "WHERE events.timestamp <= ?", (cutoff,))
                    
                    max_id = list(max_id)[0][0]
                    if max_id is not None:
                        self.cursor.execute("DELETE FROM events WHERE events.id <= ?",
                                            (max_id,))
                        self.cursor.execute("DELETE FROM attrs WHERE attrs.eventid <= ?",
                                            (max_id,))
                self.conn.commit()
                self.cursor = self.conn.cursor()
        finally:
            self.conn.commit()
            self.conn.close()

    def close(self):
        self.throw(threado.Finished())

    def find(self, room_name=None, start=None, end=None):
        query = ("SELECT events.id, events.room, events.timestamp, attrs.key, attrs.value "+
                 "FROM attrs "+
                 "INNER JOIN events ON events.id=attrs.eventid ")
        args = list()
        where = list()
    
        if room_name is not None:
            where.append("events.room = ?")
            args.append(room_name)

        if None not in (start, end):
            where.append("events.timestamp BETWEEN ? AND ?")
            args.append(start)
            args.append(end)
        elif start is not None:
            where.append("events.timestamp >= ?")
            args.append(start)
        elif end is not None:
            where.append("events.timestamp < ?")
            args.append(end)

        if where:
            query += "WHERE " + " AND ".join(where) + " "
        
        query += "ORDER BY events.id"

        event = events.Event()
        previous_id = None
        previous_ts = None
        previous_room = None
        for id, room, ts, key, value in self.conn.execute(query, args):
            if previous_id != id:
                if previous_id is not None:
                    yield previous_ts, previous_room, event
                event = events.Event()

            previous_id = id
            previous_ts = ts
            previous_room = room

            event.add(key, value)

        if previous_id is not None:
            yield previous_ts, previous_room, event

def format_time(timestamp):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

def iso_to_unix(iso_time, format=None):
    if format:
        return time.mktime(datetime.strptime(iso_time, format).timetuple())

    try:
        f = "%Y-%m-%d %H:%M:%S"
        return time.mktime(datetime.strptime(iso_time, f).timetuple())
    except ValueError:
        try:
            f = "%Y-%m-%d %H:%M"
            return time.mktime(datetime.strptime(iso_time, f).timetuple())
        except ValueError:
            f = "%Y-%m-%d"
            return time.mktime(datetime.strptime(iso_time, f).timetuple())

def parse_command(message, name):
    parts = message.text.split()
    if not len(parts) >= 2:
        return None, None, None
    command = parts[0][1:]
    if command != name:
        return None, None, None

    params = " ".join(parts[1:])

    start = list()
    end = list()
    keyed = dict()
    values = set()
    regexp = r'(\S+="[\S\s]+?")|(\S+=\S+)|("\S+\s\S+")|(\S+)'
    for match in re.findall(regexp, params):
        for group in match:
            if not group:
                continue

            pair = group.split('=')

            if len(pair) == 1:
                value = pair[0]
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                if value:
                    values.add(value)
            elif len(pair) >= 2:
                value = "=".join(pair[1:])
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]

                if value:
                    if pair[0] == "start":
                        try:
                            start.append(iso_to_unix(value))
                        except:
                            keyed.setdefault(pair[0], set())
                            keyed[pair[0]].add(value)
                    elif pair[0] == "end":
                        try:
                            end.append(iso_to_unix(value))
                        except:
                            keyed.setdefault(pair[0], set())
                            keyed[pair[0]].add(value)
                    else:
                        keyed.setdefault(pair[0], set())
                        keyed[pair[0]].add(value)

    if start:
        start = sorted(start).pop(0)
    else:
        start = None

    if end:
        end = sorted(end).pop()
    else:
        end = None

    def _match(event):
        for key, keyed_values in keyed.iteritems():
            if keyed_values.intersection(event.values(key)):
                return True
        if values.intersection(event.values()):
            return True
        return False

    return _match, start, end


class HistorianService(bot.ServiceBot):
    def __init__(self, bot_state_file=None, **keys):
        bot.ServiceBot.__init__(self, bot_state_file=None, **keys)
        self.history = HistoryDB(bot_state_file)
        self.rooms = taskfarm.TaskFarm(self.handle_room)

    @threado.stream
    def handle_room(inner, self, name):
        self.log.info("Joining room %r", name)
        room = yield inner.sub(self.xmpp.muc.join(name, self.bot_name))
        self.log.info("Joined room %r", name)

        self.xmpp.add_listener(self.query_handler)

        try:
            yield inner.sub(room
                            | events.stanzas_to_events()
                            | self.history.collect(unicode(room.room_jid))
                            | threado.dev_null())
        finally:
            self.log.info("Left room %r", name)

    @threado.stream
    def session(inner, self, state, src_room):
        try:
            yield inner.sub(self.rooms.inc(src_room))
        except services.Stop:
            inner.finish()

    def query_handler(self, success, element):
        if not success:
            return

        for message in element.named("message").with_attrs("from"):
            sender = JID(message.get_attr("from"))
            room_jid = sender.bare()
            chat_type = message.get_attr("type")

            if chat_type == "groupchat":
                attrs = dict(type=chat_type)
                to = room_jid
            else:
                attrs = dict()
                to = sender
            
            if room_jid not in self.xmpp.muc.rooms:
                return

            if room_jid == self.service_room:
                room_jid = None
            else:
                room_jid = unicode(room_jid)

            for jid in self.xmpp.muc.rooms:
                for room in self.xmpp.muc.rooms[jid]:
                    if room.nick_jid == sender:
                        return

            if message.children("body"):
                self.command_parser(element, to, room_jid, **attrs)
            if message.children("event"):
                self.event_parser(element, to, room_jid, **attrs)

    def event_parser(self, message, requester, room_jid, **attrs):
        for element in message.children("event"):
            event = events.Event.from_element(element)

            if not event or not event.contains("action") \
                         or event.value("action") != "historian":
                continue

            try:
                start = event.value("start")
                end = event.value("end")
            except:
                continue
            
            self.log.info("Got history request from %r for %r", requester, 
                                                                room_jid)
            counter = 0
            for etime, eroom, event in self.history.find(room_jid, start, end):
                counter += 1
                self.xmpp.core.message(requester, event.to_element(), **attrs)
            
            if counter == 0:
                event = events.Event()
                self.xmpp.core.message(requester, event.to_element(), **attrs) 

    def command_parser(self, message, requester, room_jid, **attrs):
        for body in message.children("body"):
            matcher, start, end = parse_command(body, "historian")
            if matcher is None:
                continue

            self.log.info("Got command %r, responding to %r", body.text, 
                                                              requester)
            counter = 0
            for etime, eroom, event in self.history.find(room_jid, start, end):
                if not matcher(event):
                    continue

                body = Element("body")
                body.text = "%s %s\n" % (format_time(etime), eroom)
                for key in event.keys():
                    vals = ", ".join(event.values(key))
                    body.text += "%s: %s\n" % (key, vals)

                elements = [body]

                self.xmpp.core.message(requester, *elements, **attrs)
                counter += 1

            self.log.info("Returned %i events.", counter)

if __name__ == "__main__":
    HistorianService.from_command_line().execute()
