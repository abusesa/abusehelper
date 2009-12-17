import struct
import collections
from hashlib import md5

unpack = struct.Struct("!Q").unpack

def dedup_key(string):
    return unpack(md5(string).digest()[:8])[0]

class Dedup(object):
    def __init__(self, size=10**6):
        self.size = size
        self.set = set()
        self.queue = collections.deque()

    def __contains__(self, string):
        return dedup_key(string) in self.set

    def add(self, string):
        key = dedup_key(string)
        if key in self.set:
            return False

        if len(self.queue) >= self.size:
            first = self.queue.popleft()
            self.set.discard(first)
        self.queue.append(key)
        self.set.add(key)
        return True

    def __getstate__(self):
        return self.size, self.queue

    def __setstate__(self, (size, queue)):
        self.size = size
        self.queue = queue
        self.set = set(self.queue)
