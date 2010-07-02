from idiokit import threado
from abusehelper.core import events, rules, taskfarm, bot, services, roomgraph, zcw

class WhoisBot(roomgraph.RoomGraphBot):
    def __init__(self, *args, **keys):
        roomgraph.RoomGraphBot.__init__(self, *args, **keys)
        

    @threado.stream_fast
    def distribute(inner, self, name):
        count = 0
        while True:
            yield inner

            tests = list(self.srcs.get(name, ()))
            for event in inner:
                ip = event.value("ip", None)
                if(ip == None):
                    continue                
                ai = zcw.searchAbuseInfo(ip)
                
                event.add("abuse_email", ai.getAbuseMail())
                if not event.contains("as_name"):
                    event.add("as_name", ai.getNetworkName())
                if not event.contains("as_description"):
                    event.add("as_description", ai.getInfos())
                if not event.contains("country"):
                    event.add("country", ai.getCountryName())
                if not event.contains("country_code"):
                    event.add("country_code", ai.getCountryCode())
 
                count += 1
                if count % 100 == 0:
                    self.log.info("Seen %d events in room %r", count, name)

                for dst_room, rules in tests:
                    dst = self.rooms.get(dst_room)
                    if dst is None:
                        continue

                    for rule in rules:
                        if rule(event):
                            dst.send(event)
                            break

if __name__ == "__main__":
    WhoisBot.from_command_line().execute()
