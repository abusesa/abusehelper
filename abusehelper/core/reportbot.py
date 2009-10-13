import time
import csv
import copy
from cStringIO import StringIO

from abusehelper.core import events
from idiokit.core import XMPPError
from idiokit.xmpp import XMPP, Element
from idiokit import threado

class Mailer(object):
    def __init__(self, host, port, username, password, 
                 from_addr, to_addr, subject):
        self.keys = list()
        self.rows = list()

        self.host = host
        self.port = port

        self.from_addr = from_addr
        self.to_addr = to_addr
        self.subject = subject

        self.username = username
        self.password = password

    def add(self, event):
        attrs = copy.deepcopy(event.attrs)
        row = list()

        for key in self.keys:
            values = attrs.get(key, None)
            if values:
                row.append(values.pop())

        for key, values in attrs.items():
            for value in values:
                self.keys.append(key)
                row.append(value)

        self.rows.append(tuple(row))

    def report(self):
        if not self.rows:
            return

        string = StringIO()
        encoder = lambda x: x.encode("utf-8")

        writer = csv.writer(string)
        writer.writerow(map(encoder, self.keys))
        for row in self.rows:
            row += ("",) * (len(self.keys)-len(row))
            writer.writerow(map(encoder, row))

        data = string.getvalue()
        self.mail(data)

        self.keys = list()
        self.rows = list()
        
    def mail(self, data):
        import smtplib
        from email.mime.text import MIMEText
        from email.Charset import Charset, QP
        from email.Utils import formatdate, make_msgid, getaddresses

        msg = MIMEText(data, "plain", "utf-8")
        msg["from"] = self.from_addr
        msg["to"] = self.to_addr
        msg["subject"] = self.subject

        server = smtplib.SMTP(self.host, self.port)
        server.ehlo()
        server.starttls()
        server.login(self.username, self.password)
        server.sendmail(self.from_addr, self.to_addr, msg.as_string())
        server.quit()

@threado.thread
def reporter(inner, reporter, base_time, interval):
    while True:
        delay = interval - (time.time() - base_time) % interval
        try:
            event = inner.next(delay)
        except threado.Timeout:
            reporter.report()
        else:
            reporter.add(event)

def main():
    xmpp = XMPP("user@example.com", "password")
    xmpp.connect()
    
    room = xmpp.muc.join("room@conference.example.com", "reportbot")

    mailer = Mailer("mail.example.com", 25, "mailuser", "mailpassword",
                    "sender@example.com", "receiver@example.com",
                    "AbuseHelper periodical example report")
    mail_base_time = 0.0
    mail_interval = 15 * 60.0

    pipeline = (room
                | events.stanzas_to_events()
                | reporter(mailer, mail_base_time, mail_interval))
    for _ in pipeline:
        pass

if __name__ == "__main__":
    main()
