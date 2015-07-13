"""
abuse.ch Palevo C&C feed RSS bot.

Maintainer: Lari Huttunen <mit-code@huttu.net>
"""

import urlparse
from abusehelper.core import bot

from . import host_or_ip, split_description, AbuseCHFeedBot


class PalevoCcBot(AbuseCHFeedBot):
    feed_malware = "palevo"
    feed_type = "c&c"

    feeds = bot.ListParam(default=["https://palevotracker.abuse.ch/?rssfeed"])

    def parse_link(self, link):
        # The source seems to provice invalid links, which can
        # be fixed by changing the URL scheme from http to https.
        split = urlparse.urlparse(link)
        if split[0].lower() == "http":
            link = urlparse.urlunparse(["https"] + list(split[1:]))
        yield "description url", link

    def parse_title(self, title):
        yield host_or_ip(title.split()[0])

    def parse_description(self, description):
        for key, value in split_description(description):
            if key == "status":
                yield key, value
            elif key == "sbl" and value.lower() != "not listed":
                yield key + " id", value
            elif key == "ip address":
                yield "ip", value

if __name__ == "__main__":
    PalevoCcBot.from_command_line().execute()
