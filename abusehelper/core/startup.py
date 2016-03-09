from __future__ import absolute_import

import os
import sys
import errno
import signal
import numbers
import inspect
import subprocess
import cPickle as pickle

import idiokit
from . import bot, config, utils


def iter_startups(iterable):
    for obj in iterable:
        startup = getattr(obj, "__startup__", None)
        if callable(startup):
            yield startup()
            continue


def _signal_numbers_to_names():
    signums = {}

    for name, value in inspect.getmembers(signal):
        if not name.startswith("SIG") or name.startswith("SIG_"):
            continue

        if not isinstance(value, numbers.Integral):
            continue

        signums.setdefault(value, []).append(name)

    for signum, names in signums.items():
        signums[signum] = tuple(sorted(names))

    return signums


_signums = _signal_numbers_to_names()


def _signal_number_to_name(signum):
    """
    Return a name for the signal number, or None if no name can be found.

    >>> _signal_number_to_name(signal.SIGINT)
    'SIGINT'
    >>> _signal_number_to_name(signal.NSIG + 1)
    """

    names = _signums.get(signum, [])
    if not names:
        return None
    return "/".join(names)


class Bot(object):
    _defaults = {}

    @classmethod
    def template(cls, *args, **keys):
        defaults = dict(cls._defaults)
        defaults.update(*args, **keys)

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


def _kill(process, signum):
    try:
        os.kill(process.pid, signum)
    except OSError as ose:
        if ose.errno != errno.ESRCH:
            raise


class _ConfSignal(Exception):
    def __init__(self, signum):
        Exception.__init__(self, signum)

    @property
    def signum(self):
        return self.args[0]


class StartupBot(bot.Bot):
    def __init__(self, *args, **keys):
        bot.Bot.__init__(self, *args, **keys)

        self._handlers = {}
        self._processes = {}

    @idiokit.stream
    def configs(self):
        yield idiokit.sleep(0.0)

    @idiokit.stream
    def handle(self, conf, delay=15):
        while True:
            self.log.info("Launching bot {0!r} from module {1!r}".format(conf.name, conf.module))
            yield self.launch(conf)

            self.log.info("Relaunching {0!r} in {1} seconds".format(conf.name, delay))
            yield idiokit.sleep(delay)

    @idiokit.stream
    def launch(self, conf):
        if conf in self._processes:
            raise RuntimeError("can not launch two processes with same conf")

        process = self._launch(conf)
        self._processes[conf] = process

        sig = None

        while self._poll(conf, process) is None:
            try:
                yield idiokit.sleep(0.25)
            except _ConfSignal as sig:
                siginfo = "signal {0}".format(sig.signum)
                signame = _signal_number_to_name(sig.signum)
                if signame is not None:
                    siginfo += " (" + signame + ")"
                self.log.info("Sending {0} to {1!r}".format(siginfo, conf.name))
                _kill(process, sig.signum)

        if sig is not None:
            raise sig
        idiokit.stop(process.returncode)

    def main(self):
        error_event = idiokit.Event()
        listen = self._listen_configs(error_event)
        idiokit.pipe(error_event, listen)
        return idiokit.pipe(self.configs(), listen)

    def run(self):
        return idiokit.main_loop(self.main())

    @idiokit.stream
    def _listen_configs(self, error_event):
        closing = False
        term_count = 0
        configs = frozenset()

        try:
            while True:
                try:
                    while not closing:
                        if frozenset(self._handlers) == configs:
                            configs = yield idiokit.next()
                            configs = frozenset(iter_startups(config.flatten(configs)))
                        yield self._apply(configs, error_event)
                    yield self._wait(self._handlers.values())
                except idiokit.Signal as sig:
                    closing = True

                    if sig.signum == signal.SIGUSR1:
                        self._clean(signal.SIGTERM)
                        continue

                    if sig.signum == signal.SIGUSR2:
                        self._clean(signal.SIGKILL)
                        continue

                    if term_count == 0:
                        self._clean(signal.SIGTERM)
                        term_count += 1
                        continue
                break
        finally:
            self._check()

    @idiokit.stream
    def _apply(self, configs, error_event):
        removed = frozenset(self._handlers).difference(configs)
        added = frozenset(configs).difference(self._handlers)

        for conf in removed:
            handler = self._handlers[conf]
            handler.throw(_ConfSignal(signal.SIGTERM))

        yield self._wait([self._handlers[conf] for conf in removed])

        for conf in removed:
            del self._handlers[conf]

        for conf in added:
            self._handlers[conf] = self._wrap_handler(self.handle(conf), error_event)

    @idiokit.stream
    def _wrap_handler(self, handler, error_event):
        try:
            yield handler
        except _ConfSignal:
            pass
        except:
            error_event.fail()

    @idiokit.stream
    def _wait(self, handlers):
        for handler in handlers:
            yield idiokit.pipe(idiokit.Event(), handler)

    def _clean(self, signum):
        for conf, handler in self._handlers.items():
            handler.throw(_ConfSignal(signum))

    def _check(self):
        for conf, process in self._processes.items():
            self._poll(conf, process)

        if self._processes:
            self.log.info("{0} bot(s) left alive: {1}".format(
                len(self._processes),
                ", ".join("{0!r}[{1}]".format(conf.name, process.pid) for (conf, process) in self._processes.items())
            ))

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
            process = subprocess.Popen(
                args,
                cwd=conf.workdir,
                env=env,
                stdin=subprocess.PIPE,
                close_fds=True
            )
        except OSError as ose:
            self.log.error("Failed launching bot {0!r} ({1})".format(
                conf.name,
                utils.format_exception(ose))
            )
            return None

        try:
            pickle.dump(conf.params, process.stdin)
            process.stdin.flush()
        except IOError as ioe:
            self.log.error("Failed sending configuration to bot {0!r} ({1})".format(
                conf.name,
                utils.format_exception(ioe))
            )

        return process

    def _poll(self, conf, process):
        if process.poll() is None:
            return None

        if self._processes.get(conf, None) is process:
            del self._processes[conf]

            if process.returncode >= 0:
                info = "with return code {0}".format(process.returncode)
            else:
                signum = -process.returncode
                info = "by signal {0}".format(signum)
                signame = _signal_number_to_name(signum)
                if signame is not None:
                    info += " (" + signame + ")"

            self.log.info("Bot {0!r} was terminated {1}".format(conf.name, info))
        return process.returncode


class DefaultStartupBot(StartupBot):
    config = bot.Param("configuration module")
    enable = bot.ListParam("bots that are run (default: run all bots)", default=None)
    disable = bot.ListParam("bots that are not run (default: run all bots)", default=None)

    def configs(self):
        abspath = os.path.abspath(self.config)
        return config.follow_config(abspath) | self._follow_config(abspath)

    @idiokit.stream
    def _follow_config(self, abspath):
        workdir = os.path.dirname(abspath)
        while True:
            ok, obj = yield idiokit.next()
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
