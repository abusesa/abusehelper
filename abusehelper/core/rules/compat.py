from __future__ import absolute_import

import warnings
import functools

from . import atoms
from . import rules


__all__ = ["AND", "OR", "NOT", "MATCH", "ANYTHING", "NETBLOCK"]


def _deprecated(callable):
    @functools.wraps(callable)
    def _callable(*args, **keys):
        warnings.warn(
            "abusehelper.core.rules.AND, OR, NOT, MATCH, ANYTHING and NETBLOCK " +
            "are deprecated. They will be removed in an upcoming AbuseHelper version. " +
            "Please use abusehelper.core.rules.And, Or, No, Match and Anything " +
            "instead.",
            DeprecationWarning,
            stacklevel=2
        )
        return callable(*args, **keys)
    return _callable


AND = _deprecated(rules.And)
OR = _deprecated(rules.Or)
NOT = _deprecated(rules.No)
MATCH = _deprecated(rules.Match)
ANYTHING = _deprecated(rules.Anything)


@_deprecated
def NETBLOCK(ip_or_range, bits_or_end=None, keys=None):
    atom = atoms.IP(ip_or_range, bits_or_end)
    if keys:
        return rules.Or(*[rules.Match(x, atom) for x in set(keys)])
    return rules.Match(value=atom)
