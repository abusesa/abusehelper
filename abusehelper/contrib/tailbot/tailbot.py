import os
import time
import errno
import idiokit
from abusehelper.core import events, bot, utils


def read(fd, amount=4096):
    try:
        data = os.read(fd, amount)
    except OSError as ose:
        if ose.args[0] != errno.EAGAIN:
            raise
        data = ""
    return data


def try_seek(fd, offset):
    try:
        if offset is None:
            os.lseek(fd, 0, os.SEEK_END)
        elif offset >= 0:
            os.lseek(fd, offset)
        else:
            os.lseek(fd, offset, os.SEEK_END)
    except OSError as ose:
        if ose.args[0] != errno.ESPIPE:
            raise


def follow_file(filename):
    while True:
        try:
            fd = os.open(filename, os.O_RDONLY | os.O_NONBLOCK)
        except OSError:
            yield None
            continue

        try:
            inode = os.fstat(fd).st_ino
            first = True

            while True:
                try:
                    stat = os.stat(filename)
                except OSError:
                    stat = None

                yield first, time.time(), fd
                if stat is None or inode != stat.st_ino:
                    break

                first = False
        finally:
            os.close(fd)


def tail_file(filename, offset=None):
    first = True
    buffer = []

    for result in follow_file(filename):
        if first and result is not None:
            _, _, fd = result
            try_seek(fd, offset)
        first = False

        if result is None:
            yield None
            continue

        flush, mtime, fd = result
        if flush and buffer:
            buffer = []

        while True:
            data = read(fd)
            if not data:
                break

            lines = data.split("\n")
            if len(lines) <= 1:
                buffer.extend(lines)
                continue

            lines[0] = "".join(buffer) + lines[0]
            for line in lines[:-1]:
                if line.endswith("\r"):
                    line = line[:-1]
                yield mtime, line

            if not lines[-1]:
                buffer = []
            else:
                buffer = lines[-1:]

        yield None


class TailBot(bot.FeedBot):
    path = bot.Param("path to the followed file")
    offset = bot.IntParam("file offset", default=None)

    @idiokit.stream
    def feed(self):
        for result in tail_file(self.path, self.offset):
            if result is None:
                yield idiokit.sleep(2.0)
                continue

            mtime, line = result
            keys = self.parse(line, mtime)
            if keys is None:
                continue

            event = events.Event()
            for key, value in keys.items():
                event.add(key, value)
            yield idiokit.send(event)

    def parse(self, line, mtime):
        line = line.rstrip()
        if not line:
            return

        line = utils.force_decode(line)
        return {"line": line}


if __name__ == "__main__":
    TailBot.from_command_line().execute()
