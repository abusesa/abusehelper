# -*- coding: utf-8 -*-

# In the runtime config:
# yield Source("cleanmxbot", csv_url="http://support.clean-mx.de/clean-mx/xmlphishing?response=alive&format=csv&domain=")
# yield Source("cleanmxbot", csv_url="http://support.clean-mx.de/clean-mx/xmlviruses?response=alive&format=csv&domain=", csv_name="xmlvirii")

"""
Important notice:

This bot is deprecated and will not be maintained. Maintained
version exists now permanently under abusehelper.bots package. 

abusehelper.contrib package will be removed after 2016-01-01.
During the migration period, you can already update your 
references the bot.
"""


from abusehelper.bots.cleanmx import cleanmxbot


class CleanMXBot(cleanmxbot.CleanMXBot):
    
    def __init__(self, *args, **keys):
        self.log.error("This bot is deprecated. It will move permanently under abusehelper.bots package after 2016-01-01. Please update your references to the bot.")
        cleanmxbot.CleanMXBot.__init__(self, *args, **keys)

if __name__ == "__main__":
    CleanMXBot.from_command_line().execute()
