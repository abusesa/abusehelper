from __future__ import absolute_import

import time
import heapq
import calendar


def _merge(sorted_iterables):
    """
    >>> list(_merge([(1, 2, 3), (0, 2, 4)]))
    [0, 1, 2, 2, 3, 4]
    """

    heap = []

    for iterable in sorted_iterables:
        iterator = iter(iterable)

        for value in iterator:
            heapq.heappush(heap, (value, iterator))
            break

    while heap:
        value, iterator = heapq.heappop(heap)

        yield value

        for value in iterator:
            heapq.heappush(heap, (value, iterator))
            break


def _dedup(sorted_iterable):
    """
    >>> list(_dedup([1, 1, 2, 3, 3]))
    [1, 2, 3]
    """

    iterator = iter(sorted_iterable)

    for previous in iterator:
        yield previous
        break

    for value in iterator:
        if value == previous:
            continue

        yield value
        previous = value


class _CmpMixin(object):
    def __eq__(self, other):
        return self is other

    def __ne__(self, other):
        result = self.__eq__(other)
        if result is NotImplemented:
            return NotImplemented
        return not result


min_time_tuple = [1970, 1, 1, 0, 0, 0, 0, 0, -1]


def normalized_time_tuple(time_tuple):
    timestamp = calendar.timegm(list(time_tuple[:6]) + [0, 0, -1])
    return time.gmtime(timestamp)[:8] + (-1,)


def is_valid_time_tuple(time_tuple):
    normalized = normalized_time_tuple(time_tuple)
    return tuple(normalized[:6]) == tuple(time_tuple[:6])


class _Unit(object):
    def __init__(self, min, max, time_tuple_index, aliases={}):
        self.min = min
        self.max = max
        self.time_tuple_index = time_tuple_index
        self.aliases = {}

        for value, alias_list in aliases.iteritems():
            for alias in alias_list:
                self.aliases[alias] = value

    def map(self, value):
        if not isinstance(value, basestring):
            return value

        normalized = value.strip().lower()
        if normalized not in self.aliases:
            raise ValueError("unknown value {0!r}".format(value))

        return self.aliases[normalized]

    def _resolve_one(self, (first, last, step)):
        first = self.min if first is None else self.map(first)
        last = self.max if last is None else self.map(last)

        if last < first:
            raise ValueError("range end {0} smaller than range start {1}".format(first, last))

        if not self.min <= first <= last <= self.max:
            if first == last:
                raise ValueError("value {0} falls outside of range {1}-{2}".format(first, self.min, self.max))
            else:
                raise ValueError("range {0}-{1} falls outside of range {2}-{3}".format(first, last, self.min, self.max))

        if not 1 <= step <= self.max - self.min + 1:
            raise ValueError("step {0} outside of range 1-{1}".format(step, self.max - self.min + 1))

        return first, last, step

    def resolve(self, ranges):
        return _Resolved(self, map(self._resolve_one, ranges))

    def iter_range(self, time_tuple, (first, last, step)):
        time_tuple = list(time_tuple)
        index = self.time_tuple_index

        if time_tuple[index] < first:
            time_tuple[index] = first
            time_tuple[index + 1:] = min_time_tuple[index + 1:]
        else:
            modulo = (time_tuple[index] - first) % step
            if modulo > 0:
                time_tuple[index] = time_tuple[index] - modulo + step
                time_tuple[index + 1:] = min_time_tuple[index + 1:]

        while time_tuple[index] <= last and is_valid_time_tuple(time_tuple):
            yield normalized_time_tuple(time_tuple)

            time_tuple[index] += step
            time_tuple[index + 1:] = min_time_tuple[index + 1:]


class _MonthUnit(_Unit):
    def iter_range(self, time_tuple, range):
        time_tuple = list(time_tuple)

        while True:
            for result in _Unit.iter_range(self, time_tuple, range):
                yield result

            # Advance to the next year
            time_tuple[0] += 1
            time_tuple[1:] = min_time_tuple[1:]


class _WeekdayUnit(_Unit):
    def iter_range(self, time_tuple, (first, last, step)):
        time_tuple = list(time_tuple)

        while True:
            if not is_valid_time_tuple(time_tuple):
                break

            weekday = (calendar.weekday(*time_tuple[:3]) + 1) % 7
            if weekday > last:
                time_tuple[2] += 7 - weekday
                time_tuple[3:] = min_time_tuple[3:]
                continue

            if weekday < first:
                time_tuple[2] += first - weekday
                time_tuple[3:] = min_time_tuple[3:]
                continue

            yield normalized_time_tuple(time_tuple)

            time_tuple[2] += 1
            time_tuple[3:] = min_time_tuple[3:]


class _Ranges(object):
    def __init__(self, ranges):
        self._ranges = list(ranges)

    def or_range(self, start, end, step=1):
        return _Ranges(self._ranges + [(start, end, step)])

    def or_value(self, value):
        return _Ranges(self._ranges + [(value, value, 1)])

    def or_any(self, step=1):
        return _Ranges(self._ranges + [(None, None, step)])

    def __iter__(self):
        return iter(tuple(self._ranges))


class _Resolved(_CmpMixin):
    def __init__(self, unit, ranges):
        self._unit = unit
        self._ranges = tuple(ranges)

    def iter_from(self, value):
        return _dedup(_merge(self._unit.iter_range(value, x) for x in self._ranges))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return set(self._ranges) == set(other._ranges)


