from abusehelper.core import events, config

sanitizer = config.load_module("sanitizer")

class DShieldSanitizer(sanitizer.Sanitizer):
    def sanitize(self, event):
        new = events.Event()
        new.update("ip", event.values("ip", sanitizer.ip))
        new.update("time", event.values("updated", sanitizer.time))
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
