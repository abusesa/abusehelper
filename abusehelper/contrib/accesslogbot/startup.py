from abusehelper.core.startup import Bot
from abusehelper.core.runtime import Room, Session
from abusehelper.core.config import load_module, relative_path

config = load_module(relative_path("./", "configuration.py"))
ACCESSLOG_ROOM = config.accesslog_room
ACCESS_LOG = config.path
COMBINED_ROOM = config.combined_room
COMBINER_WINDOW = 1 * 60
B = Bot.template(xmpp_jid=config.xmpp_jid,
                 xmpp_password=config.xmpp_password,
                 service_room=config.service_room,
                 xmpp_extra_ca_certs=config.xmpp_extra_ca_certs)


def configs():
    # bots
    yield B("runtime", config=relative_path("startup.py"))
    yield B("accesslogbot", relative_path("./", "accesslogbot.py"), path=ACCESS_LOG)
    yield B("combiner", "abusehelper.contrib.experts.combiner")
    yield B("cymruexpert", "abusehelper.contrib.experts.cymruexpert")
    yield B("geoipexpert", "abusehelper.contrib.experts.geoipexpert",
        geoip_db=relative_path("GeoLiteCity.dat"))

    # sessions
    yield (Room(ACCESSLOG_ROOM) | Session("accesslogbot") | Room(ACCESSLOG_ROOM))
    yield (Room(ACCESSLOG_ROOM) | Session("cymruexpert") | Room(ACCESSLOG_ROOM))
    yield (Room(ACCESSLOG_ROOM) | Session("geoipexpert") | Room(ACCESSLOG_ROOM))
    yield (Room(ACCESSLOG_ROOM) | Session("combiner", time_window=COMBINER_WINDOW) | Room(COMBINED_ROOM))
