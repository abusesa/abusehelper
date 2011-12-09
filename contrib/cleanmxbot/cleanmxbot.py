# -*- coding: utf-8 -*-

# runtime.py:
#    yield Source("cleanmxbot",csv_url="http://support.clean-mx.de/clean-mx/xmlphishing?response=alive&format=csv&fields=url,ip,domain&domain=", csv_name="xmlphishing")
#    yield Source("cleanmxbot",csv_url="http://support.clean-mx.de/clean-mx/xmlviruses?response=alive&format=csv&fields=url,ip,domain&domain=", csv_name="xmlviruses")


from idiokit import threado
from abusehelper.core import bot, events, utils

import httplib, urllib
import csv

def decode(text, encodings=['latin1']):
    for encoding in encodings:
        try:
            return text.decode(encoding)
        except UnicodeDecodeError:
            pass
    return text.decode('utf-8', 'ignore')

class cleanmxbot(bot.PollingBot):

    @threado.stream
    def poll(inner,self, url, name):
        yield

        try:
            self.log.info('Downloading page from: "%s"', url)
            _, fileobj = yield inner.sub(utils.fetch_url(url))
        except utils.FetchUrlFailed, e:
            self.log.error('Failed to download page "%s": %r', url, e)
            return

	data = csv.reader(fileobj,delimiter=",",quotechar='"')
	fields = data.next()
	for line in data:
	    event = events.Event()
	    event.add("feed", name)

	    line = dict(zip(fields,line))
	    for item in line:
	        event.add(item, decode(line[item]))
	    if line:
	        inner.send(event)

    def feed_keys(self, csv_url=(), csv_name=(), **keys):
        yield (str(csv_url),str(csv_name),)

if __name__ == "__main__":
    cleanmxbot.from_command_line().run()

