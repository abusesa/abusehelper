# Mail Handlers

A mail **handler** can be thought as general recipe how a single email message should be parsed and extracted into AbuseHelper events. However the handler doesn't know (and indeed doesn't *need* to know) the particulars how and from where each message should be received - that is the job for **runners**. By separating handlers and runners conceptually from each other we can write a handler and then use it with different mail sources, be it [IMAP](https://en.wikipedia.org/wiki/Internet_Message_Access_Protocol), [Maildir](https://en.wikipedia.org/wiki/Maildir), passing in files manually or automated tests.

Let's start by first defining our own custom handler, and then have a look on the different runners available.


## Writing a Handler

Create a Python file called `myhandler.py` and begin by importing `abusehelper.core.mail.Handler`.

```python
from abusehelper.core import mail


class MyHandler(mail.Handler):
    pass
```

In theory this is enough, yet useless. We need to figure out which mail parts we want to handle and their mime types. It's pretty straightforward: Defining a handler for mime type major/minor happens by defining a method called `handle_major_minor`. For example text/plain parts would be handled by `handle_text_plain`. This being AbuseHelper we need to decorate the method with `idiokit.stream`.

```python
import idiokit
from abusehelper.core import mail


class MyHandler(mail.Handler):
    @idiokit.stream
    def handle_text_plain(self, ...):
        ...
```

There is a notable exception when dealing with mime types containing hyphens such as `application/octet-stream`. In such cases replace the hyphen with a double underscore (e.g. `handle_application_octet__stream`).

So what does our `handle_text_plain` get as parameters? The complete method signature would be `handle_text_plain(self, msg)` where `msg` is the currently handled part of the mail, wrapped in a `abusehelper.core.mail.message.Message` object. `msg` can then be examined to parse AbuseHelper events from it:

```python
import idiokit
from abusehelper.core import mail, events


class MyHandler(mail.Handler):
    @idiokit.stream
    def handle_text_plain(self, msg):
        data = yield msg.get_payload(decode=True)

        for line in data.splitlines():
            yield idiokit.send(events.Event({
                "line": line.decode("utf-8", "replace")
            }))
```

And there you go, a *bona fide* handler. Let's launch and test it.


## Trying Out Handlers on the Command Line

The first runner we'll use is `abusehelper.core.mail.tester`, particularly useful when you're working on and rapidly iterating handler code. The tool accepts input from either files, directories containing files or [stdin](https://en.wikipedia.org/wiki/Standard_streams#Standard_input_.28stdin.29). Use stdin and pipe in some raw mail data:

```console
python -m abusehelper.core.mail.tester myhandler.MyHandler << EOF
From: sender@example.com
Content-Type: text/plain

Hello, World!
EOF
```

The output of the above command should be something like this:

```console
2016-05-10 23:14:27Z INFO handling stdin
{"line": ["Hello, World!"]}
2016-05-10 23:14:27Z INFO done with stdin
```

The lines starting with the timestamps are log lines. The `{"line": ["Hello, World!"]}` line is the (only) event the handler just extracted from the mail.


## Turning Handlers into Maildir Bots

`abusehelper.core.mail.maildirbot` is a runner for reading mails from a directory adhering to the [Maildir](https://en.wikipedia.org/wiki/Maildir) format, feeding them to a handler and then passing on the parsed events to an XMPP channel. So it's a runner for turning a handler into a feed bot! A basic start incantation looks like:

```console
$ python -m abusehelper.core.mail.maildirbot user@xmpp.example.com lobby.room myhandler.MyHandler Mail/customer1 myworkdir
```

The bot will start chewing through the mails in the `Mail/customer1` directory, producing the events using the `myhandler.MyHandler` and moving the handled mails under the `workdir`. In startup configs the handler is given as `handler="myhandler.MyHandler"`, input mail directory as `input_dir="Mail/customer1"` and the work directory as `work_dir="myworkdir"`. If you're feeling extra adventurous add `--concurrency=5` / `concurrency=5` there and the bot will handle 5 mails simultaneously when it can.


`abusehelper.core.mail.imapbot` is very similar the the Maildir runner, except that is fetches mails from a remote [IMAP](https://en.wikipedia.org/wiki/Internet_Message_Access_Protocol) server:

```console
$ python -m abusehelper.core.mail.imapbot user@xmpp.example.com lobby.room myhandler.MyHandler mail.example.com mailuser
```


## Automated Tests for Handlers

`abusehelper.core.mail.tester` contains function `handle` for writing repeatable tests for handlers. `handle` requires two arguments: the handler class being tested and some mail data. The return value is a list of parsed events (as `dict`s) that can be inspected to check whether it matches the expected output.

An example test file that uses the standard library's `unittest` unit testing framework follows.

```python
import unittest
from abusehelper.core.mail.tester import handle
from myhandler import MyHandler


class TestMyHandler(unittest.TestCase):
    def test_should_parse_lines_from_mails(self):
        eventlist = handle(MyHandler, """
            From: sender@example.com
            Content-Type: text/plain

            Hello, World!            
        """)

        self.assertEqual(eventlist, [
            {"line": ["Hello, World!"]}
        ])
```

Notice how the input data can be passed in as a nicely indented triple-quoted string. `handle` runs the data through `[inspect.cleandoc](https://docs.python.org/2/library/inspect.html#inspect.cleandoc)` before parsing.


## Message Objects

As mentioned earlier the handlers expect `abusehelper.core.message.Message` objects to parse. The `Message` class methods are mostly modeled after standard library's `[email.message.Message](https://docs.python.org/2/library/email.message.html#email.message.Message)` with the following differences:

 * `abusehelper.core.message.Message` objects are immutable, so all mutating methods like `add_header`, `attach` etc. are omitted.

 * `get_payload`, `as_string` and `walk` are asynchronous idiokit streams. `__str__` is omitted.

 * There's an additional convenience method `get_unicode(self, key, failobj=None, errors="strict")` that returns header field values as `unicode`.

`abusehelper.core.message.message_from_string` can be used to parse a `Message` object from a string.
