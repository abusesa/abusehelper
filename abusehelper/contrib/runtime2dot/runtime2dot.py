from abusehelper.bots.runtime2dot import runtime2dot

"""
Important notice:

This module is deprecated and will not be maintained. Maintained
version exists now permanently under abusehelper.bots package. 

abusehelper.contrib package will be removed after 2016-01-01.
During the migration period, you can already update your 
references.
"""

class DotBot(runtime2dot.DotBot):
    
    def __init__(self, *args, **keys):
        runtime2dot.DotBot.__init__(self, *args, **keys)
        self.log.error("This bot is deprecated. It will move permanently under abusehelper.bots package after 2016-01-01. Please update your references to the bot.")

if __name__ == "__main__":
    DotBot.from_command_line().execute()
