import pickle
import unittest

from .. import events


class TestEvent(unittest.TestCase):
    def test_pickling(self):
        e = events.Event({"a": "b"})
        self.assertEqual(e, pickle.loads(pickle.dumps(e)))
