from struct import unpack
from socket import inet_aton

FORMAT = "!I"
masks = tuple(((32-i, ((1<<32)-1) ^ ((1<<i)-1)) for i in range(33)))

class Matcher(object):
    def __init__(self):
        self.cidrs = dict()
    
    def set(self, cidr, value):
        ip, mask = cidr.split("/", 1)

        mask = int(mask)

        ip = inet_aton(ip)
        ip, = unpack(FORMAT, ip)
        ip &= masks[32-mask][1]

        key = ip, mask
        self.cidrs[key] = value

    def get(self, ip):
        ip_num = inet_aton(ip)
        ip_num, = unpack(FORMAT, ip_num)
        cidrs = self.cidrs

        for bits, mask in masks:
            key = ip_num & mask, bits
            if key in cidrs:
                return cidrs[key]

        raise KeyError(ip)

if __name__ == '__main__':
    import sys

    m = Matcher()
    networks = {'10.40.47.0/27': 'a', '10.40.0.0/16': 'b', 
                '10.44.0.0/16': 'c', '192.168.47.0/27': 'd'}
    for key, val in networks.iteritems():
        m.set(key, val)

    ipaddr = [x for x in sys.stdin.readlines()]
    for ip in ipaddr:
        try:
            m.get(ip)
        except KeyError:
            pass
