"""
abuse.ch Feodo RSS feed bot.

Maintainer: Codenomicon <clarified@codenomicon.com>
"""

import re

from abusehelper.core import bot
from . import host_or_ip, split_description, AbuseCHFeedBot


class FeodoCcBot(AbuseCHFeedBot):
    feed_type = "c&c"

    feeds = bot.ListParam(default=["https://feodotracker.abuse.ch/feodotracker.rss"])

    def parse_title(self, title):
        pieces = title.split(None, 1)

        yield host_or_ip(pieces[0])

        if len(pieces) > 1:
            date = pieces[1]
            date = re.sub("[()]", "", date)
            yield "additional information", "first seen: " + date + "Z"

    def parse_description(self, description):
        got_version = False

        for key, value in split_description(description):
            if key == "version":
                yield "malware", "feodo." + value.strip().lower()
                got_version = True
            elif key == "host":
                yield host_or_ip(value)

        if not got_version:
            yield "malware", "feodo"


if __name__ == "__main__":
    FeodoCcBot.from_command_line().execute()
