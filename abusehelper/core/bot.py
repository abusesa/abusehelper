from __future__ import absolute_import

import os
import csv
import sys
import time
import getpass
import hashlib
import inspect
import logging
import warnings
import logging.handlers
import optparse
import traceback
import cPickle as pickle

import idiokit
from idiokit.xmpp import connect

from . import log, events, taskfarm, utils, services
from .. import __version__


class ParamError(Exception):
    pass


class Param(object):
    NO_VALUE = object()
    nargs = 1
    param_order = 0

    def __init__(self, help="", short=None, default=NO_VALUE):
        self.short = short
        self.help = inspect.cleandoc(help).strip()
        self.default = default

        self.order = Param.param_order
        Param.param_order += 1

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
        except csv.Error:
            raise ParamError("not a valid comma separated list: " + repr(value))


class BoolParam(Param):
    nargs = 0

    def __init__(self, help="", short=None):
        Param.__init__(self, help=help, short=short, default=False)

    def parse(self, value=None):
        if value is None:
            return not self.default
        if value.lower() in ["on", "yes", "1", "true"]:
            return True
        if value.lower() in ["off", "no", "0", "false"]:
            return False
        raise ParamError("not a valid boolean value: " + repr(value))


class IntParam(Param):
    def parse(self, value):
        try:
            return int(value)
        except ValueError:
            raise ParamError("not a valid integer value: " + repr(value))


class FloatParam(Param):
    def parse(self, value):
        try:
            return float(value)
        except ValueError:
            raise ParamError("not a valid floating point value: " + repr(value))


def optparse_name(name):
    return name.replace("_", "-")


def optparse_callback(option, opt_str, value, parser, callback, parsed):
    try:
        parsed[option.dest] = callback(value)
    except ParamError as error:
        message = "option " + opt_str + ": " + error.args[0]
        raise optparse.OptionValueError(message)


