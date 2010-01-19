import csv
import uuid
import urllib2
import urlparse
from idiokit import threado, xmpp
from abusehelper.core import events

@threado.stream
def send_csv_chunk(inner, reader, columns=None, chunk_size=100):
    for count, row in enumerate(reader):
        if columns is not None:
            row = dict(zip(columns, row))
            
        event = events.Event()
        for key, value in row.items():
            if value is None:
                continue
            event.add(key.strip(), value.strip())
                
        inner.send(event)
        if count >= chunk_size:
            inner.finish(True)

        yield
        list(inner)

    inner.finish(False)

@threado.stream
def xmpp_ping(inner, namespace="abusehelper#ping"):
    uid = uuid.uuid4().hex
    element = xmpp.Element("ping", xmlns=namespace, id=uid)
    inner.send(element)

    while True:
        elements = yield inner
        if elements.children().named("ping", namespace).with_attrs(id=uid):
            return

@threado.stream
def csv2xmpp(inner, reader, columns):
    while True:
        has_more = yield inner.sub(send_csv_chunk(reader, columns)
                                   | events.events_to_elements())
        yield inner.sub(xmpp_ping())
            
        if not has_more:
            return

def main(xmpp_jid, xmpp_room, csv_file,
         xmpp_password=None, csv_delimiter=",", csv_columns=None):
    import getpass
    from idiokit.xmpp import connect

    if not xmpp_password:
        xmpp_password = getpass.getpass("XMPP password: ")

    parsed = urlparse.urlparse(csv_file)
    if not parsed.scheme.strip():
        print "Opening local file", repr(csv_file)
        fileobj = open(csv_file, "r")
    else:
        print "Opening URL", repr(csv_file)
        fileobj = urllib2.urlopen(csv_file)

    if csv_columns is None:
        reader = csv.DictReader(fileobj, delimiter=csv_delimiter)
    else:
        for csv_columns in csv.reader([csv_columns]): 
            pass
        reader = csv.reader(fileobj, delimiter=csv_delimiter)

    @threado.stream
    def bot(inner):
        print "Connecting XMPP server with JID", repr(xmpp_jid)
        xmpp = yield inner.sub(connect(xmpp_jid, xmpp_password))
        xmpp.core.presence()

        print "Joining room", repr(xmpp_room)
        room = yield inner.sub(xmpp.muc.join(xmpp_room, "csv2xmpp"))
        
        feed = csv2xmpp(reader, csv_columns)
        yield inner.sub(feed | room | feed)
    return bot()

if __name__ == "__main__":
    import opts
    threado.run(opts.optparse(main))
