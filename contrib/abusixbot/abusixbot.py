import re
import socket
import getpass
import imaplib
import email.parser

from cStringIO import StringIO
from abusehelper.core import events, bot, services, imapbot
from idiokit import threado, timer

class ABUSIXBot(imapbot.IMAPBot):
    def __init__(self, **keys):
        imapbot.IMAPBot.__init__(self, **keys)

import base64
import zipfile
import re
from cStringIO import StringIO
import arf

class ABUSIXService(ABUSIXBot):
    def handle(self, parts):
        attachments = list()

        for headers, data in parts:
            content_type = headers[-1].get_content_type()
            if content_type in ["message/feedback-report"]:
                attachments.append((headers, data))

        return imapbot.IMAPBot.handle(self, attachments)

    @threado.stream
    def handle_message_feedback__report(inner, self, headers, fileobj):
        result = yield inner.sub(arf.arf_to_events(fileobj))
        inner.finish(result)

if __name__ == "__main__":
    ABUSIXService.from_command_line().execute()
