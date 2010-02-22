import re
import getpass
import imaplib
import email.parser

from cStringIO import StringIO
from abusehelper.core import events, bot, services
from idiokit import threado, timer, util

def walk_mail(mailbox, num, path=(), headers=[]):
    path = list(path) + [0]

    while True:
        path[-1] += 1
        path_str = ".".join(map(str, path))

        body_rex_str = r"\s*%s\s+\(BODY\[%s.MIME\]\s+" % (num, path_str)
        body_rex = re.compile(body_rex_str, re.I)

        fetch = "(BODY.PEEK[%s.MIME])" % path_str
        result, data = mailbox.fetch(num, fetch)

        # Filter away parts that don't closely enough resemble tuple
        # ("<MSGNUM> (BODY[<MSGPATH>.MIME] {<SIZE>}", "<MIMEHEADERS>")
        data = [x for x in data if isinstance(x, tuple) and len(x) >= 2]
        data = [x[1] for x in data if body_rex.match(x[0])]
        if not data:
            return

        header = email.parser.Parser().parsestr(data[0], headersonly=True)
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

    @threado.stream
    def fetch_content(inner, self, mailbox, filter):
        yield inner.thread(mailbox.noop)

        result, data = yield inner.thread(mailbox.search, None, filter)
        if not data or not data[0]:
            return

        for num in data[0].split():
            for path, headers in walk_mail(mailbox, num):
                main = headers[-1].get_content_maintype().replace("-", "__")
                sub = headers[-1].get_content_subtype().replace("-", "__")
        
                handler_name = "handle_" + main + "_" + sub
                handler = getattr(self, handler_name, self.handle_default)
                if handler is None:
                    continue

                fetch = "(BODY.PEEK[%s])" % path
                result, data = yield inner.thread(mailbox.fetch, num, fetch)
                list(inner)

                skip_rest = False
                for parts in data:
                    if not isinstance(parts, tuple) or len(parts) != 2:
                        continue
                    reader = StringIO(parts[1])
                    skip_rest = yield inner.sub(handler(headers, reader))
                    list(inner)
                    break
                if skip_rest:
                    break

            mailbox.store(num, "+FLAGS", "\\Seen")

    handle_default = None

import base64
import zipfile
from cStringIO import StringIO
from abusehelper.core import utils

class IMAPService(IMAPBot):
    filter = bot.Param(default=r'(BODY "http://" UNSEEN)')
    url_rex = bot.Param(default=r"http://\S+")
    filename_rex = bot.Param(default=r"(?P<eventfile>.*)")
    from_url = bot.BoolParam()

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

    @threado.stream
    def handle_text_plain(inner, self, headers, fileobj):
        if self.from_url:
            for match in re.findall(self.url_rex, fileobj.read()):
                self.log.info("Fetching URL %r", match)
                try:
                    info, fileobj = yield inner.sub(utils.fetch_url(match))
                except utils.FetchUrlFailed, fail:
                    self.log.error("Fetching URL %r failed: %s", match, fail)
                    return

                filename = info.get_filename(None)
                if filename is None:
                    self.log.error("No filename given for the data")
                    inner.finish(False)

                self.log.info("Parsing CSV data from the URL")
                skip_rest = yield inner.sub(self.parse_csv(filename, fileobj))
                inner.finish(skip_rest)
        else:
            filename = headers[-1].get_filename(None)
            if filename is not None:
                self.log.info("Parsing CSV data from an attachment")
                skip_rest = yield inner.sub(self.parse_csv(filename, fileobj))
                inner.finish(skip_rest)                

    @threado.stream
    def handle_application_zip(inner, self, headers, fileobj):
        if self.from_url:
            return

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
            skip_rest = yield inner.sub(self.parse_csv(filename, csv_data))
            if skip_rest:
                inner.finish(skip_rest)

if __name__ == "__main__":
    IMAPService.from_command_line().execute()
