#!/usr/bin/python

import sys
import idiokit
from abusehelper.core.utils import fetch_url, FetchUrlFailed
from idiokit.ssl import SSLCertificateError


def main(host, port, ca_bundle=True):
    url = "https://{0}:{1}/".format(host, port)

    try:
        idiokit.main_loop(fetch_url(url, verify=ca_bundle))
    except FetchUrlFailed:
        print "VERIFY FAILURE"
    except SSLCertificateError:
        print "VERIFY FAILURE"
    else:
        print "VERIFY SUCCESS"

    sys.exit(0)


if __name__ == '__main__':
    args = tuple(sys.argv[1:])
    try:
        main(*args)
    except TypeError:
        print "{0} <host> <port> [ca-bundle]".format(sys.argv[0])
