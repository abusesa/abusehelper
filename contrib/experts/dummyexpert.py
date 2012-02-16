import idiokit
from abusehelper.core import events
from combiner import Expert

class DummyExpert(Expert):
    @idiokit.stream
    def augment(self):
        counter = 0

        while True:
            eid, event = yield idiokit.next()

            augment = events.Event()
            augment.add("dummy counter", unicode(counter))
            counter += 1

            yield idiokit.send(eid, augment)

if __name__ == "__main__":
    DummyExpert.from_command_line().execute()
