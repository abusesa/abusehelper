from idiokit import threado
from idiokit import xmpp
from idiokit import jid

@threado.stream
def main(inner, jid, password, src_roomname, dst_roomname):
    # Join the XMPP network
    conn = yield xmpp.connect(jid, password)

    # Join the XMPP rooms
    src_room = yield conn.muc.join(src_roomname, "bot")
    dst_room = yield conn.muc.join(dst_roomname, "bot")

    # Forward body elements from the src room to the dst room,
    # but filter away stuff by the bot itself to avoid nasty loops.
    own_jid = src_room.nick_jid
    yield src_room | room_filter(own_jid) | dst_room | threado.dev_null()

@threado.stream
def room_filter(inner, own_jid):
    while True:
        # Receive one XML element from the pipe input
        element = yield inner
        
        # Prevent endless feedback loops
        sender = jid.JID(element.get_attr("from"))
        if sender == own_jid:
            continue

        # Forward the body elements
        for body in element.named("message").children("body"):
            inner.send(body)

username = "xmppuser@xmpp.example.com"
password = "xmpppassword"
src_roomname = "src_xmpproom"
dst_roomname = "dst_xmpproom"

threado.run(main(username, password, src_roomname, dst_roomname))
