from idiokit import threado, xmpp

@threado.stream
def main(inner, jid, password, roomname):
    # Join the XMPP network
    conn = yield xmpp.connect(jid, password)

    # Join the XMPP room
    room = yield conn.muc.join(roomname, "bot")

    # Create an XML body element and send it to the room
    body = xmpp.Element("body")
    body.text = "EHLO World"
    room.send(body)

    # Exit the room
    yield room.exit("Gotta go, feel the funky flow, yo")

jid = "xmppuser@xmpp.example.com"
password = "xmpppassword"
roomname = "xmpproom"

threado.run(main(jid, password, roomname))
