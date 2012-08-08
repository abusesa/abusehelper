from abusehelper.core.startup import Bot
from abusehelper.core.runtime import Room, Session

import configuration as config

ACCESSLOG_ROOM = config.accesslog_room
ACCESS_LOG = config.path
COMBINED_ROOM = config.combined_room
COMBINER_WINDOW = 1 * 60
B = Bot.template(xmpp_jid=config.xmpp_jid,
                 xmpp_password=config.xmpp_password,
                 service_room=config.service_room,
                 xmpp_ignore_cert=config.xmpp_ignore_cert,
                 xmpp_extra_ca_certs=config.xmpp_extra_ca_certs,
                 xmpp_rate_limit=config.xmpp_rate_limit)


def configs():
    # bots
    yield B("runtime", config="startup.py")
    yield B("accesslogbot", "abusehelper.contrib.accesslogbot", path=ACCESS_LOG)
    yield B("combiner", "abusehelper.contrib.experts.combiner")
    yield B("cymruexpert", "abusehelper.contrib.experts.cymruexpert")
    yield B("geoipexpert", "abusehelper.contrib.experts.geoipexpert", geoip_db="GeoLiteCity.dat")
    yield B("historian", "vsroom.common.historian4", bot_state_file="state/historian")

    # sessions
    yield (Room(ACCESSLOG_ROOM) | Session("accesslogbot") | Room(ACCESSLOG_ROOM))
    yield (Room(ACCESSLOG_ROOM) | Session("cymruexpert") | Room(ACCESSLOG_ROOM))
    yield (Room(ACCESSLOG_ROOM) | Session("geoipexpert") | Room(ACCESSLOG_ROOM))
    yield (Room(ACCESSLOG_ROOM) | Session("combiner", time_window=COMBINER_WINDOW) | Room(COMBINED_ROOM))
    yield (Room(COMBINED_ROOM) | Session("historian"))
