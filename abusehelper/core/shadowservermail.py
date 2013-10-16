import re
import base64
import quopri
import zipfile
from cStringIO import StringIO

import idiokit
from abusehelper.core import utils, bot, imapbot


class ShadowServerMail(imapbot.IMAPBot):
    filter = bot.Param(default=r'(BODY "http://dl.shadowserver.org/" UNSEEN)')
    url_rex = bot.Param(default=r"http://dl.shadowserver.org/\S+")

    # Assume the file names to be something like
    # YYYY-dd-mm-<reporttype>-<countrycode>.<extension(s)>
    filename_rex = bot.Param(default=r"(?P<report_date>\d{4}-\d\d-\d\d)-(?P<report_type>[^-]*).*\..*")

    def _decode(self, headers, fileobj):
        encoding = headers[-1].get_all("content-transfer-encoding", ["7bit"])[0]
        encoding = encoding.lower()

        if encoding == "base64":
            try:
                data = base64.b64decode(fileobj.read())
            except TypeError as error:
                self.log.error("Base64 decoding failed ({0})".format(error))
                idiokit.stop(False)
            return StringIO(data)

        if encoding == "quoted-printable":
            output = StringIO()
            quopri.decode(fileobj, output)
            output.seek(0)
            return output

        return fileobj

    @idiokit.stream
    def normalize(self, groupdict):
        while True:
            event = yield idiokit.next()

            for key in event.keys():
                event.discard(key, "")
                event.discard(key, "-")

            for key, value in groupdict.items():
                if None in (key, value):
                    continue
                event.add(key, value)

            yield idiokit.send(event)

    @idiokit.stream
    def parse_csv(self, filename, fileobj):
        match = re.match(self.filename_rex, filename)
        if match is None:
            self.log.error("Filename {0!r} did not match".format(filename))
            idiokit.stop(False)

        yield idiokit.pipe(
            utils.csv_to_events(fileobj),
            self.normalize(match.groupdict()))
        idiokit.stop(True)

    def handle(self, parts):
        attachments = list()
        texts = list()

        for headers, data in parts:
            content_type = headers[-1].get_content_type()

            if headers[-1].get_filename(None) is None:
                if content_type == "text/plain":
                    texts.append((headers, data))
            else:
                attachments.append((headers, data))

        return imapbot.IMAPBot.handle(self, attachments + texts)

    @idiokit.stream
    def handle_text_plain(self, headers, fileobj):
        fileobj = self._decode(headers, fileobj)

        filename = headers[-1].get_filename(None)
        if filename is not None:
            self.log.info("Parsing CSV data from an attachment")
            result = yield self.parse_csv(filename, fileobj)
            idiokit.stop(result)

        for match in re.findall(self.url_rex, fileobj.read()):
            self.log.info("Fetching URL {0!r}".format(match))
            try:
                info, fileobj = yield utils.fetch_url(match)
            except utils.FetchUrlFailed as fail:
                self.log.error("Fetching URL {0!r} failed ({1})".format(match, fail))
                return

            filename = info.get_filename(None)
            if filename is None:
                self.log.error("No filename given for the data")
                continue

            self.log.info("Parsing CSV data from the URL")
            result = yield self.parse_csv(filename, fileobj)
            idiokit.stop(result)

    @idiokit.stream
    def handle_text_csv(self, headers, fileobj):
        filename = headers[-1].get_filename(None)
        if filename is None:
            self.log.error("No filename given for the data")
            idiokit.stop(False)

        self.log.info("Parsing CSV data from an attachment")
        fileobj = self._decode(headers, fileobj)
        result = yield self.parse_csv(filename, fileobj)
        idiokit.stop(result)

    @idiokit.stream
    def handle_application_zip(self, headers, fileobj):
        self.log.info("Opening a ZIP attachment")
        fileobj = self._decode(headers, fileobj)
        try:
            zip = zipfile.ZipFile(fileobj)
        except zipfile.BadZipfile as error:
            self.log.error("ZIP handling failed ({0})".format(error))
            idiokit.stop(False)

        for filename in zip.namelist():
            csv_data = StringIO(zip.read(filename))

            self.log.info("Parsing CSV data from the ZIP attachment")
            result = yield self.parse_csv(filename, csv_data)
            idiokit.stop(result)

    def handle_application_octet__stream(self, headers, fileobj):
        filename = headers[-1].get_filename(None)
        if filename is not None and filename.lower().endswith(".csv"):
            return self.handle_text_csv(headers, fileobj)
        return self.handle_application_zip(headers, fileobj)


if __name__ == "__main__":
    ShadowServerMail.from_command_line().execute()
