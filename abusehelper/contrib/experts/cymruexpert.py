from abusehelper.bots.experts import cymruexpert

"""
Important notice:

This bot is deprecated and will not be maintained. Maintained
version exists now permanently under abusehelper.bots package. 

abusehelper.contrib package will be removed after 2016-01-01.
During the migration period, you can already update your 
references to the bot.
"""

class CymruWhoisExpert(cymruexpert.CymruWhoisExpert):
    def __init__(self, *args, **keys):
        cymruexpert.CymruWhoisExpert.__init__(self, *args, **keys)
        self.log.error("This bot is deprecated. It will move permanently under abusehelper.bots package after 2016-01-01. Please update your references to the bot.")


if __name__ == "__main__":
    CymruWhoisExpert.from_command_line().execute()
