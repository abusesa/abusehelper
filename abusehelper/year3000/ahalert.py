#!/usr/bin/env python

"""
Receive alerts via prowl to your iPhone when some of your bots leave
certain XMPP rooms.  This bot watches room presence instead of user's
presence, as AbuseHelper is build on assumption that user presence is
sometimes unavailable. (E.g, you would need to be buddy, or the bots would
need to be on a globally shared roster.)

Example ini:
------
[ahalert]
rooms=blah@conference.ah.cert.ee,cert-ee@conference.ah.cert.ee
xmpp_jid=<user@ah.example.com>
xmpp_password=<yourpass>
watch_room_jids=<lobby>@conference.ah.example.com/config
apikeys = <your api key from http://prowl.weks.net>
message=Bot in your watchlist AbuseHelper left the room
------
See also: http://prowl.weks.net/
"""

from idiokit import threado, util
from idiokit.jid import JID
from abusehelper.year3000.prowl import ProwlConnection
import sys

@threado.stream
def send_alert(inner, msg, alerter):
    while True:
        yield inner
        application = 'prowlbot'
        event = 'event'
        message = msg.encode('utf-8')
        result = alerter.add(application, event, message, 0)
        print result


@threado.stream
def watchforalerts(inner,own_jid,watchlist,debug):
    while True:
        elements = yield inner
        for message in elements.with_attrs("from"):
            type=None
            sender = JID(message.get_attr("from"))
            if sender == own_jid:
                continue
            if sender.resource is None:
                continue
            for presence in message.named("presence").with_attrs("from"):
                type = presence.get_attr("type", None)

            if type == 'unavailable':

                sendertxt = "%s@%s/%s" % (sender.node, sender.domain,
                                          sender.resource)

                if sendertxt in watchlist:
                    inner.send(None)
        if debug:
            print repr(elements.serialize())

def main(rooms, watch_room_jids, xmpp_jid, message,
         apikeys, xmpp_password=None, log_file=None, debug=False):

    import getpass
    from idiokit.xmpp import connect
    from abusehelper.core import log
    
    if not xmpp_password:
        xmpp_password = getpass.getpass("XMPP password: ")

    if log_file:
        logger = log.config_logger('prowlalerts', filename=log_file)

    #strip whitespaces from apikeys
    apikeys = ",".join([key.strip() for key in apikeys.split(",")])
 
    alerter = ProwlConnection(apikeys)    

    @threado.stream
    def bot(inner):
        print "Connecting XMPP server with JID.", xmpp_jid
    
        xmpp = yield inner.sub(connect(xmpp_jid, xmpp_password))
        xmpp.core.presence()
        pipeline = None
        watchlist = [key.strip() for key in watch_room_jids.split(",")]
        for room in rooms.split(","):
            room = room.strip()
            print 'Joining room %s.' % (room)
            watchroom = yield xmpp.muc.join(room)
            if pipeline == None: 
                # Yeah, the whole watch list is given, to simplify code.
                # Lets optimize when needed.
                pipeline = watchroom | \
                           watchforalerts(xmpp_jid,
                                          watchlist,
                                          debug) | \
                           send_alert(message,alerter) | \
                           threado.throws()
        
        yield pipeline
    return bot()

main.rooms_help = "comma separated list of XMPP rooms roomreader should" + \
                  " watch. (e.g. room@conference.example.com," + \
                  " room2@conference.example.com)"
main.xmpp_jid_help = "the XMPP JID (e.g. xmppuser@example.com)"
main.watch_room_jids_help = "comma separated watchlist in a format of" + \
                           " <room>/<resource>" + \
                           " (e.g. room@conference.example.com/mybotname)."
main.message_help = "Message to be send as alert"
main.apikeys_help = "Prowl apikey, which you need to aquire from" + \
                    " https://prowl.weks.net/"
main.xmpp_password_help = "the XMPP password"
main.log_file_help = "log to the given file instead of the console"

if __name__ == "__main__":
    from abusehelper.core import opts
    threado.run(opts.optparse(main))
