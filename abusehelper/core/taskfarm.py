import idiokit


class Counter(object):
    def __init__(self):
        self.keys = dict()

    def get(self, key):
        return self.keys.get(key, ())

    def contains(self, key, value=None):
        self.inc(key, value)
        return not self.dec(key, value)

    def inc(self, key, value=None):
        if key not in self.keys:
            self.keys[key] = dict()
        if value not in self.keys[key]:
            self.keys[key][value] = 1
            return True
        self.keys[key][value] += 1
        return False

    def dec(self, key, value=None):
        if key not in self.keys:
            return True
        if value not in self.keys[key]:
            return True
        self.keys[key][value] -= 1
        if self.keys[key][value] <= 0:
            del self.keys[key][value]
            if not self.keys[key]:
                del self.keys[key]
            return True
        return False

    def __nonzero__(self):
        return not not self.keys

    def __iter__(self):
        for key, values in self.keys.iteritems():
            yield key, values


class TaskStopped(Exception):
    pass


class TaskFarm(object):
    def __init__(self, task, signal=TaskStopped(), grace_period=1.0):
        self.task = task
        self.signal = signal
        self.grace_period = grace_period

        self.tasks = dict()
        self.counter = Counter()

    def _key(self, *args, **keys):
        return tuple(args), frozenset(keys.items())

    @idiokit.stream
    def _cleanup(self, key):
        try:
            yield idiokit.consume()
        finally:
            if self.counter.dec(key):
                yield idiokit.sleep(self.grace_period)

                if not self.counter.contains(key) and key in self.tasks:
                    task = self.tasks.pop(key)
                    task.throw(self.signal)

    def inc(self, *args, **keys):
        key = self._key(*args, **keys)

        if self.counter.inc(key) and key not in self.tasks:
            self.tasks[key] = self.task(*args, **keys)
        task = self.tasks[key]

        fork = task.fork()
        idiokit.pipe(self._cleanup(key), fork)
        return fork

    def get(self, *args, **keys):
        key = self._key(*args, **keys)
        if key not in self.tasks:
            return None
        return self.tasks[key]
