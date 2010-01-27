from abusehelper.core import events, ircfeed

class IRCExampleBot(ircfeed.IRCFeedBot):
    def parse(self, prefix, command, params):
        parts = params[1].split()
        if len(parts) < 11 or not parts[7].startswith("HTTP"):
            return None

        event = events.Event()
        event.add("ip", parts[0])
        event.add("time", " ".join(parts[3:5]))
        event.add("request", parts[6])
        event.add("agent", " ".join(parts[11:]))

        return event

if __name__ == "__main__":
    IRCExampleBot.from_command_line().run()
