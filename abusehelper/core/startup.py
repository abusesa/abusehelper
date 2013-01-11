import os
import sys
import time
import errno
import signal
import subprocess
import cPickle as pickle

import idiokit
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
    def workdir(self):
        return self._workdir

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

    def __init__(self, name, _module=None, _workdir=None, **_params):
        self.name = name

        self._workdir = _workdir
        self._module = _module
        self._hash = None

        params = dict(self._defaults)
        params.update(_params)
        self._params = config.HashableFrozenDict(params)

    def with_workdir(self, workdir):
        if not os.path.isabs(workdir):
            raise ValueError("work directory path has to be absolute")
        return Bot(self.name, self._module, workdir, **self._params)

    def __startup__(self):
        return self

    def __hash__(self):
        return hash(self._workdir) ^ hash(self.name) ^ hash(self._module) ^ hash(self._params)

    def __eq__(self, other):
        if not isinstance(other, Bot):
            return NotImplemented
        if self.name != other.name:
            return False
        if self._module != self._module:
            return False
        return self._params == other._params

    def __ne__(self, other):
        result = self.__eq__(other)
        return result if result is NotImplemented else not result


def kill(process, signum):
    try:
        os.kill(process.pid, signum)
    except OSError, ose:
        if ose.errno != errno.ESRCH:
            raise


class StartupBot(bot.Bot):
    def __init__(self, *args, **keys):
        bot.Bot.__init__(self, *args, **keys)

        self._strategies = dict()
        self._processes = dict()
        self._updated = None

    @idiokit.stream
    def configs(self):
        yield idiokit.sleep(0.0)

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
            process = subprocess.Popen(args, cwd=conf.workdir, env=env, stdin=subprocess.PIPE)
        except OSError, ose:
            self.log.error("Failed launching bot %r: %r", conf.name, ose)
            return None

        try:
            pickle.dump(conf.params, process.stdin)
            process.stdin.flush()
        except IOError, ioe:
            self.log.error("Failed sending configuration to bot %r: %r", conf.name, ioe)

        return process

    def _poll(self):
        for conf, (process, strategy) in list(self._processes.iteritems()):
            if process is not None and process.poll() is None:
                continue
            if process is not None and process.poll() is not None:
                self.log.info("Bot %r exited with return value %d", conf.name, process.poll())
            self._processes.pop(conf, None)
            self._strategies[conf] = time.time(), strategy

    def _purge(self):
        now = time.time()
        for conf, (expiration, strategy) in list(self._strategies.iteritems()):
            if expiration > now:
                continue

            try:
                output_value = strategy.next()
            except StopIteration:
                del self._strategies[conf]
                continue

            if isinstance(output_value, (int, float)):
                self._strategies[conf] = output_value + now, strategy
            else:
                del self._strategies[conf]
                yield output_value, strategy

    def _close(self):
        for _, strategy in self._strategies.itervalues():
            strategy.close()
        self._strategies.clear()

    def _clean(self, signame, signum):
        self._poll()
        self._close()
        if not self._processes:
            return

        self.log.info("Sending %s to alive bots" % (signame,))
        for conf, (process, _) in self._processes.iteritems():
            kill(process, signum)

    @idiokit.stream
    def read(self):
        try:
            while True:
                configs = yield idiokit.next()
                self._updated = set(iter_startups(config.flatten(configs)))
        finally:
            self._updated = None

    @idiokit.stream
    def main(self, poll_interval=0.25):
        try:
            discard = set()
            closing = False
            term_count = 0

            while True:
                try:
                    yield idiokit.sleep(poll_interval)
                except idiokit.Signal as sig:
                    signum = sig.args[0]
                    closing = True

                    if signum == signal.SIGUSR1:
                        self._clean("SIGTERM", signal.SIGTERM)
                    elif signum == signal.SIGUSR2:
                        self._clean("SIGKILL", signal.SIGKILL)
                    elif term_count == 0:
                        self._clean("SIGTERM", signal.SIGTERM)
                        term_count += 1
                    else:
                        return

                self._poll()

                if closing:
                    self._close()
                    if not self._strategies and not self._processes:
                        return
                    continue

                if self._updated is not None:
                    current = set(self._processes) | set(self._strategies)

                    for conf in (current - self._updated) - discard:
                        if conf in self._processes:
                            process, strategy = self._processes[conf]
                            self.log.info("Sending SIGTERM to %r", conf.name)
                            kill(process, signal.SIGTERM)
                        discard.add(conf)

                    for conf in self._updated - current:
                        self._strategies[conf] = time.time(), self.strategy(conf)

                    self._updated = None

                if discard:
                    for conf in discard.intersection(self._strategies):
                        _, strategy = self._strategies.pop(conf)
                        strategy.close()
                        discard.discard(conf)
                    continue

                for conf, strategy in self._purge():
                    self.log.info("Launching bot %r from module %r", conf.name, conf.module)
                    self._processes[conf] = self._launch(conf), strategy
        finally:
            self._poll()
            if self._processes:
                info = ", ".join("%r[%d]" % (conf.name, process.pid)
                    for (conf, (process, _)) in self._processes.iteritems())
                self.log.info("%d bot(s) left alive: %s" % (len(self._processes), info))

    def run(self):
        return idiokit.main_loop(self.configs() | self.read() | self.main())


class DefaultStartupBot(StartupBot):
    config = bot.Param("configuration module")
    enable = bot.ListParam("bots that are run (default: run all bots)", default=None)
    disable = bot.ListParam("bots that are not run (default: run all bots)", default=None)

    @idiokit.stream
    def configs(self):
        abspath = os.path.abspath(self.config)
        workdir = os.path.dirname(abspath)

        follow = config.follow_config(abspath)
        while True:
            ok, obj = yield follow.next()
            if not ok:
                self.log.error(obj)
                continue

            output = set()
            for conf in iter_startups(obj):
                if self.disable is not None and conf.name in self.disable:
                    continue
                if self.enable is not None and conf.name not in self.enable:
                    continue
                output.add(conf.with_workdir(workdir))
            yield idiokit.send(output)

if __name__ == "__main__":
    DefaultStartupBot.from_command_line().execute()
