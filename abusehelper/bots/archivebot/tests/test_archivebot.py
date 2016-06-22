import os
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
        def try_to_create(directory):
            with archivebot._unique_writable_file(directory, "filename", ".ext"):
                pass

        with tmpdir() as tmp:
            non_existing_dir = os.path.join(tmp, "non-existing-dir")
            self.assertRaises(OSError, try_to_create, non_existing_dir)


class TestRename(unittest.TestCase):
    def test_should_not_go_outside_the_original_directory(self):
        with tmpdir() as directory:
            tmp_file = tempfile.NamedTemporaryFile(dir=directory, delete=False)
            new_name = archivebot._rename(tmp_file.name)
            self.assertEqual(os.path.abspath(os.path.dirname(new_name)), os.path.abspath(directory))

    def test_should_move_the_original_file(self):
        with tmpdir() as directory:
            tmp_file = tempfile.NamedTemporaryFile(dir=directory, delete=False)
            new_name = archivebot._rename(tmp_file.name)
            with open(new_name, "rb") as new_file:
                self.assertTrue(os.path.sameopenfile(new_file.fileno(), tmp_file.fileno()))

    def test_should_not_keep_the_original_file(self):
        with tmpdir() as directory:
            tmp_file = tempfile.NamedTemporaryFile(dir=directory, delete=False)
            archivebot._rename(tmp_file.name)
            self.assertFalse(os.path.isfile(tmp_file.name))

    def test_should_change_the_file_name(self):
        with tmpdir() as directory:
            tmp_file = tempfile.NamedTemporaryFile(dir=directory, delete=False)
            new_name = archivebot._rename(tmp_file.name)
            self.assertNotEqual(os.path.abspath(tmp_file.name), os.path.abspath(new_name))

    def test_should_create_a_filename_with_the_dotcompress_suffix(self):
        with tmpdir() as directory:
            tmp_file = tempfile.NamedTemporaryFile(dir=directory, delete=False)
            new_name = archivebot._rename(tmp_file.name)
            self.assertTrue(".compress" in os.path.basename(new_name))


class TestCompress(unittest.TestCase):
    def test_dotcompress(self):
        with tempfile.NamedTemporaryFile(prefix="roomname.compress@example") as tmp:
            self.assertRaises(ValueError, archivebot._compress, tmp.name)

    def test_valid_compress(self):
        with tmpdir() as directory:
            tmp = tempfile.NamedTemporaryFile(suffix=".compress-00000000", dir=directory, delete=False)
            tmp.write("test")
            gz_file = archivebot._compress(tmp.name)
            try:
                self.assertEqual(gz_file, tmp.name[:-18] + ".gz")
            finally:
                os.remove(gz_file)
