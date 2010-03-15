import os
import csv
import sys
import inspect
import logging
import optparse
import traceback
import cPickle as pickle
from ConfigParser import SafeConfigParser

class ConfigParser(SafeConfigParser):
    def __init__(self, filename):
        filename = os.path.abspath(filename)
        directory, _ = os.path.split(filename)
        SafeConfigParser.__init__(self, dict(__dir__=directory))

        opened = open(filename, "r")
        try:
            self.readfp(opened)
        finally:
            opened.close() 

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
    ini_file = Param("INI file used for configuration", 
                     default=None)
    ini_section = Param("INI section used for configuration "+
                        "(default: bot's name)",
                        default=None)
    log_file = Param(default=None)
    startup = BoolParam(default=None)

    class __metaclass__(type):
        def __new__(cls, name, parents, keys):
            bot_name = Param("Name for the bot (default=%default)",
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
            if not param.has_default():
                usage.append(name)
                positional.append((name, param))
        parser.set_usage(" ".join(usage))

        for name, param in cls.params():
            args = ["--" + optparse_name(name)]
            if param.short is not None:
                args = ["-" + optparse_name(param.short)]

            kwargs = dict(default=param.default,
                          help=param.help,
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

        if cli.get("startup", False):
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

        ini_file = cli.get("ini_file", None)
        if ini_file is not None:
            ini_section = cli.get("ini_section", None)
            if ini_section is None:
                ini_section = cli.get("bot_name", default["bot_name"])
            
            config = ConfigParser(ini_file)
            for name, param in cls.params():
                if config.has_option(ini_section, name):
                    try:
                        value = config.get(ini_section, name)
                        default[name] = param.parse(value)
                    except ParamError, error:
                        message = "parameter " + name + ": " + error.args[0]
                        parser.error(message)

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
        return logger

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

import getpass
from idiokit import threado
from idiokit.xmpp import connect
from abusehelper.core import log

class XMPPBot(Bot):
    xmpp_jid = Param("the XMPP JID (e.g. xmppuser@xmpp.example.com)")
    xmpp_password = Param("the XMPP password", 
                          default=None)
    
    def __init__(self, **keys):
        Bot.__init__(self, **keys)

        if self.xmpp_password is None:
            self.xmpp_password = getpass.getpass("XMPP password: ")

    def run(self):
        return threado.run(self.main())

    @threado.stream_fast
    def main(inner, self):
        while True:
            yield inner
            list(inner)

    @threado.stream
    def xmpp_connect(inner, self):
        self.log.info("Connecting to XMPP server with JID %r", self.xmpp_jid)
        xmpp = yield inner.sub(connect(self.xmpp_jid, self.xmpp_password))
        self.log.info("Connected to XMPP server with JID %r", self.xmpp_jid)
        xmpp.core.presence()
        inner.finish(xmpp)

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
    bot_state_file = Param(default=None)
    service_room = Param()
    service_mock_session = ListParam(default=None)

    @threado.stream
    def _run(inner, self):
        ver_str = version.version_str()
        self.log.info("Starting service %r version %s", self.bot_name, ver_str)
        self.xmpp = yield inner.sub(self.xmpp_connect())

        service = _Service(self, self.bot_state_file)
        service.start()

        if self.service_mock_session is not None:
            keys = dict(item.split("=", 1) for item in self.service_mock_session)
            self.log.info("Running a mock ression with keys %r" % keys)
            yield inner.sub(service.session(None, **keys) | service)
            return

        self.log.info("Joining lobby %r", self.service_room)
        self.lobby = yield inner.sub(services.join_lobby(self.xmpp, 
                                                         self.service_room, 
                                                         self.bot_name))
        self.log.addHandler(log.RoomHandler(self.lobby.room))

        self.log.info("Offering service %r", self.bot_name)
        try:
            yield inner.sub(self.lobby.offer(self.bot_name, service))
        finally:
            self.log.info("Retired service %r", self.bot_name)

    def run(self):
        return threado.run(self._run(), throw_on_signal=services.Stop())

    @threado.stream
    def main(inner, self, state):
        try:
            while True:
                yield inner
        except services.Stop:
            inner.finish()

    @threado.stream
    def session(inner, self, state, **keys):
        try:
            while True:
                yield inner
        except services.Stop:
            inner.finish()

from abusehelper.core.dedup import Dedup
from abusehelper.core import events, taskfarm

class FeedBot(ServiceBot):
    def __init__(self, *args, **keys):
        ServiceBot.__init__(self, *args, **keys)

        self.rooms = taskfarm.TaskFarm(self._room)
        self._room_keys = taskfarm.Counter()

    @threado.stream
    def session(inner, self, state, dst_room, **keys):
        room_keys = self.room_keys(dst_room=dst_room, **keys)
        for room_key in room_keys:
            self._room_keys.inc(room_key, dst_room)

        try:
            yield inner.sub(self.rooms.inc(dst_room))
        except services.Stop:
            inner.finish()
        finally:
            for room_key in room_keys:
                self._room_keys.dec(room_key, dst_room)

    @threado.stream
    def feed(inner, self):
        while True:
            yield inner

    def room_keys(self, **keys):
        return [None]

    def event_keys(self, event):
        return [None]

    @threado.stream
    def _room(inner, self, name):
        self.log.info("Joining room %r", name)
        room = yield inner.sub(self.xmpp.muc.join(name, self.bot_name))

        self.log.info("Joined room %r", name)
        try:
            yield inner.sub(events.events_to_elements()
                            | room
                            | threado.dev_null())
        finally:
            self.log.info("Left room %r", name)

    @threado.stream_fast
    def _distribute(inner, self):
        while True:
            yield inner

            for event in inner:
                for room_key in self.event_keys(event):
                    dst_rooms = self._room_keys.get(room_key)

                    for dst_room in dst_rooms:
                        room = self.rooms.get(dst_room)
                        if room is None:
                            continue
                        room.send(event)

                    if dst_rooms:
                        inner.send(event)

    @threado.stream_fast
    def _dedup(inner, self, dedup):
        while True:
            yield inner

            for event in inner:
                items = [(key, event.values(key)) for key in event.keys()]
                items.sort()
                if dedup.add(repr(items)):
                    inner.send(event)

    @threado.stream_fast
    def _stats(inner, self, interval=60.0):
        count = 0
        sleeper = timer.sleep(interval)

        while True:
            yield inner, sleeper

            for event in inner:
                count += 1
                inner.send(event)

            try:
                list(sleeper)
            except threado.Finished:
                if count > 0:
                    self.log.info("Sent out %d new events", count)
                count = 0
                sleeper = timer.sleep(interval)

    @threado.stream_fast
    def augment(inner, self):
        while True:
            yield inner
            for event in inner:
                inner.send(event)

    @threado.stream
    def main(inner, self, dedup):
        if dedup is None:
            dedup = Dedup(10**6)

        try:
            yield inner.sub(self.feed() 
                            | self._dedup(dedup)
                            | self.augment()
                            | self._distribute()
                            | self._stats()
                            | threado.dev_null())
        except services.Stop:
            inner.finish(dedup)

import time
import collections
from idiokit import timer

class PollingBot(FeedBot):
    poll_interval = IntParam(default=3600)

    def __init__(self, *args, **keys):
        FeedBot.__init__(self, *args, **keys)

        self.feed_queue = collections.deque()
        self._feed_keys = taskfarm.Counter()

    @threado.stream
    def session(inner, self, state, **keys):
        feed_keys = set(self.feed_keys(**keys))
        for feed_key in feed_keys:
            if self._feed_keys.inc(feed_key):
                self.feed_queue.appendleft((time.time(), feed_key))

        try:
            yield inner.sub(FeedBot.session(self, state, **keys))
        except services.Stop:
            inner.finish()
        finally:
            for feed_key in feed_keys:
                self._feed_keys.dec(feed_key)

    def feed_keys(self, **keys):
        return [None]

    @threado.stream
    def feed(inner, self):
        while True:
            while True:
                current_time = time.time()
                if self.feed_queue and self.feed_queue[0][0] <= current_time:
                    break
                yield inner, timer.sleep(1.0)
                continue
            
            _, feed_key = self.feed_queue.popleft()
            if not self._feed_keys.contains(feed_key):
                continue
            
            yield inner.sub(self.poll(feed_key))
                
            expire_time = time.time() + self.poll_interval
            self.feed_queue.append((expire_time, feed_key))
