import csv
import UserDict

from cStringIO import StringIO
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.charset import Charset, QP
from email.utils import formatdate, make_msgid, getaddresses, formataddr
from email.encoders import encode_base64

class Formatter(object):
    def format(self, result, events, *args):
        raise NotImplementedError()

class Constant(object):
    def __init__(self, value):
        self.value = value

    def format(self, obj, events):
        return self.value

class AttachAndEmbed(object):
    def __init__(self, formatter):
        self.formatter = formatter

    def format(self, msg, events, filename, *args):
        data = self.formatter.format(msg, events, *args)

        part = MIMEBase('text', "plain")
        part.set_payload(data)
        encode_base64(part)
        part.add_header('Content-Disposition', 
                        'attachment; filename="%s"' % filename)
        msg.attach(part)        
        
        return data

class Attach(AttachAndEmbed):
    def format(self, *args, **keys):
        AttachAndEmbed.format(self, *args, **keys)
        return ""

class EventDict(object):
    def __init__(self, event):
        self.event = event

    def __getitem__(self, key):
        values = self.event.attrs.get(key, None)
        if not values:
            return ""
        return list(values)[0]

class CSVFormatter(object):
    def parse_fields(self, fields):
        for field in fields:
            split = field.split("=", 1)
            if len(split) != 2:
                yield split[0], "%(" + split[0] + ")s"
            else:
                yield tuple(split)

    def format(self, obj, events, delimiter, *fields):
        stringio = StringIO()
        fields = list(self.parse_fields(fields))

        writer = csv.writer(stringio, delimiter=delimiter)
        writer.writerow([key for (key, _) in fields])

        for event in events:
            event = EventDict(event)
            writer.writerow([format % event for (_, format) in fields])

        return stringio.getvalue()

class Template(object):
    def __init__(self, data, **formatters):
        self.data = data
        self.formatters = formatters

        self.obj = None
        self.events = None
        
    def format(self, obj, events):
        self.obj = obj
        self.events = events
        try:
            print repr(self.data)
            return self.data % self
        finally:
            self.events = None
            self.obj = obj

    def __getitem__(self, key):
        for row in csv.reader([key]):
            if not row:
                return ""
            row = [x.strip() for x in row]
            formatter = self.formatters[row[0]]
            return formatter.format(self.obj, self.events, *row[1:])
        return ""
