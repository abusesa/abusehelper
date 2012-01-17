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

import idiokit
from idiokit import threadpool
from abusehelper.core import imapbot, events, cymruwhois

def get_hosts(url_lines):
    r"""
    Return (url, hostname) pairs parsed from an iterable sequence of
    URL lines. Ignore lines that don't have at least the URL scheme
    and hostname defined.

    >>> list(get_hosts(["ignore this", "http://host"]))
    [('http://host', 'host')]

    The leading and trailing whitespaces are ignored.

    >>> list(get_hosts(["    http://host    "]))
    [('http://host', 'host')]

    The input can be any iterable sequence of lines, e.g. a file-like
    object.

    >>> from StringIO import StringIO
    >>> list(get_hosts(StringIO("ignore this\nhttp://host")))
    [('http://host', 'host')]
    """

    for line in url_lines:
        line = line.strip()

        parsed = urlparse.urlparse(line)
        if parsed.scheme and parsed.hostname:
            yield line, parsed.hostname

class URLListMailBot(imapbot.IMAPBot):
    @idiokit.stream
    def get_resolved_hosts(self, url_lines):
        r"""
        Send out events containing URLs (parsed from an iterable
        sequence of URL lines) and their respective hostname's IPv4
        and IPv6 addresses. 0-n events may be sent per each URL (one
        for each resolved hostname IPv4/6 address).
        """

        for url, host in get_hosts(url_lines):
            try:
                addrinfo = yield threadpool.thread(socket.getaddrinfo, host, None)
            except socket.error, error:
                self.log.info("Could not resolve host %r: %r", host, error)
                continue

            addresses = set()
            for family, _, _, _, sockaddr in addrinfo:
                if family not in (socket.AF_INET, socket.AF_INET6):
                    continue
                addresses.add(sockaddr[0])

            for address in addresses:
                event = events.Event()
                event.add("url", url)
                event.add("ip", address)
                yield idiokit.send(event)

    @idiokit.stream
    def handle_text_plain(self, headers, fileobj):
        yield self.get_resolved_hosts(fileobj) | cymruwhois.augment("ip")
        idiokit.stop(True)

if __name__ == "__main__":
    URLListMailBot.from_command_line().execute()
