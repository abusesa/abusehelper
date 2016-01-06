import os
import uuid
import fcntl
import errno
import idiokit
import itertools
import contextlib
import email
import email.header
from abusehelper.core import bot, utils
from . import _load_callable, _CallableParam


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
            return email.message_from_file(fp)
    except IOError as ioe:
        if ioe.errno != errno.ENOENT:
            raise
    return None


def get_header(headers, key, default=None):
    value = headers.get(key, None)
    if value is None:
        return default

    bites = []
    for string, encoding in email.header.decode_header(value):
        if encoding is not None:
            string = string.decode(encoding, "replace")
        bites.append(string)

    return u" ".join(bites)


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
    handler = _CallableParam()
    input_dir = bot.Param()
    work_dir = bot.Param()
    concurrency = bot.IntParam(default=1)
    poll_interval = bot.FloatParam(default=1)

    def __init__(self, *args, **keys):
        bot.FeedBot.__init__(self, *args, **keys)

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

            subject = get_header(msg, "Subject", "<no subject>")
            sender = get_header(msg, "From", "<unknown sender>")
            self.log.info(u"Handler #{0} handling mail '{1}' from {2}".format(nth_concurrent, subject, sender))

            handler = self.handler(self.log)
            yield handler.handle(msg)

            os.rename(input_name, output_name)
            self.log.info(u"Handler #{0} done with mail '{1}' from {2}".format(nth_concurrent, subject, sender))


if __name__ == "__main__":
    import json
    import logging
    import optparse

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%SZ"
    )

    @idiokit.stream
    def print_events():
        while True:
            event = yield idiokit.next()

            json_dict = {}
            for key in event.keys():
                values = event.values(key)
                if len(values) == 1:
                    json_dict[key] = values[0]
                else:
                    json_dict[key] = list(values)
            print json.dumps(json_dict)

    parser = optparse.OptionParser()
    parser.set_usage("usage: %prog [options] handler [dirname ...]")

    options, args = parser.parse_args()

    if len(args) < 1:
        parser.error("expected handler")
    handler_class = _load_callable(args[0])

    for arg in args[1:]:
        for dirname, filename in iter_dir(arg):
            orig_name = os.path.join(dirname, filename)
            msg = try_read_message(orig_name)
            if msg is None:
                logging.info("skipped '{0}' (could not open)".format(orig_name))
                continue

            logging.info("handling '{0}'".format(orig_name))
            handler = handler_class(logging)
            idiokit.main_loop(handler.handle(msg) | print_events())
            logging.info("done with '{0}'".format(orig_name))
