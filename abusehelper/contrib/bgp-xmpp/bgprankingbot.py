import idiokit
from idiokit import xmlcore, xmpp
from idiokit.xmpp import jid
from abusehelper.core import events, bot
from abusehelper.bots.experts import combiner

"""
Important notice:

This bot is deprecated and will not be maintained. Maintained
version will be moved under ahcommunity repository. 

abusehelper.contrib package will be removed after 2016-01-01.
During the migration period, you can already update your 
references to the bot.
"""

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

@idiokit.stream
def request(xmpp, to, text):
    to = jid.JID(to)
    body = xmlcore.Element("body")
    body.text = text
    yield xmpp.core.message(to, body, type='chat', id='blue')

    while True:
        msg = yield xmpp.next()
        if(msg.with_attrs("from")):
            sender = jid.JID(msg.get_attr("from"))
            if sender.bare() != to.bare():
                continue

            for body in msg.children().named("body"):
                result = parse(body.text)
                if result is not None:
                    idiokit.stop(result)

class BGPRankingBot(combiner.Expert):
    """
        Implementation of an expert that will query the BGPRanking
        server to retrieve the ranking for the IP in the event.

        The ranking are retrieve through a live XMPP session with
        CIRCL.  This is a typical implementation of a bot-to-bot
        chat.
    """
    bgp_jid = bot.Param()
    bgp_pwd = bot.Param()
    bgp_ejid = bot.Param()

    def __init__(self, *args, **keys):
        combiner.Expert.__init__(self, *args, **keys)
        self.log.error("This bot is deprecated. It will move permanently under ahcommunity repository after 2016-01-01. Please update your references to the bot.")

    @idiokit.stream
    def main(self, *args, **keys):
        self.bgp_conn = None
        self.bgp_conn = yield xmpp.connect(self.bgp_jid,
                                                     self.bgp_pwd,
                                                     None, None,
                                                     False, None)
        self.bgp_conn.core.presence()

        yield combiner.Expert.main(self, *args, **keys)

    @idiokit.stream
    def augment(self):
        while True:
            eid, event = yield idiokit.next()
            if event.contains("bgpranking") or not event.contains("ip"):
                continue

            augmented = events.Event()

            for ip in event.values("ip"):
                if not self.bgp_conn:
                    continue

                rank = yield request(self.bgp_conn,
                                     self.bgp_ejid,
                                     "ip " + ip)
                augmented.add("bgpranking", rank["Rank"])

            yield idiokit.send(eid, augmented)

if __name__ == "__main__":
    BGPRankingBot.from_command_line().execute()
