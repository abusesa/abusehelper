"""
abuse.ch Feodo RSS feed bot.

Maintainer: Codenomicon <clarified@codenomicon.com>
"""

from abusehelper.bots.abusech import feodoccbot


class FeodoCcBot(feodoccbot.FeodoCcBot):
    
    def __init__(self, *args, **keys):
        feodoccbot.FeodoCcBot.__init__(self, *args, **keys)
        self.log.error("This bot is deprecated. It will move permanently under abusehelper.bots package after 2016-01-01. Please update your references to the bot.")


if __name__ == "__main__":
    FeodoCcBot.from_command_line().execute()
