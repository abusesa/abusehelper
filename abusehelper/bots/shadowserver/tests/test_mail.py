import os
import unittest

from abusehelper.core.mail.tester import handle

from ..mail import Handler


class TestMailHandler(unittest.TestCase):
    def assertOutput(self, filename, output):
        # Open the test data files relative to this test module.
        dirname = os.path.dirname(__file__)
        filepath = os.path.join(dirname, filename)

        with open(filepath, "rb") as fileobj:
            self.assertEqual(
                handle(Handler, fileobj.read()),
                list(output)
            )

    def test_non_shadowserver_file_should_not_be_handled(self):
        self.assertOutput("single_event.mail", [
            {
                "timestamp": "2016-01-01 00:00:00",
                "ip": "192.0.2.0",
                "report_date": "2016-01-01",
                "report_type": "single_event"
            }
        ])
