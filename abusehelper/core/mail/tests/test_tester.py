import idiokit
import unittest

from ...events import Event
from .. import Handler
from ..tester import handle


class TestTester(unittest.TestCase):
    def test_strings_should_get_handled(self):
        class PayloadLineHandler(Handler):
            @idiokit.stream
            def handle_text_plain(self, msg):
                data = yield msg.get_payload()
                for line in data.splitlines():
                    yield idiokit.send(Event(line=line))
                idiokit.stop(True)

        self.assertEqual(
            handle(PayloadLineHandler, """
                From: test@email.example

                This is the payload.
            """),
            [{"line": ["This is the payload."]}]
        )

    def test_exceptions_raised_inside_the_handler_should_get_propagated(self):
        class HandlerFailure(Exception):
            pass

        class FailingHandler(Handler):
            @idiokit.stream
            def handle_text_plain(self, msg):
                yield idiokit.sleep(0.0)
                raise HandlerFailure()

        self.assertRaises(HandlerFailure, handle, FailingHandler, """
            From: test@email.example,

            This is the payload.
        """)
