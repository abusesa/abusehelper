# Writing Maildir Bots

The module ```maildirbot``` is the basis for writing Maildir bots. That is, bots that read files from a directory adhering to the [Maildir](https://en.wikipedia.org/wiki/Maildir) format and parsing events from the handled mails.

The way Maildir bots are customized for your needs is a bit different from usual AbuseHelper workflow. ```maildirbot``` *does* provide a bot class called ```MailDirBot```, but you don't probably need to subclass it directly. Instead you write a custom subclass of ```maildirbot.Handler``` and provide that as a parameter when launching a ```MailDirBot``` instance.

How and why follows.


## Writing your own handler

Everything starts by importing ```maildirbot``` and subclassing ```maildirbot.Handler```. Let's also import ```idiokit```, as we need it in a moment. Let's write the following to a file called ```myhandler.py```:

```python
import idiokit
from abusehelper.core.mail import Handler


class MyHandler(Handler):
    pass
```

In theory this is enough, yet useless. We need to figure out which mail parts we want to handle and their mime types. It's pretty straightforward: Defining a handler for mime type major/minor happens by defining a method called ```handle_major_minor```. For example text/plain parts would be handled by ```handle_text_plain```. This being AbuseHelper we need to decorate the method with ```idiokit.stream```.

```python
import idiokit
from abusehelper.core.mail import Handler


class MyHandler(Handler):
    @idiokit.stream
    def handle_text_plain(self, ...):
        ...
```

There is a notable exception when dealing with mime types containing hyphens such as application/octet-stream. In such cases replace the hyphen with a double underscore (e.g. ```handle_application_octet__stream```).

So what does our ```handle_text_plain``` get as parameters? The complete method signature would be ```handle_text_plain(self, msg)``` where ```msg``` is the currently handled part of the mail, wrapped in Python's standard ```email.message.Message``` object. ```msg``` can then be examined to parse AbuseHelper events from it:

```python
import idiokit
from abusehelper.core import events
from abusehelper.core.mail import Handler


class MyHandler(Handler):
    @idiokit.stream
    def handle_text_plain(self, msg):
        data = msg.get_payload(decode=True)

        self.log.info("Starting to process {0} bytes of data".format(len(data)))

        for line in data.splitlines():
            yield idiokit.send(events.Event({
                "line": line.decode("utf-8", "replace")
            }))

        self.log.info("Done")
```

And there you go, a *bona fide* handler. Note how the handler has a special attribute ```self.log``` for logging information about what's happening.

Now we just want to launch and test our handler somehow.


## Launching a handler as a bot

As stated earlier a custom handler should be provided as a parameter when launching a ```MailDirBot``` instance. This happens by adding the following to the end of your handler module:

```python
if __name__ == "__main__":
    from abusehelper.core.mail import maildirbot

    maildirbot.MailDirBot.from_command_line(MyHandler()).execute()
```

And there you go. You can now launch it with

```
$ python myhandler.py user@xmpp.example.com lobby.room Mail/customer1 myworkdir
```

and the bot will start chewing through the mails in the Mail/customer1 directory, producing the events from text/plain parts and moving the handled mails under the workdir. If you're feeling extra adventurous add ```--concurrency=5``` there and the bot will handle 5 mails simultaneously when it can.

In startup configs the input mail directory is referred to as input_dir (```input_dir="Mail/customer1"```) and the work directory as work_dir (```work_dir="myworkdir"```).


## Testing handlers

All this doesn't really explain *why* we have to do this handler dance instead of just deriving directly from the ```maildirbot.MailDirBot``` as per usual.

The motivation separating the part doing the Maildir juggling (```MailDirBot```) from the part actually interpreting the data (handlers) is that now you can test your handlers while writing them, provided that you have some suitable test data available in your development environment.

Run your handler like this:

```
$ python -m abusehelper.core.mail.tester myhandler.MyHandler Mail/customer1/new
```

This will now parse the mails under the Mail/customer/new directory and output the events as JSON to STDOUT and write the logs to STDERR.
Note that the mails from Mail/customer1/new aren't moved anywhere or deleted, as we're just testing.
