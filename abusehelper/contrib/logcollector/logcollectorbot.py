"""
A simple bot for getting events from AbuseHelper to a Log Collector (Splunk, Logstash, etc..).

Contributors: "Mauro Silva (CERT.PT)" <mauro.silva@fccn.pt>, "Tomas Lima (CERT.PT)" <tomas.lima@fccn.pt>
"""

import socket
import time as _time
import idiokit
from abusehelper.core import events, bot, taskfarm

class LogCollector(bot.ServiceBot):

    logcollector_ip = bot.Param("127.0.0.1")
    logcollector_port = bot.Param("5000")

    def __init__(self, **keys):
        bot.ServiceBot.__init__(self, **keys)
        self.rooms = taskfarm.TaskFarm(self.handle_room)
        self.srcs = taskfarm.Counter()


    @idiokit.stream
    def handle_room(self, name):
        self.log.info("Joining room %r", name)
        room = yield self.xmpp.muc.join(name, self.bot_name)
        self.log.info("Joined room %r", name)
        try:
            yield idiokit.pipe(events.events_to_elements(),
                               room,
                               events.stanzas_to_events(),
                               self.distribute(name))
        finally:
            self.log.info("Left room %r", name)


    @idiokit.stream
    def distribute(self, name):
        self.connect()
        while True:
            event = yield idiokit.next()

            import json
            event_text = ''
            for key, value in event.items():
                event_text += key + '=' + json.dumps(value) + ' '   
            self.send_data(event_text)


    @idiokit.stream
    def session(self, _, src_room, **keys):
        self.srcs.inc(src_room)
        try:
            yield self.rooms.inc(src_room)
        finally:
            self.srcs.dec(src_room)


    def connect(self):
        self.con = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.con.connect((self.logcollector_ip, self.logcollector_port))


    def send_data(self, data):
        i = 0
        while i < 2:
            try:
                self.con.send(data + "\n")
                self.con.sendall( "" )
                return
            except:
                i += 1
                self.connect()


if __name__ == "__main__":
    LogCollector.from_command_line().execute()