class LineFormatter(logging.Formatter):
    def __init__(self):
        logging.Formatter.__init__(
            self,
            "%(asctime)s %(name)s[%(process)d] %(levelname)s %(message)s",
            "%Y-%m-%d %H:%M:%SZ")

        self.converter = time.gmtime

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
    bot_name = Param("name for the bot (default=%default)")
    log_file = Param(
        "write logs to the given path (default: log to stdout)",
        default=None)
    log_level = IntParam(
        "logging level (default: logging.INFO)",
        default=logging.INFO
    )

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
                    key = tuple(bites[:i + 1])
                    keys[name].append(key)
                    orders[key] = min(orders.get(key, value.order), value.order)

        return sorted(params, key=lambda x: tuple(map(orders.get, keys[x[0]])))

    @classmethod
    def param_defaults(cls, **defaults):
        result = dict()
        for name, param in cls.params():
            if param.has_default():
                result[name] = param.default
            elif name == "bot_name":
                modulename = inspect.getmodulename(inspect.getfile(cls))
                result["bot_name"] = modulename
        result.update(defaults)
        return result

    @classmethod
    def _from_sys_argv(cls, params, **defaults):
        defaults = cls.param_defaults(**defaults)

        parser = optparse.OptionParser()
        parsed = dict()

        positional = []
        for name, param in params:
            if name not in defaults:
                positional.append((name, param))

        usage = ["Usage: %prog [options]"]
        for name, param in positional:
            usage.append(name)
        parser.set_usage(" ".join(usage))

        for name, param in params:
            args = ["--" + optparse_name(name)]
            if param.short is not None:
                args = ["-" + optparse_name(param.short)]

            parser.add_option(
                *args,
                default=defaults.get(name, None),
                help=param.help,
                metavar=name,
                dest=name,
                action="callback",
                type="string" if param.nargs else None,
                nargs=param.nargs,
                callback=optparse_callback,
                callback_args=(param.parse, parsed))

        _, args = parser.parse_args()
        for (name, param), value in zip(positional, args):
            if name in parsed:
                continue

            try:
                parsed[name] = param.parse(value)
            except ParamError as error:
                message = "parameter " + name + ": " + error.args[0]
                parser.error(message)

        for name, param in positional[len(args):]:
            parser.error("no value for parameter " + name)

        defaults.update(parsed)
        return dict((name, defaults[name]) for (name, _) in params)

    @classmethod
    def _from_dict(cls, params, **defaults):
        defaults = cls.param_defaults(**defaults)
        results = dict()

        for name, param in params:
            if name not in defaults:
                continue

            value = defaults[name]
            if isinstance(value, basestring):
                try:
                    value = param.parse(value)
                except ParamError as error:
                    raise ParamError("startup parameter " + name + ": " + error.args[0])
            results[name] = value

        return results

    @classmethod
    def from_command_line(cls, *args, **keys):
        params = list()
        for name, param in cls.params():
            if name not in keys:
                params.append((name, param))

        bot_name = inspect.getmodulename(inspect.stack()[1][1])

        if "ABUSEHELPER_CONF_FROM_STDIN" in os.environ:
            defaults = dict(pickle.load(sys.stdin))
            defaults.setdefault("bot_name", bot_name)
            added = cls._from_dict(params, **defaults)
        else:
            added = cls._from_sys_argv(params, bot_name=bot_name)

        added.update(keys)
        return cls(*args, **added)

    def __init__(self, *args, **keys):
        if len(args) == 1:
            raise TypeError("got an unexpected positional argument")
        elif len(args) > 1:
            raise TypeError("got unexpected positional arguments")

        for name, param in self.params():
            if name in keys:
                value = keys.pop(name)
            elif param.has_default():
                value = param.default
            else:
                raise TypeError("missing keyword argument " + repr(name))
            setattr(self, name, value)

        if keys:
            name = keys.keys()[0]
            raise TypeError("got an unexpected keyword argument " + repr(name))

        self.log = self.create_logger(self.log_level)

    def create_logger(self, log_level=logging.INFO):
        logger = logging.getLogger(self.bot_name)
        logger.setLevel(log_level)

        if self.log_file is None:
            handler = logging.StreamHandler()
        else:
            handler = logging.handlers.WatchedFileHandler(self.log_file)
        handler.setFormatter(LineFormatter())
        handler.setLevel(log_level)

        logger.addHandler(handler)
        return log.EventLogger(logger)

    def execute(self):
        def showwarning(message, category, filename, fileno, file=None, line=None):
            msg = warnings.formatwarning(message, category, filename, fileno, line)
            self.log.warning(msg.strip())

        with warnings.catch_warnings():
            warnings.simplefilter("always")
            warnings.showwarning = showwarning

            try:
                return self.run()
            except SystemExit:
                raise
            except:
                self.log.critical(traceback.format_exc().strip())
                sys.exit(1)

    def run(self):
        pass


class XMPPBot(Bot):
    xmpp_jid = Param("the XMPP JID (e.g. xmppuser@xmpp.example.com)")
    xmpp_password = Param(
        "the XMPP password",
        default=None)
    xmpp_host = Param(
        "the XMPP service host (default: autodetect)",
        default=None)
    xmpp_port = IntParam(
        "the XMPP service port (default: autodetect)",
        default=None)
    xmpp_extra_ca_certs = Param("""
        a PEM formatted file of CAs to be used in addition to the system CAs
        """, default=None)
    xmpp_ignore_cert = BoolParam("""
        do not perform any verification for the XMPP service's SSL certificate
        """)

    def __init__(self, *args, **keys):
        Bot.__init__(self, *args, **keys)

        if self.xmpp_password is None:
            self.xmpp_password = getpass.getpass("XMPP password: ")

    def run(self):
        return idiokit.main_loop(self.main())

    def main(self):
        return idiokit.consume()

    @idiokit.stream
    def xmpp_connect(self):
        verify_cert = not self.xmpp_ignore_cert

        self.log.info("Connecting to XMPP service with JID " + repr(self.xmpp_jid))
        xmpp = yield connect(
            self.xmpp_jid, self.xmpp_password,
            host=self.xmpp_host,
            port=self.xmpp_port,
            ssl_verify_cert=verify_cert,
            ssl_ca_certs=self.xmpp_extra_ca_certs)
        self.log.info("Connected to XMPP service with JID " + repr(self.xmpp_jid))
        idiokit.stop(xmpp)


