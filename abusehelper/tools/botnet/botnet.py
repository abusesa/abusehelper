from __future__ import print_function

import os
import sys
import pwd
import platform
from optparse import OptionParser


def _flatten(iterable):
    stack = [iter(iterable)]

    while stack:
        last = stack.pop()
        if isinstance(last, basestring):
            yield last
            continue

        try:
            item = last.next()
        except StopIteration:
            pass
        else:
            stack.append(last)
            stack.append(item)


class Botnet(object):
    def __init__(self):
        self._commands = dict()

    def _is_root(self):
        return pwd.getpwuid(os.getuid()).pw_name == "root"

    def _parse(self, parser):
        options, args = parser.parse_args()

        if not options.allow_root and self._is_root():
            parser.error(
                "running as root - " +
                "run as a different user or specify the --allow-root " +
                "command line option")

        if options.python is not None:
            os.execlp(options.python, options.python, sys.argv[0], *args)
        if sys.version_info < (2, 6):
            version = platform.python_version()
            parser.error(
                "this tool requires python >= 2.6 " +
                "(you are running python " + version + "), " +
                "use the option -p/--python to define a suitable python " +
                "executable")

        return options, args

    def run(self):
        parser = OptionParser()

        parser.set_usage("usage: %prog [options] command [...]")
        parser.add_option(
            "-p", "--python",
            dest="python",
            default=None,
            help=(
                "use the given python executable instead of " +
                repr(sys.executable)))
        parser.add_option(
            "--allow-root",
            action="store_true",
            dest="allow_root",
            default=False,
            help="allow starting bots as the root user")

        parser.disable_interspersed_args()
        options, args = self._parse(parser)

        if not args:
            print(parser.get_usage())
            print("Available commands are:")
            for name in sorted(self._commands):
                print(" " + name)
            sys.exit(0)

        command = args[0]
        if command not in self._commands:
            parser.error("unknown command " + repr(command))

        parser.enable_interspersed_args()
        parser.set_usage("usage: %prog " + command + " [options] [...]")

        command_obj = self._commands[command]
        command_obj.prep(parser)

        options, args = self._parse(parser)
        for line in _flatten(command_obj.run(parser, options, args[1:])):
            print(line)

    def register_commands(self, *args, **keys):
        self._commands.update(*args, **keys)

    def load_module(self, module, init_name="register_commands"):
        if isinstance(module, basestring):
            try:
                module = __import__(module, globals(), locals(), [init_name])
            except ImportError:
                return

        init = getattr(module, init_name, None)
        if init is None:
            return

        init(self)


class Command(object):
    def __init__(self):
        pass

    def prep(self, parser):
        pass

    def run(self, parser, options, args):
        pass
