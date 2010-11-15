# A bot that parses mails containing URLs (one URL per line, ignoring
# lines that don't look like relatively sane URLs). The hosts are
# resolved to 0-n IPv4/6 addresses. The bot also makes an effort to
# find out the addresses' AS info etc.
#
# As an example the following mail could yield events 
# "host=www.example.com, ip=198.51.100.2, AS=65536, ..." and
# "host=badly-indented-url.example.com, ip=2001:db8::2, AS=65536, ...":
#
# From: urlfeed@example.com
# To: you@organization
# Subject: Daily dose of URL lines
#
# Hello, here we have some URLs for You:
#  http://www.example.com
#      https://badly-indented-url.example.com
# Sincerely, Albert Urlfeed

import socket
import urlparse

from idiokit import threado
from abusehelper.core import imapbot, events, bot, cymru

def get_hosts(url_lines):
    r"""
    Return hostnames names parsed from an iterable sequence of URL
    lines. Ignore lines that don't have at least the URL scheme and
    hostname defined.

    >>> list(get_hosts(["ignore this", "http://host"]))
    ['host']

    The leading and trailing whitespaces are ignored.

    >>> list(get_hosts(["    http://host    "]))
    ['host']

    The input can be any iterable sequence of lines, e.g. a file-like
    object.

    >>> from StringIO import StringIO
    >>> list(get_hosts(StringIO("ignore this\nhttp://host")))
    ['host']
    """

    for line in url_lines:
        line = line.strip()

        parsed = urlparse.urlparse(line)
        if parsed.scheme and parsed.hostname:
            yield parsed.hostname

@threado.stream
def get_resolved_hosts(inner, url_lines):
    r"""
    Send out events containing hostnames (parsed from an iterable
    sequence of URL lines) and their respective IPv4 and IPv6
    addresses. 0-n events may be sent per each hostname (one for each
    resolved IPv4/6 address).
    """

    for host in get_hosts(url_lines):
        current = inner.thread(socket.getaddrinfo, host, None)
        while not current.has_result():
            yield inner, current
            
        for family, socktype, proto, canonname, sockaddr in current.result():
            if family not in (socket.AF_INET, socket.AF_INET6):
                continue

            event = events.Event()
            event.add("host", host)
            event.add("ip", sockaddr[0])
            inner.send(event)

class URLListMailBot(imapbot.IMAPBot):
    def augment(self):
        return cymru.CymruWhois()

    @threado.stream
    def handle_text_plain(inner, self, headers, fileobj):
        yield inner.sub(get_resolved_hosts(fileobj))
        inner.finish(True)

if __name__ == "__main__":
    URLListMailBot.from_command_line().execute()
