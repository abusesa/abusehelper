from abusehelper.bots.accesslogbot import accesslogbot

"""
Important notice:

This bot is deprecated and will not be maintained. Maintained
version will be moved under abusehelper.bots package. 

abusehelper.contrib package will be removed after 2016-01-01.
During the migration period, you can already update your 
references to the bot.
"""


class AccessLogBot(accesslogbot.AccessLogBot):

    def __init__(self, *args, **keys):
        accesslogbot.AccessLogBot.__init__(self, *args, **keys)
        self.log.error("This bot is deprecated. It will move permanently under abusehelper.bots package after 2016-01-01. Please update your references to the bot.")

if __name__ == "__main__":
    AccessLogBot.from_command_line().execute()
