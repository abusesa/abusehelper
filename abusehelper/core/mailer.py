# -*- coding: utf-8 -*-

import csv
import copy
import time
import collections
from cStringIO import StringIO

from idiokit import threado, timer
from abusehelper.core import events, roomfarm, services

# Some XML output helpers
def node_id_and_text(doc, parent, nodename, text='', **kw):
    node = doc.createElement(nodename)
    for key, value in kw.items():
        node.setAttribute(key, value)
    parent.appendChild(node)

    if text:
        text = doc.createTextNode(text)
        node.appendChild(text)

    return node

def xml_report(rows):
    """
    Make a IODEF XML output string out of the normalised rows given

    Produces valid IODEF with regards to:
    http://xml.coverpages.org/draft-ietf-inch-iodef-14.txt
    """
    from xml.dom.minidom import Document, DocumentType, getDOMImplementation

    # First, make the header
    impl = getDOMImplementation()
    doc = impl.createDocument(None, 'IODEF-Document', None)
    top = doc.documentElement
    top.setAttribute('lang', 'en')
    top.setAttribute('version', "1.00")
    top.setAttribute('xmlns', "urn:ietf:params:xml:ns:iodef-1.0")
    top.setAttribute('xmlns:xsi', 
                     "http://www.w3.org/2001/XMLSchema-instance")
    top.setAttribute('xsi:schemaLocation',
                     "https://www.cert.fi/autoreporter/IODEF-Document.xsd")

    def ts_to_xml(ts):
        return ts.replace(' ', 'T') + '+00:00'

    for row in rows:
        asn, ip, timestamp, ptr, cc, inc_type, ticket_nro, info = row

        irt_name, irt_email, irt_phone, irt_url = '', '', '', ''
        # May be defined per feed?
        impact = 'unknown'
        # Category required
        category = 'unknown'

        # Hardcoded purpose string, for now
        inc_tag = node_id_and_text(doc, top, 
                                   'Incident', purpose='mitigation')

        node_id_and_text(doc, inc_tag, 'IncidentID', 
                         ticket_nro, name=irt_url)
        node_id_and_text(doc, inc_tag, 'ReportTime', 
                         timestamp)
                         #ts_to_xml(timestamp))

        inc_ass = node_id_and_text(doc, inc_tag, 'Assessment')
        node_id_and_text(doc, inc_ass, 'Impact', info,
                         lang='en', type=impact)

        # Provide contact details as described in config
        if irt_name or irt_email or irt_phone:
            contact = node_id_and_text(doc, inc_tag, 'Contact',
                                       role="creator", type="organization")
        if irt_name:
            node_id_and_text(doc, contact, 'ContactName', irt_name)
        if irt_email:
            node_id_and_text(doc, contact, 'Email', irt_email)
        if irt_phone:
            node_id_and_text(doc, contact, 'Telephone', irt_phone)

        event = node_id_and_text(doc, inc_tag, 'EventData')

        # These are some default values for all entries, for now
        node_id_and_text(doc, event, 'Description', inc_type)
        node_id_and_text(doc, event, 'Expectation', action="investigate")
        event = node_id_and_text(doc, event, 'EventData')
        event = node_id_and_text(doc, event, 'Flow')

        # Target system information is provided, whenever available
        system = node_id_and_text(doc, event, 'System', 
                                  category=category)

        # Only show node if data exists
        if ptr or ip or asn:
            node = node_id_and_text(doc, system, 'Node')
        if ptr:
            node_id_and_text(doc, node, 'NodeName', ptr)
        if ip:
            node_id_and_text(doc, node, 'Address', ip, 
                             category='ipv4-addr')
        if asn:
            node_id_and_text(doc, node, 'Address', asn, 
                             category='asn')

    return doc.toxml()

@threado.stream
def ticker(inner):
    sleeper = threado.Channel()

    while True:
        try:
            item = yield inner, sleeper
        except:
            sleeper.throw()
            raise

        if sleeper.has_result():
            inner.send()
        if inner.was_source:
            times = item

        current_time = time.time() + 0.01

        next = set([interval - (current_time - offset) % interval 
                    for (offset, interval) in times])
        print next
        if next:
            sleeper = timer.sleep(min(next))
        else:
            sleeper = threado.Channel()

