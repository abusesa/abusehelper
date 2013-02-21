import functools


class ParserError(Exception):
    pass


class Parser(object):
    def parse(self, string):
        data = string, 0, len(string)

        stack = []
        result = None
        current = self.parse_gen(data)

        while True:
            next, result = current.send(result)

            if next is not None:
                stack.append(current)
                current = next.parse_gen(result)
                result = None
            elif stack:
                current = stack.pop()
            else:
                break

        if result is None:
            return None
        obj, (string, start, end) = result
        return obj, string[start:end]

    def parse_gen(self, data):
        yield None, None


class FuncParser(Parser):
    def __init__(self, func, *args, **keys):
        self._func = func
        self._args = args
        self._keys = keys

    def parse_gen(self, data):
        return self._func(data, *self._args, **self._keys)


def parser(func):
    @functools.wraps(func)
    def _parser(*args, **keys):
        return FuncParser(func, *args, **keys)
    return _parser


def parser_singleton(func):
    return parser(func)()


@parser
def txt((string, start, end), text, ignore_case=False):
    if not ignore_case:
        if not string.startswith(text, start, end):
            yield None, None
        yield None, (text, (string, start + len(text), end))

    length = len(text)
    if end - start < length:
        yield None, None

    compared = string[start:start + length]
    if compared.lower() != text.lower():
        yield None, None

    yield None, (compared, (string, start + length, end))


def _seq(data, parsers, pick=None):
    results = []

    for parser in parsers:
        match = yield parser, data
        if not match:
            yield None, None

        result, data = match
        results.append(result)

    if pick is None:
        yield None, (results, data)
    if isinstance(pick, int):
        yield None, (results[pick], data)
    yield None, ([results[x] for x in pick], data)


@parser
def seq(data, *parsers, **keys):
    return _seq(data, parsers, **keys)


@parser
def union(data, *parsers):
    for parser in parsers:
        match = yield parser, data
        if match:
            yield None, match
    yield None, None


@parser
def epsilon(data, value=None):
    yield None, (value, data)


@parser
def maybe(data, parser, default=None):
    match = yield parser, data
    if not match:
        yield None, (default, data)
    yield None, match


@parser
def transform(data, func, parser):
    match = yield parser, data
    if not match:
        yield None, None
    result, data = match
    yield None, (func(result), data)


class ForwardRef(Parser):
    def __init__(self):
        self._parser = None

    def set(self, parser):
        if self._parser is not None:
            raise ParserError("forward reference already set")
        self._parser = parser

    def parse_gen(self, data):
        if self._parser is None:
            raise ParserError("forward reference not set")
        return self._parser.parse_gen(data)


def forward_ref():
    return ForwardRef()


@parser
def step(data, head, *tails):
    match = yield head, data
    if not match:
        yield None, None

    left, data = match
    for pattern, func in tails:
        match = yield pattern, data
        if not match:
            continue
        right, data = match
        yield None, (func(left, right), data)

    yield None, None


def step_default(func=None):
    if func is None:
        return epsilon(), lambda x, y: x
    return epsilon(), lambda x, y: func(x)
