# AbuseHelper command line tools

## abusehelper.tools.sender

A tool that reads JSON formatted events from the STDIN and sends them to a channel as AbuseHelper events. Thanks to the glorious UNIX piping facilities you can use pretty much every language to create the JSON events.

### Usage

```
$ abuseheleper.tools.sender XMPP_JID ROOM --rate-limit=N
```

Where:

 * ```XMPP_JID``` is your XMPP username you want to use for feeding events to the room.

 * ```ROOM``` room is the XMPP room where the events will be sent to.

 * ```--rate-limit=N``` sets the rate limit to max. N events per second for sending the data to the XMPP room. You will probably want to set this value to something conservative as it's relatively easy to melt down your XMPP server by spamming messages.

### JSON format

The tool reads lines (ending with ```\n```) from the STDIN, and interprets every line as a JSON dictionary. The dictionary should contain either a string or a list of strings as values:

```
{"ip": "192.0.2.100", "cc": "FI", "bgp prefix": ["192.0.2.0/24", "192.0.2.0/28"]}
```

### Example

Thanks to the glorious UNIX piping facilities you can use pretty much every language to create the JSON events. For this example let's use Python.

Assume you have a short script called ```producer.py``` that produces JSON data:

```
import json

for event_number in range(10000):
    print json.dumps({
        "feed": "myfeed",
        "number": unicode(event_number)
    })
```

Then you can use the script to produce data to the channel like this:

```
python producer.py | python -m abusehelper.tools.sender user@xmpp.example.com my.room --rate-limit=10
```

This uses the ```user@xmpp.example.com``` account to send the produced dummy events to the XMPP room ```my.room``` and limits the datastream to max. 10 events per second.
