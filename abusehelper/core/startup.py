import os
import sys
import time
import errno
import signal
import inspect
import subprocess
import cPickle as pickle
from abusehelper.core import bot, config

class Startup(config.Config):
    def startup(self):
        for key, value in self.member_diff(Startup):
            if not inspect.isroutine(value):
                yield key, value

def kill_processes(processes, sig):
    for process in processes:
        try:
            os.kill(process.pid, sig)
        except OSError, ose:
            if ose.errno != errno.ESRCH:
                raise

class StartupBot(bot.Bot):
    ini_file = None
    ini_section = None
    startup = None

    def configs(self):
        return []

    def run(self, poll_interval=0.1):
        def signal_handler(sig, frame):
            sys.exit()
        signal.signal(signal.SIGTERM, signal_handler)

        processes = dict()
        try:
            for startup in self.configs():
                if not hasattr(startup, "startup"):
                    continue
                params = dict(startup.startup())
                
                module = params["module"]
                bot_name = params["bot_name"]
                self.log.info("Launching bot %r from module %r", bot_name, module)

                args = [sys.executable]
                path, _ = os.path.split(module)
                if path:
                    args.extend([module])
                else:
                    args.extend(["-m", module])
                args.append("--startup")

                process = subprocess.Popen(args, stdin=subprocess.PIPE)
                processes[startup] = process

                pickle.dump(params, process.stdin)
                process.stdin.flush()

            while True:
                for startup, process in processes.items():
                    retval = process.poll()
                    if retval is not None:
                        return
                time.sleep(poll_interval)
        finally:
            processes = self.check_processes(processes)

            if processes:
                self.log.info("Sending SIGTERM to alive bots")
                kill_processes(processes.values(), signal.SIGTERM)

            while processes:
                processes = self.check_processes(processes)
                time.sleep(poll_interval)

    def check_processes(self, processes):
        processes = dict(processes)

        for startup, process in list(processes.items()):
            retval = process.poll()
            if retval is None:
                continue

            del processes[startup]
            self.log.info("Bot %r exited with return value %d", 
                          startup.bot_name, retval)

        return processes

class DefaultStartupBot(StartupBot):
    config = bot.Param("configuration module")
    enable = bot.ListParam("bots that are run (default: run all bots)",
                           default=None)
    disable = bot.ListParam("bots that are not run (default: run all bots)", 
                            default=None)

    def configs(self):
        for conf_obj in set(config.load_configs(os.path.abspath(self.config))):
            if self.disable is not None and conf_obj.name in self.disable:
                continue
            if self.enable is not None and conf_obj.name not in self.enable:
                continue
            yield conf_obj

if __name__ == "__main__":
    DefaultStartupBot.from_command_line().execute()
