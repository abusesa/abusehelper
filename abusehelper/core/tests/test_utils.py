import pickle
import doctest
import unittest

from .. import utils


def load_tests(loader, tests, ignore):
    tests.addTests(doctest.DocTestSuite(utils))
    return tests


class TestCompressedCollection(unittest.TestCase):
    def test_collection_can_be_pickled_and_unpickled(self):
        original = utils.CompressedCollection()
        original.append("ab")
        original.append("cd")

        unpickled = pickle.loads(pickle.dumps(original))
        self.assertEqual(["ab", "cd"], list(unpickled))

    def test_objects_can_be_appended_to_an_unpickled_collection(self):
        original = utils.CompressedCollection()
        original.append("ab")

        unpickled = pickle.loads(pickle.dumps(original))
        self.assertEqual(["ab"], list(unpickled))

        unpickled.append("cd")
        self.assertEqual(["ab", "cd"], list(unpickled))

    def test_objects_can_be_appended_a_collection_after_pickling(self):
        original = utils.CompressedCollection()
        original.append("ab")

        pickle.dumps(original)

        original.append("cd")
        self.assertEqual(["ab", "cd"], list(original))
