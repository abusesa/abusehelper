from idiokit import threado
from abusehelper.core import events
from combiner import Expert

class DummyExpert(Expert):
    @threado.stream
    def augment(inner, self):
        counter = 0

        while True:
            eid, event = yield inner

            augment = events.Event()
            augment.add("dummy counter", unicode(counter))
            counter += 1

            inner.send(eid, augment)

if __name__ == "__main__":
    DummyExpert.from_command_line().execute()
