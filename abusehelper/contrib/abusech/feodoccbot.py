from abusehelper.core import bot

from . import host_or_ip, split_description, AbuseCHFeedBot


class FeodoCcBot(AbuseCHFeedBot):
    feed_type = "c&c"

    feeds = bot.ListParam(default=["https://feodotracker.abuse.ch/feodotracker.rss"])

    # The timestamp in the title appears to be the firstseen timestamp,
    # skip including it as the "source time".
    parse_title = None

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
