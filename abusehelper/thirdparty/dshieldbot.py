from abusehelper.thirdparty.dshield import dshield
from idiokit import threado, timer

@threado.stream
def DSHIELD(inner, aslist, poll_frequency=10.0):
    aslist = list(set(map(int, aslist)))
    aslist.sort()

    while True:
        for asn in aslist:
            fetcher = dshield(asn)
            print "Fetching ASN", asn

            while True:
                try:
                    yield inner, fetcher
                except threado.Finished:
                    if fetcher.was_source:
                        break
                    fetcher.rethrow()
                    raise
                except:
                    fetcher.rethrow()
                    raise

            print "ASN", asn, "done"

        yield timer.sleep(poll_frequency)

if __name__ == "__main__":
    import getpass
    from idiokit import threado
    from idiokit.xmpp import XMPP
    from abusehelper.core import events
    from abusehelper.thirdparty import dshieldbot

    jid = raw_input("Username: ")

    xmpp = XMPP(jid, getpass.getpass())
    xmpp.connect()
    room = xmpp.muc.join("abusehelper.dshield")

    asns = [1111, 1112]
    bot = dshieldbot.DSHIELD(asns, poll_frequency=10.0)

    for _ in bot | events.events_to_elements() | room | threado.throws():
        pass
