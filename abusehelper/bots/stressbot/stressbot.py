"""
Bot for testing XMPP server robustness. Sends rapidly as many events
to a channel as possible.

Maintainer: Codenomicon <clarified@codenomicon.com>
"""

import idiokit
from abusehelper.core import bot, events


class StressBot(bot.FeedBot):
    data = bot.Param("event data")

    @idiokit.stream
    def feed(self):
        event = events.Event.from_unicode(self.data.decode("utf-8"))

        while True:
            yield idiokit.send(event)

if __name__ == "__main__":
    StressBot.from_command_line().execute()
