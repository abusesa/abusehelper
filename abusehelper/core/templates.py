from __future__ import absolute_import

import csv
from cStringIO import StringIO
from email.mime.text import MIMEText

from .utils import force_decode


class Formatter(object):
    def format(self, result, events, *args):
        raise NotImplementedError()


class Const(object):
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
        part.add_header(
            "Content-Disposition",
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
        value = self.event.value(key, u"")
        return self.encoder(value)


class CSVFormatter(object):
    def __init__(self, keys=True):
        self.keys = keys

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
        if self.keys:
            writer.writerow([key for (key, _) in fields])

        for event in events:
            event = _EventDict(event, self._encode)
            writer.writerow([format % event for (_, format) in fields])

        return self._decode(stringio.getvalue())


class Template(object):
    class _Formatter(object):
        def __init__(self, obj, events, formatters):
            self.obj = obj
            self.events = events
            self.formatters = formatters

        def __getitem__(self, key):
            for row in csv.reader([key], skipinitialspace=True):
                if not row:
                    return u""
                row = [x.strip() for x in row]
                formatter = self.formatters[row[0]]
                return formatter.format(self.obj, self.events, *row[1:])
            return u""

    def __init__(self, data, **formatters):
        self.data = force_decode(data)
        self.formatters = formatters

    def format(self, obj, events):
        formatter = self._Formatter(obj, events, self.formatters)
        return self.data % formatter
