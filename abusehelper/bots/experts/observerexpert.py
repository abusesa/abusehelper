"""
Observation expert, which augments events with "observation time"
in ISO8601:ish time format. Source bots often cannot add this,
since it complicates bookkeeping. This can be used in source
rooms instead of a sanitizer.

Maintainer: Lari Huttunen <mit-code@huttu.net>
"""
import idiokit
import time as _time
from abusehelper.core import events
from combiner import Expert


class ObserverExpert(Expert):

    def format_time(self, time_tuple=None):
        if time_tuple is None:
            time_tuple = _time.gmtime()
        return _time.strftime("%Y-%m-%d %H:%M:%SZ", time_tuple)

    def time(self, string, format="%Y-%m-%d %H:%M:%S"):
        try:
            parsed = _time.strptime(string, format)
        except ValueError:
            return None
        if _time.gmtime() < parsed:
            return None
        return self.format_time(parsed)

    @idiokit.stream
    def augment(self):

        while True:
            eid, event = yield idiokit.next()
            augment = events.Event()
            augment.add("observation time", self.format_time())
            yield idiokit.send(eid, augment)

if __name__ == "__main__":
    ObserverExpert.from_command_line().execute()
