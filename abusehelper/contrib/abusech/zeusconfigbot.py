"""
abuse.ch Zeus Config RSS feed bot.

Maintainer: Lari Huttunen <mit-code@huttu.net>
"""

from abusehelper.core import bot

from . import AbuseCHFeedBot
from abusehelper.bots.abusech import host_or_ip_from_url, split_description


class ZeusConfigBot(AbuseCHFeedBot):
    feed_malware = "zeus"
    feed_type = "malware configuration"

    feeds = bot.ListParam(default=["https://zeustracker.abuse.ch/monitor.php?urlfeed=configs"])

    def parse_description(self, description):
        for key, value in split_description(description):
            if key in ["status", "version"]:
                yield key, value
            elif key == "md5 hash":
                yield "md5", value
            elif key == "url":
                yield "url", value
                yield host_or_ip_from_url(value)

if __name__ == "__main__":
    ZeusConfigBot.from_command_line().execute()
