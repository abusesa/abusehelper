import os
import csv
import sys
import inspect
import logging
import optparse
import traceback
import cPickle as pickle

class ParamError(Exception):
    pass

class Param(object):
    NO_VALUE = object()
    nargs = 1
    param_order = 0

    def __init__(self, help=None, short=None, default=NO_VALUE):
        self.short = short
        self.help = help
        self.default = default

        self.order = Param.param_order
        Param.param_order += 1

    def is_visible(self):
        return True

    def has_default(self):
        return self.default is not self.NO_VALUE

    def parse(self, value):
        return value

class ListParam(Param):
    def __init__(self, *args, **keys):
        self.type = keys.pop("type", Param())
        Param.__init__(self, *args, **keys)

    def parse(self, value):
        try:
            for row in csv.reader([value]):
                split = filter(None, map(str.strip, row))
                return map(self.type.parse, split)
        except csv.Error, error:
            raise ParamError("not a valid comma separated list: %r" % value)

class BoolParam(Param):
    nargs = 0

    def __init__(self, *args, **keys):
        keys.setdefault("default", False)
        Param.__init__(self, *args, **keys)

    def parse(self, value=None):
        if value is None:
            return not self.default
        if value.lower() in ["on", "yes", "1", "true"]:
            return True
        if value.lower() in ["off", "no", "0", "false"]:
            return False
        raise ParamError("not a valid boolean value: %r" % value)

class IntParam(Param):
    def parse(self, value):
        try:
            return int(value)
        except ValueError:
            raise ParamError("not a valid integer value: %r" % value)

class _InternalParam(BoolParam):
    def is_visible(self):
        return False

def optparse_name(name):
    return name.replace("_", "-")

def optparse_callback(option, opt_str, value, parser, callback, parsed):
    try:
        parsed[option.dest] = callback(value)
    except ParamError, error:
        message = "option " + opt_str + ": " + error.args[0]
        raise optparse.OptionValueError(message)

class LineFormatter(logging.Formatter):
    def __init__(self):
        format = "%(asctime)s %(name)s[%(process)d] %(levelname)s %(message)s"
        date_format = "%Y-%m-%d %H:%M:%S"
        logging.Formatter.__init__(self, format, date_format)

    def format(self, record):
        lines = list()

        msg = record.msg
        args = record.args
        try:
            for line in record.getMessage().splitlines(True):
                record.msg = line
                record.args = ()
                lines.append(logging.Formatter.format(self, record))
        finally:
            record.msg = msg
            record.args = args

        return "".join(lines)

