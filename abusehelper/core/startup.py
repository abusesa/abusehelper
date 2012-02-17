from __future__ import with_statement

import os
import sys
import time
import errno
import heapq
import signal
import contextlib
import subprocess
import collections
import cPickle as pickle
from abusehelper.core import bot, config

def iter_startups(iterable):
    for obj in iterable:
        startup = getattr(obj, "__startup__", None)
        if callable(startup):
            yield startup()
            continue

        # Backwards compatibility
        startup_method = getattr(obj, "startup", None)
        if callable(startup_method):
            params = startup_method()
            name = params["bot_name"]
            module = params.pop("module", None)
            yield Bot(name, module, **params)
            continue

class Bot(object):
    _defaults = dict()

    @classmethod
    def template(cls, **attrs):
        defaults = dict(cls._defaults)
        defaults.update(attrs)

        class BotTemplate(cls):
            _defaults = defaults
        return BotTemplate

    @property
    def module(self):
        if self._module is None:
            return "abusehelper.core." + self.name
        return self._module

    @property
    def params(self):
        params = dict(self._params)
        params.setdefault("bot_name", self.name)
        return params

    def __init__(self, name, _module=None, **params):
        self.name = name

        self._module = _module

        self._params = dict(self._defaults)
        self._params.update(params)

    def __startup__(self):
        return self

@contextlib.contextmanager
def signal_handler(handler):
    signums = [signal.SIGTERM, signal.SIGINT, signal.SIGUSR1, signal.SIGUSR2]
    old_handlers = dict((x, signal.getsignal(x)) for x in signums)

    try:
        for signum in signums:
            signal.signal(signum, handler)
        yield
    finally:
        for signum, old_handler in old_handlers.items():
            signal.signal(signum, old_handler)

class StartupBot(bot.Bot):
    def __init__(self, *args, **keys):
        bot.Bot.__init__(self, *args, **keys)

        self._strategies = list()
        self._processes = set()

    def configs(self):
        return []

    def strategy(self, conf, delay=15):
        while True:
            yield conf

            self.log.info("Relaunching %r in %d seconds", conf.name, delay)
            yield delay

    def _launch(self, conf):
        args = [sys.executable]
        path, _ = os.path.split(conf.module)
        if path:
            args.extend([conf.module])
        else:
            # At least Python 2.5 on OpenBSD replaces the
            # argument right after the -m option with "-c" in
            # the process listing, making it harder to figure
            # out which modules are running. Workaround: Use
            # "-m runpy module" instead of "-m module".
            args.extend(["-m", "runpy", conf.module])

        env = dict(os.environ)
        env["ABUSEHELPER_CONF_FROM_STDIN"] = "1"
        try:
            process = subprocess.Popen(args, env=env, stdin=subprocess.PIPE)
        except OSError, ose:
            self.log.error("Failed launching bot %r: %r", conf.name, ose)
            return None

        try:
            pickle.dump(conf.params, process.stdin)
            process.stdin.flush()
        except IOError, ioe:
            self.log.error("Failed sending configuration to bot %r: %r",
                           conf.name, ioe)

        return process

    def _poll(self):
        for process, strategy, conf in list(self._processes):
            if process is not None and process.poll() is None:
                continue

            if process is not None and process.poll() is not None:
                self.log.info("Bot %r exited with return value %d",
                              conf.name, process.poll())

            self._processes.remove((process, strategy, conf))
            heapq.heappush(self._strategies, (time.time(), strategy))

    def _signal(self, sig):
        for process, strategy, conf in self._processes:
            try:
                os.kill(process.pid, sig)
            except OSError, ose:
                if ose.errno != errno.ESRCH:
                    raise

    def _purge(self):
        now = time.time()
        while self._strategies and self._strategies[0][0] <= now:
            _, strategy = heapq.heappop(self._strategies)

            try:
                output_value = strategy.next()
            except StopIteration:
                continue

            if isinstance(output_value, (int, float)):
                next = output_value + now
                heapq.heappush(self._strategies, (next, strategy))
            else:
                yield output_value, strategy

    def _close(self):
        for _, strategy in self._strategies:
            strategy.close()
        self._strategies = list()

    def _clean(self, signame, signum):
        self._poll()
        self._close()
        if not self._processes:
            return

        self.log.info("Sending %s to alive bots" % (signame,))
        self._signal(signum)

    def run(self, poll_interval=0.1):
        for conf in iter_startups(config.flatten(self.configs())):
            strategy = self.strategy(conf)
            heapq.heappush(self._strategies, (time.time(), strategy))

        received = collections.deque()

        def handler(signum, frame):
            received.append(signum)

        with signal_handler(handler):
            try:
                while not received and (self._strategies or self._processes):
                    self._poll()

                    for conf, strategy in self._purge():
                        self.log.info("Launching bot %r from module %r", conf.name, conf.module)
                        process = self._launch(conf)
                        self._processes.add((process, strategy, conf))

                    time.sleep(poll_interval)

                self._poll()
                self._close()

                count = 0
                while self._strategies or self._processes:
                    while received:
                        signum = received.popleft()

                        if signum == signal.SIGUSR1:
                            self._clean("SIGTERM", signal.SIGTERM)
                        elif signum == signal.SIGUSR2:
                            self._clean("SIGKILL", signal.SIGKILL)
                        elif count == 0:
                            self._clean("SIGTERM", signal.SIGTERM)
                            count += 1
                        else:
                            raise KeyboardInterrupt()

                    time.sleep(poll_interval)

                    self._poll()
                    self._close()
            except KeyboardInterrupt:
                pass
            finally:
                if self._processes:
                    info = ", ".join("%r[%d]" % (conf.name, process.pid)
                                     for (process, _, conf) in self._processes)
                    self.log.info("%d bot(s) left alive: %s" % (len(self._processes), info))

class DefaultStartupBot(StartupBot):
    config = bot.Param("configuration module")
    enable = bot.ListParam("bots that are run (default: run all bots)",
                           default=None)
    disable = bot.ListParam("bots that are not run (default: run all bots)",
                            default=None)

    def configs(self):
        configs = config.load_configs(os.path.abspath(self.config))

        for conf in iter_startups(configs):
            names = set([conf.name, conf.module])
            if self.disable is not None and names & set(self.disable):
                continue
            if self.enable is not None and not (names & set(self.enable)):
                continue
            yield conf

if __name__ == "__main__":
    DefaultStartupBot.from_command_line().execute()
