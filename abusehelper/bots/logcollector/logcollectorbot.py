"""
A simple bot for getting events from AbuseHelper to a Log Collector (Splunk, Logstash, etc..).

Contributors:
"Mauro Silva (CERT.PT)" <mauro.silva@fccn.pt>,
"Tomas Lima (CERT.PT)" <tomas.lima@fccn.pt>,
"Sebastian Turpeinen (Codenomicon Oy)" <ecode@codenomicon.com>
"""

try:
    import simplejson as json
except ImportError:
    import json

import idiokit
from idiokit import socket
from abusehelper.core import events, bot, taskfarm

class LogCollector(bot.ServiceBot):

    logcollector_ip = bot.Param(default="127.0.0.1")
    logcollector_port = bot.IntParam(default=5000)

    def __init__(self, **keys):
        bot.ServiceBot.__init__(self, **keys)
        self.rooms = taskfarm.TaskFarm(self.handle_room)

    @idiokit.stream
    def handle_room(self, name):
        self.log.info("Joining room %r", name)
        room = yield self.xmpp.muc.join(name, self.bot_name)
        self.log.info("Joined room %r", name)
        try:
            yield idiokit.pipe(room,
                               events.stanzas_to_events(),
                               self.distribute(name))
        finally:
            self.log.info("Left room %r", name)

    @idiokit.stream
    def distribute(self, name):
        yield self.connect()

        while True:
            event = yield idiokit.next()

            event_text = ''
            for key, value in event.items():
                event_text += key.replace(' ','_') + '=' + json.dumps(value) + ' '

            yield self.send_data(event_text)

    @idiokit.stream
    def session(self, state, src_room):
        yield self.rooms.inc(src_room)

    @idiokit.stream
    def connect(self):
        address = (self.logcollector_ip, self.logcollector_port)
        self.conn = socket.Socket(socket.AF_INET, socket.SOCK_STREAM)

        while True:
            try:
                yield self.conn.connect(address)
                break
            except socket.SocketError, e:
                self.log.error(e.args[1] + ". Retrying in 10 seconds.")
                yield idiokit.sleep(10)

        self.log.info("Connected successfully to %s:%i", address[0], address[1])

    @idiokit.stream
    def send_data(self, data):
        while True:
            try:
                yield self.conn.send(unicode(data + "\n").encode("utf-8"))
                yield self.conn.sendall("")
                break
            except socket.SocketError, e:
                self.log.error(e.args[1] + ". Reconnecting..")
                yield self.conn.close()
                yield self.connect()


if __name__ == "__main__":
    LogCollector.from_command_line().execute()
