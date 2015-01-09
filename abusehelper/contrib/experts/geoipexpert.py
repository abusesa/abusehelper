"""
GeoIPExpert utilizes the pygeoip module for ip geolocation.
The DB needs to be separately downloaded from MaxMind,
http://www.maxmind.com/app/city
There is a free and a commercial versions of the DB, so please
check their licensing agreement if you are using the free
version in your deployment:
http://geolite.maxmind.com/download/geoip/database/LICENSE.txt
Pygeoip can currently use only the IPv4 version of the DB.

Maintainer: Lari Huttunen <mit-code@huttu.net>
"""
import socket
import idiokit
from abusehelper.core import events, bot
from abusehelper.contrib.experts.combiner import Expert


def geoip(reader, ip):
    try:
        record = reader.city(ip)
    except geoip2.errors.AddressNotFoundError:
        return {}

    if record is None:
        return {}

    return {"geoip cc": record.country.iso_code,
            "latitude": unicode(record.location.latitude),
            "longitude": unicode(record.location.longitude)}


def legacy_geoip(reader, ip):
    if not is_ipv4(ip):
        return {}

    try:
        record = reader.record_by_addr(ip)
    except pygeoip.GeoIPError:
        return {}

    if record is None:
        return {}

    result = {}

    geoip_cc = record.get("country_code", None)
    if geoip_cc:
        result["geoip cc"] = geoip_cc

    latitude = record.get("latitude", None)
    if latitude:
        result["latitude"] = unicode(latitude)

    longitude = record.get("longitude", None)
    if longitude:
        result["longitude"] = unicode(longitude)

    return result


def is_ipv4(ip):
    try:
        socket.inet_aton(ip)
    except (ValueError, socket.error):
        return False
    return True


class GeoIPExpert(Expert):
    geoip_db = bot.Param("path to the GeoIP database")
    ip_key = bot.Param("key which has IP address as value " +
                       "(default: %default)", default="ip")

    def __init__(self, *args, **keys):
        Expert.__init__(self, *args, **keys)

        try:
            import geoip2.database
            from maxminddb.errors import InvalidDatabaseError

            try:
                self.reader = geoip2.database.Reader(self.geoip_db)
            except InvalidDatabaseError:
                raise ImportError

            self.geoip = geoip
            self.log.info("GeoIP2 initiated")
        except ImportError:
            import pygeoip

            self.reader = pygeoip.GeoIP(self.geoip_db)
            self.geoip = legacy_geoip
            self.log.info("Legacy GeoIP initiated")

    def geomap(self, event, key):
        for ip in event.values(key):
            result = self.geoip(self.reader, ip)
            if not result:
                continue

            augmentation = events.Event(result)
            augmentation.add(key, ip)
            yield augmentation

    @idiokit.stream
    def augment(self):
        while True:
            eid, event = yield idiokit.next()

            for augmentation in self.geomap(event, self.ip_key):
                yield idiokit.send(eid, augmentation)

if __name__ == "__main__":
    GeoIPExpert.from_command_line().execute()