class _Service(services.Service):
    def __init__(self, bot, *args, **keys):
        services.Service.__init__(self, *args, **keys)
        self.bot = bot

    def main(self, *args, **keys):
        return self.bot.main(*args, **keys)

    def session(self, *args, **keys):
        return self.bot.session(*args, **keys)


class ServiceBot(XMPPBot):
    bot_state_file = Param("""
        save bot state to the given path (default: do not save state)
        """, default=None)
    service_room = Param("""
        name of the multi user chat room used for bot control
        """)
    service_mock_session = ListParam(default=None)

    @idiokit.stream
    def _run(self):
        self.log.info("Starting service {0!r} version {1}".format(self.bot_name, __version__))
        self.xmpp = yield self.xmpp_connect()

        service = _Service(self, self.bot_state_file)

        if self.service_mock_session is not None:
            keys = dict(item.split("=", 1) for item in self.service_mock_session)
            self.log.info("Running a mock session with keys " + repr(keys))
            session = yield service.open_session(None, keys)
            yield session | service.run()
            return

        self.log.info("Joining lobby " + repr(self.service_room))
        self.lobby = yield services.join_lobby(self.xmpp, self.service_room, self.bot_name)
        self.log.addHandler(log.RoomHandler(self.lobby))

        self.log.info("Offering service " + repr(self.bot_name))
        try:
            yield self.lobby.offer(self.bot_name, service)
        finally:
            self.log.info("Retired service " + repr(self.bot_name))

    def run(self):
        @idiokit.stream
        def throw_stop_on_signal():
            try:
                yield idiokit.consume()
            except idiokit.Signal:
                raise services.Stop()
        return idiokit.main_loop(throw_stop_on_signal() | self._run())

    def main(self, state):
        return idiokit.consume()

    def session(self, state, **keys):
        return idiokit.consume()


class FeedBot(ServiceBot):
    xmpp_rate_limit = FloatParam("""
        how many XMPP stanzas the bot can send per second
        (default: no limiting)
        """, default=None)
    drop_older_than = IntParam("""
        drop events with source time older that given number of seconds
        """, default=None)

    def __init__(self, *args, **keys):
        ServiceBot.__init__(self, *args, **keys)

        self._feeds = taskfarm.TaskFarm(self.feed)
        self._rooms = taskfarm.TaskFarm(self.manage_room)
        self._connections = taskfarm.TaskFarm(self.manage_connection, grace_period=0.0)

        self._last_output = float("-inf")

    def feed_keys(self, *args, **keys):
        yield ()

    @idiokit.stream
    def feed(self, *args, **keys):
        while True:
            yield idiokit.next()

    @idiokit.stream
    def _cutoff(self):
        while True:
            event = yield idiokit.next()

            latest = None
            for value in event.values("source time"):
                try:
                    source_time = time.strptime(value, "%Y-%m-%d %H:%M:%SZ")
                except ValueError:
                    continue
                latest = max(latest, source_time)

            cutoff = time.gmtime(time.time() - self.drop_older_than)
            if latest and latest < cutoff:
                continue

            yield idiokit.send(event)

    @idiokit.stream
    def _output_rate_limiter(self):
        while self.xmpp_rate_limit <= 0.0:
            yield idiokit.sleep(60.0)

        while True:
            delta = max(time.time() - self._last_output, 0)
            delay = 1.0 / self.xmpp_rate_limit - delta
            if delay > 0.0:
                yield idiokit.sleep(delay)
            self._last_output = time.time()

            msg = yield idiokit.next()
            yield idiokit.send(msg)

    def session(self, state, dst_room, **keys):
        connections = []
        for feed_key in self.feed_keys(dst_room=dst_room, **keys):
            connections.append(self._connections.inc(feed_key, dst_room))

        if connections:
            return idiokit.pipe(*connections)
        return idiokit.consume()

    @idiokit.stream
    def manage_room(self, name):
        msg = "room {0!r}".format(name)
        attrs = events.Event({
            "type": "room",
            "service": self.bot_name,
            "sent events": "0",
            "room": name
        })

        with self.log.stateful(repr(self.xmpp.jid), "room", repr(name)) as log:
            log.open("Joining " + msg, attrs, status="joining")
            room = yield self.xmpp.muc.join(name, self.bot_name)

            log.open("Joined " + msg, attrs, status="joined")
            try:
                head = self.augment()
                if self.drop_older_than is not None:
                    head = self._cutoff() | head

                tail = self._stats(name) | room | idiokit.consume()
                if self.xmpp_rate_limit is not None:
                    tail = self._output_rate_limiter() | tail

                yield head | events.events_to_elements() | tail
            finally:
                log.close("Left " + msg, attrs, status="left")

    def manage_connection(self, feed_key, room_name):
        return self._feeds.inc(*feed_key) | self._rooms.inc(room_name)

    def _stats(self, name, interval=60.0):
        def counter(event):
            counter.count += 1
            return (event,)
        counter.count = 0

        @idiokit.stream
        def logger():
            while True:
                try:
                    yield idiokit.sleep(interval)
                finally:
                    if counter.count > 0:
                        self.log.info(
                            "Sent {0} events to room {1!r}".format(counter.count, name),
                            event=events.Event({
                                "type": "room",
                                "service": self.bot_name,
                                "sent events": unicode(counter.count),
                                "room": name}))
                        counter.count = 0

        result = idiokit.map(counter)
        idiokit.pipe(logger(), result)
        return result

    def augment(self):
        return idiokit.map(lambda x: (x,))


