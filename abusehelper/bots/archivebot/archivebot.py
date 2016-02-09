import os
import re
import gzip
import json
import time
import errno
import random
import urllib
import contextlib

from datetime import datetime

import idiokit
from idiokit.xmpp.jid import JID
from abusehelper.core import bot, events, taskfarm, utils


def _create_compress_path(path):
    head, tail = os.path.split(path)

    while True:
        new_tail = "{0}.compress-{1:08x}".format(tail, random.getrandbits(32))
        new_path = os.path.join(head, new_tail)

        if not os.path.isfile(new_path):
            return new_path


def _split_compress_path(path):
    r"""
    Return the rotated file path split to the (directory, filename) tuple, where
    the temporary .compress-******** part has been removed from the filename.

    >>> _split_compress_path("path/to/test.json.compress-0123abcd")
    ('path/to', 'test.json')

    Raise ValueError for paths that don not look like rotated files.

    >>> _split_compress_path("path/to/test.json")
    Traceback (most recent call last):
        ...
    ValueError: invalid filename path/to/test.json
    """

    directory, filename = os.path.split(path)

    match = re.match(r"^(.*)\.compress-[0-9a-f]{8}$", filename, re.I)
    if match is None:
        raise ValueError("invalid filename {0}".format(path))

    filename = match.group(1)
    return directory, filename


def _is_compress_path(path):
    r"""
    Return True if path is a valid rotated file path, False otherwise.

    >>> _is_compress_path("path/to/test.json.compress-1234abcd")
    True
    >>> _is_compress_path("path/to/test.json")
    False
    """

    try:
        _split_compress_path(path)
    except ValueError:
        return False
    return True


@contextlib.contextmanager
def _unique_writable_file(directory, prefix, suffix):
    count = 0
    path = os.path.join(directory, "{0}{1}".format(prefix, suffix))

    while True:
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
        try:
            fd = os.open(path, flags)
        except OSError as ose:
            if ose.errno != errno.EEXIST:
                raise
            count += 1
            path = os.path.join(directory, "{0}-{1:08d}{2}".format(prefix, count, suffix))
        else:
            break

    try:
        fileobj = os.fdopen(fd, "wb")
    except:
        os.close(fd)
        os.remove(path)
        raise

    try:
        yield path, fileobj
    finally:
        fileobj.close()


def _ensure_dir(dir_name):
    r"""
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


def _archive_path(ts, room_name):
    gmtime = time.gmtime(ts)

    return os.path.join(
        room_name,
        time.strftime("%Y", gmtime),
        time.strftime("%m", gmtime),
        time.strftime("%d.json", gmtime)
    )


def _open_archive(archive_dir, ts, room_name):
    path = os.path.join(archive_dir, _archive_path(ts, room_name))
    dirname = os.path.dirname(path)
    _ensure_dir(dirname)
    return open(path, "ab", buffering=1)


def _encode_room_jid(jid):
    r"""
    Return a sanitized and normalized path name for a bare room JID.

    The a argument should be a unicode string, a byte string or an
    idiokit.xmpp.jid.JID instance.

    >>> _encode_room_jid(u"room.subroom@example.com")
    'room.subroom@example.com'

    >>> _encode_room_jid(u"room.subroom@example.com")
    'room.subroom@example.com'

    >>> _encode_room_jid(JID("room.subroom@example.com"))
    'room.subroom@example.com'

    The argument should be a "bare JID", i.e. contain only the node@domain
    part. Otherwise a ValueError will get raised.

    >>> _encode_room_jid("room.subroom@example.com/resource")
    Traceback (most recent call last):
        ...
    ValueError: given room JID does not match with the bare room JID

    Byte strings will be first converted to unicode with the default "ascii"
    encoding. UnicodeDecodeError will be raised on failure.

    >>> _encode_room_jid(u"room.caf\xe9.subroom@example.com")
    'room.caf%C3%A9.subroom@example.com'

    >>> _encode_room_jid("room.caf\xe9.subroom@example.com")
    Traceback (most recent call last):
        ...
    UnicodeDecodeError: 'ascii' codec can't decode byte 0xe9 in position 8: ordinal not in range(128)
    """

    room_jid = JID(jid)

    if room_jid != room_jid.bare():
        raise ValueError("given room JID does not match with the bare room JID")

    return urllib.quote(unicode(room_jid).encode("utf-8"), safe=" @")


def _rename(path):
    new_path = _create_compress_path(path)
    os.rename(path, new_path)
    return new_path


def _compress(path):
    with open(path, "rb") as archive:
        directory, filename = _split_compress_path(path)
        prefix, suffix = os.path.splitext(filename)

        with _unique_writable_file(directory, prefix, suffix + ".gz") as (gz_path, gz_file):
            compressed = gzip.GzipFile(fileobj=gz_file)
            try:
                compressed.writelines(archive)
            finally:
                compressed.close()

    try:
        os.remove(path)
    except OSError:
        pass

    return gz_path


class ArchiveBot(bot.ServiceBot):
    archive_dir = bot.Param("directory where archive files are written")

    def __init__(self, *args, **keys):
        super(ArchiveBot, self).__init__(*args, **keys)

        self.rooms = taskfarm.TaskFarm(self._handle_room, grace_period=0.0)
        self.archive_dir = _ensure_dir(self.archive_dir)

    @idiokit.stream
    def session(self, state, src_room):
        src_jid = yield self.xmpp.muc.get_full_room_jid(src_room)
        yield self.rooms.inc(src_jid.bare())

    @idiokit.stream
    def _handle_room(self, name):
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
                yield idiokit.pipe(
                    room,
                    events.stanzas_to_events(),
                    self._archive(room.jid.bare())
                )
            finally:
                log.close("Left " + msg, attrs, status="left")

    def _archive(self, room_bare_jid):
        compress = utils.WaitQueue()
        room_name = _encode_room_jid(room_bare_jid)

        _dir = os.path.join(self.archive_dir, room_name)

        if _dir != os.path.normpath(_dir):
            raise ValueError("incorrect room name lands outside the archive directory")

        for root, _, filenames in os.walk(_dir):
            for filename in filenames:
                path = os.path.join(root, filename)
                if _is_compress_path(path):
                    compress.queue(0.0, path)

        return idiokit.pipe(
            self._collect(room_name, compress),
            self._compress(compress)
        )

    @idiokit.stream
    def _collect(self, room_name, compress):
        event = yield idiokit.next()

        while True:
            current = datetime.utcnow().day

            with _open_archive(self.archive_dir, time.time(), room_name) as archive:
                self.log.info("Opened archive {0!r}".format(archive.name))

                while current == datetime.utcnow().day:
                    json_dict = dict((key, event.values(key)) for key in event.keys())
                    archive.write(json.dumps(json_dict) + os.linesep)

                    event = yield idiokit.next()

            yield compress.queue(0.0, _rename(archive.name))

    @idiokit.stream
    def _compress(self, queue):
        while True:
            compress_path = yield queue.wait()

            try:
                path = yield idiokit.thread(_compress, compress_path)
                self.log.info("Compressed archive {0!r}".format(path))
            except ValueError:
                self.log.error("Invalid path {0!r}".format(compress_path))


if __name__ == "__main__":
    ArchiveBot.from_command_line().execute()
