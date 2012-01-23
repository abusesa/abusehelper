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

    def geomap(self, event, key):
        ip = event.value(key, None)
        if not ip:
            return

        try:
            record = self.geoip.record_by_addr(ip)
        except pygeoip.GeoIPError, e:
            self.log.error("GeoIP fetch failed: %s", repr(e))
            return

        if not record:
            return

        augmentation = events.Event()

        if not event.contains('cc'):
            cc = record.get('country_code', None)
            if cc:
                augmentation.add('geoip_cc', cc)

        if not event.contains('latitude'):
            latitude = record.get('latitude', None)
            if latitude:
                augmentation.add('latitude', unicode(latitude))

        if not event.contains('longitude'):
            longitude = self.geoip.record_by_addr(ip)['longitude']
            if longitude:
                augmentation.add('longitude', unicode(longitude))

        yield augmentation

    @idiokit.stream
    def augment(self):
        while True:
            eid, event = yield idiokit.next()

            for augmentation in self.geomap(event, self.ip_key):
                yield idiokit.send(eid, augmentation)

if __name__ == "__main__":
    GeoIPExpert.from_command_line().execute()
