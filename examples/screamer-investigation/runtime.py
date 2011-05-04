from abusehelper.core.runtime import Session
from abusehelper.core.config import load_module
from abusehelper.core import rules

LOBBY = load_module("./startup.py").LOBBY

#repr bot does not support sessions, so to avoid defining 
#input room in two places we load it from startup.py
INPUT = load_module("./startup.py").input_room

def configs():
    yield Session("passivedns",src_room=LOBBY+".experts",dst_room=INPUT)
    yield Session("cymruwhois",src_room=LOBBY+".experts",dst_room=INPUT)
