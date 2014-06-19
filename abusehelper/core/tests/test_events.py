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


class TestEventCollector(unittest.TestCase):
    def test_pickling_backwards_compatibility(self):
        c = pickle.loads(
            '\x80\x02cabusehelper.core.events\nEventCollector\nq\x00K\x06' +
            'UP\x1f\x8b\x08\x00N\x87KQ\x02\xffj`\xaa-d\x8c`d``H\x8c-d\x023' +
            '\x92\x12\x8b\xf5\x1a\xe0\xc2\xc90\xe1\x14\xa00\x00\x00\x00\xff' +
            '\xff\x03\x00\xe2_\xbaF.\x00\x00\x00\x1f\x8b\x08\x00h\x87KQ\x02' +
            '\xff\x02\x00\x00\x00\xff\xff\x03\x00\x00\x00\x00\x00\x00\x00\x00' +
            '\x00q\x01K\x02\x87q\x02Rq\x03.')
        self.assertEqual([events.Event({"a": "b"}), events.Event({"c": "d"})], list(c))
