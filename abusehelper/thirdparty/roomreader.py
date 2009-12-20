"""Roomreader is a simple client for reading messages in multiple rooms.
Roomreader can print messages to stdout (default) or to a log file.
"""

from idiokit import threado, util
from idiokit.jid import JID


@threado.stream
def xmpp_to_stdout(inner,own_jid,participants,debug):
    """Print messages received from room."""
    in_room={}

    for participant in  participants:
        in_room[participant.name.resource] = True
    
    while True:
        elements = yield inner
        for message in elements.with_attrs("from"):

            type=None
            sender = JID(message.get_attr("from"))
            if sender == own_jid:
                continue
            if sender.resource is None:
                continue
            sendertxt = "<%s@%s/%s>" % (sender.node, sender.domain, sender.resource)

#            # Preserving this code for documentative purposes.
#            # You've gotta love the logic behind type & status.
#            for presence in message.named("presence").with_attrs("from"):
#                type = presence.get_attr("type", None)
#                for newstatus in presence.children('status'):
#                    status = newstatus.text

            if type == None and sender.resource not in in_room:
                print "%s entered the room %s@%s." % \
                    (sender.resource, 
                     sender.node, 
                     sender.domain)
                in_room[sender.resource] = True
            elif type == 'unavailable' and sender.resource in in_room:
                print "%s left the room %s@%s" % (sender.resource, 
                                                  sender.node, 
                                                  sender.domain)
                in_room.pop(sender.resource)
            for body in message.children("body"):
                text = "%s %s" % (sendertxt, body.text)
                print text

        if debug:
            print repr(elements.serialize())

def main(rooms, xmpp_jid, xmpp_password=None, log_file=None, debug=False):
    import getpass
    from idiokit.xmpp import connect
    from abusehelper.core import log
    
    if not xmpp_password:
        xmpp_password = getpass.getpass("XMPP password: ")

    if log_file:
        logger = log.config_logger('roomreader', filename=log_file)
    
    @threado.stream
    def bot(inner):
        print "Connecting XMPP server with JID.", xmpp_jid
    
        xmpp = yield inner.sub(connect(xmpp_jid, xmpp_password))
        xmpp.core.presence()
        pipeline = None
        for room in rooms.split(","):
            room = room.strip()
            print 'Joining room %s.' % (room)
            watchroom = yield xmpp.muc.join(room)
            print 'Participants:'
            for participant in watchroom.participants:
                print " %s" % participant.name.resource


            if pipeline == None: 
                pipeline = watchroom | xmpp_to_stdout(xmpp_jid,
                                                      watchroom.participants,
                                                      debug)
            else:
                pipeline |= watchroom | xmpp_to_stdout(xmpp_jid,
                                                       watchroom.participants,
                                                       debug)

        # finally add threado.throws() that will pick up exceptions
        pipeline |= threado.throws()
        
        yield pipeline
    return bot()

main.rooms_help = "comma separated list of XMPP rooms roomreader should watch. " + \
                  "(e.g. room@conference.example.com, room2@conference.example.com)"
main.xmpp_jid_help = "the XMPP JID (e.g. xmppuser@example.com)"
main.xmpp_password_help = "the XMPP password"
main.log_file_help = "log to the given file instead of the console"

if __name__ == "__main__":
    from abusehelper.core import opts
    threado.run(opts.optparse(main))
    
