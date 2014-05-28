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
                except:
                    self.queue(0.0, *args, **keys)
                    raise
                else:
                    self._current = None

                if not result and result is not None:
                    self.queue(60.0, *args, **keys)
        except services.Stop:
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
from email.header import decode_header
from email.utils import getaddresses, formataddr


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


def format_addresses(addrs):
    if isinstance(addrs, basestring):
        addrs = [addrs]
    # FIXME: Use encoding after getaddresses
    return ", ".join(map(formataddr, getaddresses(addrs)))


def join_addresses(addrs):
    if not addrs:
        return u""
    if len(addrs) == 1:
        return addrs[0]
    return u", ".join(addrs[:-1]) + u" and " + addrs[-1]


def decode_subject(subject):
    pieces = []

    for piece, charset in decode_header(subject):
        if charset is None:
            charset = "ascii"
        pieces.append(piece.decode(charset, "replace"))

    return "".join(pieces)


class MailerService(ReportBot):
    mail_sender = bot.Param("""
        from whom it looks like the mails came from
        """)
    mail_receiver_override = bot.ListParam("""
        override the mail recipient list, sending all mails
        to these given address(es) instead of the original recipients
        """, default=None)
    smtp_host = bot.Param("""
        hostname of the SMTP service used for sending mails
        """)
    smtp_port = bot.IntParam("""
        port of the SMTP service used for sending mails
        """, default=25)
    smtp_auth_user = bot.Param("""
        username for the authenticated SMTP service
        """, default=None)
    smtp_auth_password = bot.Param("""
        password for the authenticated SMTP service
        """, default=None)
    max_retries = bot.IntParam("""
        how many times sending is retried before dropping mail
        from the send queue
        """, default=0)

    def __init__(self, **keys):
        ReportBot.__init__(self, **keys)

        if self.smtp_auth_user and not self.smtp_auth_password:
            self.smtp_auth_password = getpass.getpass("SMTP password: ")

    @idiokit.stream
    def _connect(self, host, port, retry_interval=60.0):
        server = None

        while server is None:
            self.log.info(u"Connecting to SMTP server {0!r} port {1}".format(host, port))
            try:
                server = yield idiokit.thread(smtplib.SMTP, host, port)
            except (socket.error, smtplib.SMTPException) as exc:
                self.log.error(u"Failed connecting to SMTP server: {0!r}".format(exc))
            else:
                self.log.info(u"Connected to the SMTP server")
                break

            self.log.info(u"Retrying SMTP connection in {0:.2f} seconds".format(retry_interval))
            yield idiokit.sleep(retry_interval)

        idiokit.stop(server)

    @idiokit.stream
    def _login(self, server, user, password):
        yield idiokit.thread(server.ehlo)

        if server.has_extn("starttls"):
            yield idiokit.thread(server.starttls)
            yield idiokit.thread(server.ehlo)

        if user is not None and password is not None and server.has_extn("auth"):
            yield idiokit.thread(server.login, user, password)

    @idiokit.stream
    def session(self, state, **keys):
        # Try to build a mail for quick feedback that the templates etc. are
        # at least somewhat valid.
        try:
            yield self.build_mail(None, **keys)
        except templates.TemplateError as te:
            self.log.error(u"Mail template was not valid ({0}), pausing session".format(te))
            try:
                yield idiokit.consume()
            except services.Stop:
                idiokit.stop(state)

        result = yield ReportBot.session(self, state, **keys)
        idiokit.stop(result)

    @idiokit.stream
    def build_mail(self, events, to=[], cc=[], bcc=[], template="", template_values={}, **keys):
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
            "cc": templates.Const(format_addresses(cc)),
            "bcc": templates.Const(format_addresses(bcc))
        }
        for key, value in dict(template_values).iteritems():
            template_keys[key] = templates.Const(value)

        mail_template = MailTemplate(template, **template_keys)
        msg = yield idiokit.thread(mail_template.format, events)
        idiokit.stop(msg)

    @idiokit.stream
    def report(self, eventlist, retries=None, to=[], cc=[], bcc=[], **keys):
        if retries is None:
            retries = self.max_retries
        msg = yield self.build_mail(eventlist, to=to, cc=cc, bcc=bcc, **keys)

        if "to" not in msg:
            msg["to"] = format_addresses(to)
        if "cc" not in msg:
            msg["cc"] = format_addresses(cc)
        if "bcc" not in msg:
            msg["bcc"] = format_addresses(bcc)

        # FIXME: Use encoding after getaddresses
        from_addr = getaddresses([self.mail_sender])[0]
        if "from" not in msg:
            msg["from"] = formataddr(from_addr)

        subject = decode_subject(msg.get("subject", ""))

        if self.mail_receiver_override is not None:
            to_addrs = list(self.mail_receiver_override)
        else:
            to_addrs = msg.get_all("to", []) + msg.get_all("cc", []) + msg.get_all("bcc", [])
        to_addrs = [addr for (name, addr) in getaddresses(to_addrs)]
        to_addrs = filter(None, [x.strip() for x in to_addrs])

        # No need to keep both the mail object and mail data in memory.
        msg_data = msg.as_string()
        del msg

        event = events.Event({
            "type": "mail",
            "subject": subject,
            "to": to,
            "cc": cc,
            "bcc": bcc,
            "sender": from_addr[1],
            "receiver": to_addrs,
            "event count": unicode(len(eventlist))
        })

        if not to_addrs:
            self.log.info(u"Skipped message \"{0}\" (no recipients)".format(subject),
                event=event.union(status="skipped (no recipients)"))
        elif not eventlist:
            self.log.info(u"Skipped message \"{0}\" to {1} (no events)".format(subject, join_addresses(to_addrs)),
                event=event.union(status="skipped (no events)"))
        else:
            server = yield self._connect(self.smtp_host, self.smtp_port)
            try:
                yield self._login(server, self.smtp_auth_user, self.smtp_auth_password)

                self.log.info(u"Sending message \"{0}\" to {1}".format(subject, join_addresses(to_addrs)))
                try:
                    yield idiokit.thread(server.sendmail, from_addr[1], to_addrs, msg_data)
                except smtplib.SMTPDataError as data_error:
                    self.log.error(u"Could not send message to {0}: {1!r}. Dropping message from queue".format(
                        join_addresses(to_addrs), data_error))
                except smtplib.SMTPRecipientsRefused as refused:
                    for recipient, reason in refused.recipients.iteritems():
                        self.log.error(u"Could not send message to {0}: {1!r}. Dropping message from queue".format(
                            join_addresses(to_addrs), reason))
                except (socket.error, smtplib.SMTPException) as exc:
                    self.log.error(u"Could not send message to {0}: {1!r}".format(join_addresses(to_addrs), exc))
                    if retries >= 1:
                        self.log.info(u"Retrying sending in 60 seconds")
                        self.requeue(60.0, retries=retries-1)
                    else:
                        self.log.error(u"Failed all retries, dropping the mail from the queue")
                else:
                    self.log.info(u"Sent message \"{0}\" to {1}".format(subject, join_addresses(to_addrs)),
                        event=event.union(status="sent"))
            finally:
                yield idiokit.thread(server.quit)


if __name__ == "__main__":
    MailerService.from_command_line().execute()
