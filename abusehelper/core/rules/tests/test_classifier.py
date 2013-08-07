from __future__ import unicode_literals

import unittest
from abusehelper.core.events import Event

from .. import rules
from .. import classifier


class TestClassifier(unittest.TestCase):
    def test_inc(self):
        c = classifier.Classifier()
        c.inc(rules.Match("a", "b"), "X")
        self.assertEqual(["X"], sorted(c.classify(Event(a="b"))))
        self.assertFalse(c.is_empty())

        c.inc(rules.Or(rules.Match("a", "b"), rules.Match("a", "c")), "Y")
        self.assertEqual(["X", "Y"], sorted(c.classify(Event(a="b"))))
        self.assertEqual(["Y"], sorted(c.classify(Event(a="c"))))
        self.assertFalse(c.is_empty())

    def test_dec(self):
        c = classifier.Classifier()
        c.inc(rules.Match("a", "b"), "X")
        c.inc(rules.Match("a", "b"), "Y")

        c.dec(rules.Match("a", "b"), "X")
        self.assertEqual(["Y"], sorted(c.classify(Event(a="b"))))
        self.assertFalse(c.is_empty())

        c.dec(rules.Match("a", "b"), "Y")
        self.assertEqual([], sorted(c.classify(Event(a="b"))))
        self.assertTrue(c.is_empty())
