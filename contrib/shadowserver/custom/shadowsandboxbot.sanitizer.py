from abusehelper.core import events, config

sanitizer = config.load_module("sanitizer")

class ShadowSandboxBotSanitizer(sanitizer.Sanitizer):
    def sanitize(self, event):
        
        new = events.Event()
        new.update("ip", event.values("ip", sanitizer.ip))
        new.update("time", event.values("timestamp", sanitizer.time))
        new.update("asn", event.values("asn"))
        new.add("source", "shadowserver")
        new.add("type", "sandbox")

        if not new.contains("ip"):
            self.log.error("No valid IP for event %r", event)
            return []
        if not new.contains("time"):
            self.log.error("No valid time for event %r", event)
            return []

        self.log.info("Sandbox sanitizer %r", str(event))
        return [new]

if __name__ == "__main__":
    ShadowSandboxBotSanitizer.from_command_line().execute()
