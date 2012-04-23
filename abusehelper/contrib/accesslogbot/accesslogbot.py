from abusehelper.core import bot, events
from abusehelper.contrib.tailbot.tailbot import TailBot


class AccessLogBot(TailBot):
    path = bot.Param("access_log file path")

    def parse(self, line, _):
        line = line.strip()
        if not line:
            return

        left = line.split("[", 2)
        ip, _, _ = left[0].split()
        right = left[1].split("]", 2)
        timestamp = right[0]
        entry = right[1].split("\"")
        request = entry[1]
        status, bytes = entry[2].split()
        user_agent = entry[5]

        event = events.Event()
        event.add("source", "accesslog")
        event.add("ip", ip)
        event.add("timestamp", timestamp)
        event.add("request", request)
        event.add("status", status)
        event.add("bytes", bytes)
        event.add("user_agent", user_agent)
        return event

if __name__ == "__main__":
    AccessLogBot.from_command_line().execute()
