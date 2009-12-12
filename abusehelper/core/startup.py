import os
import sys
import time
import errno
import signal
import subprocess
from abusehelper.core import opts

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

def main(config_file, enable=None, disable=None):
    def signal_handler(sig, frame):
        sys.exit()
    signal.signal(signal.SIGTERM, signal_handler)

    conf_parser = opts.ConfigParser(config_file)

    if enable is not None:
        enable = set(x.strip() for x in enable.split(","))
    if disable is not None:
        disable = set(x.strip() for x in disable.split(","))

    processes = dict()
    for section in conf_parser.sections():
        if disable is not None and section in disable:
            continue
        if enable is not None and section not in enable:
            continue
        process = subprocess.Popen([sys.executable, "-u", "-m", section,
                                    "--ini-file", config_file,
                                    "--ini-section", section])
        processes[section] = process

    try:
        while all_running(processes.values()):
            time.sleep(0.1)
    finally:
        kill_processes(processes.values(), signal.SIGTERM)
        for _, process in processes.items():
            process.wait()
main.config_filename_help = ("launch processes based in this INI file, "+
                             "one per section ([DEFAULT] section not included)")
main.enable_help = ("sections (separated by commas) that are run "+
                    "(default: run all sections except [DEFAULT])")
main.disable_help = ("sections (separated by commas) that are not run "+
                     "(default: run all sections except [DEFAULT])")

if __name__ == "__main__":
    opts.optparse(main)
