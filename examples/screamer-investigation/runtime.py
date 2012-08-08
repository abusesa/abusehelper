from abusehelper.core.runtime import Session

import startup

#repr bot does not support sessions, so to avoid defining
#input room in two places we load it from startup.py
INPUT = startup.input_room
OUTPUT = startup.output_room


def configs():
    yield Session("passivedns", src_room=INPUT, dst_room=INPUT)
    yield Session("cymruwhois", src_room=INPUT, dst_room=INPUT)
    yield Session("combiner", src_room=INPUT, dst_room=OUTPUT)
