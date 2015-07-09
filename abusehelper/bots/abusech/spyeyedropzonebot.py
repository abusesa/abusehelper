"""
abuse.ch Zeus dropzone RSS feed.

Maintainer: Lari Huttunen <mit-code@huttu.net>
"""

from abusehelper.core import bot

from . import host_or_ip_from_url, split_description, AbuseCHFeedBot


class SpyEyeDropzoneBot(AbuseCHFeedBot):
    feed_malware = "spyeye"
    feed_type = "dropzone"

    feeds = bot.ListParam(default=["https://spyeyetracker.abuse.ch/monitor.php?rssfeed=dropurls"])

    def parse_description(self, description):
        for key, value in split_description(description):
            if key == "status":
                yield key, value
            if key == "spyeye dropurl":
                yield "url", value
                yield host_or_ip_from_url(value)

if __name__ == "__main__":
    SpyEyeDropzoneBot.from_command_line().execute()
