import struct
import collections
from hashlib import md5

class Dedup(object):
    unpack = struct.Struct("!Q").unpack

    def __init__(self, size=10**6):
        self.size = size
        self.set = set()
        self.queue = collections.deque()

    def add(self, string):
        hash = self.unpack(md5(string).digest()[:8])[0]
        if hash in self.set:
            return False

        if len(self.queue) >= self.size:
            first = self.queue.popleft()
            self.set.discard(first)
        self.queue.append(hash)
        self.set.add(hash)
        return True

    def __getstate__(self):
        return self.size, self.queue

    def __setstate__(self, (size, queue)):
        self.size = size
        self.queue = queue
        self.set = set(self.queue)
