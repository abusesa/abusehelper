from idiokit import threado, xmlcore, jid, xmpp
from abusehelper.core import events, bot
from abusehelper.contrib.experts import combiner

def parse(text):
    # Expected format
    # ASN,Rank,Matched BL,Highest Malicious Ranking,Current Position
    # 2611,1.00003737554952,2/18,1.273828125,10445/61949

    for row in text.split("\n"):
        row = row.strip()

        # ignore empty row and comments
        if len(row) > 0 and row[0] == "#":
            continue

        els = row.split(",")
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
def request(inner, xmpp, to, text):
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
        xmpp.core.message(to, body, type='chat', id='blue')


        while True:
            yield inner, channel
            for _ in inner:
                pass

            for elements in channel:
                for msg in elements.named("message"):
                    if(msg.with_attrs("from")):
                        sender = jid.JID(msg.get_attr("from"))
                        if sender.bare() != to.bare():
                            continue

                    for body in msg.children().named("body"):
                        result = parse(body.text)
                        if result is not None:
                            inner.finish(result)
    finally:
        xmpp.discard_listener(callback)

class BGPRankingBot(combiner.Expert):
    bgp_jid = bot.Param()
    bgp_pwd = bot.Param()

    @threado.stream
    def main(inner, self, *args, **keys):
        self.bgp_conn = yield inner.sub(xmpp.connect(self.bgp_jid,
                                                     self.bgp_pwd,
                                                     None, None,
                                                     False, None))
        self.bgp_conn.core.presence()

        yield inner.sub(combiner.Expert.main(self, *args, **keys))

    @threado.stream
    def augment(inner, self):
        while True:
            eid, event = yield inner
            if event.contains("bgprank") or not event.contains("ip"):
                continue

            augmented = events.Event()

            for ip in event.values("ip"):
                rank = yield request(self.bgp_conn,
                                     "bgpranking@p.smile.public.lu",
                                     "ip " + ip)
                augmented.add("bgpranking", rank["Rank"])
		augmented.add("bgprankpos", rank["Position"])
		augmented.add("bgprankmax", rank["HighRank"])

            inner.send(eid, augmented)

if __name__ == "__main__":
    BGPRankingBot.from_command_line().execute()
