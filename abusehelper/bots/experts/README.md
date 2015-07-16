## Example

The following piece of code demonstrates how to create a custom expert bot that just adds the key-value pair **counter=_n_** to each event it encounters.

    import idiokit
    from abusehelper.core import events
    from abusehelper.contrib.experts import Expert


    class DummyExpert(Expert):
        @idiokit.stream
        def augment(self):
            counter = 0

            while True:
                eid, event = yield idiokit.next()

                augment = events.Event()
                augment.add("counter", unicode(counter))
                counter += 1

                yield idiokit.send(eid, augment)


    if __name__ == "__main__":
        DummyExpert.from_command_line().execute()
