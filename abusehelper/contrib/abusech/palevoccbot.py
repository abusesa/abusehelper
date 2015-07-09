"""
abuse.ch Palevo C&C feed RSS bot.

Maintainer: Lari Huttunen <mit-code@huttu.net>
"""

from abusehelper.bots.abusech import palevoccbot


class PalevoCcBot(palevoccbot.PalevoCcBot):
    
    def __init__(self, *args, **keys):
        palevoccbot.PalevoCcBot.__init__(self, *args, **keys)
        self.log.error("This bot is deprecated. It will move permanently under abusehelper.bots package after 2016-01-01. Please update your references to the bot.")

if __name__ == "__main__":
    PalevoCcBot.from_command_line().execute()
