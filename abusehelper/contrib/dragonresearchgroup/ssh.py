"""
Dragon research group bot (SSH)

This bot is deprecated and will not be maintained. Maintained
version exists now permanently under abusehelper.bots package. 

abusehelper.contrib package will be removed after 2016-01-01.
During the migration period, you can already update your 
references the bot.
"""

from . import DragonBot


class DragonSshBot(DragonBot):
    url = "http://dragonresearchgroup.org/insight/sshpwauth.txt"


if __name__ == "__main__":
    DragonSshBot.from_command_line().execute()
