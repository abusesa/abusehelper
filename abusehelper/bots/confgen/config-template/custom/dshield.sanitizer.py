from abusehelper.core import events

import sanitizer

class DShieldSanitizer(sanitizer.Sanitizer):
    def sanitize(self, event):
        new = events.Event()

        new.update("ip", event.values("ip", sanitizer.ip))
        if not new.contains("ip"):
            self.log.error("No valid IP for event %r", event)
            return

        new.update("time", event.values("updated", sanitizer.time))
        if not new.contains("time"):
            self.log.error("No valid time for event %r", event)
            return

        new.update("asn", event.values("asn"))
        yield new

if __name__ == "__main__":
    DShieldSanitizer.from_command_line().execute()
