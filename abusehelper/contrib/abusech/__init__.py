import socket


def is_ip(string):
    for addr_type in (socket.AF_INET, socket.AF_INET6):
        try:
            socket.inet_pton(addr_type, string)
        except (ValueError, socket.error):
            pass
        else:
            return True
    return False
