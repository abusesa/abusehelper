import time
import calendar

from abusehelper.core import bot, archivebot


def current_timestamp(timestamp, period):
    time_list = list(time.gmtime())
    period = period.lower()

    if period == "day":
        time_list[3:] = [0] * 6
    elif period == "month":
        time_list[2:] = [1] + [0] * 6
    elif period == "week":
        time_list[2] -= time_list[6]
        time_list[3:] = [0] * 6
    elif period == "year":
        time_list[1:] = [1, 1] + [0] * 6
    else:
        return None

    return time.gmtime(calendar.timegm(time_list))


class RollOverArchiveBot(archivebot.ArchiveBot):
    rollover = bot.Param("period for doing archive file rollover " +
                         "(day, week, month or year)")

    def archive_path(self, timestamp, room_name, event):
        path = archivebot.ArchiveBot.archive_path(self, timestamp, room_name, event)
        path += "." + time.strftime("%Y%m%d", current_timestamp(timestamp, self.rollover))
        return path

if __name__ == "__main__":
    RollOverArchiveBot.from_command_line().execute()
