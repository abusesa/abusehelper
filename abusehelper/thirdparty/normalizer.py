from idiokit import threado

@threado.stream
def normalize(inner, conf):
    while True:
        event = yield inner
        for k,v in event.attrs.items():
            if k in conf:
                for newkey in conf[k]:
                    for value in v:

                        event.add(newkey,value)
        inner.send(event)

