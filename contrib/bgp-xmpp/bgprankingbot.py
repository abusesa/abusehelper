from idiokit import threado, xmlcore, jid, xmpp, core
from abusehelper.core import events, rules, taskfarm, bot, services, roomgraph
import string, re

class BGPRankingBot(roomgraph.RoomGraphBot):
    bgpjid = bot.Param()
    bgppwd = bot.Param()
    bgpcon = None

    def __init__(self, *args, **keys):
        roomgraph.RoomGraphBot.__init__(self, *args, **keys)  
        threado.run(self.connect(self.bgpjid, self.bgppwd))

    @threado.stream
    def connect(inner, self, jid, password):
        conn = yield xmpp.connect(jid, password, None, None, False, None)
        conn.core.presence()
        self.bgpcon = conn

    @threado.stream_fast
    def request(inner, self, xmpp, to, text):
        channel = threado.Channel()

        def listener(success, value):
            if success:
                channel.send(value)
            else:
                exc, traceback = value
                channel.throw(exc, traceback)
            
        callback = xmpp.add_listener(listener)
        try:
            to = jid.JID(to)
            body = xmlcore.Element("body")
            body.text = text
            xmpp.core.message(to, body)

            while True:
                yield inner, channel
                for _ in inner:
                    pass

                for elements in channel:
                    for msg in elements.named("message"):
                        if(msg.with_attrs("from")):
                            sender = jid.JID(msg.get_attr("from"))
                            if sender.bare() !=  to.bare():
                                continue

                        for body in msg.children().named("body"):
                            result = parse(body.text)
                            if result is not None:
                                inner.finish(result)
        finally:
            xmpp.discard_listener(callback)

    def parse(text):
        #Expected format
        ## ASN,Rank,Matched BL,Highest Malicious Ranking,Current Position
        #2611,1.00003737554952,2/18,1.273828125,10445/61949
        rows = string.split(text, "\n")
    
        for row in rows:
            row = string.strip(row)
            #ignore empty row and comments
            if len(row) > 0 and row[0] == "#":
                continue
            els = string.split(row, ",")
            if(len(els) >= 5):
                bgpranking = {}
                bgpranking["ASN"] = els[0]
                bgpranking["Rank"] = els[1]
                bgpranking["BlackLists"] = els[2]
                bgpranking["HighRank"] = els[3]
                bgpranking["Position"] = els[4]
                return bgpranking
        return None

    @threado.stream_fast
    def distribute(inner, self, name):
        count = 0
        while True:
            yield inner

            tests = list(self.srcs.get(name, ()))
            for event in inner:
                if(event == None):
                    self.log.error("None event! Skipping!!")
                    continue

                ip = event.value("ip", None)
                if(ip == None):
                    self.log.error("No ip found in event %r", event)
                    continue

                if not event.contains("bgprank"):
                    bgprank = yield self.request(self.bgpcon, "bgpranking@p.smile.public.lu", ("ip %s" % (ip)))
                    if(bgprank is not None):
                        event.add("bgprank", bgprank["Rank"])

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
    BGPRankingBot.from_command_line().execute()

