"""
SpyEye C&C RSS feed bot.

Maintainer: Lari Huttunen <mit-code@huttu.net>
"""

from abusehelper.bots.abusech import spyeyeccbot


class SpyEyeCcBot(spyeyeccbot.SpyEyeCcBot):
    
    def __init__(self, *args, **keys):
        spyeyeccbot.SpyEyeCcBot.__init__(self, *args, **keys)
        self.log.error("This bot is deprecated. It will move permanently under abusehelper.bots package after 2016-01-01. Please update your references to the bot.")

if __name__ == "__main__":
    SpyEyeCcBot.from_command_line().execute()
