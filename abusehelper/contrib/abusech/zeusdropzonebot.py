"""
abuse.ch Zeus dropzone RSS feed.

Maintainer: Lari Huttunen <mit-code@huttu.net>
"""

from abusehelper.bots.abusech import zeusdropzonebot


class ZeusDropzoneBot(zeusdropzonebot.ZeusDropzoneBot):
    
    def __init__(self, *args, **keys):
        zeusdropzonebot.ZeusDropzoneBot.__init__(self, *args, **keys)
        self.log.error("This bot is deprecated. It will move permanently under abusehelper.bots package after 2016-01-01. Please update your references to the bot.")

if __name__ == "__main__":
    ZeusDropzoneBot.from_command_line().execute()
