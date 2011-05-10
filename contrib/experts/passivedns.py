import os
import errno
import signal
import subprocess

from idiokit import threado
from abusehelper.core import bot, events
from combiner import Expert

@threado.stream
def lookup(inner, host, eid, name, keys=["domain", "ip", "first seen", "last seen"]):
    process = subprocess.Popen(["whois", "-h", host, name],
                               stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)

    try:
        stdout, stderr = yield inner.thread(process.communicate)
    finally:
        if process.poll() is None:
            try:
                os.kill(process.pid, signal.SIGKILL)
            except OSError, ose:
                if ose.errno != errno.ESRCH:
                    raise

    for line in stdout.splitlines():
        event = events.Event()
        for key, value in zip(keys, line.split("\t")):
            event.add(key, value)
        inner.send(eid, event)

class PassiveDNSExpert(Expert):
    host = bot.Param()

    @threado.stream
    def augment(inner, self):
        while True:
            eid, event = yield inner
            
            for name in event.values("domain") + event.values("ip") + event.values("soa"):
                yield inner.sub(lookup(self.host, eid, name))

if __name__ == "__main__":
    PassiveDNSExpert.from_command_line().execute()
