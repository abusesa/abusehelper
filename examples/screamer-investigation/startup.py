from abusehelper.core.startup import Bot, DefaultStartupBot


LOBBY = "abusehelper.lobby"

username = "<bot username>"
password = "<bot password>"
passive_dns_whois_server = "<whois server>" # you need to know one
input_room = LOBBY + ".experts"
output_room = LOBBY + ".results"

B = Bot.template(xmpp_jid=username,
                 xmpp_password=password,
                 service_room=LOBBY,
                 xmpp_ignore_cert=True
                )
def configs():
    yield B("repr","abusehelper.contrib.reprbot.reprbot", room=input_room)
    yield B("runtime", config="./runtime.py")
    yield B("passivedns", "abusehelper.contrib.experts.passivedns", host=passive_dns_whois_server)
    yield B("cymruwhois", "abusehelper.contrib.experts.cymruexpert")
    yield B("combiner", "abusehelper.contrib.experts.combiner")
