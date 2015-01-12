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

use_legacy = False
try:
    from geoip2.database import Reader as GeoIP
    from geoip2.errors import AddressNotFoundError
except ImportError:
    from pygeoip import GeoIP, GeoIPError
    use_legacy = True

def load_geodb(path, log=None):
    reader = GeoIP(path)

    if use_legacy:
        fun = legacy_geoip
        if log:
            log.info("Legacy GeoIP initiated")
    else:
        fun = geoip
        if log:
            log.info("GeoIP2 initiated")

    def geoip_reader(ip):
        return fun(reader, ip)

    return geoip_reader


def geoip(reader, ip):
    try:
        record = reader.city(ip)
    except AddressNotFoundError:
        return {}

    if record is None:
        return {}

    result = {}

    geoip_cc = record.country.iso_code
    if geoip_cc:
        result["geoip cc"] = [geoip_cc]

    latitude = record.location.latitude
    longitude = record.location.longitude
    if latitude and longitude:
        result["latitude"] = [unicode(latitude)]
        result["longitude"] = [unicode(longitude)]

    return result


def legacy_geoip(reader, ip):
    if not is_ipv4(ip):
        return {}

    try:
        record = reader.record_by_addr(ip)
    except GeoIPError:
        return {}

    if record is None:
        return {}

    result = {}

    geoip_cc = record.get("country_code", None)
    if geoip_cc:
        result["geoip cc"] = [geoip_cc]

    latitude = record.get("latitude", None)
    longitude = record.get("longitude", None)
    if latitude and longitude:
        result["latitude"] = [unicode(latitude)]
        result["longitude"] = [unicode(longitude)]

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
        self.geoip = load_geodb(self.geoip_db, self.log)

    def geomap(self, event, key):
        for ip in event.values(key):
            result = self.geoip(ip)
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