class _ResolvedOr(_CmpMixin):
    def __init__(self, left, right):
        self._left = left
        self._right = right

    def iter_from(self, value):
        left = self._left.iter_from(value)
        right = self._right.iter_from(value)
        return _dedup(_merge([left, right]))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        if self._left == other._left and self._right == other._right:
            return True
        if self._left == other._right and self._right == other._left:
            return True
        return False


def empty():
    return _Ranges([])


def range(start, end, step=1):
    return _Ranges([(start, end, step)])


def value(value):
    return _Ranges([(value, value, 1)])


def any(step=1):
    return _Ranges([(None, None, step)])


class Cron(_CmpMixin):
    _units = {
        "minute": _Unit(0, 59, 4),

        "hour": _Unit(0, 23, 3),

        "day": _Unit(1, 31, 2),

        "weekday": _WeekdayUnit(0, 6, 2, aliases={
            0: ["sun", "sunday"],
            1: ["mon", "monday"],
            2: ["tue", "tuesday"],
            3: ["wed", "wednesday"],
            4: ["thu", "thursday"],
            5: ["fri", "friday"],
            6: ["sat", "saturday"]
        }),

        "month": _MonthUnit(1, 12, 1, aliases={
            1: ["jan", "january"],
            2: ["feb", "february"],
            3: ["mar", "march"],
            4: ["apr", "april"],
            5: ["may", "may"],
            6: ["jun", "june"],
            7: ["jul", "july"],
            8: ["aug", "august"],
            9: ["sep", "september"],
            10: ["oct", "october"],
            11: ["nov", "november"],
            12: ["dec", "december"]
        })
    }

    def __init__(self, *args, **keys):
        self._spec = {}

        max_priority = min(x.time_tuple_index for x in self._units.values())

        for key, arg in dict(*args, **keys).iteritems():
            if key not in self._units:
                raise TypeError("unexpected unit {0!r}".format(key))

            unit = self._units[key]
            max_priority = max(max_priority, unit.time_tuple_index)
            rangeobj = self._coerce(arg)
            self._spec[key] = unit.resolve(rangeobj)

        for key, unit in self._units.iteritems():
            if key in self._spec:
                continue

            if max_priority >= unit.time_tuple_index:
                self._spec[key] = unit.resolve(any())
            else:
                self._spec[key] = unit.resolve(value(unit.min))

        # Special case: If both day or weekday is limited, then use OR instead of AND.
        if self._is_any("day"):
            self._spec["day"] = self._units["day"].resolve(empty())
        elif self._is_any("weekday"):
            self._spec["weekday"] = self._units["weekday"].resolve(empty())
        self._spec["day"] = _ResolvedOr(self._spec.pop("day"), self._spec.pop("weekday"))

    def _is_any(self, unit_name):
        unit = self._units[unit_name]
        return unit.resolve(any()) == self._spec[unit_name]

    def _coerce(self, arg):
        if isinstance(arg, _Ranges):
            return arg
        return value(arg)

    def _iter(self, time_tuple, order):
        if not order:
            yield time_tuple
            return

        resolved = self._spec[order[0]]
        for new_tuple in resolved.iter_from(time_tuple):
            for result in self._iter(new_tuple, order[1:]):
                yield normalized_time_tuple(result)

    def iter(self, time_tuple=None):
        if time_tuple is None:
            time_tuple = time.localtime()
        time_tuple = normalized_time_tuple(time_tuple)

        order = sorted(self._spec, key=lambda x: self._units[x].time_tuple_index)
        return self._iter(time_tuple, order)

    def next(self, time_tuple=None):
        if time_tuple is None:
            time_tuple = time.localtime()
        time_tuple = normalized_time_tuple(time_tuple)

        for result in self.iter(time_tuple):
            if result[:6] != time_tuple[:6]:
                return result
        return None

    def matches(self, time_tuple):
        if time_tuple is None:
            time_tuple = time.localtime()
        time_tuple = normalized_time_tuple(time_tuple)

        for result in self.iter(time_tuple):
            return result[:6] == time_tuple[:6]
        return False

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self._spec == other._spec


class CronParser(object):
    _units = ["minute", "hour", "day", "month", "weekday"]

    def parse(self, string):
        fields = string.split()
        if len(fields) != 5:
            raise ValueError("unknown format {0!r}".format(string))

        results = {}
        for unit, field in zip(self._units, fields):
            ranges = empty()

            for part in [x.strip() for x in field.split(",")]:
                if not part:
                    raise ValueError("empty " + unit + " value")

                if "/" not in part:
                    step = 1
                else:
                    part, step = part.rsplit("/", 1)
                    if not step.isdigit():
                        raise ValueError("step value {0!r} should be an integer".format(step))
                    step = int(step)

                if part.strip() == "*":
                    first = None
                    last = None
                else:
                    if "-" in part:
                        first, last = part.rsplit("-", 1)
                    else:
                        first = part
                        last = part

                    if first.isdigit():
                        first = int(first)
                    if last.isdigit():
                        last = int(last)

                ranges = ranges.or_range(first, last, step)

            results[unit] = ranges
        return Cron(results)

parse = CronParser().parse
