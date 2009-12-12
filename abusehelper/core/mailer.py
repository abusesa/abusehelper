import time
import collections

from idiokit import threado, timer
from abusehelper.core import events, roomfarm, services, templates

def next_time(time_string):
    parsed = list(time.strptime(time_string, "%H:%M"))
    now = time.localtime()

    current = list(now)
    current[3:6] = parsed[3:6]

    current_time = time.time()
    delta = time.mktime(current) - current_time
    if delta <= 0.0:
        current[2] += 1
        return time.mktime(current) - current_time
    return delta

@threado.stream
def ticker(inner):
    sleeper = threado.Channel()

    while True:
        try:
            item = yield inner, sleeper
        except:
            sleeper.throw()
            raise

        if sleeper.has_result():
            inner.send()
        if inner.was_source:
            times = item

        if times:
            sleeper = timer.sleep(min(map(next_time, times)))
        else:
            sleeper = threado.Channel()

class MailerSession(services.Session):
    def __init__(self, service, from_addr):
        services.Session.__init__(self)

        self.events = dict()
        self.configs = threado.Channel()

        self.service = service
        self.from_addr = from_addr
        self.room_name = None

    def add_event(self, event):
        emails = event.attrs.get("email", list())
        if not emails:
            self.events.setdefault(None, list()).append(event)
        else:
            for email in emails:
                self.events.setdefault(email, list()).append(event)

    def create_reports(self, to, cc):
        default = self.events.pop(None, ())
        for email in to:
            self.events.setdefault(email, list()).extend(default)

        for email, events in self.events.iteritems():
            if not events:
                continue
            if email in to:
                yield [email], cc, events
            else:
                yield [email], to + cc, events
        self.events.clear()

    def prepare_mail(self, events, to, cc, subject, template):
        from email.header import Header
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.charset import Charset, QP
        from email.utils import formatdate, make_msgid, getaddresses, formataddr
        
        ENCODING = "utf-8"
        
        from_addr = getaddresses([self.from_addr])[0]
        to_addrs = getaddresses(to)
        cc_addrs = getaddresses(cc)

        msg = MIMEMultipart()
    
        # FIXME: Use encoding after getaddresses
        msg["From"] = formataddr(from_addr)
        msg["To"] = ", ".join(map(formataddr, to_addrs))
        msg["Cc"] = ", ".join(map(formataddr, cc_addrs))
        msg["Subject"] = Header(subject, ENCODING)
        msg['Date'] = formatdate()
        msg['Message-ID'] = make_msgid()

        charset = Charset(ENCODING)
        charset.header_encoding = QP
        msg.set_charset(charset)

        del msg['Content-Transfer-Encoding']
        msg['Content-Transfer-Encoding'] = '7bit'

        parts = list()
        data = template.format(parts, events)

        msg.attach(MIMEText(data.encode("utf-8"), "plain", "utf-8"))
        for part in parts:
            msg.attach(part)

        msg_data = msg.as_string()
        for to in to_addrs + cc_addrs:
            yield from_addr[1], to[1], subject, msg_data

    def create_template(self, template):
        csv = templates.CSVFormatter()
        attach_csv = templates.AttachUnicode(csv)
        embed_csv = templates.AttachAndEmbedUnicode(csv)

        template = templates.Template(template, 
                                      csv=csv,
                                      attach_csv=attach_csv,
                                      attach_and_embed_csv=embed_csv)
        return template

    def run(self):
        alarm_ticker = ticker()

        while True:
            while True:
                item = yield self.inner, self.configs
                if self.inner.was_source:
                    self.add_event(item)
                elif item is not None:
                    to, cc, subject, template, times = item
                    template = self.create_template(template)
                    break

            alarm_ticker.send(times)
            while True:
                item = yield self.inner, self.configs, alarm_ticker

                if alarm_ticker.was_source:
                    for to, cc, data in self.create_reports(to, cc):                        
                        prepare = self.prepare_mail(data, to, cc, subject, template)
                        for from_addr, to_addr, subject, msg_str in prepare:
                            self.service.send(from_addr, to_addr, subject, msg_str)
                elif self.inner.was_source:
                    self.add_event(item)
                elif item is not None:
                    to, cc, subject, template, times = item
                    template = self.create_template(template)
                    alarm_ticker.send(times)
                else:
                    alarm_ticker.send([])
                    break
        
    @threado.stream
    def config(inner, self, conf):
        self.service.srcs.dec(self.room_name, self)

        if conf is None:
            self.service.rooms(self)
            self.configs.send(None)
        else:
            to = conf.get("to", [])
            cc = conf.get("cc", [])
            subject = conf["subject"]
            template = conf["template"]
            times = conf["times"]
            self.room_name = conf["room"]

            self.service.rooms(self, self.room_name)
            self.service.srcs.inc(self.room_name, self)
            self.configs.send(to, cc, subject, template, times)
        yield
        inner.finish(conf)

