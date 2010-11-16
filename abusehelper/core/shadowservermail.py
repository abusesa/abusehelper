import re
import base64
import zipfile
from cStringIO import StringIO
from idiokit import threado
from abusehelper.core import utils, bot, imapbot

class ShadowServerMail(imapbot.IMAPBot):
    filter = bot.Param(default=r'(BODY "http://dl.shadowserver.org/" UNSEEN)')
    url_rex = bot.Param(default=r"http://dl.shadowserver.org/\S+")
    filename_rex = bot.Param(default=r"\d{4}-\d\d-\d\d-(?P<report_type>.*)-[^-]+\..*")

    @threado.stream
    def normalize(inner, self, groupdict):
        while True:
            event = yield inner

            for key in event.keys():
                event.discard(key, "")
                event.discard(key, "-")

            for key, value in groupdict.items():
                if None in (key, value):
                    continue
                event.add(key, value)

            inner.send(event)

    @threado.stream
    def parse_csv(inner, self, filename, fileobj):
        match = re.match(self.filename_rex, filename)
        if match is None:
            self.log.error("Filename %r did not match", filename)
            inner.finish(False)

        yield inner.sub(utils.csv_to_events(fileobj)
                        | self.normalize(match.groupdict()))
        inner.finish(True)
        
    def handle(self, parts):
        attachments = list()
        texts = list()

        for headers, data in parts:
            content_type = headers[-1].get_content_type()
            if headers[-1].get_filename(None) is None:
                if content_type == "text/plain":
                    texts.append((headers, data))
            elif content_type in ["text/plain", 
                                  "application/zip",
                                  "application/octet-stream"]:
                attachments.append((headers, data))

        return imapbot.IMAPBot.handle(self, attachments + texts)

    @threado.stream
    def handle_text_plain(inner, self, headers, fileobj):
        filename = headers[-1].get_filename(None)
        if filename is not None:
            self.log.info("Parsing CSV data from an attachment")
            result = yield inner.sub(self.parse_csv(filename, fileobj))
            inner.finish(result)

        for match in re.findall(self.url_rex, fileobj.read()):
            self.log.info("Fetching URL %r", match)
            try:
                info, fileobj = yield inner.sub(utils.fetch_url(match))
            except utils.FetchUrlFailed, fail:
                self.log.error("Fetching URL %r failed: %r", match, fail)
                return

            filename = info.get_filename(None)
            if filename is None:
                self.log.error("No filename given for the data")
                continue
            
            self.log.info("Parsing CSV data from the URL")
            result = yield inner.sub(self.parse_csv(filename, fileobj))
            inner.finish(result)

    @threado.stream
    def handle_application_zip(inner, self, headers, fileobj):
        self.log.info("Opening a ZIP attachment")
        try:
            data = base64.b64decode(fileobj.read())
        except TypeError, error:
            self.log.error("Base64 decoding failed: %s", error)
            return

        temp = StringIO(data)
        try:
            zip = zipfile.ZipFile(temp)
        except zipfile.BadZipfile, error:
            self.log.error("ZIP handling failed: %s", error)
            return

        for filename in zip.namelist():
            csv_data = StringIO(zip.read(filename))
            
            self.log.info("Parsing CSV data from the ZIP attachment")
            result = yield inner.sub(self.parse_csv(filename, csv_data))
            inner.finish(result)

    handle_application_octet__stream = handle_application_zip

if __name__ == "__main__":
    ShadowServerMail.from_command_line().execute()
