import re

from abusehelper.core import events, bot
from idiokit import threado, util
from idiokit.irc import IRC

class IRCFeedBot(bot.FeedBot):
    irc_host = bot.Param()
    irc_channel = bot.Param()
    irc_port = bot.IntParam(default=6667)
    irc_feed_nick = bot.Param(default=None)
    irc_own_nick = bot.Param(default="ircbot")
    irc_password = bot.Param(default=None)
    irc_use_ssl = bot.BoolParam()

    def filter(self, prefix, command, params):
        if command != "PRIVMSG":
            return False
        if not params or params[0] != self.irc_channel:
            return False
        
        sender = prefix.split("@", 1)[0].split("!", 1)[0]
        if self.irc_feed_nick is None or sender == self.irc_feed_nick:
            return True

    def parse(self, prefix, command, params):
        event = events.Event()

        event.add("prefix", prefix)
        event.add("command", command)
        for param in params:
            event.add("param", params)

        return event

    @threado.stream
    def _handle(inner, self):
        while True:
            prefix, command, params = yield inner
            if self.filter(prefix, command, params):
                event = self.parse(prefix, command, params)
                if event is not None:
                    inner.send(event)

    @threado.stream
    def feed(inner, self):
        irc = IRC(self.irc_host, self.irc_port, ssl=self.irc_use_ssl)

        self.log.info("Connecting to IRC server %r port %d", 
                      self.irc_host, self.irc_port)
        yield inner.sub(irc.connect(self.irc_own_nick, 
                                    password=self.irc_password))
        self.log.info("Connected to IRC server %r port %d", 
                      self.irc_host, self.irc_port)
        
        irc.join(self.irc_channel)
        self.log.info("Joined IRC channel %r", self.irc_channel)
        
        yield inner.sub(irc | self._handle())

class IRCFeedService(IRCFeedBot):
    def parse(self, prefix, command, params):
        field_rex = r"([^\s=]+)='([^']*)'"
        data_rex = r"^([^\s>]+)>\s*(("+ field_rex +"\s*,?\s*)*)\s*$"
        
        match = re.match(data_rex, util.guess_encoding(params[-1]))
        if not match:
            return None

        event = events.Event()
        event.add("type", match.group(1))

        fields = re.findall(field_rex, match.group(2) or "")
        for key, value in fields:
            event.add(key, value)
            
        return event

if __name__ == "__main__":
    IRCFeedService.from_command_line().execute()
