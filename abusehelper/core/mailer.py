import time
import socket
import getpass
import smtplib
import collections
from idiokit import threado, timer
from abusehelper.core import events, taskfarm, services, templates, bot

@threado.stream
def wait(inner, amount):
    sleeper = timer.sleep(amount)

    while not sleeper.has_result():
        yield inner, sleeper

def next_time(time_string):
    try:
        parsed = list(time.strptime(time_string, "%H:%M"))
    except (TypeError, ValueError):
        return float(time_string)

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

    @threado.stream
    def distribute(inner, self, name):
        while True:
            event = yield inner

            collectors = self.collectors.get(name)
            for collector in collectors:
                collector.send(event)

    @threado.stream
    def main(inner, self, queue):
        if queue:
            self.queue.extendleft(queue)

        try:
            while True:
                while self.queue:
                    item = self.queue.popleft()
                    success = yield inner.sub(self.report(item))
                    if not success:
                        self.queue.append(item)

                yield inner.sub(wait(1.0))
        except services.Stop:
            inner.finish(self.queue)

    @threado.stream
    def session(inner, self, state, src_room, **keys):
        @threado.stream
        def _alert(inner):
            alert = self.alert(**keys)
            while True:
                source, item = yield threado.any(inner, alert)
                if inner is source:
                    inner.send(item)
                else:
                    inner.send(self.REPORT_NOW)

        @threado.stream
        def _collect(inner):
            while True:
                item = yield inner
                self.queue.append(item)

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

    @threado.stream
    def collect(inner, self, state, **keys):
        if state is None:
            state = events.EventCollector()

        try:
            while True:
                event = yield inner
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

def format_addresses(addrs):
    from email.utils import getaddresses, formataddr

    # FIXME: Use encoding after getaddresses
    return ", ".join(map(formataddr, getaddresses(addrs)))

class MailerService(ReportBot):
    TOLERATED_EXCEPTIONS = (socket.error, smtplib.SMTPException)

    mail_sender = bot.Param("from whom it looks like the mails came from")
    smtp_host = bot.Param("hostname of the SMTP service used for sending mails")
    smtp_port = bot.IntParam("port of the SMTP service used for sending mails",
                             default=25)
    smtp_auth_user = bot.Param("username for the authenticated SMTP service",
                               default=None)
    smtp_auth_password = bot.Param("password for the authenticated SMTP "+
                                   "service", default=None)

    def __init__(self, **keys):
        super(MailerService, self).__init__(**keys)

        if self.smtp_auth_user and not self.smtp_auth_password:
            self.smtp_auth_password = getpass.getpass("SMTP password: ")
        self.server = None

    @threado.stream
    def build_mail(inner, self, events, template="", to=[], cc=[], **keys):
        """
        Return a mail object produced based on collected events and
        session parameters.
        """

        csv = templates.CSVFormatter()
        template = MailTemplate(template,
                                csv=csv,
                                attach_csv=templates.AttachUnicode(csv),
                                attach_and_embed_csv=templates.AttachAndEmbedUnicode(csv),
                                to=templates.Const(format_addresses(to)),
                                cc=templates.Const(format_addresses(cc)))
        yield
        inner.finish(template.format(events))

    def collect(self, state, **keys):
        return ReportBot.collect(self, state, **keys) | self._collect(**keys)

    @threado.stream
    def _collect(inner, self, to=[], cc=[], **keys):
        from email.header import decode_header
        from email.utils import formatdate, make_msgid, getaddresses, formataddr

        # FIXME: Use encoding after getaddresses
        from_addr = getaddresses([self.mail_sender])[0]

        while True:
            events = yield inner
            if not events:
                continue

            msg = yield inner.sub(self.build_mail(events, to=to, cc=cc, **keys))

            if "To" not in msg:
                msg["To"] = format_addresses(to)
            if "Cc" not in msg:
                msg["Cc"] = format_addresses(cc)

            del msg["From"]
            msg["From"] = formataddr(from_addr)
            msg["Date"] = formatdate()
            msg["Message-ID"] = make_msgid()
            subject = msg.get("Subject", "")

            msg_data = msg.as_string()

            mail_to = msg.get_all("To", list()) + msg.get_all("Cc", list())
            mail_to = [addr for (name, addr) in getaddresses(mail_to)]
            mail_to = filter(None, [x.strip() for x in mail_to])
            for address in mail_to:
                inner.send(from_addr[1], address, subject, msg_data)

    @threado.stream
    def main(inner, self, state):
        try:
            result = yield inner.sub(ReportBot.main(self, state))
        finally:
            if self.server is not None:
                _, server = self.server
                self.server = None

                try:
                    yield inner.thread(server.quit)
                except self.TOLERATED_EXCEPTIONS, exc:
                    pass
        inner.finish(result)

    @threado.stream
    def _ensure_connection(inner, self):
        while self.server is None:
            host, port = self.smtp_host, self.smtp_port
            self.log.info("Connecting %r port %d", host, port)
            try:
                server = yield inner.thread(smtplib.SMTP, host, port)
            except self.TOLERATED_EXCEPTIONS, exc:
                self.log.error("Error connecting SMTP server: %r", exc)
            else:
                self.log.info("Connected to the SMTP server")
                self.server = False, server
                break

            self.log.info("Retrying SMTP connection in 10 seconds")
            yield inner.sub(wait(10.0))

    def _try_to_authenticate(self, server):
        if server.has_extn("starttls"):
            server.starttls()
            server.ehlo()

        if (self.smtp_auth_user is not None and
            self.smtp_auth_password is not None and
            server.has_extn("auth")):
            server.login(self.smtp_auth_user, self.smtp_auth_password)

    @threado.stream
    def _try_to_send(inner, self, item):
        from_addr, to_addr, subject, msg = item

        yield inner.sub(self._ensure_connection())

        ehlo_done, server = self.server

        self.log.info("Sending message %r to %r", subject, to_addr)
        try:
            if not ehlo_done:
                yield inner.thread(server.ehlo)
                self.server = True, server

            try:
                yield inner.thread(server.sendmail, from_addr, to_addr, msg)
            except smtplib.SMTPSenderRefused, refused:
                if refused.smtp_code != 530:
                    raise
                yield inner.thread(self._try_to_authenticate, server)
                yield inner.thread(server.sendmail, from_addr, to_addr, msg)
        except smtplib.SMTPDataError, data_error:
            self.log.error("Could not send message to %r: %r. "+
                           "Dropping message from queue.",
                           to_addr, data_error)
            inner.finish(True)
        except smtplib.SMTPRecipientsRefused, refused:
            for recipient, reason in refused.recipients.iteritems():
                self.log.error("Could not send message to %r: %r. "+
                               "Dropping message from queue.",
                               recipient, reason)
            inner.finish(True)
        except self.TOLERATED_EXCEPTIONS, exc:
            self.log.error("Could not send message to %r: %r", to_addr, exc)
            self.server = None
            try:
                yield inner.thread(server.quit)
            except self.TOLERATED_EXCEPTIONS:
                pass
            inner.finish(False)

        self.log.info("Sent message to %r", to_addr)
        inner.finish(True)

    @threado.stream
    def report(inner, self, item):
        while True:
            result = yield inner.sub(self._try_to_send(item))
            if result:
                inner.finish(True)

            self.log.info("Retrying sending in 10 seconds")
            yield inner.sub(wait(10.0))

if __name__ == "__main__":
    MailerService.from_command_line().execute()
