"""
abuse.ch Zeus dropzone RSS feed.

Maintainer: Lari Huttunen <mit-code@huttu.net>
"""

from abusehelper.bots.abusech import spyeyedropzonebot


class SpyEyeDropzoneBot(spyeyedropzonebot.SpyEyeDropzoneBot):
    
    def __init__(self, *args, **keys):
        spyeyedropzonebot.SpyEyeDropzoneBot.__init__(self, *args, **keys)
        self.log.error("This bot is deprecated. It will move permanently under abusehelper.bots package after 2016-01-01. Please update your references to the bot.")

if __name__ == "__main__":
    SpyEyeDropzoneBot.from_command_line().execute()
