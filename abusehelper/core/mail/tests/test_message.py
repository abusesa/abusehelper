import inspect
import unittest

from .. import message


class TestMessage(unittest.TestCase):
    def test_get_unicode_should_parse_internationalized_headers(self):
        msg = message.message_from_string(inspect.cleandoc("""
            Subject: =?UTF-8?B?5ryi5a2X?= and US-ASCII

            The subject line of this message contains UTF-8 encoded kanji for
            the word "kanji" along with some US-ASCII characters.
        """))
        self.assertEqual(msg.get_unicode("Subject"), u"\u6f22\u5b57 and US-ASCII")
