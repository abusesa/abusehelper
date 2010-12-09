# A bot that joins channels and archives the events is sees. Creates
# files into the given archive directory, one file per channel and
# named after the channel. Each event takes one line, and the format
# is as follows:
# 2010-12-09 15:11:34 {"a": ["1"], "b": ["2", "3"]}
# 2010-12-09 17:12:32 {"a": ["4", "5"], "b": ["6"]}

import os
import time
import errno

try:
    import json
except ImportError:
    import simplejson as json

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

def ensure_dir(dir_name, mode=0700):
    """
    Ensure that the directory exists (create if necessary) and return
    the absolute directory path.
    """

    dir_name = os.path.abspath(dir_name)
    try:
        os.makedirs(dir_name, mode)
    except OSError, (code, error_str):
        if code != errno.EEXIST:
            raise
    return dir_name

def dump_event(event):
    """
    Return an event serialized into a JSON dict of lists.

    >>> event = events.Event()
    >>> event.add("a", "1")
    >>> dump_event(event)
    '{"a": ["1"]}'
    """

    event_dict = dict()
    for key in event.keys():
        event_dict[key] = list(event.values(key))
    return json.dumps(event_dict)

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

                for event in inner:
                    line = isoformat() + " " + dump_event(event)
                    archive.write(line + os.linesep)

                archive.flush()
        finally:
            archive.flush()
            archive.close()

if __name__ == "__main__":
    ArchiveBot.from_command_line().execute()
