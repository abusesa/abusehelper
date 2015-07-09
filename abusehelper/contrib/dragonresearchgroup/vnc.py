"""
Dragon research group bot (VNC)

This bot is deprecated and will not be maintained. Maintained
version exists now permanently under abusehelper.bots package. 

abusehelper.contrib package will be removed after 2016-01-01.
During the migration period, you can already update your 
references the bot.
"""

from . import DragonBot


class DragonVncBot(DragonBot):
    url = "https://dragonresearchgroup.org/insight/vncprobe.txt"


if __name__ == "__main__":
    DragonVncBot.from_command_line().execute()
