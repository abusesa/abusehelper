import idiokit
from ...core import events, cymruwhois
from . import Expert


class CymruWhoisExpert(Expert):
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

            for ip in event.values(ip_key):
                items = yield cymruwhois.lookup(ip)
                if not items:
                    continue

                augmentation = events.Event()
                for key, value in items:
                    augmentation.add(prefix + key, value)
                yield idiokit.send(eid, augmentation)


if __name__ == "__main__":
    CymruWhoisExpert.from_command_line().execute()
