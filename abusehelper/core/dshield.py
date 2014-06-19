from __future__ import absolute_import

import idiokit
from . import utils, cymruwhois, bot


class DShieldBot(bot.PollingBot):
    COLUMNS = ["ip", "reports", "targets", "firstseen", "lastseen", "updated"]

    use_cymru_whois = bot.BoolParam()

    def feed_keys(self, asns=(), **keys):
        for asn in asns:
            yield (str(asn),)

    def poll(self, asn):
        tail = self.normalize(asn)
        if self.use_cymru_whois:
            tail = tail | cymruwhois.augment("ip") | self.filter(asn)
        return self._poll(asn) | tail

    @idiokit.stream
    def _poll(self, asn, url="http://dshield.org/asdetailsascii.html"):
        url += "?as={0}".format(asn)

        self.log.info("ASN{0}: downloading".format(asn))
        try:
            info, fileobj = yield utils.fetch_url(url)
        except utils.FetchUrlFailed as fuf:
            raise bot.PollSkipped("downloading ASN{0} data failed ({1})".format(asn, fuf))
        self.log.info("ASN{0}: downloaded".format(asn))

        charset = info.get_param("charset")
        filtered = (x for x in fileobj if x.strip() and not x.startswith("#"))
        yield utils.csv_to_events(
            filtered,
            delimiter="\t",
            columns=self.COLUMNS,
            charset=charset)

    @idiokit.stream
    def normalize(self, asn):
        while True:
            event = yield idiokit.next()

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
            yield idiokit.send(event)

    @idiokit.stream
    def filter(self, asn):
        while True:
            event = yield idiokit.next()
            if event.contains("asn", asn):
                yield idiokit.send(event)


if __name__ == "__main__":
    DShieldBot.from_command_line().execute()
