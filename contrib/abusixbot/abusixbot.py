import re
import socket
import getpass
import imaplib
import email.parser

from cStringIO import StringIO
from abusehelper.core import events, bot, services, imapbot
from idiokit import threado, timer

### WHAT TO DO WITH THESE STUFFES??? ###
@threado.stream
def thread(inner, call, *args, **keys):
    thread = inner.thread(call, *args, **keys)
    while not thread.has_result():
        yield inner, thread
    inner.finish(thread.result())

@threado.stream
def collect(inner):
    collection = list()
    try:
        while True:
            item = yield inner
            collection.append(item)
    except threado.Finished:
        inner.finish(collection)
### HERE START CLEANING PIECES OF CODE ###

class ABUSIXBot(imapbot.IMAPService):

    def __init__(self, **keys):
        imapbot.IMAPBot.__init__(self, **keys)

import base64
import zipfile
import re
from cStringIO import StringIO

import arf

class ABUSIXService(ABUSIXBot):
    filename_rex = bot.Param(default=r"(?P<eventfile>.*)")

    def handle(self, parts):
        attachments = list()
        texts = list()

        for headers, data in parts:
            content_type = headers[-1].get_content_type()
            if content_type in ["message/feedback-report"]:
                attachments.append((headers, data))

        return imapbot.IMAPBot.handle(self, attachments)

    @threado.stream
    def handle_message_feedback__report(inner, self, headers, fileobj):
        filename = headers[-1].get_filename(None)
        if filename is not None:
            result = yield inner.sub(self.parse_text(filename, fileobj))
            inner.finish(result)

    @threado.stream
    def parse_text(inner, self, filename, fileobj):
        match = re.match(self.filename_rex, filename)
        if match is None:
            inner.finish(False)
    
        yield inner.sub(arf.arf_to_events(fileobj)
                        | self.normalize(match.groupdict()))
        inner.finish(True)

if __name__ == "__main__":
    ABUSIXService.from_command_line().execute()
