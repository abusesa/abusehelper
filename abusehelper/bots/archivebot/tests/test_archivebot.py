import os
import stat
import shutil
import tempfile
import unittest
import contextlib

from .. import archivebot


def touch(path):
    with open(path, "wb"):
        pass


@contextlib.contextmanager
def tmpdir():
    tmp = tempfile.mkdtemp()
    try:
        yield tmp
    finally:
        shutil.rmtree(tmp)


class TestUniqueWritableFile(unittest.TestCase):
    def test_should_create_a_file_without_a_sequence_number_when_no_files_exist(self):
        with tmpdir() as tmp:
            with archivebot._unique_writable_file(tmp, "filename", ".ext") as (filename, _):
                self.assertEqual(filename, os.path.join(tmp, "filename.ext"))

    def test_should_pick_the_next_sequential_number_when_files_exist(self):
        with tmpdir() as tmp:
            touch(os.path.join(tmp, "filename.ext"))
            touch(os.path.join(tmp, "filename-00000001.ext"))
            touch(os.path.join(tmp, "filename-00000002.ext"))

            with archivebot._unique_writable_file(tmp, "filename", ".ext") as (filename, _):
                self.assertEqual(filename, os.path.join(tmp, "filename-00000003.ext"))

    def test_should_raise_OSError_other_than_EEXIST(self):
        def try_to_create(tmp):
            with archivebot._unique_writable_file(tmp, "filename", ".ext"):
                pass

        with tmpdir() as tmp:
            os.chmod(os.path.join(tmp), stat.S_IREAD)
            self.assertRaises(OSError, try_to_create, tmp)


class TestRename(unittest.TestCase):
    def test_valid_rename(self):
        try:
            tmp = tempfile.NamedTemporaryFile()
            new_tmp = archivebot._rename(tmp.name)
            self.assertFalse(os.path.isfile(tmp.name))
            self.assertTrue(os.path.isfile(new_tmp))
            self.assertTrue(new_tmp.find(".compress") > 1)
        finally:
            for file in [tmp.name, new_tmp]:
                if os.path.isfile(file):
                    os.remove(file)


class TestCompress(unittest.TestCase):
    def test_dotcompress(self):
        with tempfile.NamedTemporaryFile(prefix="roomname.compress@example") as tmp:
            self.assertRaises(ValueError, archivebot.compress, tmp.name)

    def test_valid_compress(self):
        try:
            tmp = tempfile.NamedTemporaryFile(suffix=".compress-00000000", delete=False)
            tmp.write("test")
            gz_file = archivebot.compress(tmp.name)
            try:
                self.assertEqual(gz_file, tmp.name[:-18] + ".gz")
            finally:
                os.remove(gz_file)
        finally:
            if os.path.isfile(tmp.name):
                os.remove(tmp.name)
