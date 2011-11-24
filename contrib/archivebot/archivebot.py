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

from calendar import monthrange, timegm
from datetime import date, timedelta

import idiokit
from idiokit import timer
from abusehelper.core import bot, taskfarm, services, events

def isoformat(seconds=None, format="%Y-%m-%d %H:%M:%S"):
    """
    Return the ISO 8601 formatted timestamp based on the time
    expressed in seconds since the epoch. Use time.time() if seconds
    is not given or None.

    >>> isoformat(0)
    '1970-01-01 00:00:00'
    """

    return time.strftime(format, time.gmtime(seconds))

def calculate_rollover(timestamp, period):
    cur = date.fromtimestamp(timestamp)
    if period == 'day':
        next = cur + timedelta(days=1)
    elif period == 'month':
        next = cur + timedelta(days=monthrange(cur.year, cur.month)[1])
    elif period == 'week':
        next = cur + timedelta(weeks=1)
    elif period == 'year':
        next = cur.replace(year=cur.year+1)
    else:
        return None

    return timegm(next.timetuple())

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

class ArchiveBot(bot.ServiceBot):
    archive_dir = bot.Param("directory where archive files are written")
    rollover = bot.Param("period for doing archive filerollover (day, week, month or year)", default=None)
    bot_state_file = None

    def __init__(self, *args, **keys):
        super(ArchiveBot, self).__init__(*args, **keys)

        self.rooms = taskfarm.TaskFarm(self.handle_room)
        self.archive_dir = ensure_dir(self.archive_dir)

    @idiokit.stream
    def handle_room(self, name):
        self.log.info("Joining room %r", name)
        room = yield self.xmpp.muc.join(name, self.bot_name)
        self.log.info("Joined room %r", name)

        try:
            yield idiokit.pipe(room,
                               events.stanzas_to_events(),
                               self.collect(room.jid.bare()))
        finally:
            self.log.info("Left room %r", name)

    @idiokit.stream
    def session(self, state, src_room):
        try:
            yield self.rooms.inc(src_room)
        except services.Stop:
            idiokit.stop()

    def collect(self, room_name):
        collect = self._collect(room_name)
        idiokit.pipe(self._alert(), collect)
        return collect

    @idiokit.stream
    def _alert(self, flush_interval=2.0):
        while True:
            yield timer.sleep(flush_interval)
            yield idiokit.send()

    @idiokit.stream
    def _collect(self, room_name):
        room_name = unicode(room_name).encode("utf-8")
        archivename = os.path.join(self.archive_dir, room_name)
        archive = open(archivename, "ab")
        needs_flush = False

        rollover = None
        if self.rollover:
            rollover = calculate_rollover(time.time(), self.rollover)
            if not rollover:
                self.log.warning("Invalid period (%s), disabling rollover", 
                                 self.rollover)
                self.rollover = None

        try:
            while True:
                event = yield idiokit.next()
                if event is None:
                    if needs_flush:
                        archive.flush()
                        needs_flush = False
                    continue

                timestamp = time.time()
                if self.rollover:
                    if timestamp > rollover:
                        curtime = time.strftime('%Y%m%d', time.gmtime())
                        newname = "%s.%s" % (archivename, curtime)
                        self.log.info("Rolling over %r to %r", 
                                      archivename, newname)
                        archive.close()
                        os.rename(archivename, newname)
                        rollover = calculate_rollover(timestamp, period)
                        archive = open(archivename, "ab")
                archive.write(self.format(timestamp, event))
                needs_flush = True
        finally:
            archive.flush()
            archive.close()

    def format(self, timestamp, event):
        data = unicode(event).encode("utf-8")
        return isoformat(timestamp) + " " + data + os.linesep

if __name__ == "__main__":
    ArchiveBot.from_command_line().execute()
