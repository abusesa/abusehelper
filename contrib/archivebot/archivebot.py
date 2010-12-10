# A bot that joins channels and archives the events is sees. Creates
# files into the given archive directory, one file per channel and
# named after the channel. Each event takes one line, and the format
# is as follows:
# 2010-12-09 15:11:34 a=1,b=2,b=3
# 2010-12-09 17:12:32 a=4,a=5,b=6

import re
import os
import csv
import time
import errno

from abusehelper.core import bot, taskfarm, services, events
from idiokit import threado

def isoformat(seconds=None, format="%Y-%m-%d %H:%M:%S"):
    """
    Return the ISO 8601 formatted timestamp based on the time
    expressed in seconds since the epoch. Use time.time() if seconds
    is not given or None.

    >>> isoformat(0)
    '1970-01-01 00:00:00'
    """

    return time.strftime(format, time.gmtime(seconds))

def ensure_dir(dir_name):
    """
    Ensure that the directory exists (create if necessary) and return
    the absolute directory path.
    """

    dir_name = os.path.abspath(dir_name)
    try:
        os.makedirs(dir_name)
    except OSError, (code, error_str):
        if code != errno.EEXIST:
            raise
    return dir_name

_ESCAPE_RE = re.compile("[\r\n\",=]")

def dump_string(string):
    r"""
    Return an escaped utf-8 encoded string. 

    >>> dump_string(u'\u00e4')
    '\xc3\xa4'

    Escaping is done in two phases. 1) Double quotes are doubled.  2)
    Add double quote around the string when the string contains any of
    the following characters: ",\r\n
    
    >>> dump_string('"') == '"' * 4
    True
    >>> dump_string("a=b")
    '"a=b"'
    """

    string = string.encode("utf-8")
    if _ESCAPE_RE.search(string):
        return '"' + string.replace('"', '""') + '"'
    return string

def dump_event(event):
    """
    Return an event serialized into key-value pairs.

    >>> event = events.Event()
    >>> event.add('a', '1')
    >>> dump_event(event)
    'a=1'

    >>> event = events.Event()
    >>> event.add('=', '"')
    >>> dump_event(event)
    '"="="\"\""'
    """
    
    result = []
    for key in event.keys():
        for value in event.values(key):
            result.append(dump_string(key) + "=" + dump_string(value))
    return ",".join(result)

class ArchiveBot(bot.ServiceBot):
    archive_dir = bot.Param("directory where archive files are written")
    bot_state_file = None

    def __init__(self, *args, **keys):
        super(ArchiveBot, self).__init__(*args, **keys)

        self.rooms = taskfarm.TaskFarm(self.handle_room)
        self.archive_dir = ensure_dir(self.archive_dir)

    @threado.stream
    def handle_room(inner, self, name):
        self.log.info("Joining room %r", name)
        room = yield inner.sub(self.xmpp.muc.join(name, self.bot_name))
        self.log.info("Joined room %r", name)

        try:
            yield inner.sub(room
                            | events.stanzas_to_events()
                            | self.collect(room.room_jid)
                            | threado.dev_null())
        finally:
            self.log.info("Left room %r", name)

    @threado.stream
    def session(inner, self, state, src_room):
        try:
            yield inner.sub(self.rooms.inc(src_room))
        except services.Stop:
            inner.finish()

    @threado.stream_fast
    def collect(inner, self, room_name):
        room_name = unicode(room_name).encode("utf-8")
        archive = open(os.path.join(self.archive_dir, room_name), "ab")

        try:
            while True:
                yield inner

                timestamp = time.time()
                for event in inner:
                    archive.write(self.format(timestamp, event))

                archive.flush()
        finally:
            archive.flush()
            archive.close()

    def format(self, timestamp, event):
        return isoformat(timestamp) + " " + dump_event(event) + os.linesep

if __name__ == "__main__":
    ArchiveBot.from_command_line().execute()
