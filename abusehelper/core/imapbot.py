import re
import csv
import urllib2
import imaplib
import email.parser
from abusehelper.core import events
from idiokit import threado, util

class IMAP(threado.ThreadedStream):
    def __init__(self, server, user, password, imapfilter, 
                 url_rex="http://\S+", filename_rex=".*"):
        threado.ThreadedStream.__init__(self)

        self.mailbox = imaplib.IMAP4_SSL(server)
        self.mailbox.login(user, password)
        self.mailbox.select('INBOX', readonly=False)

        self.filter = imapfilter
        self.url_rex = re.compile(url_rex)
        self.filename_rex = re.compile(filename_rex)

        self.email_parser = email.parser.Parser()
        self.poll_frequency = 1.0

        self.start()

    def fetch_url(self, url):
        opened = urllib2.urlopen(url)

        try:
            info = str(opened.info())
            header = self.email_parser.parsestr(info, headersonly=True)

            filename = header.get_filename(None)
            groupdict = dict()
            if filename is not None:
                match = self.filename_rex.match(filename)
                if match is not None:
                    groupdict = match.groupdict()

            reader = csv.DictReader(opened)
            for row in reader:
                event = events.Event()

                for key, value in groupdict.items():
                    if None in (key, value):
                        continue
                    event.add(key, value)

                for key, value in row.items():
                    if None in (key, value):
                        continue
                    key = util.guess_encoding(key).lower().strip()
                    value = util.guess_encoding(value).strip()
                    if not value or value == "-":
                        continue
                    event.add(key, value)

                self.inner.send(event)
        finally:
            opened.close()
            
    def find_payload(self, num, path=()):
        path = list(path) + [0]
        while True:
            path[-1] += 1
            path_str = ".".join(map(str, path))
            fetch = "(BODY.PEEK[%s.MIME])" % path_str

            result, data = self.mailbox.fetch(num, fetch)
            if not data or not isinstance(data[0], tuple) or len(data[0]) < 2:
                return

            header = self.email_parser.parsestr(data[0][1], headersonly=True)
            disposition = header.get_params(list(), "content-disposition")
            if ("attachment", "") in disposition:
                continue

            if header.is_multipart():
                for result in self.find_payload(num, path):
                    yield result
            else:
                yield path_str, header.get_content_type()

    def poll(self):
        self.mailbox.noop()

        result, data = self.mailbox.search(None, self.filter)
        if not data:
            return

        for num in data[0].split():
            for path, content_type in self.find_payload(num):
                if content_type != "text/plain":
                    continue
                fetch = "(BODY.PEEK[%s]<0.2048>)" % path
                result, data = self.mailbox.fetch(num, fetch)

                for parts in data:
                    for part in parts:
                        matches = re.findall(self.url_rex, part)
                        for match in matches:
                            self.fetch_url(match)
            self.mailbox.store(num, "+FLAGS", "\\Seen")

    def run(self):
        while True:
            try:
                item = self.inner.next(self.poll_frequency)
            except threado.Timeout:
                pass
            self.poll()

def main():
    from idiokit.xmpp import XMPP

    imap = IMAP("mail.example.com", "mailuser", "mailpassword",
                '(FROM "eventfeed.com" BODY "http://" UNSEEN)',
                url_rex=r"http://\S+", filename_rex=r"(?P<eventfile>.*)")
    xmpp = XMPP("user@example.com", "password")
    xmpp.connect()

    room = xmpp.muc.join("room@conference.example.com", "imapbot")
    for _ in imap | events.events_to_elements() | room | threado.throws():
        pass

if __name__ == "__main__":
    main()
