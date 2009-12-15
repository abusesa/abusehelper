import re
import csv
import time
import urllib2
import imaplib
import email.parser

from abusehelper.core import events, services, roomfarm
from idiokit import threado, util, timer

@threado.stream
def fetch_content(inner, mailbox, filter, url_rex, filename_rex):
    mailbox.noop()

    result, data = mailbox.search(None, filter)
    if not data or not data[0]:
        return

    for num in data[0].split():
        for path, content_type in find_payload(mailbox, num):
            if content_type != "text/plain":
                continue
            fetch = "(BODY.PEEK[%s]<0.2048>)" % path
            result, data = mailbox.fetch(num, fetch)

            for parts in data:
                for part in parts:
                    matches = re.findall(url_rex, part)
                    for match in matches:
                        yield inner.sub(fetch_url(match, filename_rex))
        mailbox.store(num, "+FLAGS", "\\Seen")

def find_payload(mailbox, num, path=()):
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
        disposition = header.get_params((), "content-disposition")
        if ("attachment", "") in disposition:
            continue

        if header.is_multipart():
            for result in find_payload(num, path):
                yield result
        else:
            yield path_str, header.get_content_type()

@threado.stream
def fetch_url(inner, url, filename_rex):
    print "Fetching url", url
    opened = urllib2.urlopen(url)

    try:
        info = str(opened.info())
        header = email.parser.Parser().parsestr(info, headersonly=True)

        filename = header.get_filename(None)
        groupdict = dict()
        if filename is not None:
            match = filename_rex.match(filename)
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
            yield inner.send(event)
    finally:
        yield
        opened.close()

class ImapbotService(roomfarm.RoomFarm):
    def __init__(self, xmpp, mail_server, mail_user, mail_password, 
                 state_file=None, filter=None, url_rex=None, 
                 filename_rex=None):

        if not filter:
            filter = '(FROM "eventfeed.com" BODY "http://" UNSEEN)'
        if not url_rex:
            url_rex = r"http://\S+"
        if not filename_rex:
            filename_rex = r"(?P<eventfile>.*)"

        roomfarm.RoomFarm.__init__(self, state_file)

        self.xmpp = xmpp
        self.dsts = roomfarm.Counter()

        self.mailbox = imaplib.IMAP4_SSL(mail_server, 993)
        self.mailbox.login(mail_user, mail_password)
        self.mailbox.select('INBOX', readonly=False)

        self.filter = filter
        self.url_rex = re.compile(url_rex)
        self.filename_rex = re.compile(filename_rex)

        self.poll_frequency = 300.0
        self.expire_time = float()

    @threado.stream
    def handle_room(inner, self, name):
        print "Joining room", repr(name)
        room = yield inner.sub(self.xmpp.muc.join(name))
        print "Joined room", repr(name)

        try:
            yield inner.sub(events.events_to_elements()
                            | room
                            | threado.throws())
        finally:
            print "Left room", repr(name)

    @threado.stream_fast
    def distribute(inner, self):
        while True:
            yield inner

            rooms = self.dsts.get("room")
            for event in inner:
                for room in rooms:
                    room.send(event)

    def run(self):
        while True:
            current_time = time.time()
            if self.expire_time > current_time:
                yield self.inner, timer.sleep(self.expire_time-current_time)
            else:
                yield self.inner.sub(fetch_content(self.mailbox, self.filter, 
                                               self.url_rex, self.filename_rex)
                                     | self.distribute())

                self.expire_time = time.time() + self.poll_frequency

    @threado.stream
    def session(inner, self, state, room):
        room = self.rooms(inner, room)
        self.dsts.inc("room", room)
        try:
            while True:
                yield inner
        except services.Stop:
            inner.finish()
        finally:
            self.dsts.dec("room", room)
            self.rooms(inner)

def main(name, xmpp_jid, service_room, mail_server, mail_user,
         xmpp_password=None, mail_password=None, filter=None, url_rex=None,
         filename_rex=None, log_file=None):

    import getpass
    from idiokit.xmpp import connect
    from abusehelper.core import log

    if not xmpp_password:
        xmpp_password = getpass.getpass("XMPP password: ")
        mail_password = xmpp_password

    logger = log.config_logger(name, filename=log_file)

    @threado.stream
    def bot(inner):
        print "Connecting XMPP server with JID", xmpp_jid
        xmpp = yield connect(xmpp_jid, xmpp_password)
        xmpp.core.presence()

        print "Joining lobby", service_room
        lobby = yield services.join_lobby(xmpp, service_room, name)
        logger.addHandler(log.RoomHandler(lobby.room))

        service = ImapbotService(xmpp, mail_server, mail_user, mail_password,
                                 filter, url_rex, filename_rex)

        yield inner.sub(lobby.offer(name, service))
    return bot()

main.service_room_help = "the room where the services are collected"
main.xmpp_jid_help = "the XMPP JID (e.g. xmppuser@xmpp.example.com)"
main.mail_server_help = "the mail server where the mail account is"
main.mail_user_help = "the mail account user"
main.mail_password_help = "the password for the mail account"
main.filter_help = "the filter for the imap mail"
main.url_rex_help = "regexp for the urls"
main.filename_rex_help = "regexp for the filenames"
main.xmpp_password_help = "the XMPP password"
main.log_file_help = "log to the given file instead of the console"

if __name__ == "__main__":
    from abusehelper.core import opts
    threado.run(opts.optparse(main), throw_on_signal=services.Stop())

