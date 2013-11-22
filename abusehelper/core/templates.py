from __future__ import absolute_import

import csv
import zipfile

from cStringIO import StringIO
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.encoders import encode_base64

from .utils import force_decode


class TemplateError(Exception):
    pass


class Formatter(object):
    def check(self, *args):
        pass

    def format(self, result, events, *args):
        raise NotImplementedError()


class Const(Formatter):
    def __init__(self, value):
        self.value = value

    def format(self, obj, events, *args):
        return self.value


class AttachAndEmbedUnicode(Formatter):
    def __init__(self, formatter, subtype="plain"):
        self.formatter = formatter
        self.subtype = subtype

    def check(self, filename=None, *args):
        if filename is None:
            raise TemplateError("filename parameter required")

    def format(self, parts, events, filename, *args):
        data = self.formatter.format(parts, events, *args)

        part = MIMEText(data.encode("utf-8"), self.subtype, "utf-8")
        part.add_header(
            "Content-Disposition",
            "attachment",
            filename=filename)

        parts.append(part)
        return data


class AttachZip(Formatter):

    def __init__(self, formatter):
        self.formatter = formatter

    def check(self, filename=None, *args):
        if filename is None:
            raise TemplateError("filename parameter required")

    def format(self, parts, events, filename, *args):
        if filename.endswith(".zip"):
            filename = filename[:-4]

        data = self.formatter.format(parts, events, *args)
        memfile = StringIO()
        zipped = zipfile.ZipFile(memfile, 'w', zipfile.ZIP_DEFLATED)
        zipped.writestr(filename+".csv", data.encode("utf-8"))
        zipped.close()
        memfile.flush()
        memfile.seek(0)

        part = MIMEBase("application", "zip")
        part.set_payload(memfile.read())
        encode_base64(part)
        part.add_header("Content-Disposition",
                        "attachment",
                        filename=filename+".zip")
        parts.append(part)

        return u""


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


class CSVFormatter(Formatter):
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

    def check(self, delimiter=None, *fields):
        if delimiter is None:
            raise TemplateError("delimiter parameter required")
        if len(delimiter) != 1:
            raise TemplateError("delimiter must be a single character")

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
    class _Null(object):
        def format(self, name, *args):
            return ""

        def __getitem__(self, key):
            for row in csv.reader([key], skipinitialspace=True):
                if not row:
                    return u""
                row = [x.strip() for x in row]
                return self.format(*row)
            return u""

    class _Checker(_Null):
        def __init__(self, formatters):
            self.formatters = formatters

        def format(self, name, *args):
            if name not in self.formatters:
                raise TemplateError("unknown formatter " + repr(name))

            formatter = self.formatters[name]
            try:
                formatter.check(*args)
            except TemplateError as err:
                raise TemplateError("invalid formatter " + repr(name) + ": " + err.message)
            return u""

    class _Formatter(_Null):
        def __init__(self, obj, events, formatters):
            self.obj = obj
            self.events = events
            self.formatters = formatters

        def format(self, name, *args):
            formatter = self.formatters[name]
            return formatter.format(self.obj, self.events, *args)

    def __init__(self, data, **formatters):
        self.data = force_decode(data)
        self.formatters = formatters

        try:
            self.data % self._Null()
        except ValueError:
            raise TemplateError("invalid format")
        except TypeError as type_error:
            raise TemplateError(type_error.message)

        self.data % self._Checker(self.formatters)

    def format(self, obj, events):
        formatter = self._Formatter(obj, events, self.formatters)
        return self.data % formatter
