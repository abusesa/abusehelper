from __future__ import absolute_import

from . import atoms
from . import rules


__all__ = ["AND", "OR", "NOT", "MATCH", "ANYTHING", "NETBLOCK"]


AND = rules.And
OR = rules.Or
NOT = rules.No
MATCH = rules.Match
ANYTHING = rules.Anything


def NETBLOCK(ip_or_range, bits_or_end=None, keys=None):
    atom = atoms.IP(ip_or_range, bits_or_end)
    if keys:
        return rules.Or(*[rules.Match(x, atom) for x in set(keys)])
    return rules.Match(value=atom)