class Bot(object):
    log_file = Param("write logs to the given path (default: log to stdout)",
                     default=None)
    read_config_pickle_from_stdin = _InternalParam("internal use only, "+
                                                   "bot should read its "+
                                                   "configuration from stdin "+
                                                   "as a Python pickle")

    class __metaclass__(type):
        def __new__(cls, name, parents, keys):
            bot_name = Param("name for the bot (default=%default)",
                             default=name)
            bot_name.order = -1
            keys.setdefault("bot_name", bot_name)
            return type.__new__(cls, name, parents, keys)

    @classmethod
    def params(cls):
        params = list()
        for name, value in inspect.getmembers(cls):
            if not isinstance(value, Param):
                continue
            params.append((name, value))

        keys = dict()
        orders = dict()
        for base in inspect.getmro(cls):
            for name, value in inspect.getmembers(base):
                if not isinstance(value, Param):
                    continue

                bites = list(name.split("_"))
                keys[name] = list()

                for i in range(len(bites)):
                    key = tuple(bites[:i+1])
                    keys[name].append(key)
                    orders[key] = min(orders.get(key, value.order), value.order)

        return sorted(params, key=lambda x: tuple(map(orders.get, keys[x[0]])))

    @classmethod
    def param_defaults(cls):
        return dict((name, param.default)
                    for (name, param) in cls.params()
                    if param.has_default())

    @classmethod
    def params_from_command_line(cls, argv=None):
        import optparse

        parser = optparse.OptionParser()
        parsed = dict()

        usage = ["Usage: %prog [options]"]
        positional = list()
        for name, param in cls.params():
            if not param.has_default() and param.is_visible():
                usage.append(name)
                positional.append((name, param))
        parser.set_usage(" ".join(usage))

        for name, param in cls.params():
            args = ["--" + optparse_name(name)]
            if param.short is not None:
                args = ["-" + optparse_name(param.short)]

            help = param.help
            if not param.is_visible():
                help = optparse.SUPPRESS_HELP

            kwargs = dict(default=param.default,
                          help=help,
                          metavar=name,
                          dest=name,
                          action="callback",
                          type="string" if param.nargs else None,
                          nargs=param.nargs,
                          callback=optparse_callback,
                          callback_args=(param.parse, parsed))
            parser.add_option(*args, **kwargs)

        _, args = parser.parse_args(argv)
        for (name, param), value in zip(positional, args):
            if name in parsed:
                continue

            try:
                parsed[name] = param.parse(value)
            except ParamError:
                message = "parameter " + name + ": " + error.args[0]
                parser.error(message)

        return parser, parsed

    @classmethod
    def from_command_line(cls, argv=None):
        default = cls.param_defaults()
        parser, cli = cls.params_from_command_line(argv)

        if cli.get("read_config_pickle_from_stdin", False):
            conf = dict(pickle.load(sys.stdin))
            for name, param in cls.params():
                if name not in conf:
                    continue
                value = conf[name]
                if isinstance(value, basestring):
                    try:
                        value = param.parse(value)
                    except ParamError, error:
                        message = "startup parameter " + name + ": " + error.args[0]
                        parser.error(message)
                default[name] = value

        default.update(cli)
        for name, param in cls.params():
            if name not in default:
                parser.error("no value for parameter " + name)

        return cls(**default)

    def __init__(self, **keys):
        for name, param in self.params():
            if name in keys:
                value = keys.pop(name)
            elif param.has_default():
                value = param.default
            else:
                raise TypeError("missing keyword argument %r" % name)
            setattr(self, name, value)

        if keys:
            name = keys.keys()[0]
            raise TypeError("got an unexpected keyword argument %r" % name)

        self.log = self.create_logger()

    def create_logger(self):
        logger = logging.getLogger(self.bot_name)
        logger.setLevel(logging.INFO)

        if self.log_file is None:
            handler = logging.StreamHandler()
        else:
            handler = logging.FileHandler(self.log_file)
        handler.setFormatter(LineFormatter())
        handler.setLevel(logging.INFO)

        logger.addHandler(handler)
        return log.EventLogger(logger)

    def execute(self):
        try:
            return self.run()
        except SystemExit:
            raise
        except:
            self.log.critical(traceback.format_exc())
            sys.exit(1)

    def run(self):
        pass

import time
import getpass
import collections

import idiokit
from idiokit import timer
from idiokit.xmpp import connect
from abusehelper.core import log

@idiokit.stream
def output_rate_limiter(rate):
    queue = collections.deque()

    while True:
        msg = yield idiokit.next()

        now = time.time()
        queue.append(now + 1.0)

        while True:
            while queue and now > queue[0]:
                queue.popleft()

            if not queue or len(queue) <= rate:
                break

            yield timer.sleep(queue[0] - now)
            now = time.time()

        yield idiokit.send(msg)