class MailerSession(services.Session):
    def __init__(self, service, from_addr):
        services.Session.__init__(self)

        self.events = dict()
        self.configs = threado.Channel()

        self.service = service
        self.from_addr = from_addr
        self.room_name = None

    def add_event(self, event):
        emails = event.attrs.get("email", list())
        if not emails:
            self.events.setdefault(None, list()).append(event)
        else:
            for email in emails:
                self.events.setdefault(email, list()).append(event)

    def create_reports(self, to, cc):
        if not self.events:
            return

        default = self.events.pop(None, ())
        for email in to:
            self.events.setdefault(email, list()).extend(default)

        for email, events in self.events.iteritems():
            keys = list()
            rows = list()
            for event in events:
                row, keys = normalise(event, keys)
                rows.append(row)

            string = StringIO()
            encoder = lambda x: x.encode("utf-8")
            
            writer = csv.writer(string, delimiter='|', quoting=csv.QUOTE_NONE)
            writer.writerow(map(encoder, keys))
            for row in rows:
                row += ("",) * (len(keys)-len(row))
                writer.writerow(map(encoder, row))
            csv_data = string.getvalue()

            xml_data = xml_report(rows)

            if email in to:
                yield [email], cc, (csv_data, xml_data)
            else:
                yield [email], to + cc, (csv_data, xml_data)
        self.events.clear()

    def prepare_mail(self, csv_data, xml_data, to, cc, subject, template):
        from email.header import Header
        from email.mime.multipart import MIMEMultipart
        from email.mime.base import MIMEBase
        from email.mime.text import MIMEText
        from email.charset import Charset, QP
        from email.utils import formatdate, make_msgid, getaddresses, formataddr
        from email.encoders import encode_base64
        
        ENCODING = "utf-8"
        
        from_addr = getaddresses([self.from_addr])[0]
        to_addrs = getaddresses(to)
        cc_addrs = getaddresses(cc)

        msg = MIMEMultipart()
    
        # FIXME: Use encoding after getaddresses
        msg["From"] = formataddr(from_addr)
        msg["To"] = ", ".join(map(formataddr, to_addrs))
        msg["Cc"] = ", ".join(map(formataddr, cc_addrs))
        msg["Subject"] = Header(subject, ENCODING)
        msg['Date'] = formatdate()
        msg['Message-ID'] = make_msgid()

        charset = Charset(ENCODING)
        charset.header_encoding = QP
        msg.set_charset(charset)

        del msg['Content-Transfer-Encoding']
        msg['Content-Transfer-Encoding'] = '7bit'

        msg.attach(MIMEText(template, "plain", "utf-8"))

        part = MIMEBase('text', "plain")
        part.set_payload(csv_data)
        encode_base64(part)
        part.add_header('Content-Disposition', 
                        'attachment; filename="report.csv"')
        msg.attach(part)

        part = MIMEBase('text', "xml")
        part.set_payload(xml_data)
        encode_base64(part)
        part.add_header('Content-Disposition', 
                        'attachment; filename="report.xml"')
        msg.attach(part)

        msg_data = msg.as_string()
        for to in to_addrs + cc_addrs:
            yield from_addr[1], to[1], msg_data

    def run(self):
        alarm_ticker = ticker()

        while True:
            while True:
                item = yield self.inner, self.configs
                if self.inner.was_source:
                    self.add_event(item)
                elif item is not None:
                    to, cc, subject, template, times = item
                    break

            alarm_ticker.send(times)
            while True:
                item = yield self.inner, self.configs, alarm_ticker
                
                if alarm_ticker.was_source:
                    for to, cc, data in self.create_reports(to, cc):
                        csv_data, xml_data = data
                        prepare = self.prepare_mail(csv_data, xml_data, 
                                                    to, cc, subject, template)
                        for from_addr, to_addr, msg_str in prepare:
                            self.service.send(from_addr, to_addr, msg_str)
                elif self.inner.was_source:
                    self.add_event(item)
                elif item is not None:
                    to, cc, subject, template, times = item
                    alarm_ticker.send(times)
                else:
                    alarm_ticker.send([])
                    break
        
    @threado.stream
    def config(inner, self, conf):
        self.service.srcs.dec(self.room_name, self)

        if conf is None:
            self.service.rooms(self)
            self.configs.send(None)
        else:
            to = conf.get("to", [])
            cc = conf.get("cc", [])
            subject = conf["subject"]
            template = conf["template"]
            times = conf["times"]
            self.room_name = conf["room"]

            self.service.rooms(self, self.room_name)
            self.service.srcs.inc(self.room_name, self)
            self.configs.send(to, cc, subject, template, times)
        yield
        inner.finish(conf)

def normalise(event, keys):
    attrs = copy.deepcopy(event.attrs)
    row = list()

    if u'dshield' in attrs.get('feed', ['']):
        keys = ('asn', 'ip', 'timestamp', 'ptr', 
                'cc', 'type', 'ticket', 'info')
        row.extend([attrs['asn'].pop(), attrs['ip'].pop(), 
                    attrs['updated'].pop(), '', '', 'scanners', 
                    '0', "firstseen: %s lastseen: %s" % 
                    (attrs['firstseen'].pop(), attrs['lastseen'].pop())])
    else:
        for key in keys:
            values = attrs.get(key, None)
            if values:
                row.append(values.pop())
            else:
                row.append("")

        for key, values in attrs.items():
            for value in values:
                keys.append(key)
                row.append(value)

    return tuple(row), keys

