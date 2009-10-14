import logging
import uuid

from abusehelper.thirdparty.couchbot import events_to_couchdb
from abusehelper.thirdparty.dshield import dshield

from idiokit.xmpp import XMPP
from idiokit import pep, threado

from abusehelper.core import events, splitterbot

from abusehelper.core import rules

@threado.stream
def dshields(inner, asns):
    for asn in asns:
        dshield_stream = dshield(asn)

        while True:
            try:
                event = yield inner, dshield_stream
            except threado.Finished:
                break

            if dshield_stream.was_source:
                inner.send(event)

def main():
    asn_list = ['xxx']

    feed_nick = 'dshield_parser'

    creds = ("user@example.com", "password")

    xmpp = XMPP(*creds)
    xmpp.connect()
    xmpp.core.presence()
    
    server_name = "@conference.example.com"

    dshield_name = "dshield" + server_name

    customer_room = xmpp.muc.join('customera' + server_name, 'customera')

    asn_rooms = None

    ruleset = rules.RuleSet()
    for asn in asn_list:
        asn_roomname = "as%s%s" % (asn, server_name)
        nick = '%s_room' % (asn)
        print asn_roomname, nick

        new_room = xmpp.muc.join(asn_roomname, nick)

        if not asn_rooms:
            asn_rooms = new_room
        else:
            asn_rooms = asn_rooms + new_room

        ruleset.add(asn_roomname, rules.CONTAINS("ip", asn=asn))

    splitter = splitterbot.Splitter(xmpp)

    splitterbot.publish_ruleset(ruleset, *creds)

    event = events.Event()
    event.add("kanunbra_password", 'jaffa7mk')
    event.add("status", "31337")

    pep.publish(xmpp, 'abusehelper/customer#config', event.to_element())

    logging.getLogger().setLevel(logging.INFO)

    print dshield_name
    dshield_room = xmpp.muc.join(dshield_name, 'dshield_bot')

    pipes = (dshields(asn_list)
             | events.events_to_elements() 
             | dshield_room
             | events.stanzas_to_events() 
             | splitter)
    pipes = pipes + (asn_rooms
                     | events.stanzas_to_events()
                     | events.events_to_elements()
                     | customer_room
                     | events_to_couchdb("http://localhost:5984", "customera"))
    
    for _ in pipes: pass

if __name__ == "__main__":
    main()
