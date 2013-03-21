import pickle
import unittest

from .. import events


class TestEventCollector(unittest.TestCase):
    def test_collectors_can_be_pickled_and_unpickled(self):
        ab = events.Event({"a": "b"})
        cd = events.Event({"c": "d"})

        original = events.EventCollector()
        original.append(ab)
        original.append(cd)

        unpickled = pickle.loads(pickle.dumps(original))
        self.assertEqual([ab, cd], list(unpickled.purge()))

    def test_events_can_be_appended_to_an_unpickled_collector(self):
        ab = events.Event({"a": "b"})
        cd = events.Event({"c": "d"})

        original = events.EventCollector()
        original.append(ab)

        unpickled = pickle.loads(pickle.dumps(original))
        unpickled.append(cd)
        self.assertEqual([ab, cd], list(unpickled.purge()))
