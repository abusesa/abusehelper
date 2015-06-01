from abusehelper.bots.csv2xmpp import csv2xmpp

"""
Important notice:

This bot is deprecated and will not be maintained. Maintained
version exists now permanently under abusehelper.bots package. 

abusehelper.contrib package will be removed after 2016-01-01.
During the migration period, you can already update your 
references the bot.
"""

class CSV2XMPP(csv2xmpp.CSV2XMPP):

    def __init__(self, **keys):
        self.log.error("This bot is deprecated. It will move permanently under abusehelper.bots package after 2016-01-01. Please update your references to the bot.")
        csv2xmpp.CSV2XMPP.__init__(self, **keys)

if __name__ == "__main__":
    CSV2XMPP.from_command_line().execute()
