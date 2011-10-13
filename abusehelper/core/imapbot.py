import re
import socket
import getpass
import imaplib
import email.parser

import idiokit
from idiokit import threadpool, timer
from cStringIO import StringIO
from abusehelper.core import events, bot, services

@idiokit.stream
def collect():
    collection = list()
    try:
        while True:
            item = yield idiokit.next()
            collection.append(item)
    except StopIteration:
        idiokit.stop(collection)

class IMAPBot(bot.FeedBot):
    poll_interval = bot.IntParam(default=300)
    filter = bot.Param(default="(UNSEEN)")

    mail_server = bot.Param()
    mail_port = bot.IntParam(default=993)
    mail_user = bot.Param()
    mail_password = bot.Param(default=None)
    mail_box = bot.Param(default="INBOX")

    def __init__(self, **keys):
        bot.FeedBot.__init__(self, **keys)

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
                            mailbox = yield threadpool.thread(self.connect)
                        except (imaplib.IMAP4.abort, socket.error), error:
                            self.log.error("Failed IMAP connection: %r", error)
                        else:
                            break

                        self.log.info("Retrying connection in %.02f seconds", delay)
                        yield timer.sleep(delay)
                        delay = min(2 * delay, max_delay)

                    event, name, args, keys = item
                    if event.result().is_set():
                        break

                    try:
                        method = getattr(mailbox, name)
                        result = yield threadpool.thread(method, *args, **keys)
                    except (imaplib.IMAP4.abort, socket.error), error:
                        yield threadpool.thread(self.disconnect, mailbox)
                        self.log.error("Lost IMAP connection: %r", error)
                        mailbox = None
                    except imaplib.IMAP4.error, error:
                        event.fail(type(error), error, None)
                        break
                    else:
                        event.succeed(result)
                        break
        finally:
            if mailbox is not None:
                yield threadpool.thread(self.disconnect, mailbox)

    def connect(self):
        self.log.info("Connecting to IMAP server %r port %d",
                      self.mail_server, self.mail_port)
        mailbox = imaplib.IMAP4_SSL(self.mail_server, self.mail_port)

        self.log.info("Logging in to IMAP server %s port %d",
                      self.mail_server, self.mail_port)
        mailbox.login(self.mail_user, self.mail_password)
        try:
            status, msgs = mailbox.select(self.mail_box, readonly=False)

            if status != "OK":
                for msg in msgs:
                    raise imaplib.IMAP4.abort(msg)
        except:
            mailbox.logout()
            raise

        self.log.info("Logged in to IMAP server %s port %d",
                      self.mail_server, self.mail_port)
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
    def noop(self, noop_interval=10.0):
        while True:
            yield self.call("noop")
            yield timer.sleep(noop_interval)

    # Main polling

    @idiokit.stream
    def poll(self):
        while True:
            yield self.fetch_mails(self.filter)
            yield timer.sleep(self.poll_interval)

    @idiokit.stream
    def get_header(self, uid, section):
        body_rex_str = r"\s*\d+\s+\(UID %s\s+BODY\[%s\]\s+" % (uid, section)
        body_rex = re.compile(body_rex_str, re.I)

        fetch = "(UID BODY.PEEK[%s])" % section
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
            fetch = "(BODY.PEEK[%s])" % path
            result, data = yield self.call("uid", "FETCH", uid, fetch)

            for parts in data:
                if not isinstance(parts, tuple) or len(parts) != 2:
                    continue
                reader = StringIO(parts[1])
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
            collected = yield self.walk_mail(uid) | collect()

            parts = list()
            for path, headers in collected:
                parts.append((headers, self.fetcher(uid, path)))

            if parts:
                top_header = parts[0][0][0]
                subject = top_header["Subject"] or "<no subject>"
                sender = top_header["From"] or "<unknown sender>"
                self.log.info("Handling mail %r from %r", subject, sender)
                yield self.handle(parts)
                self.log.info("Done with mail %r from %r", subject, sender)

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
