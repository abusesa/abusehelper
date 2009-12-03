import os
import csv
from idiokit import threado, timer
from abusehelper.core import events, services

def event_rows(event):
    result = dict()
    result["addresses"] = event.attrs.get('Abuse email', set([''])).pop()
    result["asn"] = event.attrs.get('ASN1', set([''])).pop()
    result["AS Name"] = event.attrs.get('AS Name', set([''])).pop()
    result["ip-range"] = ""
    result["dshield addresses"] = ""
    result["dshield template"] = "dshield_template_fi"
    result["pgp"] = ""
    return result

def csv_rows(data):
    lines = [line for line in data.splitlines()
             if line.strip() and not line.strip().startswith("#")]
    reader = csv.reader(lines, delimiter="|")

    first = ["asn", "country", "addresses", "as name"]
    first = [x.strip() for x in first]
    for row in reader:
        row = [x.strip() for x in row]
        result = dict(map(None, first, row))
        result["ip-range"] = ""
        result["dshield addresses"] = ""
        result["dshield template"] = "dshield_template_fi"
        result["pgp"] = ""
        yield result

def csv_rows2(data):
    lines = [line for line in data.splitlines()
             if line.strip() and not line.strip().startswith("#")]
    reader = csv.reader(lines, delimiter="|")
    for first in reader:
        break
    else:
        return
    first = [x.strip() for x in first]
    for row in reader:
        row = [x.strip() for x in row]
        yield dict(map(None, first, row))

class Config(object):
    def __init__(self, asn, filter, addresses):
        self.asn = asn
        self.filter = filter
        self.addresses = addresses
        self.pgp = None
        self.template = None

class ConfigFollower(threado.GeneratorStream):
    def __init__(self, filename, refresh_interval=2.0):
        threado.GeneratorStream.__init__(self)

        self.filename = filename
        self.refresh_interval = refresh_interval
        self.confs = dict()

        self.start()

    def run(self):
        conf_file = open(self.filename, "r")
        while True:
            last_mod = os.path.getmtime(self.filename)
            
            conf_file.seek(0)
            update, discard = self._update(conf_file.read())
            self.inner.send(update, discard)

            while True:
                yield self.inner, timer.sleep(self.refresh_interval)
                if last_mod < os.path.getmtime(self.filename):
                    break

    def _update(self, data):
        confs = dict()
        defaults = dict()

        for row in csv_rows(data):
            asn = row["asn"]
            ranges = row["ip-range"]
            addresses = row["dshield addresses"] or row["addresses"]
            addresses = frozenset(x.strip() for x in addresses.split(","))
            template = row["dshield template"]
            pgp = row["pgp"]

            if addresses and template:
                if ranges:
                    defaults.setdefault(asn, list()).append(ranges)

                key = asn, ranges, addresses
                if key in self.confs:
                    item, _, _ = self.confs[key]
                else:
                    item = Config(asn, ranges, addresses)
                confs[key] = item, template, pgp

        update = set()
        discard = set(self.confs[key][0] for key in set(self.confs)-set(confs))
        for key, (item, template, pgp) in confs.iteritems():
            asn, ranges, addresses = key

            if not ranges:
                default = ",".join(defaults.get(asn, list()))
                if default:
                    default = "not (" + default + ")"
                if item.filter != default:
                    update.add(item)
                item.filter = default

            if template != item.template:
                item.template = template
                update.add(item)

            if pgp != item.pgp:
                item.pgp = pgp
                update.add(item)
                
            if key not in self.confs:
                update.add(item)

        self.confs = confs
        return update, discard

