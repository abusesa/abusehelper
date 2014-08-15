from __future__ import absolute_import

import socket
import idiokit
from idiokit import dns

from . import utils


def _parse_ip(string, families=(socket.AF_INET, socket.AF_INET6)):
    for family in families:
        try:
            return socket.inet_ntop(family, socket.inet_pton(family, string))
        except (ValueError, socket.error):
            pass
    return None


def _nibbles(ipv6, _hex="0123456789abcdef"):
    result = []
    for ch in socket.inet_pton(socket.AF_INET6, ipv6):
        num = ord(ch)
        result.append(_hex[num >> 4])
        result.append(_hex[num & 0xf])
    return result


def _split(txt_results, keys):
    results = set()

    for strings in txt_results:
        pieces = "".join(strings).split("|")
        decoded = map(lambda x: x.strip().decode("utf-8", "replace"), pieces)

        item_list = list()
        for key, value in zip(keys, decoded):
            if key is None:
                continue
            if value in ("", "-"):
                continue
            item_list.append((key, value))

        if not item_list:
            continue

        results.add(frozenset(item_list))

    return tuple(tuple(x) for x in results)


class ASNameLookup(object):
    _keys = (None, None, None, "as allocated", "as name")

    def __init__(self, resolver=None, cache_time=4 * 60 * 60):
        self._resolver = resolver
        self._cache = utils.TimedCache(cache_time)

    @idiokit.stream
    def lookup(self, asn):
        try:
            asn = int(asn)
        except ValueError:
            idiokit.stop(())

        results = self._cache.get(asn, None)
        if results is not None:
            idiokit.stop(results)

        try:
            txt_results = yield dns.txt(
                "AS{0}.asn.cymru.com".format(asn),
                resolver=self._resolver)
        except dns.DNSError:
            idiokit.stop(())

        results = _split(txt_results, self._keys)
        self._cache.set(asn, results)
        idiokit.stop(results)


class OriginLookup(object):
    _keys = ("asn", "bgp prefix", "cc", "registry", "bgp prefix allocated")

    def __init__(self, resolver=None, cache_time=4 * 60 * 60):
        self._resolver = resolver
        self._cache = utils.TimedCache(cache_time)

    @idiokit.stream
    def _lookup(self, cache_key, query):
        results = self._cache.get(cache_key, None)
        if results is not None:
            idiokit.stop(results)

        try:
            txt_results = yield dns.txt(query, resolver=self._resolver)
        except dns.DNSError:
            idiokit.stop(())

        results = []
        for result in _split(txt_results, self._keys):
            result_dict = dict(result)
            for asn in result_dict.get("asn", "").split():
                if not asn:
                    continue
                result_dict["asn"] = asn
                results.append(tuple(result_dict.iteritems()))

        self._cache.set(cache_key, tuple(results))
        idiokit.stop(results)

    @idiokit.stream
    def lookup(self, ip):
        ipv4 = _parse_ip(ip, families=[socket.AF_INET])
        if ipv4 is not None:
            prefix = ".".join(reversed(ipv4.split(".")))
            results = yield self._lookup(ipv4, prefix + ".origin.asn.cymru.com")
            idiokit.stop(results)

        ipv6 = _parse_ip(ip, families=[socket.AF_INET6])
        if ipv6 is not None:
            prefix = ".".join(reversed(_nibbles(ipv6)))
            results = yield self._lookup(ipv6, prefix + ".origin6.asn.cymru.com")
            idiokit.stop(results)

        idiokit.stop(())


class CymruWhois(object):
    def __init__(self, resolver=None, cache_time=4 * 60 * 60):
        self._origin_lookup = OriginLookup(resolver, cache_time)
        self._asname_lookup = ASNameLookup(resolver, cache_time)

    def _ip_values(self, event, keys):
        for key in keys:
            for value in event.values(key, parser=_parse_ip):
                yield value

    @idiokit.stream
    def augment(self, *ip_keys):
        while True:
            event = yield idiokit.next()
            if not ip_keys:
                values = event.values(parser=_parse_ip)
            else:
                values = self._ip_values(event, ip_keys)

            for ip in values:
                items = yield self.lookup(ip)
                for key, value in items:
                    event.add(key, value)

            yield idiokit.send(event)

    @idiokit.stream
    def lookup(self, ip):
        results = yield self._origin_lookup.lookup(ip)
        for result in results:
            result = dict(result)

            asn = result.get("asn", None)
            if asn is not None:
                infos = yield self._asname_lookup.lookup(asn)
                for info in infos:
                    result.update(info)
                    break
                idiokit.stop(tuple(result.items()))
        idiokit.stop(())


global_whois = CymruWhois()

augment = global_whois.augment
lookup = global_whois.lookup
