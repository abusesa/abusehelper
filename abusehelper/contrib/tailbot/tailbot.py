import os
import time
import idiokit
from abusehelper.core import events, bot, utils

def follow_file(filename):
    prev_inode = None
    prev_size = None
    prev_mtime = None
    opened = None

    while True:
        try:
            stat = os.stat(filename)
        except OSError:
            if opened is not None:
                opened.close()
                opened = None
            yield None
            prev_inode = prev_size = prev_mtime = None
            continue

        inode, size, mtime = stat[1], stat[6], stat[8]

        if inode != prev_inode:
            prev_inode = prev_size = prev_mtime = None
            if opened is not None:
                opened.close()
                opened = None

            try:
                opened = open(filename, "rb")
            except IOError:
                yield None
                prev_inode = prev_size = prev_mtime = None
                continue
            yield True, mtime, opened
        elif prev_size != size and prev_mtime != mtime:
            opened.seek(opened.tell())
            yield False, mtime, opened
        else:
            yield None

        prev_size = size
        prev_mtime = mtime
        prev_inode = inode


def tail_file(filename, offset=None):
    first = True
    buffer = []

    for result in follow_file(filename):
        if first and result is not None:
            _, _, opened = result

            if offset is None:
                opened.seek(0, os.SEEK_END)
            elif offset >= 0:
                opened.seek(offset)
            else:
                opened.seek(offset, os.SEEK_END)
        first = False

        if result is None:
            yield None
            continue

        flush, mtime, opened = result
        if flush and buffer:
            buffer = []

        while True:
            data = opened.read(4096)
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

def tail_fifo(filename, offset=None):
    buffer = []
    fd = os.open(filename, os.O_RDONLY | os.O_NONBLOCK)

    while True:
        data = os.read(fd, 4096)
        if not data:
            yield None
            continue

        lines = data.split("\n")
        if len(lines) <= 1:
            buffer.extend(lines)
            continue

        lines[0] = "".join(buffer) + lines[0]
        for line in lines[:-1]:
            if line.endswith("\r"):
                line = line[:-1]
            yield int(time.time()), line

        if not lines[-1]:
            buffer = []
        else:
            buffer = lines[-1:]

    yield None


class TailBot(bot.FeedBot):
    path = bot.Param("path to the followed file")
    offset = bot.IntParam("file offset", default=None)
    is_named_pipe = bot.BoolParam("followed file is named pipe")

    @idiokit.stream
    def feed(self):
        tail_func = tail_fifo if self.is_named_pipe else tail_file
        for result in tail_func(self.path, self.offset):
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

