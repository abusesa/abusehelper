import pickle
import doctest
import unittest

from .. import events


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(events))
    return tests


class TestEvent(unittest.TestCase):
    def test_pickling(self):
        e = events.Event({"a": "b"})
        self.assertEqual(e, pickle.loads(pickle.dumps(e)))
