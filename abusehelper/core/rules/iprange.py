import re
import math
import struct
from socket import inet_ntop, inet_pton, AF_INET, AF_INET6, error

import parsing


def parse_ipv4(ip):
    try:
        packed = inet_pton(AF_INET, ip.strip())
    except (error, UnicodeEncodeError):
        return None

    ip_num, = struct.unpack("!I", packed)
    return ip_num


def format_ipv4(ip_num):
    return inet_ntop(AF_INET, struct.pack("!I", ip_num))


def parse_ipv6(ip):
    try:
        packed = inet_pton(AF_INET6, ip.strip())
    except (error, UnicodeEncodeError):
        return None

    hi, lo = struct.unpack("!QQ", packed)
    return (hi << 64) | lo


def format_ipv6(ip_num):
    hi = ip_num >> 64
    lo = ip_num & 0xffffffffffffffff
    return inet_ntop(AF_INET6, struct.pack("!QQ", hi, lo))


class IPVersion(object):
    def __init__(self, max_bits, parser, formatter):
        self._max_bits = max_bits
        self._parser = parser
        self._formatter = formatter

    @property
    def max_bits(self):
        return self._max_bits

    def parse(self, string):
        return self._parser(string)

    def format(self, ip_num):
        return self._formatter(ip_num)

    def range_from_bitmask(self, ip_num, bits):
        max_bits = self._max_bits

        mask = ((1 << max_bits) - 1) ^ ((1 << (max_bits - bits)) - 1)
        first = ip_num & mask
        last = first + (1 << (max_bits - bits)) - 1

        return first, last


ipv4 = IPVersion(32, parse_ipv4, format_ipv4)
ipv6 = IPVersion(128, parse_ipv6, format_ipv6)


class IPRangeParser(parsing.Parser):
    def __init__(self, version, pattern):
        self._version = version

        self._ip_rex = re.compile(r"(" + pattern + r")", re.U | re.I)
        self._cidr_rex = re.compile(r"\s*/\s*(\d{1,5})", re.U | re.I)
        self._range_rex = re.compile(r"\s*-\s*(" + pattern + r")", re.U | re.I)

    def parse_gen(self, (string, start, end)):
        ver = self._version

        match = self._ip_rex.match(string, start, end)
        if match is None:
            yield None, None

        first = ver.parse(match.group(1))
        if first is None:
            yield None, None

        start = match.end()

        match = self._cidr_rex.match(string, start, end)
        if match:
            bits = int(match.group(1))
            if not 0 <= bits <= ver.max_bits:
                yield None, None
            first, last = ver.range_from_bitmask(first, bits)
            yield None, (IPRange(ver, first, last), (string, match.end(), end))

        match = self._range_rex.match(string, start, end)
        if match:
            last = self._version.parse(match.group(1))
            if last is None:
                yield None, None
            yield None, (IPRange(ver, first, last), (string, match.end(), end))

        yield None, (IPRange(ver, first, first), (string, start, end))


ipv4_parser = IPRangeParser(ipv4, r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
ipv6_parser = IPRangeParser(ipv6, r"[0-9a-f]*:[0-9a-f]*:[0-9a-f:]*")


class IPRange(object):
    parser = parsing.union(ipv4_parser, ipv6_parser)

    @classmethod
    def _parse_ip(cls, string):
        ip_num = ipv4.parse(string)
        if ip_num is not None:
            return ipv4, ip_num

        ip_num = ipv6.parse(string)
        if ip_num is not None:
            return ipv6, ip_num

        raise ValueError("invalid IP address" + repr(string))

    @classmethod
    def from_autodetected(cls, string, other=None):
        if "-" in string:
            if other is not None:
                raise TypeError("unexpected second argument " + repr(other))
            return cls.from_range_str(string)
        elif "/" in string:
            if other is not None:
                raise TypeError("unexpected second argument " + repr(other))
            return cls.from_cidr_str(string)
        elif other is None:
            return cls.from_ip(string)

        if isinstance(other, basestring):
            return cls.from_range(string, other)
        return cls.from_cidr(string, other)

    @classmethod
    def from_range_str(cls, string):
        split = string.strip().split("-", 1)
        if len(split) < 2:
            raise ValueError("invalid IP range " + repr(string))
        return cls.from_range(*split)

    @classmethod
    def from_cidr_str(cls, string):
        split = string.strip().split("/", 1)
        if len(split) < 2:
            raise ValueError("invalid CIDR " + repr(string))

        ip, bits = split
        try:
            bits = int(bits)
        except ValueError:
            raise ValueError("invalid bitmask " + repr(bits))
        return cls.from_cidr(ip, bits)

    @classmethod
    def from_range(cls, first, last):
        first_ver, first_num = cls._parse_ip(first)
        last_ver, last_num = cls._parse_ip(last)
        if first_ver == last_ver:
            return cls(first_ver, *sorted([first_num, last_num]))

        raise ValueError(
            "mismatching IP addresses ({0!r} and {1!r})".format(first, last))

    @classmethod
    def from_cidr(cls, ip, bits):
        version, ip_num = cls._parse_ip(ip)
        if 0 <= bits <= version.max_bits:
            first, last = version.range_from_bitmask(ip_num, bits)
            return cls(version, first, last)

        raise ValueError(
            "bitmask {0} outside of range 0-{1}".format(bits, version.max_bits))

    @classmethod
    def from_ip(cls, ip):
        version, ip_num = cls._parse_ip(ip)
        return cls(version, ip_num, ip_num)

    def __init__(self, version, first, last):
        self._version = version
        self._first = first
        self._last = last
        self._hash = None

    def __hash__(self):
        if self._hash is None:
            self._hash = hash((self.__class__, self._version, self._first, self._last))
        return self._hash

    def __eq__(self, other):
        if not isinstance(other, IPRange):
            return NotImplemented

        if self._version is not other._version:
            return False

        return self._first == other._first and self._last == other._last

    def __ne__(self, other):
        eq = self.__eq__(other)
        if eq is NotImplemented:
            return NotImplemented
        return not eq

    def contains(self, other):
        if not isinstance(other, IPRange):
            return False

        if self._version is not other._version:
            return False

        return self._first <= other._first <= other._last <= self._last

    def __unicode__(self):
        first_str = unicode(self._version.format(self._first))

        count = self._last - self._first + 1
        if count == 1:
            return first_str

        bits = self._version.max_bits - int(math.log(count, 2))
        first, last = self._version.range_from_bitmask(self._first, bits)
        if first == self._first and last == self._last:
            return first_str + u"/" + unicode(repr(bits))

        return first_str + u"-" + unicode(self._version.format(self._last))
