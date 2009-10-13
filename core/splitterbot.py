import uuid
import rules
import logging
import time

from idiokit import threado, events, pep
from idiokit.xmpp import XMPP
from idiokit.core import XMPPError

SPLITTER_CONFIG_NS = "idiokit/splitter#ruleset"

class Splitter(threado.GeneratorStream):
    def __init__(self, xmpp):
        threado.GeneratorStream.__init__(self)

        self.xmpp = xmpp
        self.rooms = dict()
        self.ruleset = rules.RuleSet()

        self.start()

    def _add_room(self, tag):
        if tag in self.rooms:
            return self.rooms[tag]
        room = events.events_to_elements() | self._handle_room(tag)
        self.rooms[tag] = room
        return room

    def _discard_room(self, tag):
        if tag not in self.rooms:
            return
        room = self.rooms.pop(tag, None)
        room.finish()

    @threado.thread
    def _handle_room(inner, self, tag, retry_delay=10.0, max_retry_delay=120.0):
        while True:
            logging.info("Attempting to join room '%s'.", tag)
            try:
                room = self.xmpp.muc.join(tag, "splitter" + uuid.uuid4().hex)
            except XMPPError, error:
                logging.warning("Could not join room '%s': %s", tag, error)
                logging.warning("Retrying in %d seconds.", retry_delay)

                retry_time = time.time() + retry_delay
                retry_delay *= 2
                while True:
                    try:
                        inner.next(max(0.0, retry_time-time.time()))
                    except threado.Timeout:
                        break
            else:
                logging.info("Joined room '%s'.", tag)
                break

        try:
            for elements in inner + room:
                if room.was_source:
                    continue
                room.send(*elements)
        finally:
            logging.info("Left room '%s'.", tag)
            room.exit()

    @threado.stream
    def update_ruleset(inner, self):
        logging.info("Waiting for a ruleset.")

        while True:
            elements = yield inner

            for element in elements:
                logging.info("Got a new ruleset: %s", element.serialize())
                try:
                    ruleset = rules.RuleSet.from_element(element)
                except rules.RuleError, error:
                    logging.warning("Could not parse rule: %s",
                                    error.args[0].serialize())
                    logging.info("Ruleset not updated.")
                else:
                    logging.info("Ruleset updated.")
                    for tag in set(self.ruleset.tags()) - set(ruleset.tags()):
                        self._discard_room(tag)
                    for tag in set(ruleset.tags()) - set(self.ruleset.tags()):
                        self._add_room(tag)
                    self.ruleset = ruleset
        
    def run(self):
        pep_stream = pep.pep_stream(self.xmpp, SPLITTER_CONFIG_NS)
        config_stream = pep_stream | self.update_ruleset()

        while True:
            try:
                event = yield self.inner, config_stream
            except:
                config_stream.rethrow()
                raise

            for tag in self.ruleset.tags_for(event):
                room = self._add_room(tag)
                room.send(event)

def publish_ruleset(ruleset, jid, password):
    xmpp = XMPP(jid, password)
    xmpp.connect()
    xmpp.core.presence()
    pep.publish(xmpp, SPLITTER_CONFIG_NS, ruleset.to_element())

def main(jid, password, room):
    xmpp = XMPP(jid, password)
    xmpp.connect()
    xmpp.core.presence()
    room = xmpp.muc.join(room, "splitter" + uuid.uuid4().hex)

    logging.getLogger().setLevel(logging.INFO)
    splitter = Splitter(xmpp)

    for _ in room | events.stanzas_to_events() | splitter: pass

if __name__ == "__main__":
    main("user@example.com", "password", "room@conference.example.com")
