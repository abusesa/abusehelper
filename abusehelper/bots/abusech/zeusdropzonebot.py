"""
abuse.ch Zeus dropzone RSS feed.

Maintainer: Lari Huttunen <mit-code@huttu.net>
"""

from abusehelper.core import bot

from . import host_or_ip_from_url, split_description, AbuseCHFeedBot


class ZeusDropzoneBot(AbuseCHFeedBot):
    feed_malware = "zeus"
    feed_type = "dropzone"

    feeds = bot.ListParam(default=["https://zeustracker.abuse.ch/monitor.php?urlfeed=dropzones"])

    def parse_description(self, description):
        for key, value in split_description(description):
            if key == "status":
                yield key, value
            elif key == "url":
                yield "url", value
                yield host_or_ip_from_url(value)

if __name__ == "__main__":
    ZeusDropzoneBot.from_command_line().execute()