class MailerService(roomfarm.RoomFarm):
    def __init__(self, xmpp, host, port, from_addr, username="", password=""):
        roomfarm.RoomFarm.__init__(self, xmpp)

        self.srcs = roomfarm.Counter()
        self.from_addr = from_addr

        self.host = host
        self.port = port
        self.username = username
        self.password = password

    @threado.stream
    def handle_room(inner, self, name):
        print "Joining room", name
        room = yield inner.sub(self.xmpp.muc.join(name))
        print "Joined room", name
        yield inner.sub(room
                        | events.stanzas_to_events()
                        | self.distribute(name))

    @threado.stream_fast
    def distribute(inner, self, name):
        while True:
            yield inner

            dsts = self.srcs.get(name)
            for event in inner:
                for dst in dsts:
                    dst.send(event)
        
    def get_smtp(self):
        import smtplib

        server = smtplib.SMTP(self.host, self.port)
        try:
            server.ehlo()
            try:
                if server.has_extn('starttls'):
                    server.starttls()
                    # redundant ehlo, yeah!
                    server.ehlo()
                    server.login(self.username, self.password)
            except:
                pass
        except:
            server.quit()
            raise
        return server

    def run(self):
        queue = collections.deque()
        server = None

        @threado.stream
        def sleep_and_collect(inner, delay):
            sleeper = timer.sleep(delay)
            while True:
                item = yield inner, sleeper
                if sleeper.was_source:
                    inner.finish()
                queue.append(item)            

        while True:
            # Wait for something to send
            if not queue:
                item = yield self.inner
                queue.append(item)

            # Try to connect to the SMTP server if we're haven't done that yet
            while server is None:
                try:
                    print "Connecting %s port %d" % (self.host, self.port)
                    server = yield self.inner.thread(self.get_smtp)
                except:
                    print "Error connecting SMTP server, retrying in 10 seconds"
                    yield self.inner.sub(sleep_and_collect(10.0))
                else:
                    print "Connected to the SMTP server"

            while queue:
                # Send the oldest mail
                from_addr, to_addr, subject, msg_str = queue[0]
                print "Sending message %r to %s" % (subject, to_addr)
                try:
                    yield self.inner.thread(server.sendmail, from_addr, 
                                            to_addr, msg_str)
                except Exception, exc:
                    print "Could not send message to %s: %s" % (to_addr, exc)
                    try:
                        yield self.inner.thread(server.quit)
                    except:
                        pass
                    server = None
                    break
                else:
                    queue.popleft()
                    print "Sent message to %s" % to_addr
                
    def session(self):
        return MailerSession(self, self.from_addr)

def main(xmpp_jid, service_room, smtp_host, mail_sender, 
         xmpp_password=None, smtp_port=25,
         submission_username=None, submission_password=None,
         log_file=None):
    import getpass
    from idiokit.xmpp import connect
    from abusehelper.core import log
    
    if not xmpp_password:
        xmpp_password = getpass.getpass("XMPP password: ")
    if submission_username and not submission_password:
        submission_password = getpass.getpass("SMTP password: ")

    logger = log.config_logger("mailer", filename=log_file)

    @threado.stream
    def bot(inner):
        print "Connecting XMPP server with JID", xmpp_jid
        xmpp = yield connect(xmpp_jid, xmpp_password)
        xmpp.core.presence()

        print "Joining lobby", service_room
        lobby = yield services.join_lobby(xmpp, service_room, "mailer")
        logger.addHandler(log.RoomHandler(lobby.room))

        mailer = MailerService(xmpp, smtp_host, smtp_port, mail_sender,
                               submission_username, submission_password)
        yield inner.sub(lobby.offer("mailer", mailer))
    return bot()
main.service_room_help = "the room where the services are collected"
main.xmpp_jid_help = "the XMPP JID (e.g. xmppuser@xmpp.example.com)"
main.xmpp_password_help = "the XMPP password"
main.smtp_host_help = "hostname of the SMTP service used for sending mails"
main.smtp_port_help = "port of the SMTP service used for sending mails"
main.mail_sender_help = "from whom it looks like the mails came from"
main.submission_username_help = "username for the authenticated SMTP service"
main.submission_password_help = "password for the authenticated SMTP service"
main.log_file_help = "log to the given file instead of the console"

if __name__ == "__main__":
    from abusehelper.core import opts
    threado.run(opts.optparse(main))
