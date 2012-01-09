import pygeoip

import idiokit
from abusehelper.core import events, bot
from abusehelper.contrib.experts.combiner import Expert

class GeoIPExpert(Expert):
    geoip_db = bot.Param("path to the GeoIP database")
    ip_key = bot.Param("key which has IP address as value " +
                       "(default: %default)", default="ip")

    def __init__(self, *args, **keys):
        Expert.__init__(self, *args, **keys)

        self.geoip = pygeoip.GeoIP(self.geoip_db)
        self.log.info('GeoIP initiated')

    def set_geo(self, event, key):
        ip = event.value(key, None)
        if not ip:
            return event

        try:
            record = self.geoip.record_by_addr(ip)
        except pygeoip.GeoIPError, e:
            self.log.error("GeoIP fetch failed: %s", repr(e))
            return event

        if not record:
            return event

        if not event.contains('cc'):
            cc = record.get('country_code', None)
            if cc:
                event.add('geoip_cc', cc)

        if not event.contains('latitude'):
            latitude = record.get('latitude', None)
            if latitude:
                event.add('latitude', unicode(latitude))

        if not event.contains('longitude'):
            longitude = self.geoip.record_by_addr(ip)['longitude']
            if longitude:
                event.add('longitude', unicode(longitude))

        return event

    @idiokit.stream
    def augment(self):
        while True:
            eid, event = yield idiokit.next()

            augmented = self.set_geo(event, self.ip_key)
            yield idiokit.send(eid, augmented)

if __name__ == "__main__":
    GeoIPExpert.from_command_line().execute()