class PollSkipped(Exception):
    def __init__(self, reason):
        Exception.__init__(self, reason)

    @property
    def reason(self):
        return self.args[0]


class PollingBot(FeedBot):
    poll_interval = IntParam("""
        wait at least the given amount of seconds before polling
        the data source again (default: %default seconds)
        """, default=3600)
    ignore_initial_poll = BoolParam("""
        don't send out events collected during the first poll,
        just use them to populate the deduplication filter
        (WARNING: this is an experimental flag that may change
        or be removed without prior notice)
        """)

    def __init__(self, *args, **keys):
        FeedBot.__init__(self, *args, **keys)

        self._poll_queue = utils.WaitQueue()
        self._poll_dedup = dict()
        self._poll_cleanup = dict()

    @idiokit.stream
    def poll(self, *key):
        yield idiokit.sleep(0.0)

    @idiokit.stream
    def dedup(self, key):
        initial_poll = key not in self._poll_dedup

        old_filter = self._poll_dedup.setdefault(key, set())
        new_filter = set()

        while True:
            try:
                event = yield idiokit.next()
            except StopIteration:
                self._poll_dedup[key] = new_filter
                raise

            event_key = int(events.hexdigest(event, hashlib.md5), 16)
            if event_key not in old_filter:
                if not initial_poll or not self.ignore_initial_poll:
                    yield idiokit.send(event)
            old_filter.add(event_key)
            new_filter.add(event_key)

    @idiokit.stream
    def feed(self, *key):
        if key in self._poll_cleanup:
            node = self._poll_cleanup.pop(key)
            yield self._poll_queue.cancel(node)

        try:
            waiter = idiokit.Event()
            result = idiokit.Event()
            node = yield self._poll_queue.queue(0.0, (False, (waiter, result)))

            while True:
                try:
                    yield waiter
                finally:
                    yield self._poll_queue.cancel(node)

                try:
                    yield self.poll(*key) | self.dedup(key)
                except PollSkipped as skip:
                    self.log.info("Poll skipped: {0.reason}".format(skip))
                finally:
                    result.succeed()

                waiter = idiokit.Event()
                result = idiokit.Event()
                node = yield self._poll_queue.queue(self.poll_interval, (False, (waiter, result)))
        finally:
            node = yield self._poll_queue.queue(self.poll_interval, (True, key))
            self._poll_cleanup[key] = node

    @idiokit.stream
    def main(self, state):
        if state is None:
            state = dict()
        self._poll_dedup = state

        if self.ignore_initial_poll:
            self.log.info("Ignoring initial polls")

        try:
            for key in self._poll_dedup:
                node = yield self._poll_queue.queue(self.poll_interval, (True, key))
                self._poll_cleanup[key] = node

            while True:
                cleanup, arg = yield self._poll_queue.wait()
                if cleanup:
                    self._poll_dedup.pop(arg, None)
                    self._poll_cleanup.pop(arg, None)
                else:
                    waiter, result = arg
                    waiter.succeed()
                    yield result
        except services.Stop:
            idiokit.stop(self._poll_dedup)
