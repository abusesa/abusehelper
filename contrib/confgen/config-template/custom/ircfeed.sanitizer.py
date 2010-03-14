import re
from abusehelper.core import events, config

sanitizer = config.load_module("sanitizer")
dnsbl = re.compile("(?:^|,)([^,]+):[^0]").findall

class IRCFeedSanitizer(sanitizer.Sanitizer):
    def sanitize(self, event):
        new = events.Event()
        new.update("ip", event.values("ip", sanitizer.ip))
        new.update("asn", event.values("asn"))
        new.add("time", sanitizer.format_time())
        
        for types in event.values("dnsbl", dnsbl):
            new.update("type", types)
        if not new.contains("type"):
            new.add("type", "unknown")
            
        if not new.contains("ip"):
            self.log.error("No valid IP for event %r", event)
            return []
        return [new]

if __name__ == "__main__":
    IRCFeedSanitizer.from_command_line().execute()
