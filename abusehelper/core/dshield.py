from idiokit import threado
from abusehelper.core import utils, cymru, bot, events

class DShieldBot(bot.PollingBot):
    COLUMNS = ["ip", "reports", "targets", "firstseen", "lastseen", "updated"]

    use_cymru_whois = bot.BoolParam(default=False)

    def __init__(self, *args, **keys):
        bot.PollingBot.__init__(self, *args, **keys)
        self.whois = cymru.CymruWhoisAugmenter()

    def feed_keys(self, asns=(), **keys):
        for asn in asns:
            yield (str(asn),)

    def poll(self, asn):
        tail = self.normalize(asn)
        if self.use_cymru_whois:
            tail = tail | self.whois.augment() | self.filter(asn)
        return self._poll(asn) | tail

    @threado.stream
    def _poll(inner, self, asn, url="http://dshield.org/asdetailsascii.html"):
        url += "?as=%s" % asn

        self.log.info("ASN%s: downloading", asn)
        try:
            info, fileobj = yield inner.sub(utils.fetch_url(url))
        except utils.FetchUrlFailed, fuf:
            self.log.error("ASN%s: downloading failed: %r", asn, fuf)
            return
        self.log.info("ASN%s: downloaded", asn)

        charset = info.get_param("charset")
        filtered = (x for x in fileobj if x.strip() and not x.startswith("#"))
        yield inner.sub(utils.csv_to_events(filtered,
                                            delimiter="\t", 
                                            columns=self.COLUMNS,
                                            charset=charset))

    @threado.stream
    def normalize(inner, self, asn):
        while True:
            event = yield inner

            if self.use_cymru_whois:
                event.add("dshield asn", asn)
            else:
                event.add("asn", asn)

            ips = list(event.values("ip"))
            event.clear("ip")
            for ip in ips:
                try:
                    ip = ".".join(map(str, map(int, ip.split("."))))
                except ValueError:
                    pass
                event.add("ip", ip)
            
            event.add("feed", "dshield")
            inner.send(event)

    @threado.stream
    def filter(inner, self, asn):
        while True:
            event = yield inner
            if event.contains("asn", asn):
                inner.send(event)

if __name__ == "__main__":
    DShieldBot.from_command_line().execute()