class XMPPBot(Bot):
    xmpp_jid = Param("the XMPP JID (e.g. xmppuser@xmpp.example.com)")
    xmpp_password = Param("the XMPP password", default=None)
    xmpp_host = Param("the XMPP service host (default: autodetect)",
                      default=None)
    xmpp_port = IntParam("the XMPP service port (default: autodetect)",
                         default=None)
    xmpp_extra_ca_certs = Param("a PEM formatted file of CAs to be used "+
                                "in addition to the system CAs", default=None)
    xmpp_ignore_cert = BoolParam("do not perform any verification "+
                                 "for the XMPP service's SSL certificate")
    xmpp_rate_limit = IntParam("how many XMPP stanzas the bot can send per "+
                               "second (default: no limit)", default=None)

    def __init__(self, **keys):
        Bot.__init__(self, **keys)

        if self.xmpp_password is None:
            self.xmpp_password = getpass.getpass("XMPP password: ")

    def run(self):
        return idiokit.main_loop(self.main())

    @idiokit.stream
    def main(self):
        yield idiokit.consume()

    @idiokit.stream
    def xmpp_connect(self):
        verify_cert = not self.xmpp_ignore_cert

        if self.xmpp_rate_limit is not None:
            limiter = output_rate_limiter(self.xmpp_rate_limit)
        else:
            limiter = None

        self.log.info("Connecting to XMPP service with JID %r", self.xmpp_jid)
        xmpp = yield connect(self.xmpp_jid,
                             self.xmpp_password,
                             host=self.xmpp_host,
                             port=self.xmpp_port,
                             rate_limiter=limiter,
                             ssl_verify_cert=verify_cert,
                             ssl_ca_certs=self.xmpp_extra_ca_certs)
        self.log.info("Connected to XMPP service with JID %r", self.xmpp_jid)
        yield xmpp.core.presence()
        idiokit.stop(xmpp)

from abusehelper.core import services

class _Service(services.Service):
    def __init__(self, bot, *args, **keys):
        services.Service.__init__(self, *args, **keys)
        self.bot = bot

    def main(self, *args, **keys):
        return self.bot.main(*args, **keys)

    def session(self, *args, **keys):
        return self.bot.session(*args, **keys)

from abusehelper.core import version

class ServiceBot(XMPPBot):
    bot_state_file = Param("save bot state to the given path "+
                           "(default: do not save state)",
                           default=None)
    service_room = Param("name of the multi user chat room used "+
                         "for bot control")
    service_mock_session = ListParam(default=None)

    @idiokit.stream
    def _run(self):
        ver_str = version.version_str()
        self.log.info("Starting service %r version %s", self.bot_name, ver_str)
        self.xmpp = yield self.xmpp_connect()

        service = _Service(self, self.bot_state_file)

        if self.service_mock_session is not None:
            keys = dict(item.split("=", 1)
                        for item in self.service_mock_session)
            self.log.info("Running a mock ression with keys %r" % keys)
            yield service.session(None, **keys) | service.run()
            return

        self.log.info("Joining lobby %r", self.service_room)
        self.lobby = yield services.join_lobby(self.xmpp,
                                               self.service_room,
                                               self.bot_name)
        self.log.addHandler(log.RoomHandler(self.lobby.room))

        self.log.info("Offering service %r", self.bot_name)
        try:
            yield self.lobby.offer(self.bot_name, service)
        finally:
            self.log.info("Retired service %r", self.bot_name)

    def run(self):
        @idiokit.stream
        def throw_stop_on_signal():
            try:
                yield idiokit.consume()
            except idiokit.Signal:
                raise services.Stop()
        return idiokit.main_loop(throw_stop_on_signal() | self._run())

    @idiokit.stream
    def main(self, state):
        try:
            yield idiokit.consume()
        except services.Stop:
            pass

    @idiokit.stream
    def session(self, state, **keys):
        try:
            yield idiokit.consume()
        except services.Stop:
            pass

from abusehelper.core import events, taskfarm

