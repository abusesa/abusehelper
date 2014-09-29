import os
import re
import sys
import time
import errno
import signal
import select

from botnet import Command


# Helpers

def popen(*args, **keys):
    import subprocess

    defaults = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "stdin": subprocess.PIPE,
        "close_fds": True
    }
    defaults.update(keys)
    return subprocess.Popen(args, **defaults)


def send_signal(pid, signum):
    try:
        os.kill(pid, signum)
    except OSError, ose:
        if ose.errno != errno.ESRCH:
            raise


def name_for_signal(signum, default=None):
    for key, value in vars(signal).iteritems():
        if not key.startswith("SIG"):
            continue
        if key.startswith("SIG_"):
            continue
        if value != signum:
            continue
        return key
    return default


def ps():
    process = popen("ps", "-wwAo", "pid=,ppid=,command=")
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


# Instance

class Instance(object):
    def __init__(self, instance):
        instance = os.path.realpath(instance)
        if os.path.isdir(instance):
            instance = os.path.join(instance, "startup.py")
        self._instance = instance

    @property
    def _id(self):
        import hashlib

        instance = self._instance
        return hashlib.sha1(instance).hexdigest() + "-" + instance

    @property
    def path(self):
        return self._instance

    @property
    def logpath(self):
        path, filename = os.path.split(self.path)
        return os.path.join(path, "log", filename + ".log")

    @property
    def is_running(self):
        return bool(self.find())

    @property
    def exists(self):
        return os.path.exists(self.path)

    def find(self, processes=None):
        rex = re.compile(r"\s" + re.escape(self._id))
        if processes is None:
            processes = ps()

        found = list()
        for pid, ppid, command in processes:
            if rex.search(command):
                found.append((int(pid), command))
        return found

    def start(self):
        if not self.exists:
            yield "Instance does not exist."
            return
        if self.is_running:
            yield "Already running."
            return

        logfile = open(self.logpath, "a")
        try:
            yield "Starting."
            process = popen(
                sys.executable,
                "-m", "runpy",
                "abusehelper.core.startup", self.path,
                self._id,
                stdout=logfile,
                stderr=logfile)
        finally:
            logfile.close()

        for _ in xrange(20):
            code = process.poll()
            if code is not None:
                yield "Warning, process died with return code {0}.".format(code)
                return
            time.sleep(0.1)

    def stop(self, signum, signame=None):
        if not self.is_running:
            yield "Nothing running."
            return

        yield "Shutting down."
        if signame is None:
            signame = name_for_signal(signum, "signal {0}".format(signum))

        previous = set()
        try:
            while True:
                pids = set(self.find())
                if not pids:
                    break

                for pid, command in pids - previous:
                    send_signal(pid, signum)
                    yield "Sent {0} to process {1}.".format(signame, pid)

                previous = pids
                time.sleep(0.2)
        finally:
            pids = set(self.find())
            for index, (pid, command) in enumerate(pids):
                if index == 0:
                    yield "Warning, some instances survived:"
                yield "  pid={0} command={1!r}".format(pid, command)

    def status(self):
        processes = ps()
        pids = self.find(processes)
        if not pids:
            yield "Not running."
            return

        if len(pids) == 1:
            yield "1 instance running:"
        else:
            yield "{0} instances running:".format(len(pids))

        parents = dict()
        for pid, ppid, command in processes:
            parents.setdefault(ppid, list()).append((pid, command))

        for parent_pid, parent_command in pids:
            yield "[{0}] {1}".format(parent_pid, parent_command)

            for pid, command in parents.get(parent_pid, ()):
                yield "  [{0}] {1}".format(pid, command)

    def follow(self, lines=20):
        if not self.exists:
            yield "Instance does not exist."
            return

        process = popen("tail", "-n", str(lines), "-f", self.logpath)
        streams = set([process.stdout, process.stderr])

        try:
            while self.is_running and streams:
                readable, _, errors = select.select(streams, (), (), 0.5)
                for stream in readable:
                    line = stream.readline()
                    if not line:
                        streams.discard(stream)
                        continue

                    yield line.rstrip("\n").rstrip("\r")
        finally:
            send_signal(process.pid, signal.SIGKILL)


def running_instances():
    import hashlib

    rex = re.compile("\s([a-f0-9]{40})-", re.I)

    for pid, _, command in ps():
        match = rex.search(command)
        if not match:
            continue

        start = match.end()
        hashed = match.group(1)

        candidate = hashlib.sha1()
        if hashed == candidate.hexdigest():
            yield pid, Instance("")
            continue

        for index in xrange(start, len(command)):
            candidate.update(command[index])
            if hashed == candidate.hexdigest():
                yield pid, Instance(command[start:index + 1])


# Commands

class InstanceCommand(Command):
    def run(self, parser, options, args):
        if not args:
            parser.error("expected a instance argument")
        if len(args) > 1:
            parser.error("expected only one instance argument")
        return self.run_for_instance(options, Instance(args[0]))

    def run_for_instance(self, _, instance):
        return []


class Start(InstanceCommand):
    def run_for_instance(self, _, instance):
        yield instance.start()


class Stop(InstanceCommand):
    def prep(self, parser):
        parser.add_option(
            "-k", "--kill",
            action="store_true",
            dest="kill",
            default=False,
            help="stop the botnet(s) with the SIGKILL signal")

    def run_for_instance(self, options, instance):
        if not options.kill:
            yield instance.stop(signal.SIGUSR1)
        else:
            yield instance.stop(signal.SIGUSR2)


class Restart(InstanceCommand):
    def run_for_instance(self, _, instance):
        yield instance.stop(signal.SIGUSR1)
        yield instance.start()


class Status(InstanceCommand):
    def run_for_instance(self, _, instance):
        yield instance.status()


class Follow(InstanceCommand):
    def run_for_instance(self, _, instance):
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
        yield instance.follow(lines=height)


class List(Command):
    def run(self, parser, options, args):
        instances = list(running_instances())
        if not instances:
            yield "No running instances."
            return

        if len(instances) == 1:
            yield "1 instance running:"
        else:
            yield "{0} instances running:".format(len(instances))

        for pid, instance in instances:
            yield "[{0}] {1}".format(pid, instance.path)


def register_commands(botnet):
    botnet.register_commands({
        "start": Start(),
        "stop": Stop(),
        "restart": Restart(),
        "status": Status(),
        "follow": Follow(),
        "list": List()
    })
