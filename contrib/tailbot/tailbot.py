import os
from abusehelper.core import events, bot
from idiokit import threado, timer

class TailBot(bot.FeedBot):
    path=bot.Param("Path to file.")

    def open(self, path):
        try:
            return os.open(path, os.O_RDONLY)
        except IOError, e:
            self.log.info("Failed to open file %s", path)
            raise IOError, e

    @threado.stream
    def feed(inner, self):
        fileobj = self.open(self.path)
        stats = os.fstat(fileobj)
        old_inode = stats[1]
        old_size = stats[6]
        old_mtime = stats[8]

        count = 0
        while True:
            yield inner, timer.sleep(1)

            stats = os.fstat(fileobj)
            inode = stats[1]
            size = stats[6]
            mtime = stats[8]

            if old_inode != inode:
                old_inode = inode
                old_size = 0
            elif old_mtime == mtime:
                #If file doesn't change, reopen it to see if inode is changed.
                count += 1
                if count >= 5:
                    count = 0
                    os.close(fileobj)
                    fileobj = self.open(self.path)
                continue
            elif size < old_size:
                old_size = 0

            os.lseek(fileobj, old_size, 0)
            data = os.read(fileobj, size-old_size)
            for line in data.split("\n"):
                event = self.parse(unicode(line.decode("utf-8")))
                if event:
                    yield inner.send(event)

            count = 0
            old_size = size
            old_mtime = mtime

        os.close(fileobj)

    def parse(self, line):
        if not line:
            return 

        event = events.Event()
        event.add("line", line)
        return event

if __name__ == "__main__":
    TailBot.from_command_line().execute()

