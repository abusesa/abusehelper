import time as _time
import socket
from abusehelper.core.events import Event
from abusehelper.core.config import load_module

sanitizer = load_module("sanitizer")

def time(string, format="%Y-%m-%d %H:%M:%S"):
    parsed = _time.strptime(string, format)
    if _time.gmtime() < parsed:
        raise ValueError()
    return _time.strftime("%Y-%m-%d %H:%M:%S", parsed)

def ip(string):
    return socket.inet_ntoa(socket.inet_aton(string))

class DShieldSanitizer(sanitizer.Sanitizer):
    def sanitize(self, event):
        new = Event()
        new.update("ip", event.values("ip", ip))
        new.update("time", event.values("updated", time))
        new.update("asn", event.values("asn"))
        new.add("type", "unknown")

        if not new.contains("ip"):
            self.log.error("No valid IP for event %r", event)
            return []
        if not new.contains("time"):
            self.log.error("No valid time for event %r", event)
            return []
        return [new]

if __name__ == "__main__":
    DShieldSanitizer.from_command_line().execute()
