import idiokit
import combiner
from abusehelper.core import events, cymruwhois

class CymruWhoisExpert(combiner.Expert):
    def augment_keys(self, keys=["ip"], **_):
        for key in keys:
            if isinstance(key, basestring):
                prefix = ""
            else:
                key, prefix = key
            yield key, prefix

    @idiokit.stream
    def augment(self, ip_key, prefix):
        while True:
            eid, event = yield idiokit.next()

            augmentation = events.Event()
            for ip in event.values(ip_key):
                items = yield cymruwhois.resolve(ip)
                for key, value in items:
                    augmentation.add(prefix + key, value)

            if augmentation.contains():
                yield idiokit.send(eid, augmentation)

if __name__ == "__main__":
    CymruWhoisExpert.from_command_line().execute()
