from abusehelper.core.runtime import Session

from startup import service_room as room_prefix

sources_room = room_prefix + ".sources"

def archive(room):
    return Session("archivebot",
        src_room=room)

def source(name, dst_room=None, **attrs):
    if dst_room is None:
        dst_room = room_prefix + ".source." + name

    yield Session(name,
        dst_room=dst_room,
        **attrs)
    yield archive(dst_room)

    yield Session(name + ".sanitizer",
        src_room=dst_room,
        dst_room=sources_room)
    yield archive(sources_room)

def customer(name, rule, *outputs):
    room = room_prefix + ".customer." + name

    yield Session("roomgraph",
        src_room=sources_room,
        dst_room=room,
        rule=rule)
    yield archive(room)

    for output in outputs:
        yield output(room)

def mail(to=[], cc=[], times=["08:00"], template=None):
    if template is None:
        template = """
Subject: AbuseHelper CSV report

# Here is the data:
%(attach_and_embed_csv, report.csv, ",", time, ip, type)s
"""

    def _mail(room):
        yield Session("mailer",
            src_room=room,
            to=to,
            cc=cc,
            times=times,
            template=template)
    return _mail

def configs():
    # Source definitions

    yield source("dshield",
        asns=[0, 1, 2, 3])

    yield source("malwaredomainlist")

    # Customer definitions

    yield customer("everything-to-mail-at-8-o-clock", "*", mail(to="someone@example.com", times=["08:00"]))
    yield customer("asn3-or-netblock", "asn=3 or 127.0.0.1/16")
    yield customer("fi-urls", r"url=/^https?:\/\/[\w\.]+\.fi(\W|$)/i")
