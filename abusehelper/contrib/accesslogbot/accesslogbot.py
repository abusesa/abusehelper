from abusehelper.core import bot, events
from abusehelper.contrib.tailbot.tailbot import TailBot

import re
import time
from calendar import timegm


DATE_REX = re.compile(
    r"^(\d{1,2}/.+?/\d{4}:\d{1,2}:\d{1,2}:\d{1,2})\s+([+-]\d{4})$")


def convert_date(datestring, to_format="%Y-%m-%d %H:%M:%S UTC"):
    """
    >>> convert_date('01/Jan/1970:00:00:00 +0000')
    '1970-01-01 00:00:00 UTC'
    >>> convert_date('01/Jan/1970:00:00:00 -0100')
    '1970-01-01 01:00:00 UTC'
    >>> convert_date('01/Jan/1970:01:00:00 +0100')
    '1970-01-01 00:00:00 UTC'

    >>> convert_date('half past midnight')
    'half past midnight'
    """

    match = DATE_REX.match(datestring)
    if not match:
        return datestring

    datetime, timezone = match.groups()
    try:
        timestamp = timegm(time.strptime(datetime, "%d/%b/%Y:%H:%M:%S"))
    except ValueError:
        return datestring

    tz_offset = int(timezone)
    timestamp -= 3600 * (tz_offset // 100) + 60 * (tz_offset % 100)
    return time.strftime(to_format, time.gmtime(timestamp))


def split_prefix(string, separator=" "):
    left, _, right = string.partition(separator)
    return left.strip(), right.strip()


def parse_log_line(line):
    """
    >>> sorted(parse_log_line('192.0.2.0 a b [01/Jan/1970:00:00:00 +0000] "/" 200 1337'))
    [('bytes', '1337'), ('ident', 'a'), ('ip', '192.0.2.0'), ('request', '/'), ('status', '200'), ('timestamp', '01/Jan/1970:00:00:00 +0000'), ('user', 'b')]

    >>> sorted(parse_log_line('192.0.2.0 - - [01/Jan/1970:00:00:00 +0000] "/" 200 1337'))
    [('bytes', '1337'), ('ip', '192.0.2.0'), ('request', '/'), ('status', '200'), ('timestamp', '01/Jan/1970:00:00:00 +0000')]

    >>> sorted(parse_log_line('192.0.2.0 - - [01/Jan/1970:00:00:00 +0000] "/" 200 1337 "referer" "useragent"'))
    [('bytes', '1337'), ('ip', '192.0.2.0'), ('referer', 'referer'), ('request', '/'), ('status', '200'), ('timestamp', '01/Jan/1970:00:00:00 +0000'), ('user_agent', 'useragent')]
    """

    # LogFormat "%h %l %u %t \"%r\" %>s %b" common
    # LogFormat "%h %l %u %t \"%r\" %>s %b \"%{Referer}i\" \"%{User-agent}i\"" combined

    ip, right = split_prefix(line)
    yield "ip", ip

    ident, right = split_prefix(right)
    if ident and ident != "-":
        yield "ident", ident

    user, right = split_prefix(right)
    if user and user != "-":
        yield "user", user

    if not right.startswith("["):
        return
    timestamp, right = split_prefix(right[1:], "]")
    yield "timestamp", timestamp

    if not right.startswith("\""):
        return
    request, right = split_prefix(right[1:], "\"")
    yield "request", request

    status, right = split_prefix(right)
    if status and status != "-":
        yield "status", status

    bytes, right = split_prefix(right)
    if bytes and bytes != "-":
        yield "bytes", bytes

    if not right.startswith("\""):
        return
    referer, right = split_prefix(right[1:], "\"")
    if referer and referer != "-":
        yield "referer", referer

    if not right.startswith("\""):
        return
    user_agent, _ = split_prefix(right[1:], "\"")
    if user_agent and user_agent != "-":
        yield "user_agent", user_agent


def parse_request(request):
    # Split request also into three parts
    method, url, protocol = request.split(" ", 3)
    yield "method", method
    yield "url", url
    yield "protocol", protocol


def parse_user_agent(user_agent):
    # Split user agent into software-version key-value pairs
    user_agent = user_agent.strip()

    products = list()
    while user_agent:
        if user_agent.startswith("("):
            _, user_agent = split_prefix(user_agent[1:], ")")
            continue

        left, user_agent = split_prefix(user_agent)
        split = left.split("/", 2)
        if len(split) != 2:
            continue

        sw, version = split
        if sw and version:
            yield sw.lower(), version
            products.append(sw + "/" + version)
    yield "product", products


class AccessLogBot(TailBot):
    path = bot.Param("access_log file path")

    def parse(self, line, _):
        line = line.strip()
        if not line:
            return

        facts = dict(parse_log_line(line))
        if "timestamp" in facts:
            facts["timestamp"] = convert_date(facts["timestamp"])
        if "request" in facts:
            facts.update(parse_request(facts["request"]))
        if "user_agent" in facts:
            facts.update(parse_user_agent(facts["user_agent"]))
        return events.Event(facts)


if __name__ == "__main__":
    AccessLogBot.from_command_line().execute()
