from __future__ import absolute_import

from . import atoms
from . import rules
from . import classifier


__all__ = ["AND", "OR", "NOT", "MATCH", "ANYTHING", "MATCHError", "NETBLOCK", "NETBLOCKError", "RuleClassifier"]


AND = rules.And
OR = rules.Or
NOT = rules.No
RuleClassifier = classifier.Classifier


MATCHError = ValueError
MATCH = rules.Match


NETBLOCKError = ValueError


def NETBLOCK(ip_or_range, bits_or_end=None, keys=None):
    atom = atoms.IP(ip_or_range, bits_or_end)
    if keys:
        return rules.Or(*[rules.In(x, atom) for x in set(keys)])
    return rules.In(value=atom)


def ANYTHING():
    return rules.MATCH()
