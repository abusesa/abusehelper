from idiokit import threado
from idiokit.xmlcore import Element

EVENT_NS = "idiokit#event"

class Event(object):
    @classmethod
    def from_element(self, element):
        if len(element) != 1:
            return None
        if not element.named("event", EVENT_NS):
            return None

        event = Event()
        for attr in element.children("attr").with_attrs("key", "value"):
            event.add(attr.get_attr("key"), attr.get_attr("value"))
        return event

    def __init__(self):
        self.attrs = dict()

    def add(self, key, value):
        self.attrs.setdefault(key, set()).add(value)

    def contains_key_value(self, key, value):
        return value in self.attrs.get(key, ())
        
    def contains_key(self, key):
        return key in self.attrs

    def to_element(self):
        event = Element("event", xmlns=EVENT_NS)

        for key, values in self.attrs.items():
            for value in values:
                attr = Element("attr", key=key, value=value)
                event.add(attr)
        return event

@threado.stream
def stanzas_to_events(inner):
    while True:
        element = yield inner

        for child in element.children():
            event = Event.from_element(child)
            if event is not None:
                inner.send(event)

@threado.stream
def events_to_elements(inner, include_body=True):
    while True:
        event = yield inner

        if include_body:
            fields = list()
            for key, values in event.attrs.items():
                for value in values:
                    fields.append("%s=%s" % (key, value))
            body = Element("body")
            body.text = "%s" % ", ".join(fields)
            inner.send(body, event.to_element())
        else:
            inner.send(event.to_element())
