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


_levels = {
    "1": ["bulletproof hosted"],
    "2": ["hacked webserver"],
    "3": ["free hosting service"],
    "4": [],  # "4" denotes an unknown level
    "5": ["hosted on a fastflux botnet"]
}


def resolve_level(value):
    return tuple(_levels.get(value, []))
