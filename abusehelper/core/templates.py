# -*- coding: utf-8 -*-

import csv
import codecs
from cStringIO import StringIO
from idiokit.util import guess_encoding
from email.mime.text import MIMEText
from email.encoders import encode_base64

class Formatter(object):
    def format(self, result, events, *args):
        raise NotImplementedError()

class Constant(object):
    def __init__(self, value):
        self.value = value

    def format(self, obj, events):
        return self.value

class AttachAndEmbedUnicode(object):
    def __init__(self, formatter, subtype="plain"):
        self.formatter = formatter
        self.subtype = subtype

    def format(self, parts, events, filename, *args):
        data = self.formatter.format(parts, events, *args)

        part = MIMEText(data.encode("utf-8"), self.subtype, "utf-8")
        encode_base64(part)
        part.add_header("Content-Disposition", 
                        "attachment", 
                        filename=filename)

        parts.append(part)
        return data

class AttachUnicode(AttachAndEmbedUnicode):
    def format(self, *args, **keys):
        AttachAndEmbedUnicode.format(self, *args, **keys)
        return u""

class _EventDict(object):
    def __init__(self, event, encoder=unicode):
        self.event = event
        self.encoder = encoder

    def __getitem__(self, key):
        values = self.event.attrs.get(key, None)
        if not values:
            return self.encoder(u"")
        return self.encoder(u"äää")#list(values)[0])

class CSVFormatter(object):
    def _encode(self, string):
        return string.encode("utf-8")

    def _decode(self, string):
        return string.decode("utf-8")

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
            event = _EventDict(event, self._encode)
            writer.writerow([format % event for (_, format) in fields])

        return self._decode(stringio.getvalue())

class Template(object):
    def __init__(self, data, **formatters):
        self.data = guess_encoding(data)
        self.formatters = formatters

        self.obj = None
        self.events = None
        
    def format(self, obj, events):
        self.obj = obj
        self.events = events
        try:
            return self.data % self
        finally:
            self.events = None
            self.obj = obj

    def __getitem__(self, key):
        for row in csv.reader([key]):
            if not row:
                return u""
            row = [x.strip() for x in row]
            formatter = self.formatters[row[0]]
            return formatter.format(self.obj, self.events, *row[1:])
        return u""
