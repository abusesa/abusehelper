import re
import zipfile
from cStringIO import StringIO

import idiokit
from ...core import mail, utils


@idiokit.stream
def _collect_texts_and_attachments():
    texts = []
    attachments = []

    while True:
        try:
            msg_part = yield idiokit.next()
        except StopIteration:
            idiokit.stop(texts, attachments)

        content_type = msg_part.get_content_type()
        filename = msg_part.get_filename(None)

        if filename is not None:
            attachments.append(msg_part)
        elif content_type == "text/plain":
            texts.append(msg_part)


@idiokit.stream
def _normalize(subject):
    while True:
        event = yield idiokit.next()
        if subject is not None:
            event.add("report_subject", subject)

        for key in event.keys():
            event.discard(key, "")
            event.discard(key, "-")

        yield idiokit.send(event)


@idiokit.stream
def _add_filename_info(groupdict):
    while True:
        event = yield idiokit.next()

        for key, value in groupdict.items():
            if None in (key, value):
                continue
            event.add(key, value)

        yield idiokit.send(event)


class Handler(mail.Handler):
    def __init__(
        self,
        log,
        url_rex=r"http[s]?://dl.shadowserver.org/\S+",
        # Assume the file names to be something like
        # YYYY-dd-mm-<reporttype>-<countrycode>.<extension(s)>
        filename_rex=r"(?P<report_date>\d{4}-\d\d-\d\d)-(?P<report_type>[^-]*).*\..*",
        retry_count=5,
        retry_interval=600
    ):
        mail.Handler.__init__(self, log)

        self.url_rex = url_rex
        self.filename_rex = filename_rex
        self.retry_count = retry_count
        self.retry_interval = retry_interval

    @idiokit.stream
    def parse_csv(self, filename, fileobj):
        match = re.match(self.filename_rex, filename)
        if match is None:
            self.log.error("Filename {0!r} did not match".format(filename))
            idiokit.stop(False)

        yield idiokit.pipe(
            utils.csv_to_events(fileobj),
            _add_filename_info(match.groupdict())
        )
        idiokit.stop(True)

    @idiokit.stream
    def handle(self, msg):
        texts, attachments = yield msg.walk() | _collect_texts_and_attachments()
        subject = msg.get_unicode("Subject", None)
        for msg in attachments + texts:
            result = yield mail.Handler.handle(self, msg) | _normalize(subject)
            if result:
                break

    @idiokit.stream
    def handle_text_plain(self, msg):
        data = yield msg.get_payload(decode=True)

        filename = msg.get_filename(None)
        if filename is not None:
            self.log.info("Parsing CSV data from an attachment")
            result = yield self.parse_csv(filename, StringIO(data))
            idiokit.stop(result)

        for match in re.findall(self.url_rex, data):
            for try_num in xrange(max(self.retry_count, 0) + 1):
                self.log.info("Fetching URL {0!r}".format(match))
                try:
                    info, fileobj = yield utils.fetch_url(match)
                except utils.FetchUrlFailed as fail:
                    if self.retry_count <= 0:
                        self.log.error("Fetching URL {0!r} failed ({1}), giving up".format(match, fail))
                        idiokit.stop(False)
                    elif try_num == self.retry_count:
                        self.log.error("Fetching URL {0!r} failed ({1}) after {2} retries, giving up".format(match, fail, self.retry_count))
                        idiokit.stop(False)
                    else:
                        self.log.error("Fetching URL {0!r} failed ({1}), retrying in {2:.02f} seconds".format(match, fail, self.retry_interval))
                        yield idiokit.sleep(self.retry_interval)
                else:
                    break

            filename = info.get_filename(None)
            if filename is None:
                self.log.error("No filename given for the data")
                continue

            self.log.info("Parsing CSV data from the URL")
            result = yield self.parse_csv(filename, fileobj)
            idiokit.stop(result)

    @idiokit.stream
    def handle_text_csv(self, msg):
        filename = msg.get_filename(None)
        if filename is None:
            self.log.error("No filename given for the data")
            idiokit.stop(False)

        self.log.info("Parsing CSV data from an attachment")
        data = yield msg.get_payload(decode=True)
        result = yield self.parse_csv(filename, StringIO(data))
        idiokit.stop(result)

    @idiokit.stream
    def handle_application_zip(self, msg):
        self.log.info("Opening a ZIP attachment")
        data = yield msg.get_payload(decode=True)
        try:
            zip = zipfile.ZipFile(StringIO(data))
        except zipfile.BadZipfile as error:
            self.log.error("ZIP handling failed ({0})".format(error))
            idiokit.stop(False)

        for filename in zip.namelist():
            csv_data = zip.open(filename)

            self.log.info("Parsing CSV data from the ZIP attachment")
            result = yield self.parse_csv(filename, csv_data)
            idiokit.stop(result)

    def handle_application_octet__stream(self, msg):
        filename = msg.get_filename(None)
        if filename is not None and filename.lower().endswith(".csv"):
            return self.handle_text_csv(msg)
        return self.handle_application_zip(msg)
