import re
import csv
import sys
import imaplib
import email.parser

from abusehelper.core import utils, events, services, roomfarm
from idiokit import threado, timer

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
                        print "Downloading URL", match
                        try:
                            info, csv_data = yield inner.sub(utils.fetch_url(match))
                        except utils.FetchUrlFailed, fuf:
                            print >> sys.stderr, "Could not fetch URL %s:" % match, fuf
                            return

                        print "Parsing data from URL", match
                        yield inner.sub(parse_csv(info, csv_data, filename_rex))
                        print "Done with URL", match
                        
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
def parse_csv(inner, info, csv_data, filename_rex):
    groupdict = dict()

    charset = info.get_param("charset")
    if charset is None:
        print >> sys.stderr, "No character set given for the data"
        return

    filename = info.get_filename(None)
    if filename is None:
        print >> sys.stderr, "No filename given for the data"
        return

    match = filename_rex.match(filename)
    if match is None:
        print >> sys.stderr, "Filename did not match"
        return

    groupdict = match.groupdict()
    for row in csv.DictReader(csv_data.splitlines()):
        list(inner)
        yield

        event = events.Event()
        for key, value in groupdict.items():
            if None in (key, value):
                continue
            event.add(key, value)

        for key, value in row.items():
            if None in (key, value):
                continue
            key = key.decode(charset).lower().strip()
            value = value.decode(charset).strip()
            if not value or value == "-":
                continue
            event.add(key, value)

        inner.send(event)

class ImapbotService(roomfarm.RoomFarm):
    def __init__(self, xmpp, mail_server, mail_user, mail_password, 
                 filter=None, url_rex=None, 
                 filename_rex=None, poll_interval=60.0,
                 state_file=None):

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

        self.poll_interval = poll_interval
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
        try:
            while True:
                yield self.inner, timer.sleep(self.poll_interval)
                yield self.inner.sub(fetch_content(self.mailbox, self.filter, 
                                                   self.url_rex, 
                                                   self.filename_rex)
                                     | self.distribute())
        except services.Stop:
            self.inner.finish()

    @threado.stream
    def session(inner, self, state, room, **keys):
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
         poll_interval=60.0,
         xmpp_password=None, mail_password=None, state_file=None,
         filter=None, url_rex=None, filename_rex=None, log_file=None):

    import getpass
    from idiokit.xmpp import connect
    from abusehelper.core import log

    if not xmpp_password:
        xmpp_password = getpass.getpass("XMPP password: ")

    if not mail_password:
        mail_password = getpass.getpass("Mail password: ")

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
                                 filter, url_rex, filename_rex, poll_interval,
                                 state_file)

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

