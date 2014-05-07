import time
import heapq
import socket
import getpass
import smtplib
import collections

import idiokit
from abusehelper.core import events, taskfarm, services, templates, bot, utils


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


@idiokit.stream
def alert(*times):
    if not times:
        yield idiokit.Event()
        return

    while True:
        yield idiokit.sleep(min(map(next_time, times)))
        yield idiokit.send()


class _ReportBotState(object):
    def __init__(self, queue=[], version_and_args=(1, None)):
        self._queue = tuple(queue)

    def __iter__(self):
        return iter(self._queue)

    def __reduce__(self):
        return self.__class__, (self._queue, (1, None))


class ReportBot(bot.ServiceBot):
    REPORT_NOW = object()

    def __init__(self, *args, **keys):
        bot.ServiceBot.__init__(self, *args, **keys)

        self._rooms = taskfarm.TaskFarm(self._handle_room)
        self._queue = []
        self._current = None

    def queue(self, _delay, *args, **keys):
        expires = time.time() + _delay
        heapq.heappush(self._queue, (expires, args, keys))

    def requeue(self, _delay, *args_diff, **keys_diff):
        if self._current is None:
            raise RuntimeError("no current report")

        args, keys = self._current

        args = list(args)
        args[:len(args_diff)] = args_diff

        keys = dict(keys)
        keys.update(keys_diff)

        self.queue(_delay, *args, **keys)

    @idiokit.stream
    def _handle_room(self, name):
        msg = "room {0!r}".format(name)
        attrs = events.Event(type="room", service=self.bot_name, room=name)

        with self.log.stateful(repr(self.xmpp.jid), "room", repr(name)) as log:
            log.open("Joining " + msg, attrs, status="joining")
            room = yield self.xmpp.muc.join(name, self.bot_name)

            log.open("Joined " + msg, attrs, status="joined")
            try:
                yield idiokit.pipe(room, events.stanzas_to_events())
            finally:
                log.close("Left " + msg, attrs, status="left")

    @idiokit.stream
    def main(self, state):
        if isinstance(state, collections.deque):
            for item, keys in state:
                self.queue(0.0, item, **keys)
        elif state is not None:
            for delay, args, keys in state:
                self.queue(delay, *args, **keys)

        try:
            while True:
                now = time.time()
                if not self._queue or self._queue[0][0] > now:
                    yield idiokit.sleep(1.0)
                    continue

                _, args, keys = heapq.heappop(self._queue)
                self._current = args, keys
                try:
                    result = yield self.report(*args, **keys)
                finally:
                    self._current = None

                if not result and result is not None:
                    self.queue(60.0, *args, **keys)
        except services.Stop:
            if self._current is not None:
                args, keys = self._current
                self.queue(0.0, *args, **keys)

            now = time.time()
            dumped = [(max(x - now, 0.0), y, z) for (x, y, z) in self._queue]
            idiokit.stop(_ReportBotState(dumped))

    @idiokit.stream
    def session(self, state, src_room, **keys):
        keys["src_room"] = src_room

        def _alert(_):
            yield self.REPORT_NOW

        @idiokit.stream
        def _collect():
            while True:
                item = yield idiokit.next()
                self.queue(0.0, item, **keys)

        collector = idiokit.pipe(self.collect(state, **keys), _collect())
        idiokit.pipe(self.alert(**keys), idiokit.map(_alert), collector)
        result = yield idiokit.pipe(self._rooms.inc(src_room), collector)
        idiokit.stop(result)

    @idiokit.stream
    def alert(self, times, **keys):
        yield alert(*times)

    @idiokit.stream
    def collect(self, state, **keys):
        if state is None:
            state = utils.CompressedCollection()

        try:
            while True:
                event = yield idiokit.next()

                if event is self.REPORT_NOW:
                    yield idiokit.send(state)
                    state = utils.CompressedCollection()
                else:
                    state.append(event)
        except services.Stop:
            idiokit.stop(state)

    @idiokit.stream
    def report(self, collected):
        yield idiokit.sleep(0.0)


from email import message_from_string
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.charset import Charset, QP
from email.utils import formatdate, make_msgid, getaddresses, formataddr


class MailTemplate(templates.Template):
    def format(self, events, encoding="utf-8"):
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


