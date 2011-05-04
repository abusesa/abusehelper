from abusehelper.core.config import relative_path
from abusehelper.core.startup import Bot, DefaultStartupBot


LOBBY = "abusehelper.lobby"

username = "<bot username>"
password = "<bot password>"
passive_dns_whois_server = "<whois server>" # you need to know one
input_room = LOBBY + ".experts"

B = Bot.template(xmpp_jid=username,
                 xmpp_password=password,
                 service_room=LOBBY
                )
def configs():
    yield B("repr","abusehelper.contrib.reprbot.reprbot", room=input_room)
    yield B("runtime", 
            config=relative_path("./runtime.py"))
    yield B("passivedns", "abusehelper.contrib.experts.passivedns", host=passive_dns_whois_server)
    yield B("cymruwhois", "abusehelper.contrib.experts.cymruexpert")
