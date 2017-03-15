# AbuseHelper command line tools

## abusehelper.tools.sender

A tool that reads JSON formatted events from the STDIN and sends them to an XMPP room as AbuseHelper events.

### Usage

```ShellSession
$ abusehelper.tools.sender XMPP_JID ROOM --rate-limit=N
```

Where:

 * ```XMPP_JID``` is your XMPP username you want to use for feeding events to the room.

 * ```ROOM``` room is the XMPP room where the events will be sent to.

 * ```--rate-limit=N``` sets the rate limit to max. N events per second for sending the data to the XMPP room. You will probably want to set this value to something conservative as it's relatively easy to melt down your XMPP server by spamming messages.

### JSON format

The tool reads lines (ending with ```\n```) from the STDIN, and interprets every line as a JSON dictionary. The dictionary should contain either a string or a list of strings as values:

```json
{"ip": "192.0.2.100", "cc": "FI", "bgp prefix": ["192.0.2.0/24", "192.0.2.0/28"]}
```

### Example

Thanks to the glorious UNIX piping facilities you can use pretty much every programming language to create the JSON events. Let's use Python for this example.

Assume you have a short script called ```producer.py``` that produces JSON data:

```python
import json

for event_number in range(10000):
    print json.dumps({
        "feed": "myfeed",
        "number": unicode(event_number)
    })
```

Then you can use the script to produce data to the channel like this:

```ShellSession
$ python producer.py | python -m abusehelper.tools.sender user@xmpp.example.com my.room --rate-limit=10
```

This uses the ```user@xmpp.example.com``` account to send the produced dummy events to the XMPP room ```my.room``` and limits the datastream to max. 10 events per second.

## abusehelper.tools.receiver

A tool that reads AbuseHelper events from an XMPP room and writes them to STDOUT as JSON formatted lines.

### Usage

```ShellSession
$ abusehelper.tools.receiver XMPP_JID ROOM
```

Where:

 * ```XMPP_JID``` is your XMPP username you want to use for receiving events from the room.

 * ```ROOM``` room is the XMPP room from where the events will be received from.

### JSON format

The tool produces the same kind of format as ```abusehelper.core.sender``` consumes: One JSON dictionary by line, each dictinary value can be either a string or a list of strings.

See the ```abusehelper.core.sender``` documentation for example.

### Example

Assume you have a short script called ```consumer.py``` that consumes the data lines and filters out all non-c&c events:

```python
import sys
import json

for line in sys.stdin:
    obj = json.loads(line)

    event_type = obj.get("type", None)
    if isinstance(event_type, list):
        if "c&c" in event_type:
            print line,
    elif event_type == "c&c":
        print line,
```

Then you can use the script to consume data from the channel like this:

```ShellSession
$ python -m abusehelper.tools.receiver user@xmpp.example.com my.room | python myconsumer.py
```
