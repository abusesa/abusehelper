#!/usr/bin/python

import sys

import idiokit
from abusehelper.core.utils import fetch_url, FetchUrlFailed


def main():
    if len(sys.argv) < 3:
        print "{0} <host> <port> [ca-bundle]".format(sys.argv[0])
        sys.exit(1)

    host = sys.argv[1]
    port = sys.argv[2]
    ca_bundle = None
    if len(sys.argv) == 4:
        ca_bundle = sys.argv[3]

    url = "http://{0}:{1}/".format(host, port)

    try:
        if ca_bundle:
            foo = idiokit.main_loop(fetch_url(url, verify=ca_bundle))
        else:
            foo = idiokit.main_loop(fetch_url(url))
    except FetchUrlFailed:
        print "VERIFY SUCCESS"
        sys.exit(0)

    print "VERIFY FAILURE"
    sys.exit(0)


if __name__ == '__main__':
    main()
