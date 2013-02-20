import re


class ParserError(Exception):
    pass


class Parser(object):
    def parse_iter(self, data):
        raise NotImplementedError()

    def parse(self, string):
        data = string, 0, len(string)

        stack = []
        parser = self
        next, result = parser.init_parse(data)

        while True:
            if next is not None:
                data, state = result
                stack.append((parser, state))
                parser = next
                next, result = parser.init_parse(data)
            elif stack:
                parser, state = stack.pop()
                next, result = parser.cont_parse(result, state)
            else:
                break

        if result is None:
            return None
        (string, start, end), obj = result
        return obj, string[start:end]

    def take(self, first, *rest):
        def _take(result):
            if not rest:
                return result[first]
            return (result[first],) + tuple(result[key] for key in rest)
        return Transform(self, _take)


class Transform(Parser):
    def __init__(self, parser, func):
        self._parser = parser
        self._func = func

    def init_parse(self, data):
        return self._parser, (data, None)

    def cont_parse(self, match, _):
        if not match:
            return None, None
        data, result = match
        return None, (data, self._func(result))


def transform(parser):
    def _transform(func):
        return Transform(parser, func)
    return _transform


class ForwardRef(Parser):
    def __init__(self):
        self._parser = None

    def set(self, parser):
        if self._parser is not None:
            raise ParserError("forward reference already set")
        self._parser = parser

    def init_parse(self, data):
        if self._parser is None:
            raise ParserError("forward reference not set")
        return self._parser, (data, None)

    def cont_parse(self, match, _):
        return None, match


class RegExp(Parser):
    def __init__(self, *args, **keys):
        regexp = re.compile(*args, **keys)
        self._regexp = re.compile(regexp.pattern, regexp.flags | re.U)

    def init_parse(self, data):
        string, start, end = data
        match = self._regexp.match(string, start, end)
        if match is None:
            return None, None
        return None, ((string, match.end(), end), match.groups())


class Sequence(Parser):
    def __init__(self, *parsers):
        self._parsers = parsers

    def init_parse(self, data):
        parsers = self._parsers
        if not parsers:
            return None, (data, [])

        length = len(parsers)
        return parsers[0], (data, (1, length, parsers, []))

    def cont_parse(self, match, (index, length, parsers, results)):
        if not match:
            return None, None

        data, result = match
        results.append(result)

        if index >= length:
            return None, (data, results)
        return parsers[index], (data, (index + 1, length, parsers, results))


class OneOf(Parser):
    def __init__(self, *parsers):
        self._parsers = parsers

    def init_parse(self, data):
        parsers = self._parsers
        if not parsers:
            return None, None

        length = len(parsers)
        return parsers[0], (data, (data, 1, length, parsers))

    def cont_parse(self, match, (data, index, length, parsers)):
        if match:
            return None, match
        if index >= length:
            return None, None
        return parsers[index], (data, (data, index + 1, length, parsers))


class Repeat(Parser):
    def __init__(self, parser, min=0, max=None):
        self._parser = parser
        self._min = min
        self._max = max

    def init_parse(self, data):
        if self._max is not None:
            if self._min > self._max:
                return None, None
            if self._max <= 0:
                return None, (data, [])
        return self._parser, (data, (data, []))

    def cont_parse(self, match, (data, results)):
        if not match:
            if len(results) < self._min:
                return None, None
            return None, (data, results)

        data, result = match
        results.append(result)
        if self._max is None or len(results) <= self._max:
            return self._parser, (data, (data, results))
        return None, (data, results)
