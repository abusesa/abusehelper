from abusehelper.core import events, bot
from idiokit import threado, timer

import json
import cgi
import threading
import BaseHTTPServer

class POSTBot(bot.FeedBot):
    http_host = bot.Param(default="")
    http_port = bot.IntParam()

    def __init__(self, *args, **keys):
        bot.FeedBot.__init__(self, *args, **keys)
        self.buffer = buffer = list()

        class Handler(BaseHTTPServer.BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.getheader("Content-Length"))
                data = self.rfile.read(length)
                data = cgi.parse_qs(data)

                event = events.Event()
                event.add("src_ip", str(self.client_address[0]))
                event.add("src_port", str(self.client_address[1]))
                for key in data:
                    if key.lower() == "submit":
                        continue

                    ukey = unicode(key, "utf8")
                    for value in data[key]:
                        if isinstance(value, basestring):
                            event.add(ukey, unicode(value, "utf8")) 
        
                buffer.append(event)
                self.send_response(200)

        httpd = BaseHTTPServer.HTTPServer((self.http_host, self.http_port), 
                                          Handler)
        self.thread = threading.Thread(target=httpd.serve_forever)
        self.thread.setDaemon(True)
        self.thread.start()
        self.log.info("HTTP server started at http://%s:%i/", self.http_host,
                                                              self.http_port)

    @threado.stream
    def feed(inner, self):
        while True:
            yield inner, timer.sleep(1)

            while len(self.buffer) > 0:
                event = self.buffer.pop(0)
                yield inner.send(event)

if __name__ == "__main__":
    POSTBot.from_command_line().execute()
