import unittest
import os
from tempfile import NamedTemporaryFile

from .. import archivebot


class TestRename(unittest.TestCase):
    def test_valid_rename(self):
        try:
            tmp = NamedTemporaryFile()
            new_tmp = archivebot._rename(tmp.name)
            self.assertFalse(os.path.isfile(tmp.name))
            self.assertTrue(os.path.isfile(new_tmp))
            self.assertTrue(new_tmp.find(".compress") > 1)
        finally:
            if os.path.isfile(tmp.name):
                os.remove(tmp.name)
            if os.path.isfile(new_tmp):
                os.remove(new_tmp)


class TestCompress(unittest.TestCase):
    def test_dotcompress(self):
        with NamedTemporaryFile(prefix="roomname.compress@example") as tmp:
            self.assertRaises(ValueError, archivebot.compress, tmp.name)

    def test_valid_compress(self):
        try:
            tmp = NamedTemporaryFile(suffix=".compress")
            tmp.write("test")
            gz_file = archivebot.compress(tmp.name)
            self.assertEqual(gz_file, tmp.name.replace(".compress", ".gz"))
        finally:
            if os.path.isfile(tmp.name):
                os.remove(tmp.name)
