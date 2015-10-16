from __future__ import absolute_import

import re
import ssl
import socket
import getpass
import imaplib
import email.parser
import email.header

import idiokit
from cStringIO import StringIO
from . import bot, utils


def get_header(headers, key, default=None):
    value = headers.get(key, None)
    if value is None:
        return default

    bites = []
    for string, encoding in email.header.decode_header(value):
        if encoding is not None:
            string = string.decode(encoding, "replace")
        bites.append(string)

    return u" ".join(bites)


_DEFAULT_PORT_IMAP4 = 143
_DEFAULT_PORT_IMAP4_SSL = 993


class _IMAP4(imaplib.IMAP4):
    def __init__(self, host, port, timeout=None):
        self._timeout = timeout

        imaplib.IMAP4.__init__(self, host, port)

    def open(self, host="", port=_DEFAULT_PORT_IMAP4):
        self.host = host
        self.port = port
        self.sock = socket.create_connection((host, port), timeout=self._timeout)
        self.file = self.sock.makefile("rb")


class _IMAP4_SSL(imaplib.IMAP4_SSL):
    def __init__(self, host, port, certfile=None, keyfile=None, timeout=None):
        self._timeout = timeout

        imaplib.IMAP4_SSL.__init__(self, host, port, certfile, keyfile)

    def open(self, host="", port=_DEFAULT_PORT_IMAP4_SSL):
        self.host = host
        self.port = port
        self.sock = socket.create_connection((host, port), timeout=self._timeout)
        self.sslobj = ssl.wrap_socket(self.sock, self.keyfile, self.certfile)
        self.file = self.sslobj.makefile("rb")


