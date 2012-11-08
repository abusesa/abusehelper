"""
abuse.ch Palevo C&C feed RSS bot.

Maintainer: Lari Huttunen <mit-code@huttu.net>
"""

from abusehelper.core import bot

from . import is_ip, split_description, AbuseCHFeedBot


class PalevoCcBot(AbuseCHFeedBot):
    feeds = bot.ListParam(default=["https://palevotracker.abuse.ch/?rssfeed"])
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
            yield "source time", pieces[1]

    def parse_description(self, description):
        for key, value in split_description(description):
            if key == "status":
                yield key, value
            elif key == "sbl" and value.lower() != "not listed":
                yield key + " id", value
            elif key == "ip address" and not self.treat_as_dns_source:
                yield "ip", value

if __name__ == "__main__":
    PalevoCcBot.from_command_line().execute()
