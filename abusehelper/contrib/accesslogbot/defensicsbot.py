from abusehelper.core import bot, events
from accesslogbot import AccessLogBot

class DefensicsBot(AccessLogBot):
    path = bot.Param("access_log file path")

    def parse(self, line, _):
        line = line.strip()
        if not line:
            return

        event = super(DefensicsBot, self).parse(line, _)
        if event.contains("defensics") and not event.contains("user"):
            return event
        else:
            return


if __name__ == "__main__":
    DefensicsBot.from_command_line().execute()
