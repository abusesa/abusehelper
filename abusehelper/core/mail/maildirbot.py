import os
import uuid
import fcntl
import errno
import idiokit
import itertools
import contextlib
from abusehelper.core import bot, utils
from .message import message_from_string, escape_whitespace
from . import HandlerParam, load_handler


def try_rename(from_name, to_name):
    try:
        os.rename(from_name, to_name)
    except OSError as ose:
        if ose.errno != errno.ENOENT:
            raise
        return False
    return True


def try_read_message(path):
    try:
        with open(path, "rb") as fp:
            return message_from_string(fp.read())
    except IOError as ioe:
        if ioe.errno != errno.ENOENT:
            raise
    return None


def makedirs(*args, **keys):
    try:
        os.makedirs(*args, **keys)
    except OSError as ose:
        if ose.errno != errno.EEXIST:
            raise


def iter_dir(dirname):
    try:
        dirlist = os.listdir(dirname)
    except OSError as ose:
        if ose.errno != errno.ENOENT:
            raise
        return

    for filename in dirlist:
        yield dirname, filename


@contextlib.contextmanager
def lockfile(filename):
    with open(filename, "wb") as opened:
        fd = opened.fileno()
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except IOError as ioe:
            if ioe.errno not in (errno.EACCES, errno.EAGAIN):
                raise
            yield False
        else:
            try:
                yield True
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)


class MailDirBot(bot.FeedBot):
    handler = HandlerParam()
    input_dir = bot.Param()
    work_dir = bot.Param()
    concurrency = bot.IntParam(default=1)
    poll_interval = bot.FloatParam(default=1)

    def __init__(self, *args, **keys):
        bot.FeedBot.__init__(self, *args, **keys)

        self.handler = load_handler(self.handler)

        self._queue = utils.WaitQueue()

    def feed_keys(self, *args, **keys):
        for nth_concurrent in range(1, self.concurrency + 1):
            yield (nth_concurrent,)

    def run(self):
        makedirs(self.work_dir)

        with lockfile(os.path.join(self.work_dir, ".lock")) as success:
            if not success:
                self.log.error(u"Someone else is using the directory {0}".format(self.work_dir))
            else:
                bot.FeedBot.run(self)

    @idiokit.stream
    def _poll_files(self):
        in_progress = os.path.join(self.work_dir, "in-progress")
        done = os.path.join(self.work_dir, "done")

        makedirs(in_progress)
        makedirs(done)

        for dirname, filename in iter_dir(in_progress):
            input_name = os.path.join(dirname, filename)
            output_name = os.path.join(done, filename)
            yield idiokit.send(input_name, output_name)

        while True:
            paths = itertools.chain(
                iter_dir(os.path.join(self.input_dir, "new")),
                iter_dir(os.path.join(self.input_dir, "cur"))
            )

            for dirname, filename in paths:
                uuid_name = uuid.uuid4().hex + "." + filename
                input_name = os.path.join(in_progress, uuid_name)
                output_name = os.path.join(done, uuid_name)
                if try_rename(os.path.join(dirname, filename), input_name):
                    yield idiokit.send(input_name, output_name)

            yield idiokit.sleep(self.poll_interval)

    @idiokit.stream
    def _forward_files(self):
        while True:
            input_name, output_name = yield idiokit.next()

            ack = idiokit.Event()
            node = yield self._queue.queue(0, (input_name, output_name, ack))
            try:
                yield ack
            finally:
                yield self._queue.cancel(node)

    @idiokit.stream
    def main(self, state):
        yield self._poll_files() | self._forward_files()

    @idiokit.stream
    def feed(self, nth_concurrent):
        while True:
            input_name, output_name, ack = yield self._queue.wait()
            ack.succeed()

            msg = try_read_message(input_name)
            if msg is None:
                continue

            subject = escape_whitespace(msg.get_unicode("Subject", "<no subject>", errors="replace"))
            sender = escape_whitespace(msg.get_unicode("From", "<unknown sender>", errors="replace"))
            self.log.info(u"Handler #{0} handling mail '{1}' from {2}".format(nth_concurrent, subject, sender))

            handler = self.handler(log=self.log)
            yield handler.handle(msg)

            os.rename(input_name, output_name)
            self.log.info(u"Handler #{0} done with mail '{1}' from {2}".format(nth_concurrent, subject, sender))


if __name__ == "__main__":
    MailDirBot.from_command_line().execute()
