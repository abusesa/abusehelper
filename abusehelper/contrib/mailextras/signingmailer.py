import re
import os
import urllib
import httplib
import hashlib

import pyme.core
try:
    import pyme.pygpgme as gpgme
except ImportError:
    import pyme.gpgme as gpgme

from random import randint as randrange
from time import gmtime, strftime
from email.mime.text import MIMEText

import idiokit
from idiokit import timer, threadpool
from abusehelper.core import mailer, templates, bot

from iodef import XMLFormatter

def get_valid_keys(ctx, patterns=[], sign=0):
    keys = []
    for pattern in patterns:
        keys.extend(key for key in ctx.op_keylist_all(pattern, sign)
                    if (key.can_encrypt != 0))
    return keys

# Sign and encrypt as much as it is possible
def sign_and_encrypt(data, sign_key='', passphrase='',
                     send_to=[], own_key='', attachment=False):

    ctx = pyme.core.Context()
    ctx.set_armor(1)

    plaintext = pyme.core.Data(data)
    encrypted = pyme.core.Data()

    recipients = get_valid_keys(ctx, send_to)

    if recipients:
        recipients.extend(get_valid_keys(ctx, [own_key]))

    if sign_key:
        ctx.signers_add(sign_key)
        ctx.set_passphrase_cb(lambda *args, **kw: passphrase)

    if sign_key and passphrase and recipients:
        # http://pyme.sourceforge.net/doc/gpgme/Encrypting-a-Plaintext.html
        # The 1 is gpgme_encrypt_flags_t for GPGME_ENCRYPT_ALWAYS_TRUST
        ctx.op_encrypt_sign(recipients, 1, plaintext, encrypted)
    elif sign_key and passphrase:
        if attachment:
            mode = pyme.pygpgme.GPGME_SIG_MODE_DETACH
        else:
            mode = pyme.pygpgme.GPGME_SIG_MODE_CLEAR

        ctx.op_sign(plaintext, encrypted, mode)
    elif recipients:
        ctx.op_encrypt(recipients, 1, plaintext, encrypted)
    else:
        return data, ''

    encrypted.seek(0, 0)
    enc_data = encrypted.read()

    # Detach sig
    if attachment and not recipients:
        return enc_data, data

    return enc_data, ''

class AugmentingIterator(object):
    def __init__(self, events, **added_keys):
        self._events = events
        self._keys = added_keys

    def __iter__(self):
        for event in self._events:
            for key, value in self._keys.iteritems():
                event.add(key, value)
            yield event

    def __nonzero__(self):
        return not not self._events

