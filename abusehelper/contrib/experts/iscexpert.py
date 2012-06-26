import idiokit
from abusehelper.core import bot, events, utils
from combiner import Expert
import socket
import json

ISC_IP_API_URL = "http://isc.sans.edu/api/ip"

def is_ipv4(ip):
    try:
        socket.inet_aton(ip)
    except (ValueError, socket.error):
        return False
    return True

class IscExpert(Expert):
    ip_key = bot.Param("key which has IP address as value " +
                       "(default: %default)", default="ip")

    @idiokit.stream
    def get_isc_info(self, event, key, eid):
        for ip in event.values(key, filter=is_ipv4):
            url = "{0}/{1}?json".format(ISC_IP_API_URL, ip)
            
            try:
                info, fileobj = yield utils.fetch_url(url)
            except utils.FetchUrlFailed, fuf:
                self.log.error("Fetch failed: %r", fuf)
                continue

            data = json.load(fileobj)
            ip_data = data.get("ip")

            if ip_data:
                augmentation = events.Event()

                if int(ip_data.get("attacks", 0)) == 0:
                    augmentation.add("dshield attacks", "0")
                else:
                    for key, value in ip_data.iteritems():
                        key = unicode(key).strip()
                        value = unicode(value).strip()
                        if key == "country":
                            key = "cc"
                        augmentation.add("dshield " + key, value)

                yield idiokit.send(eid, augmentation)

    @idiokit.stream
    def augment(self):
        while True:
            eid, event = yield idiokit.next()
            yield self.get_isc_info(event, self.ip_key, eid)

if __name__ == "__main__":
    IscExpert.from_command_line().execute()
