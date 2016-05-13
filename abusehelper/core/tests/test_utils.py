import socket
import pickle
import urllib2
import unittest

import idiokit

from .. import utils


class TestFetchUrl(unittest.TestCase):
    def test_should_raise_TypeError_when_passing_in_an_opener(self):
        sock = socket.socket()
        try:
            sock.bind(("localhost", 0))
            sock.listen(1)
            _, port = sock.getsockname()

            opener = urllib2.build_opener()
            fetch = utils.fetch_url("http://localhost:{0}".format(port), opener=opener)
            self.assertRaises(TypeError, idiokit.main_loop, fetch)
        finally:
            sock.close()


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
