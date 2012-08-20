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

        return events.Event({
            "source": "accesslog",
            "ip": ip,
            "timestamp": timestamp,
            "request": request,
            "status": status,
            "bytes": bytes,
            "user_agent": user_agent
        })

if __name__ == "__main__":
    AccessLogBot.from_command_line().execute()
