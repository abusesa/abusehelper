# Mail Handlers

A mail **handler** can be thought as general recipe how a single email message should be parsed and extracted into AbuseHelper events. However the handler doesn't know (and indeed doesn't *need* to know) the specifics how and from where each message should be received - that is the job for **runners**. By separating handlers and runners conceptually from each other we can write a handler and then use it with different mail sources, be it [IMAP](https://en.wikipedia.org/wiki/Internet_Message_Access_Protocol), [Maildir](https://en.wikipedia.org/wiki/Maildir), passing in files manually or automated tests.

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

So what does our `handle_text_plain` get as arguments? The complete method signature would be `handle_text_plain(self, msg)` where `msg` is the currently handled part of the mail, wrapped in a `abusehelper.core.mail.message.Message` object. `msg` can then be examined to parse AbuseHelper events from it:

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

The first runner we'll use is `abusehelper.core.mail.tester`, useful when you're working on and rapidly iterating handler code. The tool accepts input from either files, directories containing files or [stdin](https://en.wikipedia.org/wiki/Standard_streams#Standard_input_.28stdin.29). Use stdin and pipe in some raw mail data:

```console
$ python -m abusehelper.core.mail.tester myhandler.MyHandler <<EOF
From: sender@example.com
Subject: Greetings

Hello, World!
EOF
```

The output of the above command should be something like this:

```console
2016-05-10 23:14:27Z INFO Handling stdin
{"line": ["Hello, World!"]}
2016-05-10 23:14:27Z INFO Done with stdin
```

The lines starting with the timestamps are log lines written to stderr. The `{"line": ["Hello, World!"]}` line is the (only) event the handler just extracted from the mail, written to stdout in [JSON](https://en.wikipedia.org/wiki/JSON) format.


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

An example test file that uses the standard library's [`unittest`](https://docs.python.org/2/library/unittest.html) unit testing framework follows.

```python
import unittest
from abusehelper.core.mail.tester import handle
from myhandler import MyHandler


class TestMyHandler(unittest.TestCase):
    def test_should_parse_lines_from_mails(self):
        eventlist = handle(MyHandler, """
            From: sender@example.com
            Subject: Greetings

            Hello, World!            
        """)

        self.assertEqual(eventlist, [
            {"line": ["Hello, World!"]}
        ])
```

Notice how the input data can be passed in as a nicely indented triple-quoted string. `handle` runs the data through [`inspect.cleandoc`](https://docs.python.org/2/library/inspect.html#inspect.cleandoc) before parsing.


## Message Objects

As mentioned earlier the handlers expect `abusehelper.core.message.Message` objects to parse. The method of `Message` are modeled after standard library's [`email.message.Message`](https://docs.python.org/2/library/email.message.html#email.message.Message) class with the following notable differences:

 * `abusehelper.core.message.Message` objects are immutable, so all mutating methods like `add_header`, `attach` etc. are omitted.

 * `get_payload`, `as_string` and `walk` are asynchronous idiokit streams. `__str__` is omitted.

 * There's an additional convenience method `get_unicode(self, key, failobj=None, errors="strict")` that returns header field values as `unicode`.

`abusehelper.core.message.message_from_string` can be used to parse a `Message` object from a string.


## Configuring Handlers

Up to this point we have used a shorthand in our examples. Turns out that the command line parameter `myhandler.MyHandler` is just a shorthand for `{"type": "myhandler.MyHandler"}`, and the startup parameter `handler="myhandler.MyHandler"` is just a shorthand for `handler={"type": "myhandler.MyHandler"}`. Therefore command:

```console
$ python -m abusehelper.core.mail.tester myhandler.MyHandler
```

is actually exactly the same thing as:

```console
$ python -m abusehelper.core.mail.tester '{"type": "myhandler.MyHandler"}'
```

Now why would anyone want to use this longer form? Configurability! Sometimes the ability to configure our handlers is a good idea for reusability, and the longer form allows just that. The `"type"` key will be used to pinpoint the used handler, but rest of the keys will be passed on to the handler's constructor as keyword arguments. Let's modify `MyHandler` to take in a configurable list of mail headers it should include in the parsed events.

```python
import idiokit
from abusehelper.core import mail, events


class MyHandler(mail.Handler):
    def __init__(self, headers=[], *args, **keys):
        mail.Handler.__init__(self, *args, **keys)

        self.headers = headers

    @idiokit.stream
    def handle_text_plain(self, msg):
        data = yield msg.get_payload(decode=True)

        for line in data.splitlines():
            event = events.Event({
                "line": line.decode("utf-8", "replace"),
            })

            for header in self.headers:
                value = msg.get_unicode(header, None, errors="replace")
                if value is not None:
                    event.add(header, value)

            yield idiokit.send(event)
```

`headers` is the argument in question and is an empty list `[]` by default. What happens when we pass in `["subject"]`?

```console
$ python -m abusehelper.core.mail.tester '{"type": "myhandler.MyHandler", "headers": ["subject"]}' <<EOF
From: sender@example.com
Subject: Greetings

Hello, World!
EOF
```

Now we can see that the mail subject indeed appears in the output event:

```console
2016-05-11 01:01:47Z INFO Handling stdin
{"line": ["Hello, World!"], "subject": ["Greetings"]}
2016-05-11 01:01:47Z INFO Done with stdin
```

We can also add a new test to our unit test file:

```python
...

class TestMyHandler(unittest.TestCase):
    ...

    def test_should_include_given_headers(self):
        eventlist = handle({
            "type": MyHandler,
            "headers": ["subject"]
        }, """
            From: sender@example.com
            Subject: Greetings

            Hello, World!            
        """)

        self.assertEqual(eventlist, [
            {"line": ["Hello, World!"], "subject": ["Greetings"]}
        ])
```


## Logging

In fact *all* handlers are configurable - the base class `abusehelper.core.mail.Handler` requires all runners to pass in the keyword argument `log`. The log can then be used inside the handler as `self.log` for, well, logging.

```python
import idiokit
from abusehelper.core import mail, events


class MyHandler(mail.Handler):
    def __init__(self, headers=[], *args, **keys):
        mail.Handler.__init__(self, *args, **keys)

        self.headers = headers

    @idiokit.stream
    def handle_text_plain(self, msg):
        data = yield msg.get_payload(decode=True)

        sender = msg.get_unicode("From", "<unknown sender>", errors="replace")
        self.log.info(u"Parsing data from {0}".format(sender))

        for line in data.splitlines():
            event = events.Event({
                "line": line.decode("utf-8", "replace"),
            })

            for header in self.headers:
                value = msg.get_unicode(header, None, errors="replace")
                if value is not None:
                    event.add(header, value)

            yield idiokit.send(event)
```

Run the command again:

```console
$ python -m abusehelper.core.mail.tester '{"type": "myhandler.MyHandler", "headers": ["subject"]}' <<EOF
From: sender@example.com
Subject: Greetings

Hello, World!
EOF
```

There should now be a new log line giving us information about the mail's sender.

```console
2016-05-11 00:59:46Z INFO Handling stdin
2016-05-11 00:59:46Z INFO Parsing data from sender@example.com
{"line": ["Hello, World!"], "subject": ["Greetings"]}
2016-05-11 00:59:46Z INFO Done with stdin
```
