import os
import sys
import time
import errno
import signal
import subprocess
import ConfigParser

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

def main(config_filename):
    def signal_handler(sig, frame):
        sys.exit()
    signal.signal(signal.SIGTERM, signal_handler)

    conf_parser = ConfigParser.SafeConfigParser()

    conf_file = open(config_filename, "r")
    try:
        conf_parser.readfp(conf_file)
    finally:
        conf_file.close()

    processes = dict()
    for section in conf_parser.sections():
        process = subprocess.Popen([sys.executable, "-m", section,
                                    "--ini-file", config_filename,
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

if __name__ == "__main__":
    from abusehelper.core import opts
    opts.optparse(main)