class IMAPBot(bot.FeedBot):
    poll_interval = bot.IntParam(default=300)
    filter = bot.Param(default="(UNSEEN)")

    mail_server = bot.Param("the mail server hostname")
    mail_port = bot.IntParam("""
        the mail server port (default: 993 for SSL connections,
        143 for plain text connections)
        """, default=None)
    mail_connection_timeout = bot.FloatParam("""
        the timeout for the mail server connection socket, in seconds
        (default: %default seconds)
        """, default=60.0)
    mail_user = bot.Param("""
        the username used for mail server authentication
        """)
    mail_password = bot.Param("""
        the password used for mail server authentication
        """, default=None)
    mail_box = bot.Param("""
        the polled mailbox (default: %default)
        """, default="INBOX")
    mail_disable_ssl = bot.BoolParam("""
        connect to the mail server using unencrypted plain
        text connections (default: use encrypted SSL connections)
        """)

    def __init__(self, **keys):
        bot.FeedBot.__init__(self, **keys)

        if self.mail_port is None:
            if self.mail_disable_ssl:
                self.mail_port = _DEFAULT_PORT_IMAP4
            else:
                self.mail_port = _DEFAULT_PORT_IMAP4_SSL

        if self.mail_password is None:
            self.mail_password = getpass.getpass("Mail password: ")
        self.queue = self.run_mailbox()

    def feed(self):
        return self.queue | self.noop() | self.poll()

    # Mailbox handling

    @idiokit.stream
    def run_mailbox(self, min_delay=5.0, max_delay=60.0):
        mailbox = None

        try:
            while True:
                item = yield idiokit.next()

                while True:
                    delay = min(min_delay, max_delay)
                    while mailbox is None:
                        try:
                            mailbox = yield idiokit.thread(self.connect)
                        except (imaplib.IMAP4.abort, socket.error) as error:
                            self.log.error("Failed IMAP connection ({0})".format(utils.format_exception(error)))
                        else:
                            break

                        self.log.info("Retrying connection in {0:.2f} seconds".format(delay))
                        yield idiokit.sleep(delay)
                        delay = min(2 * delay, max_delay)

                    event, name, args, keys = item
                    if event.result().unsafe_is_set():
                        break

                    try:
                        method = getattr(mailbox, name)
                        result = yield idiokit.thread(method, *args, **keys)
                    except (imaplib.IMAP4.abort, socket.error) as error:
                        yield idiokit.thread(self.disconnect, mailbox)
                        self.log.error("Lost IMAP connection ({0})".format(utils.format_exception(error)))
                        mailbox = None
                    except imaplib.IMAP4.error as error:
                        event.fail(type(error), error, None)
                        break
                    else:
                        event.succeed(result)
                        break
        finally:
            if mailbox is not None:
                yield idiokit.thread(self.disconnect, mailbox)

    def connect(self):
        self.log.info("Connecting to IMAP server {0!r} port {1}".format(
            self.mail_server, self.mail_port))

        if self.mail_disable_ssl:
            mail_class = _IMAP4
        else:
            mail_class = _IMAP4_SSL
        mailbox = mail_class(self.mail_server, self.mail_port, timeout=self.mail_connection_timeout)

        self.log.info("Logging in to IMAP server {0!r} port {1}".format(
            self.mail_server, self.mail_port))
        mailbox.login(self.mail_user, self.mail_password)
        try:
            status, msgs = mailbox.select(self.mail_box, readonly=False)

            if status != "OK":
                for msg in msgs:
                    raise imaplib.IMAP4.abort(msg)
        except:
            mailbox.logout()
            raise

        self.log.info("Logged in to IMAP server {0!r} port {1}".format(
            self.mail_server, self.mail_port))
        return mailbox

    def disconnect(self, mailbox):
        try:
            mailbox.close()
        except (imaplib.IMAP4.error, socket.error):
            pass

        try:
            mailbox.logout()
        except (imaplib.IMAP4.error, socket.error):
            pass

    def call(self, name, *args, **keys):
        event = idiokit.Event()
        self.queue.send(event, name, args, keys)
        return event

    # Keep-alive

    @idiokit.stream
    def noop(self, noop_interval=60.0):
        while True:
            yield self.call("noop")
            yield idiokit.sleep(noop_interval)

    # Main polling

    @idiokit.stream
    def poll(self):
        while True:
            yield self.fetch_mails(self.filter)
            yield idiokit.sleep(self.poll_interval)

    @idiokit.stream
    def get_header(self, uid, section):
        body_rex_str = r"\s*\d+\s+\(UID {0}\s+BODY\[{1}\]\s+".format(uid, section)
        body_rex = re.compile(body_rex_str, re.I)

        fetch = "(UID BODY.PEEK[{0}])".format(section)
        result, data = yield self.call("uid", "FETCH", uid, fetch)

        # Filter away parts that don't closely enough resemble tuple
        # ("<MSGNUM> (UID <MSGUID> BODY[<SECTION>] {<SIZE>}", "<HEADERS>")
        data = [x for x in data if isinstance(x, tuple) and len(x) >= 2]
        data = [x[1] for x in data if body_rex.match(x[0])]

        # Accept only non-empty header data
        data = [x for x in data if x]
        if not data:
            idiokit.stop()
        idiokit.stop(email.parser.Parser().parsestr(data[0], headersonly=True))

    def fetcher(self, uid, path):
        @idiokit.stream
        def fetch():
            fetch = "(BODY.PEEK[{0}])".format(path)
            result, data = yield self.call("uid", "FETCH", uid, fetch)

            for parts in data:
                if not isinstance(parts, tuple) or len(parts) != 2:
                    continue
                idiokit.stop(StringIO(parts[1]))
        return fetch

    @idiokit.stream
    def walk_mail(self, uid, path=(), headers=[]):
        if not path:
            header = yield self.get_header(uid, "HEADER")
            if header is None:
                return
            if header.get_content_maintype() != "multipart":
                yield idiokit.send("TEXT", tuple(headers + [header]))
                return
            headers = headers + [header]

        path = list(path) + [0]
        while True:
            path[-1] += 1
            path_str = ".".join(map(str, path))

            header = yield self.get_header(uid, path_str + ".MIME")
            if header is None:
                return

            if header.get_content_maintype() == "multipart":
                yield self.walk_mail(uid, path, headers + [header])
            else:
                yield idiokit.send(path_str, tuple(headers + [header]))

    @idiokit.stream
    def fetch_mails(self, filter):
        result, data = yield self.call("uid", "SEARCH", None, filter)
        if not data or not data[0]:
            return

        for uid in data[0].split():
            collected = []
            yield self.walk_mail(uid) | idiokit.map(collected.append)

            parts = list()
            for path, headers in collected:
                parts.append((headers, self.fetcher(uid, path)))

            if parts:
                top_header = parts[0][0][0]
                subject = get_header(top_header, "Subject", "<no subject>")
                sender = get_header(top_header, "From", "<unknown sender>")

                self.log.info("Handling mail {0!r} from {1!r}".format(subject, sender))
                yield self.handle(parts)
                self.log.info("Done with mail {0!r} from {1!r}".format(subject, sender))

            # UID STORE command flags have to be in parentheses, otherwise
            # imaplib quotes them, which is not allowed.
            yield self.call("uid", "STORE", uid, "+FLAGS", "(\\Seen)")

    @idiokit.stream
    def handle(self, parts):
        handle_default = getattr(self, "handle_default", None)

        for headers, fetch in parts:
            content_type = headers[-1].get_content_type()
            suffix = content_type.replace("-", "__").replace("/", "_")

            handler = getattr(self, "handle_" + suffix, handle_default)
            if handler is None:
                continue

            fileobj = yield fetch()
            skip_rest = yield handler(headers, fileobj)
            if skip_rest:
                return