class WikiConfigFollower(ConfigFollower):
    def __init__(self, url, username, password, search, **kw):
        threado.GeneratorStream.__init__(self)

        self.url = url
        self.confs = dict()
        self.username = username
        self.password = password
        self.search = search

        self.start()

    def run(self):
        from opencollab.meta import Metas
        from opencollab.util.wiki import getPages
        from opencollab.wiki import GraphingWiki
        from idiokit import timer

        while True:
            self.gwiki = GraphingWiki(self.url)
            yield self.inner.thread(self.gwiki.authenticate, 
                                    self.username, 
                                    self.password)
            data = yield self.inner.thread(getPages, self.gwiki, self.search)

            all_events = list()

            for page in data.keys():
                event = events.Event()

                for key, values in data[page].iteritems():
                    for value in values:
                        event.add(key, value)

                all_events.append(event)

            update, discard = self._update(all_events)

            self.inner.send(update, discard)

            timer.sleep(10.0)

    def _update(self, events):
        confs = dict()
        defaults = dict()

        for event in events:
            row = event_rows(event)

            asn = row["asn"]
            ranges = row["ip-range"]
            addresses = row["dshield addresses"] or row["addresses"]
            template = row["dshield template"]
            pgp = row["pgp"]

            if addresses and template:
                if ranges:
                    defaults.setdefault(asn, list()).append(ranges)

                key = asn, ranges, addresses
                if key in self.confs:
                    item, _, _ = self.confs[key]
                else:
                    item = Config(asn, ranges, addresses)
                confs[key] = item, template, pgp

        update = set()
        discard = set(self.confs[key][0] for key in set(self.confs)-set(confs))
        for key, (item, template, pgp) in confs.iteritems():
            asn, ranges, addresses = key

            if not ranges:
                default = ",".join(defaults.get(asn, list()))
                if default:
                    default = "not (" + default + ")"
                if item.filter != default:
                    update.add(item)
                item.filter = default

            if template != item.template:
                item.template = template
                update.add(item)

            if pgp != item.pgp:
                item.pgp = pgp
                update.add(item)
                
            if key not in self.confs:
                update.add(item)

        self.confs = confs
        return update, discard

class Setup(threado.GeneratorStream):
    def __init__(self, lobby):
        threado.GeneratorStream.__init__(self)
        self.lobby = lobby
        self.start()

    def run(self):
        setups = dict()
        while True:
            updated, discarded = yield self.inner

            for item in updated:
                print "+", item.asn, "filter="+repr(item.filter),
                print item.addresses, item.template
                if item not in setups:
                    setups[item] = self.setup(self.lobby)
                    services.bind(self, setups[item])
                setups[item].send(item)

            for item in discarded:
                print "-", item.asn, "filter="+repr(item.filter), 
                print item.addresses, item.template
                if item not in setups:
                    continue
                setups.pop(item).throw(threado.Finished())
    
    @threado.stream
    def setup(inner, self, lobby):
        dshield = None
        roomgraph = None
        mailer = None

        try:
            dshield = yield lobby.session("dshield")
            roomgraph = yield lobby.session("roomgraph")
            mailer = yield lobby.session("mailer")

            while True:
                item = yield inner, roomgraph, dshield, mailer
                if not inner.was_source:
                    continue

                asn_room = "regret.asn" + item.asn

                dshield_conf = yield dshield.config(asn=item.asn)
                mailer_conf = dict(to=item.addresses,
                                   room=asn_room,
                                   subject="Report for ASN"+item.asn,
                                   template=item.template,
                                   time_interval=15.0)
                yield inner.sub(mailer.config(**mailer_conf))

                roomgraph_conf = dict(src=dshield_conf["room"], 
                                      dst=asn_room,
                                      filter=item.asn)
                yield roomgraph.config(**roomgraph_conf)
        except:
            if dshield is not None:
                dshield.rethrow()
            if roomgraph is not None:
                roomgraph.rethrow()
            if mailer is not None:
                mailer.rethrow()
            raise

def main(xmpp_jid, service_room, customer_file, 
         xmpp_password=None, log_file=None):
    import getpass
    from idiokit.xmpp import connect
    from abusehelper.core import log
    
    if not xmpp_password:
        xmpp_password = getpass.getpass("XMPP password: ")

    logger = log.config_logger("config", filename=log_file)

    @threado.stream
    def bot(inner):
        print "Connecting XMPP server with JID", xmpp_jid
        xmpp = yield connect(xmpp_jid, xmpp_password)
        xmpp.core.presence()

        print "Joining lobby", service_room
        lobby = yield services.join_lobby(xmpp, service_room, "config")
        logger.addHandler(log.RoomHandler(lobby.room))

        yield inner.sub(ConfigFollower(customer_file) | Setup(lobby))
    return bot()
main.customer_file_help = "the customer database file"
main.service_room_help = "the room where the services are collected"
main.xmpp_jid_help = "the XMPP JID (e.g. xmppuser@xmpp.example.com)"
main.xmpp_password_help = "the XMPP password"
main.log_file_help = "log to the given file instead of the console"

if __name__ == "__main__":
    from abusehelper.core import opts
    threado.run(opts.optparse(main))
