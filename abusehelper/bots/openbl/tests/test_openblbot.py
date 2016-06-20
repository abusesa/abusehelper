import unittest

from abusehelper.core import events

from ..openblbot import _parse_line


class TestOpenBLBot(unittest.TestCase):
    def test_empty_string(self):
        line = ""
        self.assertEqual(_parse_line(line), None)

    def test_empty_line(self):
        line = "\n"
        self.assertEqual(_parse_line(line), None)

    def test_comment_line(self):
        line = "# source\tipdate"
        self.assertEqual(_parse_line(line), None)

    def test_valid_line(self):
        line = "127.0.0.1\t1466409706"
        event = events.Event()
        event.add("ip", "127.0.0.1")
        event.add("source time", "2016-06-20 07:01:46Z")
        self.assertEqual(_parse_line(line), event)