class FeedBot(ServiceBot):
    def __init__(self, *args, **keys):
        ServiceBot.__init__(self, *args, **keys)

        self._feeds = taskfarm.TaskFarm(self.manage_feed)
        self._rooms = taskfarm.TaskFarm(self.manage_room)
        self._dsts = taskfarm.Counter()

    def feed_keys(self, *args, **keys):
        yield ()

    @idiokit.stream
    def feed(self, *args, **keys):
        while True:
            yield idiokit.next()

    @idiokit.stream
    def session(self, state, dst_room, **keys):
        feeds = [self._rooms.inc(dst_room)]
        feed_keys = set(self.feed_keys(dst_room=dst_room, **keys))

        for key in feed_keys:
            self._dsts.inc(key, dst_room)
            feeds.append(self._feeds.inc(key))

        try:
            yield idiokit.pipe(*feeds)
        except services.Stop:
            idiokit.stop()
        finally:
            for key in feed_keys:
                self._dsts.dec(key, dst_room)

    def manage_feed(self, key):
        return idiokit.pipe(self.feed(*key),
                            self.augment(),
                            self._distribute(key))

    @idiokit.stream
    def manage_room(self, name):
        self.log.info("Joining room %r", name)
        room = yield self.xmpp.muc.join(name, self.bot_name)

        self.log.info("Joined room %r", name)
        try:
            yield (events.events_to_elements()
                   | self._stats(name)
                   | room
                   | idiokit.consume())
        finally:
            self.log.info("Left room %r", name)

    @idiokit.stream
    def _distribute(self, key):
        while True:
            event = yield idiokit.next()

            for name in self._dsts.get(key):
                room = self._rooms.get(name)
                if room is None:
                    continue
                yield room.send(event)

    def _stats(self, name, interval=60.0):
        def counter(event):
            counter.count += 1
            return (event,)
        counter.count = 0

        @idiokit.stream
        def logger():
            sleep = interval / 2.0

            while True:
                try:
                    yield timer.sleep(sleep)
                finally:
                    if counter.count > 0:
                        self.log.info("Sent %d events to room %r", counter.count, name)
                        counter.count = 0

                sleep = interval

        result = idiokit.map(counter)
        idiokit.pipe(logger(), result)
        return result

    def augment(self):
        return idiokit.map(lambda x: (x,))

import codecs
from hashlib import md5

_utf8encoder = codecs.getencoder("utf-8")

def event_hash(event):
    result = list()
    for key, value in sorted(event.items()):
        result.append(_utf8encoder(key)[0])
        result.append(_utf8encoder(value)[0])
    return md5("\x80".join(result)).digest()

class PollingBot(FeedBot):
    poll_interval = IntParam("wait at least the given amount of seconds "+
                             "before polling the data source again "+
                             "(default: %default seconds)", default=3600)

    def __init__(self, *args, **keys):
        FeedBot.__init__(self, *args, **keys)

        self._poll_queue = collections.deque()
        self._poll_dedup = dict()
        self._poll_cleanup = set()

    @idiokit.stream
    def poll(self, *args, **keys):
        yield timer.sleep(0.0)

    def feed_keys(self, *args, **keys):
        # Return (None,) instead of () for backwards compatibility.
        yield (None,)

    @idiokit.stream
    def manage_feed(self, key):
        if key not in self._poll_cleanup:
            self._poll_queue.appendleft((time.time(), key))
            self._poll_dedup.setdefault(key, dict())
        else:
            self._poll_cleanup.discard(key)

        try:
            yield idiokit.consume()
        finally:
            self._poll_cleanup.add(key)

    @idiokit.stream
    def main(self, state):
        try:
            while True:
                while not self._poll_queue or self._poll_queue[0][0] > time.time():
                    yield timer.sleep(1.0)

                _, key = self._poll_queue.popleft()
                if key in self._poll_cleanup:
                    self._poll_cleanup.remove(key)
                    self._poll_dedup.pop(key, None)
                    continue

                yield self.poll(*key) | self.augment() | self._distribute(key)

                expire_time = time.time() + self.poll_interval
                self._poll_queue.append((expire_time, key))
        except services.Stop:
            pass

    @idiokit.stream
    def _distribute(self, key):
        if key not in self._poll_dedup:
            self._poll_dedup[key] = dict()
        old_dedups = self._poll_dedup[key]
        new_dedups = self._poll_dedup[key] = dict()

        while True:
            event = yield idiokit.next()
            event_key = event_hash(event)

            for name in self._dsts.get(key):
                room = self._rooms.get(name)
                if room is None:
                    continue

                if event_key in new_dedups.get(room, ()):
                    continue
                new_dedups.setdefault(room, set()).add(event_key)

                if event_key in old_dedups.get(room, ()):
                    continue
                yield room.send(event)
