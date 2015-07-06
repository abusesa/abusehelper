from __future__ import absolute_import

from . import atoms
from . import rules


__all__ = ["AND", "OR", "NOT", "MATCH", "ANYTHING", "MATCHError", "NETBLOCK", "NETBLOCKError"]


AND = rules.And
OR = rules.Or
NOT = rules.No


MATCHError = ValueError
MATCH = rules.Match


NETBLOCKError = ValueError


def NETBLOCK(ip_or_range, bits_or_end=None, keys=None):
    atom = atoms.IP(ip_or_range, bits_or_end)
    if keys:
        return rules.Or(*[rules.Match(x, atom) for x in set(keys)])
    return rules.Match(value=atom)


def ANYTHING():
    return rules.Anything()
