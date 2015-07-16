"""
Important notice:

This bot is deprecated and will not be maintained. Maintained
version will be moved under ahcommunity repository.

abusehelper.contrib package will be removed after 2016-01-01.
During the migration period, you can already update your
references to the bot.
"""

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
    def __init__(self, *args, **keys):
        Expert.__init__(self, *args, **keys)
        self.log.error("This bot is deprecated. It will move permanently under ahcommunity repository after 2016-01-01. Please update your references to the bot.")

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
