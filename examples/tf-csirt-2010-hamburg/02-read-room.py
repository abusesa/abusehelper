from idiokit import threado
from idiokit import xmpp

# And introducing...
from idiokit import jid

@threado.stream
def main(inner, jid, password, roomname):
    # Join the XMPP network
    conn = yield xmpp.connect(jid, password)

    # Join the XMPP room
    room = yield conn.muc.join(roomname, "bot")

    # Pipe XML elements from the room to read_room
    yield room | read_room()

@threado.stream
def read_room(inner):
    while True:
        # Receive one XML element from the pipe input
        element = yield inner
        
        # Parse the sender's nickname in the room
        sender = jid.JID(element.get_attr("from"))
        nick = sender.resource.encode("unicode-escape")

        # Print the message bodies included in the element
        for body in element.named("message").children("body"):            
            print "<"+nick+">", body.text.encode("unicode-escape")

username = "xmppuser@xmpp.example.com"
password = "xmpppassword"
roomname = "xmpproom"

threado.run(main(username, password, roomname))
