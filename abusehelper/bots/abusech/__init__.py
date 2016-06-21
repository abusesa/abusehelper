import re
import socket
import urlparse

from abusehelper.core import events
from abusehelper.bots.rssbot.rssbot import RSSBot


def parse_ip(string):
    for addr_type in (socket.AF_INET, socket.AF_INET6):
        try:
            return socket.inet_ntop(addr_type, socket.inet_pton(addr_type, string))
        except (ValueError, socket.error):
            pass
    return None


def host_or_ip(host):
    ip = parse_ip(host)
    if ip is None:
        return "domain name", host
    else:
        return "ip", ip


def host_or_ip_from_url(url):
    parsed = urlparse.urlparse(url)
    return host_or_ip(parsed.netloc)


_levels = {
    "1": ["The malicious service is hosted on a bulletproof server."],
    "2": ["The malicious service is offered through a hacked webserver."],
    "3": ["The malicious service is offered through a free hosting service."],
    "4": [],  # "4" denotes an unknown level
    "5": ["The malicious service is hosted on a fastflux botnet."]
}


def resolve_level(value):
    return tuple(_levels.get(value, []))


def sanitize_url(url):
    return re.sub("^http:\/\/", "hxxp://", url)


def split_description(description):
    for part in description.split(","):
        pair = part.split(":", 1)
        if len(pair) < 2:
            continue

        key = pair[0].lower().strip()
        value = pair[1].strip()
        if not key or not value:
            continue

        yield key, value


class AbuseCHFeedBot(RSSBot):
    feed_malware = []
    feed_type = []

    def create_descriptions(self, event):
        types = "/".join(event.values("type"))
        if not types:
            return

        malwares = "/".join(event.values("malware") or [u"malware"])
        yield u"This host is most likely hosting a {0} {1}".format(malwares, types)

    def parse_link(self, link):
        yield "description url", link

    def parse_title(self, title):
        parts = title.split()
        if len(parts) < 2:
            return

        tstamp = parts[1]
        tstamp = re.sub("[()]", "", tstamp)
        yield "source time", tstamp

    def parse(self, input_key, input_value):
        parser = getattr(self, "parse_" + input_key, None)
        if not callable(parser):
            return

        for output_key, output_value in parser(input_value):
            yield output_key, output_value

    def create_event(self, source, **keys):
        event = events.Event({
            "feeder": "abuse.ch",
            "feed": self.feed_name,
            "malware family": self.feed_malware,
            "type": self.feed_type,
            "feed url": source
        })

        for input_key, input_value in keys.iteritems():
            for output_key, output_value in self.parse(input_key, input_value):
                if isinstance(output_value, basestring):
                    event.add(output_key, output_value)
                else:
                    event.update(output_key, output_value)

        if not event.contains("description"):
            event = event.union(description=self.create_descriptions(event))
        return event
