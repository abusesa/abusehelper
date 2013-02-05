"""
abuse.ch Palevo C&C feed RSS bot.

Maintainer: Lari Huttunen <mit-code@huttu.net>
"""

from abusehelper.core import bot

from . import host_or_ip, split_description, AbuseCHFeedBot


class PalevoCcBot(AbuseCHFeedBot):
    feed_malware = "Palevo"
    feed_type = "c&c"

    feeds = bot.ListParam(default=["https://palevotracker.abuse.ch/?rssfeed"])

    def parse_title(self, title):
        pieces = title.split(None, 1)

        yield host_or_ip(pieces[0])

        if len(pieces) > 1:
            yield "source time", pieces[1]

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
