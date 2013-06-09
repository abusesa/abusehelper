"""
abuse.ch Zeus Binary RSS feed bot.

Maintainer: Lari Huttunen <mit-code@huttu.net>
"""

from abusehelper.core import bot

from . import sanitize_url, host_or_ip_from_url, split_description, AbuseCHFeedBot


class ZeusBinaryBot(AbuseCHFeedBot):
    feed_malware = "zeus"
    feed_type = "malware"

    feeds = bot.ListParam(default=["https://zeustracker.abuse.ch/monitor.php?urlfeed=binaries"])

    def parse_description(self, description):
        for key, value in split_description(description):
            if key == "url":
                yield "url", sanitize_url(value)
                yield host_or_ip_from_url(value)
            elif key == "virustotal" and value.lower() != "n/a":
                yield "virustotal", value
            elif key == "status":
                yield "status", value
            elif key == "md5 hash":
                yield "md5", value

if __name__ == "__main__":
    ZeusBinaryBot.from_command_line().execute()
