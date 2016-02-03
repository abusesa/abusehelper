import os
import gzip
import json
import time
import errno
import random
import urllib

from datetime import datetime

import idiokit
from idiokit.xmpp.jid import JID
from abusehelper.core import bot, events, taskfarm, utils


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


def archive_path(ts, room_name):
    gmtime = time.gmtime(ts)

    return os.path.join(
        room_name,
        time.strftime("%Y", gmtime),
        time.strftime("%m", gmtime),
        time.strftime("%d.json", gmtime)
    )


def open_archive(archive_dir, ts, room_name):
    path = os.path.join(archive_dir, archive_path(ts, room_name))
    dirname = os.path.dirname(path)
    ensure_dir(dirname)
    return open(path, "ab")


def _encode_room_jid(jid):
    """Return sanitized and normalised domain/node path name from
    a bare or a full room JID.
    """
    room_jid = JID(jid)

    room_node = urllib.quote(room_jid.node, safe=" @")
    room_domain = urllib.quote(room_jid.domain, safe=" @")

    return "{0}@{1}".format(room_node, room_domain)


def _rename(path):
    head, tail = os.path.split(path)
    base = os.path.join(head, tail + ".compress")

    new_path = "{0}-{1:x}".format(base, random.getrandbits(32))
    while os.path.isfile(new_path):
        new_path = "{0}-{1:x}".format(base, random.getrandbits(32))

    os.rename(path, new_path)
    return new_path


def compress(path):
    try:
        base = path[:path.index(".compress")]
    except ValueError:
        return

    gz_path = "{0}.gz".format(base)
    while os.path.isfile(gz_path):
        gz_path = "{0}-{1:x}.gz".format(base, random.getrandbits(32))

    with open(path, "rb") as archive:
        compressed = gzip.open(gz_path, "wb")
        try:
            compressed.writelines(archive)
        finally:
            compressed.close()

    try:
        os.remove(path)
    except OSError:
        pass

    return gz_path


@idiokit.stream
def flush(flush_interval=2.0):
    while True:
        yield idiokit.send()
        yield idiokit.sleep(flush_interval)


@idiokit.stream
def rotate():
    last = None

    while True:
        now = datetime.utcnow().day
        if now != last:
            last = now
            yield idiokit.send(True)

        yield idiokit.sleep(1.0)


class ArchiveBot(bot.ServiceBot):
    archive_dir = bot.Param("directory where archive files are written")

    def __init__(self, *args, **kwargs):
        super(ArchiveBot, self).__init__(*args, **kwargs)

        self.rooms = taskfarm.TaskFarm(self.handle_room, grace_period=0.0)
        self.archive_dir = ensure_dir(self.archive_dir)

    @idiokit.stream
    def session(self, state, src_room):
        src_jid = yield self.xmpp.muc.get_full_room_jid(src_room)
        yield self.rooms.inc(src_jid.bare())

    @idiokit.stream
    def handle_room(self, name):
        msg = "room {0!r}".format(name)

        attrs = events.Event({
            "type": "room",
            "service": self.bot_name,
            "room": unicode(name)
        })

        with self.log.stateful(repr(self.xmpp.jid), "room", repr(name)) as log:
            log.open("Joining " + msg, attrs, status="joining")
            room = yield self.xmpp.muc.join(name, self.bot_name)

            log.open("Joined " + msg, attrs, status="joined")
            try:
                yield idiokit.pipe(room,
                                   events.stanzas_to_events(),
                                   self._archive(room.jid.bare()))
            finally:
                log.close("Left " + msg, attrs, status="left")

    def _archive(self, room_bare_jid):
        compress = utils.WaitQueue()
        room_name = _encode_room_jid(room_bare_jid)

        _dir = os.path.join(self.archive_dir, room_name)

        if _dir != os.path.normpath(_dir):
            self.log.error("Incorrect room name lands outside the archive directory.")
            raise ValueError

        for root, _, filenames in os.walk(_dir):
            for filename in filenames:
                if ".json.compress" in filename:
                    compress.queue(0.0, os.path.join(root, filename))

        collect = idiokit.pipe(
            self._collect(room_name, compress),
            self._compress(compress)
        )

        idiokit.pipe(flush(), collect)
        idiokit.pipe(rotate(), collect)

        return collect

    @idiokit.stream
    def _collect(self, room_name, compress):
        archive = None
        needs_flush = False

        try:
            while True:
                event = yield idiokit.next()

                if event is None:
                    if archive is not None and needs_flush:
                        archive.flush()
                        needs_flush = False
                elif event is True:
                    if archive is not None:
                        archive.flush()
                        archive.close()
                        yield compress.queue(0.0, _rename(archive.name))
                        archive = None

                    needs_flush = False
                    archive = open_archive(self.archive_dir, time.time(), room_name)
                    self.log.info("Opened archive {0!r}".format(archive.name))
                elif archive is not None:
                    json_dict = dict((key, event.values(key)) for key in event.keys())
                    archive.write(json.dumps(json_dict) + os.linesep)
                    needs_flush = True
        finally:
            if archive is not None:
                archive.flush()
                archive.close()
                self.log.info("Closed archive {0!r}".format(archive.name))

    @idiokit.stream
    def _compress(self, queue):
        while True:
            compress_path = yield queue.wait()

            path = yield idiokit.thread(compress, compress_path)
            if path:
                self.log.info("Compressed archive {0!r}".format(path))
            else:
                self.log.error("Invalid path {0!r}".format(compress_path))


if __name__ == "__main__":
    ArchiveBot.from_command_line().execute()
