import time
import collections

from idiokit import threado, timer
from abusehelper.core import events, taskfarm, services, templates, bot

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
def alert(inner, *times):
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

class ReportBot(bot.ServiceBot):
    REPORT_NOW = object()
    
    def __init__(self, *args, **keys):
        bot.ServiceBot.__init__(self, *args, **keys)

        self.rooms = taskfarm.TaskFarm(self.handle_room)
        self.collectors = dict()
        self.waker = threado.Channel()
        self.queue = collections.deque()

    @threado.stream
    def handle_room(inner, self, name):
        self.log.info("Joining room %r", name)
        room = yield inner.sub(self.xmpp.muc.join(name, self.bot_name))
        self.log.info("Joined room %r", name)

        try:
            yield inner.sub(room
                            | events.stanzas_to_events()
                            | self.distribute(name))
        finally:
            self.log.info("Left room %r", name)

    @threado.stream_fast
    def distribute(inner, self, name):
        while True:
            yield inner

            collectors = self.collectors.get(name)
            for event in inner:
                for collectors in collectors:
                    collectors.send(event)

    @threado.stream
    def main(inner, self, queue):
        if queue:
            self.queue.extendleft(queue)

        try:
            while True:
                yield inner, self.waker

                list(self.waker)
                list(inner)

                while self.queue:
                    first = self.queue.popleft()
                    success = yield inner.sub(self.report(first))
                    if not success:
                        self.queue.append(first)
        except services.Stop:
            inner.finish(self.queue)

    @threado.stream
    def session(inner, self, state, src_room, **keys):
        @threado.stream_fast
        def _alert(inner):
            alert = self.alert(**keys)
            while True:
                yield inner, alert
                
                for item in inner:
                    inner.send(item)
                    
                if list(alert):
                    inner.send(self.REPORT_NOW)

        @threado.stream_fast
        def _collect(inner):
            while True:
                yield inner
                
                for item in inner:
                    self.queue.append(item)
                    self.waker.send()

        collector = _alert() | self.collect(state, **keys) | _collect()
        self.collectors.setdefault(src_room, set()).add(collector)

        try:
            result = yield inner.sub(collector | self.rooms.inc(src_room))
        finally:
            collectors = self.collectors.get(src_room, set())
            collectors.discard(collector)
            if not collectors:
                self.collectors.pop(src_room, None)

        inner.finish(result)

    @threado.stream
    def alert(inner, self, times, **keys):
        yield inner.sub(alert(*times))

    @threado.stream_fast
    def collect(inner, self, state, **keys):
        if state is None:
            state = events.EventCollector()

        try:
            while True:
                yield inner

                for event in inner:
                    if event is self.REPORT_NOW:
                        inner.send(state.purge())
                    else:
                        state.append(event)
        except services.Stop:
            inner.finish(state)

    @threado.stream
    def report(inner, self, collected):
        yield
        inner.finish(True)

class MailTemplate(templates.Template):
    def format(self, events, encoding="utf-8"):
        from email import message_from_string
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
        from email.charset import Charset, QP
        from email.utils import formatdate, make_msgid

        parts = list()
        data = templates.Template.format(self, parts, events)
        parsed = message_from_string(data.encode(encoding))

        charset = Charset(encoding)
        charset.header_encoding = QP

        msg = MIMEMultipart()
        msg.set_charset(charset)
        for key, value in msg.items():
            del parsed[key]
        for key, value in parsed.items():
            msg[key] = value

        for encoded in ["Subject", "Comment"]:
            if encoded not in msg:
                continue
            value = charset.header_encode(msg[encoded])
            del msg[encoded]
            msg[encoded] = value

        del msg['Content-Transfer-Encoding']
        msg['Content-Transfer-Encoding'] = '7bit'

        msg.attach(MIMEText(parsed.get_payload(), "plain", encoding))
        for part in parts:
            msg.attach(part)
        return msg

