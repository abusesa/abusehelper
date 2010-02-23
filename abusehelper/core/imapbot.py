import re
import getpass
import imaplib
import email.parser

from cStringIO import StringIO
from abusehelper.core import events, bot, services
from idiokit import threado, timer

def get_header(mailbox, num, section):
    body_rex_str = r"\s*%s\s+\(BODY\[%s\]\s+" % (num, section)
    body_rex = re.compile(body_rex_str, re.I)
    
    fetch = "(BODY.PEEK[%s])" % section
    result, data = mailbox.fetch(num, fetch)

    # Filter away parts that don't closely enough resemble tuple
    # ("<MSGNUM> (BODY[<MSGPATH>.MIME] {<SIZE>}", "<MIMEHEADERS>")
    data = [x for x in data if isinstance(x, tuple) and len(x) >= 2]
    data = [x[1] for x in data if body_rex.match(x[0])]
    if not data:
        return None

    return email.parser.Parser().parsestr(data[0], headersonly=True)

def walk_mail(mailbox, num, path=(), headers=[]):
    if not path:
        header = get_header(mailbox, num, "HEADER")
        if header is None:
            return
        headers = headers + [header]

    path = list(path) + [0]
    while True:
        path[-1] += 1
        path_str = ".".join(map(str, path))        

        header = get_header(mailbox, num, path_str + ".MIME")
        if header is None:
            return

        if header.get_content_maintype() == "multipart":
            for result in walk_mail(mailbox, num, path, headers + [header]):
                yield result
        else:
            yield path_str, tuple(headers + [header])

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

    @threado.stream
    def feed(inner, self):
        self.log.info("Connecting to IMAP server %r port %d",
                      self.mail_server, self.mail_port)
        mailbox = yield inner.thread(imaplib.IMAP4_SSL,
                                     self.mail_server,
                                     self.mail_port)

        self.log.info("Logging in to IMAP server %s port %d",
                      self.mail_server, self.mail_port)
        try:
            yield inner.thread(mailbox.login, 
                               self.mail_user, 
                               self.mail_password)

            status, msgs = yield inner.thread(mailbox.select,
                                              self.mail_box,
                                              readonly=False)
            if status != "OK":
                for msg in msgs:
                    self.log.critical(msg)
                return
            self.log.info("Logged in to IMAP server %s port %d",
                          self.mail_server, self.mail_port)
                
            try:
                while True:
                    yield inner.sub(self.fetch_content(mailbox, self.filter))
                    yield inner, timer.sleep(self.poll_interval)
            finally:
                yield inner.thread(mailbox.close)
        finally:
            yield inner.thread(mailbox.logout)

    def _fetch(self, mailbox, num, path):
        @threado.stream
        def fetch(inner):
            list(inner)
            fetch = "(BODY.PEEK[%s])" % path
            result, data = yield inner.thread(mailbox.fetch, num, fetch)
            list(inner)
            
            for parts in data:
                if not isinstance(parts, tuple) or len(parts) != 2:
                    continue
                reader = StringIO(parts[1])
                inner.finish(StringIO(parts[1]))
        return fetch

    @threado.stream
    def fetch_content(inner, self, mailbox, filter):
        yield inner.thread(mailbox.noop)

        result, data = yield inner.thread(mailbox.search, None, filter)
        if not data or not data[0]:
            return

        for num in data[0].split():
            parts = list()
            for path, headers in walk_mail(mailbox, num):
                parts.append((headers, self._fetch(mailbox, num, path)))

            if parts:
                headers, _ = parts[0]
                top_header = headers[0]
                subject = top_header["Subject"] or "<no subject>"
                sender = top_header["From"] or "<unknown sender>"
                self.log.info("Handling mail %r from %r", subject, sender)
                yield inner.sub(self.handle(parts))
            mailbox.store(num, "+FLAGS", "\\Seen")

    @threado.stream
    def handle(inner, self, parts):
        handle_default = getattr(self, "handle_default", None)

        for headers, fetch in parts:
            content_type = headers[-1].get_content_type()
            suffix = content_type.replace("-", "__").replace("/", "_")

            handler = getattr(self, "handle_" + suffix, handle_default)
            if handler is None:
                continue

            list(inner)
            fileobj = yield inner.sub(fetch())
            list(inner)
            skip_rest = yield inner.sub(handler(headers, fileobj))
            if skip_rest:
                return
        list(inner)

import base64
import zipfile
from cStringIO import StringIO
from abusehelper.core import utils

class IMAPService(IMAPBot):
    filter = bot.Param(default=r'(BODY "http://" UNSEEN)')
    url_rex = bot.Param(default=r"http://\S+")
    filename_rex = bot.Param(default=r"(?P<eventfile>.*)")

    @threado.stream
    def normalize(inner, self, groupdict):
        while True:
            event = yield inner

            for key in event.keys():
                event.discard(key, "")
                event.discard(key, "-")

            for key, value in groupdict.items():
                if None in (key, value):
                    continue
                event.add(key, value)

            inner.send(event)

    @threado.stream
    def parse_csv(inner, self, filename, fileobj):
        match = re.match(self.filename_rex, filename)
        if match is None:
            self.log.error("Filename %r did not match", filename)
            inner.finish(False)

        yield inner.sub(utils.csv_to_events(fileobj)
                        | self.normalize(match.groupdict()))
        inner.finish(True)
        
    def handle(self, parts):
        attachments = list()
        texts = list()

        for headers, data in parts:
            content_type = headers[-1].get_content_type()
            if headers[-1].get_filename(None) is None:
                if content_type == "text/plain":
                    texts.append((headers, data))
            elif content_type in ["text/plain", "application/zip"]:
                attachments.append((headers, data))

        return IMAPBot.handle(self, attachments + texts)

    @threado.stream
    def handle_text_plain(inner, self, headers, fileobj):
        filename = headers[-1].get_filename(None)
        if filename is not None:
            self.log.info("Parsing CSV data from an attachment")
            result = yield inner.sub(self.parse_csv(filename, fileobj))
            inner.finish(result)

        for match in re.findall(self.url_rex, fileobj.read()):
            self.log.info("Fetching URL %r", match)
            try:
                info, fileobj = yield inner.sub(utils.fetch_url(match))
            except utils.FetchUrlFailed, fail:
                self.log.error("Fetching URL %r failed: %r", match, fail)
                return

            filename = info.get_filename(None)
            if filename is None:
                self.log.error("No filename given for the data")
                continue
            
            self.log.info("Parsing CSV data from the URL")
            result = yield inner.sub(self.parse_csv(filename, fileobj))
            inner.finish(result)

    @threado.stream
    def handle_application_zip(inner, self, headers, fileobj):
        self.log.info("Opening a ZIP attachment")
        try:
            data = base64.b64decode(fileobj.read())
        except TypeError, error:
            self.log.error("Base64 decoding failed: %s", error)
            return

        temp = StringIO(data)
        try:
            zip = zipfile.ZipFile(temp)
        except zipfile.BadZipfile, error:
            self.log.error("ZIP handling failed: %s", error)
            return

        for filename in zip.namelist():
            csv_data = StringIO(zip.read(filename))
            
            self.log.info("Parsing CSV data from the ZIP attachment")
            result = yield inner.sub(self.parse_csv(filename, csv_data))
            inner.finish(result)

if __name__ == "__main__":
    IMAPService.from_command_line().execute()
