"""
abuse.ch SpyEye config RSS feed bot.

Maintainer: Lari Huttunen <mit-code@huttu.net>
"""

from abusehelper.core import bot

from abusehelper.bots.abusech import host_or_ip_from_url, split_description, AbuseCHFeedBot


class SpyEyeConfigBot(AbuseCHFeedBot):
    feed_malware = "spyeye"
    feed_type = "malware configuration"

    feeds = bot.ListParam(default=["https://spyeyetracker.abuse.ch/monitor.php?rssfeed=configurls"])

    def parse_description(self, description):
        for key, value in split_description(description):
            if key == "status":
                yield key, value
            if key == "spyeye configurl":
                yield "url", value
                yield host_or_ip_from_url(value)
            elif key == "md5 hash":
                yield "md5", value

if __name__ == "__main__":
    SpyEyeConfigBot.from_command_line().execute()