class MailerService(roomfarm.RoomFarm):
    def __init__(self, xmpp, host, port, from_addr, username="", password=""):
        roomfarm.RoomFarm.__init__(self, xmpp)

        self.srcs = roomfarm.Counter()
        self.from_addr = from_addr

        self.host = host
        self.port = port
        self.username = username
        self.password = password

    @threado.stream
    def handle_room(inner, self, name):
        print "Joining room", name
        room = yield inner.sub(self.xmpp.muc.join(name))
        print "Joined room", name
        yield inner.sub(room
                        | events.stanzas_to_events()
                        | self.distribute(name))

    @threado.stream_fast
    def distribute(inner, self, name):
        while True:
            yield inner

            dsts = self.srcs.get(name)
            for event in inner:
                for dst in dsts:
                    dst.send(event)
        
    def get_smtp(self):
        import smtplib

        server = smtplib.SMTP(self.host, self.port)
        try:
            server.ehlo()
            try:
                if server.has_extn('starttls'):
                    server.starttls()
                    # redundant ehlo, yeah!
                    server.ehlo()
                    server.login(self.username, self.password)
            except:
                pass
        except:
            server.quit()
            raise
        return server

    def run(self):
        queue = collections.deque()
        server = None

        @threado.stream
        def sleep_and_collect(inner, delay):
            sleeper = timer.sleep(delay)
            while True:
                item = yield inner, sleeper
                if sleeper.was_source:
                    inner.finish()
                queue.append(item)            

        while True:
            # Wait for something to send
            if not queue:
                item = yield self.inner
                queue.append(item)

            # Try to connect to the SMTP server if we're haven't done that yet
            while server is None:
                try:
                    print "Connecting %s port %d" % (self.host, self.port)
                    server = yield self.inner.thread(self.get_smtp)
                except:
                    print "Error connecting SMTP server, retrying in 10 seconds"
                    yield self.inner.sub(sleep_and_collect(10.0))
                else:
                    print "Connected to the SMTP server"

            while queue:
                # Send the oldest mail
                from_addr, to_addr, msg_str = queue[0]
                try:
                    yield self.inner.thread(server.sendmail, from_addr, 
                                            to_addr, msg_str)
                except Exception, exc:
                    print "Could not send message to %s: %s" % (to_addr, exc)
                    try:
                        yield self.inner.thread(server.quit)
                    except:
                        pass
                    server = None
                    break
                else:
                    queue.popleft()
                    print "Sent message to %s" % to_addr
                
    def session(self):
        return MailerSession(self, self.from_addr)

def main(xmpp_jid, service_room, smtp_host, mail_sender, 
         xmpp_password=None, smtp_port=25,
         submission_username=None, submission_password=None,
         log_file=None):
    import getpass
    from idiokit.xmpp import connect
    from abusehelper.core import log
    
    if not xmpp_password:
        xmpp_password = getpass.getpass("XMPP password: ")
    if submission_username and not submission_password:
        submission_password = getpass.getpass("SMTP password: ")

    logger = log.config_logger("mailer", filename=log_file)

    @threado.stream
    def bot(inner):
        print "Connecting XMPP server with JID", xmpp_jid
        xmpp = yield connect(xmpp_jid, xmpp_password)
        xmpp.core.presence()

        print "Joining lobby", service_room
        lobby = yield services.join_lobby(xmpp, service_room, "mailer")
        logger.addHandler(log.RoomHandler(lobby.room))

        mailer = MailerService(xmpp, smtp_host, smtp_port, mail_sender,
                               submission_username, submission_password)
        yield inner.sub(lobby.offer("mailer", mailer))
    return bot()
main.service_room_help = "the room where the services are collected"
main.xmpp_jid_help = "the XMPP JID (e.g. xmppuser@xmpp.example.com)"
main.xmpp_password_help = "the XMPP password"
main.smtp_host_help = "hostname of the SMTP service used for sending mails"
main.smtp_port_help = "port of the SMTP service used for sending mails"
main.mail_sender_help = "from whom it looks like the mails came from"
main.submission_username_help = "username for the authenticated SMTP service"
main.submission_password_help = "password for the authenticated SMTP service"
main.log_file_help = "log to the given file instead of the console"

if __name__ == "__main__":
    from abusehelper.core import opts
    threado.run(opts.optparse(main))
