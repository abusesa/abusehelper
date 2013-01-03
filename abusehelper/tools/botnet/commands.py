import os
import re
import sys
import time
import errno
import signal

from botnet import Command


# Helpers

def module_id(module):
    import hashlib

    return hashlib.sha1(module).hexdigest() + "-" + module


def popen(*args, **keys):
    import subprocess

    defaults = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "stdin": subprocess.PIPE
    }
    defaults.update(keys)
    return subprocess.Popen(args, **defaults)


def send_signal(pid, signum):
    try:
        os.kill(pid, signum)
    except OSError, ose:
        if ose.errno != errno.ESRCH:
            raise


def ps():
    process = popen("ps", "-wweo", "pid=,ppid=,command=")
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        sys.stderr.write(stderr)
        sys.stderr.flush()
        sys.exit(process.returncode)

    found = list()
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        pid, ppid, command = line.split(None, 2)
        found.append((int(pid), int(ppid), command))
    return found


def find(module, processes=None):
    rex = re.compile(r"\s" + re.escape(module_id(module)))
    if processes is None:
        processes = ps()

    found = list()
    for pid, ppid, command in processes:
        if rex.search(command):
            found.append((int(pid), command))
    return found


def is_running(module):
    return bool(find(module))


def _signal(module, signame, signum):
    waiting = set()

    try:
        while True:
            pids = find(module)
            if not pids:
                break

            for item in pids:
                if item in waiting:
                    continue
                pid, command = item

                send_signal(pid, signum)
                print "Sent {0} to process {1}.".format(signame, pid)

            waiting = set(pids)
            time.sleep(0.2)
    finally:
        pids = find(module)
        if pids:
            print "Warning, some instances survived:"
            print "  pid={0} command={1!r}".format(pid, command)


def normalized_module(module):
    module = os.path.abspath(module)
    if os.path.isdir(module):
        module = os.path.join(module, "startup.py")
    return module


def logpath(module):
    path, filename = os.path.split(module)
    return os.path.join(path, "log", filename + ".log")


# Commands

class _LegacyCommand(Command):
    def run(self, parser, options, args):
        if not args:
            parser.error("expected a module argument")
        if len(args) > 1:
            parser.error("expected only one module argument")
        self.run_for_module(normalized_module(args[0]))

    def run_for_module(self, module):
        pass


class Start(_LegacyCommand):
    def run_for_module(self, module):
        module = normalized_module(module)
        if is_running(module):
            print "Already running."
            return

        logfile = open(logpath(module), "a")
        try:
            print "Starting."
            process = popen(sys.executable,
                "-m", "runpy",
                "abusehelper.core.startup", module,
                module_id(module),
                stdout=logfile,
                stderr=logfile,
                close_fds=True)
        finally:
            logfile.close()

        for _ in xrange(20):
            code = process.poll()
            if code is not None:
                print "Warning, process died with return code {0}".format(code)
                return
            time.sleep(0.1)


class Stop(_LegacyCommand):
    def __init__(self, kill=False):
        Command.__init__(self)

        self._kill = kill

    def run_for_module(self, module):
        if not is_running(module):
            print "Nothing running."
            return

        print "Shutting down."
        if self._kill:
            _signal(module, "SIGUSR2", signal.SIGUSR2)
        else:
            _signal(module, "SIGUSR1", signal.SIGUSR1)


class Restart(_LegacyCommand):
    def __init__(self):
        _LegacyCommand.__init__(self)

        self._stop = Stop()
        self._start = Start()

    def prep(self, parser):
        self._stop.prep(parser)
        self._start.prep(parser)

    def run(self, parser, options, args):
        self._stop.run(parser, options, args)
        self._start.run(parser, options, args)


class Status(_LegacyCommand):
    def run_for_module(self, module):
        processes = ps()
        pids = find(module, processes)
        if not pids:
            print "Not running."
            return

        if len(pids) == 1:
            print "1 instance running:"
        else:
            print "{0} instances running:".format(len(pids))

        parents = dict()
        for pid, ppid, command in processes:
            parents.setdefault(ppid, list()).append((pid, command))

        for parent_pid, parent_command in pids:
            print "[{0}] {1}".format(parent_pid, parent_command)

            for pid, command in parents.get(parent_pid, ()):
                print "  [{0}] {1}".format(pid, command)


class Follow(_LegacyCommand):
    def run_for_module(self, module):
        height = 20
        try:
            process = popen("stty", "size", stdin=sys.stdin)
        except OSError:
            pass
        else:
            stdout, _ = process.communicate()
            if process.returncode == 0:
                try:
                    height = max(int(stdout.split()[0]) - 2, 0)
                except ValueError:
                    pass

        process = popen("tail", "-n", str(height), "-f", logpath(module),
            stdout=sys.stdout,
            stderr=sys.stderr)
        try:
            while is_running(module):
                time.sleep(0.2)
        finally:
            send_signal(process.pid, signal.SIGKILL)


def register_commands(botnet):
    botnet.register_commands({
        "start": Start(),
        "stop": Stop(),
        "kill": Stop(kill=True),
        "restart": Restart(),
        "status": Status(),
        "follow": Follow()
    })
