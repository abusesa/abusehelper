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
def ticker(inner, times):
    while True:
        if times:
            sleeper = timer.sleep(min(map(next_time, times)))
        else:
            sleeper = threado.Channel()

        while not sleeper.has_result():
            try:
                yield inner, sleeper
            except:
                sleeper.rethrow()
                raise
        inner.send()

class MailerState(object):
    def __init__(self):
        self.events = collections.defaultdict(events.EventCollector)

    def __getstate__(self):
        return self.events

    def __setstate__(self, events):
        self.events = events

    def add_event(self, event):
        emails = event.attrs.get("email", [None])
        for email in emails:
            self.events[email].append(event)

    def create_reports(self, to, cc):
        emails = collections.defaultdict(events.EventList)
        emails.update((key, value.purge())
                      for (key, value) 
                      in self.events.iteritems())

        default = emails.pop(None, events.EventList())
        for email in to:
            emails[email].extend(default)

        for email, event_list in emails.iteritems():
            if not event_list:
                continue
            if email in to:
                yield [email], cc, event_list
            else:
                yield [email], to + cc, event_list
        self.events.clear()

    def prepare_mail(self, events, from_addr, to, cc, subject, template):
        from email.header import Header
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.charset import Charset, QP
        from email.utils import formatdate, make_msgid, getaddresses, formataddr
        
        ENCODING = "utf-8"
        
        from_addr = getaddresses([from_addr])[0]
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

class MailerService(roomfarm.RoomFarm):
    def __init__(self, xmpp, host, port, from_addr, 
                 state_file=None, username="", password=""):
        roomfarm.RoomFarm.__init__(self, state_file)

        self.xmpp = xmpp

        self.from_addr = from_addr
        self.host = host
        self.port = port
        self.username = username
        self.password = password

        self.states = roomfarm.Counter()

    @threado.stream
    def handle_room(inner, self, name):
        print "Joining room", repr(name)
        room = yield inner.sub(self.xmpp.muc.join(name))
        print "Joined room", repr(name)

        try:
            yield inner.sub(room
                            | events.stanzas_to_events()
                            | self.distribute(name))
        finally:
            print "Left room", repr(name)

    @threado.stream_fast
    def distribute(inner, self, name):
        while True:
            yield inner

            states = self.states.get(name)
            for event in inner:
                for state in states:
                    state.add_event(event)
        
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

    @threado.stream
    def main(inner, self, queue):
        if queue is None:
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

        try:
            while True:
                # Wait for something to send
                if not queue:
                    item = yield inner
                    queue.append(item)
                    
                # Try to connect to the SMTP server if we're haven't done that yet
                while server is None:
                    try:
                        print "Connecting %s port %d" % (self.host, self.port)
                        server = yield inner.thread(self.get_smtp)
                    except:
                        print "Error connecting SMTP server, retrying in 10 seconds"
                        yield inner.sub(sleep_and_collect(10.0))
                    else:
                        print "Connected to the SMTP server"

                while queue:
                    # Send the oldest mail
                    from_addr, to_addr, subject, msg_str = queue[0]
                    print "Sending message %r to %s" % (subject, to_addr)
                    try:
                        yield inner.thread(server.sendmail, from_addr, 
                                           to_addr, msg_str)
                    except Exception, exc:
                        print "Could not send message to %s: %s" % (to_addr, exc)
                        try:
                            yield inner.thread(server.quit)
                        except:
                            pass
                        server = None
                        break
                    else:
                        queue.popleft()
                        print "Sent message to %s" % to_addr
        except services.Stop:
            inner.finish(queue)

    @threado.stream
    def session(inner, self, state, 
                room, subject, template, times, to=[], cc=[]):
        if state is None:
            state = MailerState()

        alarm_ticker = ticker(times)
        template = state.create_template(template)

        self.rooms(inner, room)
        self.states.inc(room, state)
        try:
            while True:
                yield inner, alarm_ticker
                if inner.was_source:
                    continue

                for to, cc, events in state.create_reports(to, cc):
                    prepare = state.prepare_mail(events, 
                                                 self.from_addr, 
                                                 to, 
                                                 cc, 
                                                 subject, 
                                                 template)
                    for from_addr, to_addr, subject, msg_data in prepare:
                        self.send(from_addr, to_addr, subject, msg_data)
        except services.Stop:
            inner.finish(state)
        finally:
            alarm_ticker.throw(threado.Finished())
            self.states.dec(room, state)
            self.rooms(inner)

def main(name, xmpp_jid, service_room, smtp_host, mail_sender, 
         xmpp_password=None, smtp_port=25,
         submission_username=None, submission_password=None,
         state_file=None, log_file=None):
    import getpass
    from idiokit.xmpp import connect
    from abusehelper.core import log
    
    if not xmpp_password:
        xmpp_password = getpass.getpass("XMPP password: ")
    if submission_username and not submission_password:
        submission_password = getpass.getpass("SMTP password: ")

    logger = log.config_logger(name, filename=log_file)

    @threado.stream
    def bot(inner):
        print "Connecting XMPP server with JID", xmpp_jid
        xmpp = yield inner.sub(connect(xmpp_jid, xmpp_password))
        xmpp.core.presence()

        print "Joining lobby", service_room
        lobby = yield inner.sub(services.join_lobby(xmpp, service_room, name))
        logger.addHandler(log.RoomHandler(lobby.room))

        service = MailerService(xmpp, smtp_host, smtp_port, mail_sender,
                                state_file, 
                                submission_username, submission_password)
        yield inner.sub(lobby.offer(name, service))
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
    threado.run(opts.optparse(main), throw_on_signal=services.Stop())