class Mailer(object):
    TOLERATED_EXCEPTIONS = (socket.error, smtplib.SMTPException)

    def __init__(self, smtp_host, smtp_port=25, user=None, password=None, log=None):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.user = user
        self.password = password
        self.log = log

        if self.user and not self.password:
            self.password = getpass.getpass("SMTP password: ")

    @idiokit.stream
    def _connect(self):
        server = None

        while server is None:
            host, port = self.smtp_host, self.smtp_port
            if self.log:
                self.log.info("Connecting %r port %d", host, port)
            try:
                server = yield idiokit.thread(smtplib.SMTP, host, port)
            except self.TOLERATED_EXCEPTIONS as exc:
                if self.log:
                    self.log.error("Error connecting SMTP server: %r", exc)
            else:
                if self.log:
                    self.log.info("Connected to the SMTP server")
                break

            if self.log:
                self.log.info("Retrying SMTP connection in 10 seconds")
            yield idiokit.sleep(10.0)

        try:
            yield idiokit.thread(server.ehlo)

            if server.has_extn("starttls"):
                yield idiokit.thread(server.starttls)
                yield idiokit.thread(server.ehlo)

            if self.user is not None and self.password is not None and server.has_extn("auth"):
                yield idiokit.thread(server.login, self.user, self.password)
        except:
            self._disconnect(server)
            raise

        idiokit.stop(server)

    def _disconnect(self, server):
        yield idiokit.thread(server.quit)

    @idiokit.stream
    def send(self, from_addr, to_addrs, subject, msg):
        server = yield self._connect()
        try:
            if self.log:
                self.log.info("Sending message %r to %r", subject, to_addrs)
            yield idiokit.thread(server.sendmail, from_addr, to_addrs, msg)
        except smtplib.SMTPDataError as data_error:
            if self.log:
                self.log.error(
                    "Could not send message to %r: %r. " +
                    "Dropping message from queue.",
                    to_addrs, data_error)
            idiokit.stop(True)
        except smtplib.SMTPRecipientsRefused as refused:
            if self.log:
                for recipient, reason in refused.recipients.iteritems():
                    self.log.error(
                        "Could not send message to %r: %r. " +
                        "Dropping message from queue.",
                        recipient, reason)
            idiokit.stop(True)
        except self.TOLERATED_EXCEPTIONS as exc:
            if self.log:
                self.log.error("Could not send message to %r: %r", to_addrs, exc)
            idiokit.stop(False)
        finally:
            self._disconnect(server)

        if self.log:
            self.log.info("Sent message to %r", to_addrs)
        idiokit.stop(True)


def format_addresses(addrs):
    if isinstance(addrs, basestring):
        addrs = [addrs]
    # FIXME: Use encoding after getaddresses
    return ", ".join(map(formataddr, getaddresses(addrs)))


class MailerService(ReportBot):
    mail_sender = bot.Param(
        "from whom it looks like the mails came from")
    smtp_host = bot.Param(
        "hostname of the SMTP service used for sending mails")
    smtp_port = bot.IntParam(
        "port of the SMTP service used for sending mails",
        default=25)
    smtp_auth_user = bot.Param(
        "username for the authenticated SMTP service",
        default=None)
    smtp_auth_password = bot.Param(
        "password for the authenticated SMTP " +
        "service", default=None)
    max_retries = bot.IntParam(
        "how many times sending is retried before moving mail " +
        "to the end of the buffer", default=None)

    def __init__(self, **keys):
        ReportBot.__init__(self, **keys)

        self._mailer = Mailer(
            self.smtp_host,
            self.smtp_port,
            self.smtp_auth_user,
            self.smtp_auth_password,
            self.log)

    @idiokit.stream
    def session(self, state, **keys):
        # Try to build a mail for quick feedback that the templates etc. are
        # at least somewhat valid.
        yield self.build_mail(None, **keys)

        result = yield ReportBot.session(self, state, **keys)
        idiokit.stop(result)

    @idiokit.stream
    def build_mail(self, events, to=[], cc=[], template="", template_values={}, **keys):
        """
        Return a mail object produced based on collected events and session parameters.
        The "events" parameter is None when we just want to test building a mail.
        """
        if events is None:
            events = []

        csv = templates.CSVFormatter()
        template_keys = {
            "csv": csv,
            "attach_csv": templates.AttachUnicode(csv),
            "attach_and_embed_csv": templates.AttachAndEmbedUnicode(csv),
            "attach_zip": templates.AttachZip(csv),
            "to": templates.Const(format_addresses(to)),
            "cc": templates.Const(format_addresses(cc))
        }
        for key, value in dict(template_values).iteritems():
            template_keys[key] = templates.Const(value)

        mail_template = MailTemplate(template, **template_keys)
        msg = yield idiokit.thread(mail_template.format, events)
        idiokit.stop(msg)

    @idiokit.stream
    def report(self, events, to=[], cc=[], **keys):
        msg = yield self.build_mail(events, to=to, cc=cc, **keys)

        if "To" not in msg:
            msg["To"] = format_addresses(to)
        if "Cc" not in msg:
            msg["Cc"] = format_addresses(cc)

        # FIXME: Use encoding after getaddresses
        from_addr = getaddresses([self.mail_sender])[0]

        if "From" not in msg:
            msg["From"] = formataddr(from_addr)

        msg["Date"] = formatdate()
        msg["Message-ID"] = make_msgid()
        subject = msg.get("Subject", "")

        to_addrs = msg.get_all("To", list()) + msg.get_all("Cc", list())
        to_addrs = [addr for (name, addr) in getaddresses(to_addrs)]
        to_addrs = filter(None, [x.strip() for x in to_addrs])

        if not to_addrs:
            self.log.info("Skipped message %r (no recipients)", subject)
            idiokit.stop(True)

        if not events:
            self.log.info("Skipped message %r to %r (no events)", subject, to_addrs)
            idiokit.stop(True)

        # No need to keep both the mail object and mail data in memory.
        msg_data = msg.as_string()
        del msg

        retries = 0
        while True:
            result = yield self._mailer.send(from_addr[1], to_addrs, subject, msg_data)
            if result:
                break

            if self.max_retries is not None:
                retries += 1

                if retries > self.max_retries:
                    self.log.error("Sending mail failed")
                    idiokit.stop(False)

            self.log.info("Retrying sending in 10 seconds")
            yield idiokit.sleep(10.0)
        idiokit.stop(True)

if __name__ == "__main__":
    MailerService.from_command_line().execute()
