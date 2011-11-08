import csv
import urllib2
from idiokit import threado
from abusehelper.core import events, bot, utils
import time
from idiokit import threado, util
from idiokit.xmlcore import Element


class CSV2XMPP(bot.XMPPBot):
    csv_url = bot.Param()
    csv_delimiter = bot.Param(default=",")
    csv_columns = bot.ListParam(default=None)
    timestamp_column = bot.Param(default=None)
    xmpp_room = bot.Param()
    add_values = bot.ListParam("List of key/values to be added to every event." +
                           'example: "key1=value1,key1=value2,key3=value3"',
                           default=dict())

    def __init__(self, **keys):
        bot.XMPPBot.__init__(self, **keys)

        if self.add_values:
            temp = dict()
            for pair in self.add_values:
                key_value = pair.split("=")
                if len(key_value) < 2:
                    continue
                values = temp.setdefault(key_value[0], set())
                values.add("=".join(key_value[1:]))
            self.add_values = temp

    @threado.stream
    def _add_values(inner, self):
        while True:
            event = yield inner
            for key in self.add_values:
                event.add(key, *self.add_values[key])
            inner.send(event)

    @threado.stream
    def main(inner, self):
        self.log.info("Opening URL %r", self.csv_url)
        _, fileobj = yield inner.sub(utils.fetch_url(self.csv_url))
        self.log.info("Opened URL %r", self.csv_url)

        xmpp = yield inner.sub(self.xmpp_connect())

        self.log.info("Joining room %r", self.xmpp_room)
        room = yield xmpp.muc.join(self.xmpp_room, self.bot_name)

        if self.timestamp_column == None:
            yield inner.sub(utils.csv_to_events(fileobj, self.csv_delimiter, self.csv_columns)
                            | self._add_values()
                            | events.events_to_elements()
                            | room)
        else:
            yield inner.sub(utils.csv_to_events(fileobj, self.csv_delimiter, self.csv_columns)
                            | self._add_values()
                            | events_to_elements_with_delay_element(self.timestamp_column)
                            | room)

@threado.stream
def events_to_elements_with_delay_element(inner,timestamp_column):
    eventnum=0
    while True:
        event = yield inner

        fields = list()
        hourminute = None
        event = sanitize(event,timestamp_column)

        for key in event.keys():
            for value in event.values(key):
                fields.append(key + "=" + value)
        body = Element("body")
        body.text = ", ".join(fields)
        if event.contains('start'):
            etime = event.value('start')
            etime = sanitize_time(etime)
            inner.send(body,event.to_element(),delay_element(etime))
        else:
            inner.send(body,event.to_element())

def sanitize(event,timestamp_column):
    if event.contains(timestamp_column) and event.contains('description'):
        etime = event.value(timestamp_column)
        etime = sanitize_time(etime)
        event.clear(timestamp_column)
        event.add(timestamp_column,etime)

        hourminute = etime2hourminute(etime)
        description = event.value('description')
        description = hourminute + " " + description

        event.clear('description')
        event.add('description',description)
    return event

def etime2hourminute(strstamp):
    timestamp_seconds = timestr_to_seconds(strstamp)
    if time.daylight:
        timestamp_seconds = timestamp_seconds + time.altzone
    else:
        timestamp_seconds = timestamp_seconds + time.timezone

    return time.strftime("%H:%M",time.gmtime(timestamp_seconds))

def sanitize_time(strstamp):
    timestamp_seconds = timestr_to_seconds(strstamp)
    if time.daylight:
        timestamp_seconds = timestamp_seconds + time.altzone
    else:
        timestamp_seconds = timestamp_seconds + time.timezone

    return time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime(timestamp_seconds))

def delay_element(strstamp):

    delay = Element("delay")
    delay.text = "Greetings earthlings"
    delay.set_attr("xmlns", 'urn:xmpp:delay')


    delay.set_attr("stamp", strstamp)
    return delay

def timestr_to_seconds(strstamp, format="%Y-%m-%d %H:%M:%SZ"):
    try:
        timestamp_seconds = time.mktime(time.strptime(strstamp,"%Y-%m-%dT%H:%M:%SZ"))
    except ValueError, e:
        pass
    else:

        return timestamp_seconds

    try:
        timestamp_seconds = time.time() + (60*float(strstamp))
    except ValueError, e:
        pass
    else:
        return float(int(timestamp_seconds))

    #almost like famous, 'this should never happen' ;)
    return None

if __name__ == "__main__":
    CSV2XMPP.from_command_line().run()