class Mailer(mailer.MailerService):
    sign_keys = bot.ListParam("PGP signing key ids", default=None)
    passphrase = bot.Param("PGP signing key passphrase", default=None)
    rt_server = bot.Param("RT server to get ticket numbers from", default='')
    rt_user = bot.Param("RT server username", default='')
    rt_passwd = bot.Param("RT server user password", default='')
    rt_queue = bot.Param("RT queue to create tickets to", default='')
    rt_close_delay = \
        bot.IntParam("Delay after which generated tickets are closed", 
                     default=300)
    rt_manual_queue = \
        bot.Param("RT queue to move tickets with no valid recipient",
                  default='')
    debug = bot.Param("Do not send, only debug how the mail would be sent",
                  default='')
    sent_dir = bot.Param("Directory for logs on sent data", default='')
    ticket_preamble = \
        bot.Param("A possible ticketing header, eg. CERT in [CERT #1]", 
                  default='')


    def get_random_ticket_no(self, **kw):
        from random import randint as randrange
        number = unicode(randrange(80000, 100000))
        return number

    @idiokit.stream
    def close_ticket(self, number, **kw):
        self.log.info("Sleeping for %s seconds before closing ticket %s",
                      self.rt_close_delay, number)
        yield timer.sleep(self.rt_close_delay)
        kw['action'] = "edit"
        kw['content'] = "Status: resolved\nid: ticket/%s\n" % (number)
        success = self.rt_ticket(**kw)
        if success:
            self.log.info("Closed ticket %s", number)
        else:
            self.log.info("Could not close ticket %s", number)

    def rt_ticket(self, manual=False, **kw):
        headers = {"Content-type": "application/x-www-form-urlencoded",
                   "Accept": "text/plain"}
        hostport = self.rt_server
        host, port = hostport.split(':')
        user = self.rt_user
        passwd = self.rt_passwd

        if manual:
            queue = self.rt_manual_queue
        else:
            queue = self.rt_queue

        if not host or not port or not user or not passwd or not queue:
            self.log.error("Could contact RT, bad or missing args" +
                           "(host: %s port: %s user: %s queue: %s) or passwd",
                           host, port, user, queue)
            return u""

        params = urllib.urlencode({'user': user, 'pass': passwd}) + "&"
        mode = kw.get('action', 'new')
        if mode == 'new':
            text = kw.get('ticket_text', '')
            subject = kw.get('ticket_subject', '')
            urlpath =  "/REST/1.0/ticket/new"
            content = "id: ticket/new\nStatus: new\n" + \
                "Subject: %s\nQueue: %s\nText: %s\n" % (subject, queue, text)
        elif mode == 'edit':
            urlpath = "/REST/1.0/edit"
            content = kw.get('content', '')
            if not content:
                self.log.error("No content for editing RT ticket!")
                return u""
        else:
            self.log.error("Unknown RT action: %s", mode)
            return u""

        params += urllib.urlencode({"content": content})

        try:
            if port == '80':
		conn = httplib.HTTPConnection(hostport)
            else:
		conn = httplib.HTTPSConnection(hostport)
            conn.request("POST", urlpath, params, headers)
            response = conn.getresponse()
            data = response.read()
            conn.close()
        except Exception, fuf:
            self.log.error("RT Connection failed: %r", fuf)
            return u""

        if mode == 'new':
            ticketno = re.findall("(\d+) created.", data, re.M)
            try:
                int(ticketno[0])
            except (TypeError, ValueError):
                self.log.error("Weird response from rt: %r", data)
                return u""

            return ticketno[0]
        else:
            ticketno = re.findall("Ticket (\d+) updated.", data, re.M)
            if not ticketno:
                return u""
            return u"-1"

    def build_mail(self, *args, **keys):
        return threadpool.thread(self._build_mail, *args, **keys)

    def _build_mail(self,
                    events, number,
                    template="", to=[],
                    cc=[], keywords=(),
                    **keys):
        kws = dict(keywords)
        xml = XMLFormatter(**kws)
        csv = templates.CSVFormatter(keys=False)
        template = (
            mailer.MailTemplate(template,
                                csv=csv,
                                attach_csv=templates.AttachUnicode(csv),
                                embed_csv=templates.AttachAndEmbedUnicode(csv),
                                attach_xml = templates.AttachUnicode(xml),
                                to=templates.Const(mailer.format_addresses(to)),
                                cc=templates.Const(mailer.format_addresses(cc))))

        msg = template.format(events)

        # Silly tricks needed to add anything to the subject so that
        # mail servers will not muck about with it...

        from email.header import decode_header
        from email.charset import Charset, QP
        subject = msg.get("Subject", "")
        encoding = ''
        if subject:
            s = decode_header(subject)[0]
            encoding = s[1]
        if not encoding:
            encoding = 'utf-8'

        if keys.get('manual', False):
            subject = kws.get('manual_subject', '')
        elif subject:
            subject = s[0].decode(encoding)
        del msg["Subject"]

        # If were missing the ticket number, the priority is still on
        # sending the report
        if number:
            number = u"[%s #%s] " % (self.ticket_preamble, number)
        else:
            number = u""
        number = number.encode(encoding)
        subject = subject.encode(encoding)

        postscript = kws.get("subject_postscript", u"")
        if postscript:
            postscript = u" %s" % (postscript)
        postscript = postscript.encode(encoding)

        charset = Charset(encoding)
        charset.header_encoding = QP
        msg["Subject"] = charset.header_encode("%s%s%s" % 
                                               (number, subject, postscript))

        if not self.sign_keys or not self.passphrase:
            return msg

        # Sign mail
        msgparts = msg.walk()
        msgparts.next()

        ctx = pyme.core.Context()
        ctx.set_armor(1)
        sign_key = get_valid_keys(ctx, self.sign_keys, sign=1)
        if sign_key:
            sign_key = sign_key[0]
        else:
            return msg

        newparts = list()

        for i, part in enumerate(msgparts):
            # Sign message body
            if i == 0:
                data = part.get_payload(decode=True)
                data = sign_and_encrypt(data, sign_key, self.passphrase)[0]
                part.set_payload(data.encode('base64'))
            else:
                fname = part.get_filename()
                data = part.get_payload(decode=True)
                sig = sign_and_encrypt(data, sign_key, self.passphrase,
                                       attachment=True)[0]

                newpart = MIMEText(sig, 'application/pgp-signature', "utf-8")
                newpart.add_header("Content-Disposition", "attachment",
                                   filename=fname + '.asc')

                newparts.append(newpart)

        for part in newparts:
            msg.attach(part)

        return msg

    def _log_events(self, events, logfile):
        sdate = strftime("%Y-%m-%d %H:%M:%S", gmtime())
        for event in events:
            data = list()
            data.append(event.value('asn', ''))
            data.append(event.value('ip', ''))
            data.append(event.value('time', ''))
            data.append(event.value('ptr', ''))
            data.append(event.value('cc', ''))
            data.append(event.value('type', ''))
            data.append(event.value('case', ''))
            data.append(event.value('info', ''))
            data.append(sdate)
            data.append(event.value('_received', ''))
            data.append(event.value('feed', ''))
            logfile.write("%s\n" % (' | '.join(data).encode('utf-8')))

    @idiokit.stream
    def report(self, _events, keywords=(), **keys):
        if not _events:
            idiokit.stop(True)

        real_to = list()
        for to in keys.get('to', list()):
            if '@' in to:
                real_to.append(to)
        if not real_to:
            self.log.info("No email address (%r) for customer %r, quitting report",
                          keys.get('to', list()), keys.get('src_room', ''))
            idiokit.stop(True)

        kws = dict(keywords)

        # If we only have our own irt mailbox as recipient, it means
        # the ticket won't be sent to the real customer, and we need
        # to do some manual handling. Hence, do not close the ticket,
        # and send it to the manual queue.
        manual = False
        addrs = keys.get('to', ())
        addrs = addrs + keys.get('cc', ())
        addrs = set(addrs)
        addrs.discard(kws.get('irt_email', ''))
        if not addrs:
            keys['cc'] = []
            manual = True
            kws["ticket_subject"] = kws.get('manual_subject', 
                                            'ERROR: no manual subject defined')
            keys['manual'] = True

        if keys.has_key('to_override'):
            keys['to'] = keys['to_override']
            keys['cc'] = []

        number = yield threadpool.thread(self.rt_ticket, manual, **kws)
        if manual:
            self.log.info("No valid recipients, manual ticket: %s" % number)

        events = AugmentingIterator(_events, case=number)

        success = yield mailer.MailerService.report(self, events,
                                                    number=number,
                                                    keywords=keywords,
                                                    **keys)

        if success:
            fdate = strftime("%Y%m%d-%H%M%S")
            fname = os.path.join(self.sent_dir, 'abuh-%s.csv' % fdate)
            self.log.info("Writing events to log file %r" % fname)

            logfile = file(fname, "a")
            try:
                yield threadpool.thread(self._log_events, events, logfile)
            finally:
                logfile.flush()
                logfile.close()

            self.log.info("Finished writing events to log file %r" % fname)

            if not manual:
                self.close_ticket(number, **kws)
            else:
                self.log.info("Not closing manual ticket %s" % number)

        idiokit.stop(success)

    @idiokit.stream
    def _try_to_send(self, from_addr, to_addr, subject, msg):
        if self.debug:
            yield timer.sleep(0)
            self.log.info("DEBUG: Would have sent message to %r", 
                          to_addr)
            idiokit.stop(True)
        else:
            result = yield self._try_to_send(from_addr, to_addr, subject, msg)
            idiokit.stop(result)

    def collect(self, *args, **keys):
        return self._stats(keys.get("src_room", "COLLECT")) \
            | mailer.MailerService.collect(self, *args, **keys)

    def _stats(self, name, interval=60.0):
        @idiokit.stream
        def counter():
            while True:
                event = yield idiokit.next()
                yield idiokit.send(event)
                counter.count += 1
        counter.count = 0

        def log():
            if counter.count > 0:
                self.log.info("Sent %d events to room %r", counter.count, name)
            counter.count = 0

        @idiokit.stream
        def logger():
            try:
                yield timer.sleep(interval / 2.0)
                log()

                while True:
                    yield timer.sleep(interval)
                    log()
            finally:
                log()

        result = counter()
        idiokit.pipe(logger(), result)
        return result

if __name__ == "__main__":
    Mailer.from_command_line().execute()
