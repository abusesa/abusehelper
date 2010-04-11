import csv
import urllib2
from idiokit import threado
from abusehelper.core import events, bot, utils
import time
from idiokit import threado, util
from idiokit.xmpp import Element


class CSV2XMPP(bot.XMPPBot):
    csv_url = bot.Param()
    csv_delimiter = bot.Param(default=",")
    csv_columns = bot.ListParam(default=None)
    timestamp_column = bot.Param(default=None)
    xmpp_room = bot.Param()

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
                            | events.events_to_elements() 
                            | room)
        else:
            yield inner.sub(utils.csv_to_events(fileobj, self.csv_delimiter, self.csv_columns)
                            | events_to_elements_with_delay_element(self.timestamp_column) |room)

@threado.stream_fast
def events_to_elements_with_delay_element(inner,timestamp_column):
    eventnum=0
    while True:
        eventnum += 1
        yield inner
        for event in inner:
            print "Event %d" % (eventnum)
            fields = list()
            for key, values in event.attrs.iteritems():
                for value in values:
                    fields.append(key + "=" + value)
            body = Element("body")
            body.text = ", ".join(fields)
            if event.contains(timestamp_column):
                etime = event.value(timestamp_column)
                inner.send(body,event.to_element(),delay_element(etime))
            else:
                inner.send(body,event.to_element())

def delay_element(strstamp):
    timestamp = time.mktime(time.strptime(strstamp,"%Y-%m-%dT%H:%M:%SZ"))
    if time.daylight:
        timestamp = timestamp + time.altzone
    else:
        timestamp = timestamp + time.timezone

    delay = Element("delay")
    delay.text = "Greetings earthlings"
    delay.set_attr("xmlns", 'urn:xmpp:delay')
    delay.set_attr("stamp", strstamp)
    return delay

def format_time(timestamp, format="%Y-%m-%d %H:%M:%S"):
    return time.strftime(format, time.localtime(timestamp))


if __name__ == "__main__":
    CSV2XMPP.from_command_line().run()
