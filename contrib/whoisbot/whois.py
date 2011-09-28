from idiokit import threado
from abusehelper.contrib.whois import iptools
from abusehelper.core import events, bot
from abusehelper.contrib.experts import combiner

class WhoisBot(combiner.Expert):
    __iptools = None

    dbsrv = bot.Param()
    dbname = bot.Param()
    dbusr = bot.Param()
    dbpwd = bot.Param()

    def __init__(self, *args, **keys):
        combiner.Expert.__init__(self, *args, **keys)
        self.__iptools = iptools.IPTools(self.dbsrv, self.dbname, self.dbusr, self.dbpwd)
        
    @threado.stream
    def augment(inner, self):
        count = 0
        while True:
            eid, event = yield inner
            if(event == None):
                continue

            augmented = events.Event()

            for ip in event.values("ip"):
                if(ip == None):
                    self.log.error("No ip found in event %r", event)
                    continue      

                # Search abuse contact info          
                ai = self.__iptools.lookup(ip)
                if (ai == None):
                    self.log.error("No abuse info found for %s", str(ip))
                    continue               
 
                email = ai.getAbuseMail()
                if email is None:
                    self.log.error("No abuse email found for %r", event)
                else:
                    augmented.add("abuse_email", email)

                if not event.contains("as_name") and ai.getNetworkName() is not None:
                    augmented.add("as_name", ai.getNetworkName())
                if not event.contains("as_description") and ai.getNetworkInfo() is not None:
                    augmented.add("as_description", ai.getNetworkInfo())
                if not event.contains("country") and ai.getCountryName() is not None:
                    augmented.add("country", ai.getCountryName())
                if not event.contains("country_code") and ai.getCountryCode() is not None:
                    augmented.add("country_code", ai.getCountryCode())
 
                count += 1
                if count % 100 == 0:
                    self.log.info("Seen %d events in room %r", count, name)

                inner.send(eid, augmented)

if __name__ == "__main__":
    WhoisBot.from_command_line().execute()
