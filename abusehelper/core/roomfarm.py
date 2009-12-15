from idiokit import threado, callqueue
from abusehelper.core import services

class Counter(object):
    def __init__(self):
        self.keys = dict()

    def get(self, key):
        return set(self.keys.get(key, ()))

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
            yield key, set(values)

class RoomFarm(services.Service):
    def __init__(self, *args, **keys):
        services.Service.__init__(self, *args, **keys)

        self.room_handlers = dict()
        self.room_counter = Counter()
        self.room_keys = dict()

    def _check_room(self, name):
        if self.room_counter.contains(name):
            return
        if name not in self.room_handlers:
            return
        self.room_handlers.pop(name).throw(threado.Finished())

    def rooms(self, key, *names):
        for name in names:
            if self.room_counter.inc(name):
                self.room_handlers[name] = self.handle_room(name)
                services.bind(self, self.room_handlers[name])
        for name in self.room_keys.get(key, ()):
            if self.room_counter.dec(name):
                callqueue.add(self._check_room, name)

        if not names:
            self.room_keys.pop(key, None)
        else:
            self.room_keys[key] = names

        if not names:
            return None
        if len(names) == 1:
            return self.room_handlers[name]
        return tuple(self.room_handlers[name] for name in names)

    @threado.stream_fast
    def handle_room(inner, self, name):
        while True:
            yield inner
            list(inner)
