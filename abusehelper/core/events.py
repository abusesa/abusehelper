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

        event = Event(element)
        for attr in element.children("attr").with_attrs("key", "value"):
            event.add(attr.get_attr("key"), attr.get_attr("value"))
        return event

    def __init__(self, element=None):
        self.attrs = dict()
        self._element = None

    def add(self, key, value):
        self._element = None
        self.attrs.setdefault(key, set()).add(value)

    def contains_key_value(self, key, value):
        return value in self.attrs.get(key, ())
        
    def contains_key(self, key):
        return key in self.attrs

    def to_element(self):
        if self._element is None:
            event = Element("event", xmlns=EVENT_NS)

            for key, values in self.attrs.items():
                for value in values:
                    attr = Element("attr", key=key, value=value)
                    event.add(attr)
            self._element = event
        return self._element

@threado.stream_fast
def stanzas_to_events(inner):
    while True:
        yield inner

        for element in inner.iter():
            for child in element.children():
                event = Event.from_element(child)
                if event is not None:
                    inner.send(event)

@threado.stream_fast
def events_to_elements(inner, include_body=True):
    while True:
        yield inner

        for event in inner.iter():
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
