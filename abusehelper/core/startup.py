import os
import sys
import time
import errno
import signal
import subprocess
from abusehelper.core import bot

def all_running(processes):
    for process in processes:
        retval = process.poll()
        if retval is not None:
            return False
    return True

def kill_processes(processes, sig):
    for process in processes:
        try:
            os.kill(process.pid, sig)
        except OSError, ose:
            if ose.errno != errno.ESRCH:
                raise

class Startup(bot.Bot):
    bot_name = None
    ini_file = None
    ini_section = None

    config_file = bot.Param("launch processes based in this INI file, "+
                            "one per section ([DEFAULT] section not included)")
    enable = bot.ListParam("sections (separated by commas) that are run "+
                           "(default: run all sections except [DEFAULT])",
                           default=None)
    disable = bot.ListParam("sections (separated by commas) that are not run "+
                            "(default: run all sections except [DEFAULT])",
                            default=None)

    def run(self):
        def signal_handler(sig, frame):
            sys.exit()
        signal.signal(signal.SIGTERM, signal_handler)
            
        config = bot.ConfigParser(self.config_file)

        processes = dict()
        for section in config.sections():
            if self.disable is not None and section in self.disable:
                continue
            if self.enable is not None and section not in self.enable:
                continue
            if not config.has_option(section, "module"):
                continue
            module = config.get(section, "module")

            process = subprocess.Popen([sys.executable,  
                                        "-m", module,
                                        "--ini-file", self.config_file,
                                        "--ini-section", section])
            processes[section] = process

        try:
            while all_running(processes.values()):
                time.sleep(0.1)
        finally:
            kill_processes(processes.values(), signal.SIGTERM)
            for _, process in processes.items():
                process.wait()

if __name__ == "__main__":
    Startup.from_command_line().run()
