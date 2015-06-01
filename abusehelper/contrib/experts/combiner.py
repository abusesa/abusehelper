from abusehelper.bots.experts import combiner
from abusehelper.bots.experts.combiner import *

"""
Important notice:

This bot is deprecated and will not be maintained. Maintained
version exists now permanently under abusehelper.bots package. 

abusehelper.contrib package will be removed after 2016-01-01.
During the migration period, you can already update your 
references to the bot.
"""

class RoomBot(combiner.RoomBot):
    def __init__(self, *args, **keys):
        combiner.RoomBot.__init__(self, *args, **keys)
        self.log.error("This bot is deprecated. It will move permanently under abusehelper.bots package after 2016-01-01. Please update your references to the bot.")


class Expert(combiner.Expert):
    def __init__(self, *args, **keys):
        combiner.Expert.__init__(self, *args, **keys)
        self.log.error("This bot is deprecated. It will move permanently under abusehelper.bots package after 2016-01-01. Please update your references to the bot.")


class Combiner(combiner.Combiner):
    def __init__(self, *args, **keys):
        combiner.Combiner.__init__(self, *args, **keys)
        self.log.error("This bot is deprecated. It will move permanently under abusehelper.bots package after 2016-01-01. Please update your references to the bot.")

if __name__ == "__main__":
    Combiner.from_command_line().execute()