class MailerService(ReportBot):
    mail_sender = bot.Param("from whom it looks like the mails came from")
    smtp_host = bot.Param("hostname of the SMTP service used for sending mails")
    smtp_port = bot.IntParam("port of the SMTP service used for sending mails",
                             default=25)
    smtp_auth_user = bot.Param("username for the authenticated SMTP service",
                               default=None)
    smtp_auth_password = bot.Param("password for the authenticated SMTP "+
                                   "service", default=None)

    def __init__(self, **keys):
        ReportBot.__init__(self, **keys)

        if self.smtp_auth_user and not self.smtp_auth_password:
            self.smtp_auth_password = getpass.getpass("SMTP password: ")
        self.server = None

        csv = templates.CSVFormatter()
        attach_csv = templates.AttachUnicode(csv)
        embed_csv = templates.AttachAndEmbedUnicode(csv)
        self.formatters = dict(csv=csv,
                               attach_csv=attach_csv,
                               attach_and_embed_csv=embed_csv)

    def collect(self, state, **keys):
        return ReportBot.collect(self, state, **keys) | self._collect(**keys)

    @threado.stream
    def _collect(inner, self, to=[], cc=[], template="", **keys):
        from email.header import decode_header
        from email.utils import formatdate, make_msgid, getaddresses, formataddr

        # FIXME: Use encoding after getaddresses
        from_addr = getaddresses([self.mail_sender])[0]
        to_addrs = ", ".join(map(formataddr, getaddresses(to)))
        cc_addrs = ", ".join(map(formataddr, getaddresses(cc)))

        formatters = dict(self.formatters)
        formatters["to"] = templates.Const(to_addrs)
        formatters["cc"] = templates.Const(cc_addrs)
        template = MailTemplate(template, **formatters)

        while True:
            events = yield inner
            if not events:
                continue

            msg = template.format(events)
    
            if "To" not in msg:
                msg["To"] = to_addrs
            if "Cc" not in msg:
                msg["Cc"] = cc_addrs

            del msg["From"]
            msg["From"] = formataddr(from_addr)
            msg['Date'] = formatdate()             
            msg['Message-ID'] = make_msgid()
            subject = msg.get("Subject", "")

            msg_data = msg.as_string()

            mail_to = (msg.get_all("To", list()) 
                       + msg.get_all("Cc", list()))
            mail_to = [addr for (name, addr) in getaddresses(mail_to)]
            mail_to = filter(None, map(str.strip, mail_to))
            for address in mail_to:
                inner.send(from_addr[1], address, subject, msg_data)

    def _connect(self):
        import smtplib

        server = smtplib.SMTP(self.smtp_host, self.smtp_port)
        try:
            server.ehlo()
            try:
                if server.has_extn('starttls'):
                    server.starttls()
                    # redundant ehlo, yeah!
                    server.ehlo()
                    server.login(self.smtp_auth_user, self.smtp_auth_password)
            except:
                pass
        except:
            server.quit()
            raise
        return server

    @threado.stream
    def main(inner, self, state):
        try:
            result = yield inner.sub(ReportBot.main(self, state))
        finally:
            if self.server is not None:
                try:
                    yield inner.thread(self.server.quit)
                except:
                    pass
                self.server = None
        inner.finish(result)

    @threado.stream
    def report(inner, self, item):
        from_addr, to_addr, subject, msg_str = item

        # Try to connect to the SMTP server if we're haven't done that yet
        while self.server is None:
            list(inner)
            try:
                self.log.info("Connecting %r port %d", 
                              self.smtp_host, self.smtp_port)
                self.server = yield inner.thread(self._connect)
            except:
                self.log.error("Error connecting SMTP server, "+
                               "retrying in 10 seconds")
                yield inner.sub(timer.sleep(10.0))
            else:
                self.log.info("Connected to the SMTP server")
        list(inner)
                
        self.log.info("Sending message %r to %r", subject, to_addr)
        try:
            yield inner.thread(self.server.sendmail, 
                               from_addr, to_addr, msg_str)
        except Exception, exc:
            self.log.info("Could not send message to %r: %s", to_addr, exc)
            try:
                yield inner.thread(self.server.quit)
            except:
                pass
            self.server = None
            inner.finish(False)

        self.log.info("Sent message to %r", to_addr)
        inner.finish(True)

if __name__ == "__main__":
    MailerService.from_command_line().execute()
