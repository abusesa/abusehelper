import os
from abusehelper.core import events, bot
import idiokit

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
            yield mtime, opened
        elif prev_size != size and prev_mtime != mtime:
            opened.seek(opened.tell())
            yield mtime, opened
        else:
            yield None

        prev_size = size
        prev_mtime = mtime
        prev_inode = inode

class TailBot(bot.FeedBot):
    path = bot.Param("path to the followed file")

    @idiokit.stream
    def feed(self):
        first = True

        for result in follow_file(self.path):
            yield idiokit.timer.sleep(2.0)

            if result is not None:
                mtime, opened = result
                if first:
                    opened.seek(0, os.SEEK_END)

                for line in opened:
                    keys = self.parse(line, mtime)
                    if keys is None:
                        continue

                    event = events.Event()
                    for key, value in keys.items():
                        event.add(key, value)
                    yield idiokit.send(event)

            first = False

    def parse(self, line, mtime):
        line = line.rstrip()
        if not line:
            return

        return {"line": line}

if __name__ == "__main__":
    TailBot.from_command_line().execute()

