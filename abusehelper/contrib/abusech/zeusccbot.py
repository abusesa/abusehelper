"""
abuse.ch Zeus C&C RSS feed bot.

Maintainer: Lari Huttunen <mit-code@huttu.net>
"""

import re
from abusehelper.core import bot

from . import is_ip, resolve_level, split_description, AbuseCHFeedBot


class ZeusCcBot(AbuseCHFeedBot):
    feed_malware = "ZeuS"
    feed_type = "c&c"

    feeds = bot.ListParam(default=["https://zeustracker.abuse.ch/rss.php"])
    # If treat_as_dns_source is set, the feed ip is dropped.
    treat_as_dns_source = bot.BoolParam()

    def parse_title(self, title):
        pieces = title.split(None, 1)

        host = pieces[0]
        if is_ip(host):
            yield "ip", host
        else:
            yield "host", host

        if len(pieces) > 1:
            date = pieces[1]
            date = re.sub("[()]", "", date)
            yield "source time", date + " UTC"

    def parse_description(self, description):
        for key, value in split_description(description):
            if key == "status":
                yield key, value
            elif key == "level":
                yield "description", resolve_level(value)
            elif key == "sbl" and value.lower() != "not listed":
                yield key + " id", value
            elif key == "ip address" and not self.treat_as_dns_source:
                yield "ip", value

if __name__ == "__main__":
    ZeusCcBot.from_command_line().execute()
