"""Roomreader is a simple client for reading messages in the room.
Roomreader can print messages to stdout (default) or log to a file.
"""

from idiokit import threado, util
from idiokit.jid import JID


@threado.stream
def xmpp_to_stdout(inner,own_jid,debug):
    """Print messages received from room."""
    while True:
        elements = yield inner

        for message in elements.named("message").with_attrs("from"):
            sender = JID(message.get_attr("from"))
            if sender == own_jid:
                continue
            if sender.resource is None:
                continue
            
            for body in message.children("body"):
                text = "<%s@%s/%s> %s" % (sender.node, sender.domain, sender.resource, body.text)
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
        for room in rooms.split(","):
            room = room.strip()
            print 'Joining room %s.' % (room)
            watchroom = yield xmpp.muc.join(room)
            inner.sub(watchroom | xmpp_to_stdout(xmpp_jid,debug) | threado.throws())
        yield inner
    return bot()

main.rooms_help = "comma separated list of XMPP rooms roomreader should watch. " + \
                  "(e.g. room@conference.example.com, room2@conference.example.com)"
main.xmpp_jid_help = "the XMPP JID (e.g. xmppuser@example.com)"
main.xmpp_password_help = "the XMPP password"
main.log_file_help = "log to the given file instead of the console"

if __name__ == "__main__":
    from abusehelper.core import opts
    threado.run(opts.optparse(main))
    
