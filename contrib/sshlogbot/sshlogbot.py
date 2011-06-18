import re
import os
import time

PARSE_REX = re.compile(" for\s+(\S+)(\s+from\s+(\S+)\s+port\s+(\d+))?")

def parse(string, base_time):
    """
    >>> parse("Jan 01 00:11:22 srv1 sshd[1000]: Accepted password for xxxx from 10.10.0.1 port 64000 ssh2", time.gmtime())
    >>> parse("Feb 22 11:22:33 srv1 sshd[2000]: Failed password for xxxx from 10.10.0.2 port 4550 ssh2", time.gmtime())
    >>> parse("Mar 30 22:33:44 srv1 sshd[3000]: fatal: Timeout before authentication for 10.10.0.3", time.gmtime())
    """

    bites = string.split(" ", 5)
    if len(bites) < 6:
        return None

    try:
        ts = time.strptime(" ".join(bites[:3]), "%b %d %H:%M:%S")
    except ValueError:
        return None

    if ts[1:] > base_time[1:]:
        ts = time.mktime((base_time[0]-1,) + ts[1:])
    else:
        ts = time.mktime((base_time[0],) + ts[1:])

    result = dict()
    result["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(ts))
    result["server"] = bites[3]

    match = PARSE_REX.search(bites[5])
    if match is not None:
        _for, group, _from, port = match.groups()
        if group is not None:
            result["user"] = _for
            result["ip"] = _from
            result["port"] = port
        else:
            result["ip"] = _for
        result["message"] = bites[5][:match.start()]
    else:
        result["message"] = bites[5]
    
    return result

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

from idiokit import threado, timer
from abusehelper.core import bot, events

def flush(inner):
    for _ in inner:
        pass

@threado.stream
def sleep(inner, delay):
    sleeper = timer.sleep(delay)

    while not sleeper.has_result():
        yield inner, sleeper
        flush(inner)

class SSHLogBot(bot.FeedBot):
    file = bot.Param()

    @threado.stream
    def feed(inner, self):
        first = True

        for result in follow_file(self.file):
            yield inner.sub(sleep(2.0))

            if result is not None:
                mtime, opened = result
                if first:
                    opened.seek(0, os.SEEK_END)

                for line in opened:
                    keys = parse(line, time.gmtime(mtime))
                    if keys is None:
                        continue

                    event = events.Event()
                    for key, value in keys.iteritems():
                        event.add(key, value)
                    inner.send(event)

                    yield flush(inner)

            first = False

if __name__ == "__main__":
    SSHLogBot.from_command_line().execute()
