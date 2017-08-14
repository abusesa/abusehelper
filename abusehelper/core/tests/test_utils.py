import sys
import socket
import pickle
import urllib2
import unittest
import tempfile
import contextlib

import idiokit
import idiokit.ssl
import idiokit.socket

from .. import utils


# Self-signed CA certificate created using cfssl version 1.2.0 with the
# following command:
#   echo '{"CN": "test", "key":{"algo":"rsa","size":2048}}' | cfssl gencert -initca -
ca_data = """
-----BEGIN CERTIFICATE-----
MIIC8TCCAdmgAwIBAgIUZKwA0MC0N6knKYV7jk9kyImTlLcwDQYJKoZIhvcNAQEL
BQAwDzENMAsGA1UEAxMEdGVzdDAeFw0xNzA1MTgxOTAwMDBaFw0yMjA1MTcxOTAw
MDBaMA8xDTALBgNVBAMTBHRlc3QwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEK
AoIBAQCcMwNEKbY0GjOYOJ8jIHIYD7YEBbKvlIr8xa7AGZ1AQ+bmYScSv6Hqwsxh
j3/gZiUjzrsHLnaVAkj6+XoNlJ1V+AiGgyU4A7jAF7EMX3CZOJOrkFb64802k54x
23NTan+wM4rdwMB82+Rj/+wqHNFKjZufOZ0rJbhSHrDMkgDcDUfI9pfjquSMItGI
j/GGDQIcq3MVqNIFq/2Nrk6Sx2DbqROJsfOD+4zdzgynwMiRh3H5oMR7g8c4Ot5g
7ewtWYO3dvcUKR9/gfErtaNa79SMrDm1qGMqVIVDx4aZ2fohnmPoxH6GEagOir50
iLyIv1xgDok6dQFMfp3yD3mZwHGdAgMBAAGjRTBDMA4GA1UdDwEB/wQEAwIBBjAS
BgNVHRMBAf8ECDAGAQH/AgECMB0GA1UdDgQWBBR4ekZIYbhhYTBANFvM4+LASmCy
UzANBgkqhkiG9w0BAQsFAAOCAQEARmG4bg2D36E8SToiF9lQ3vYaCGY63lP6kaVV
qYPKYCe0b11dJHTXjBm40wiBd44NbWcoq3lumA97vPEmrIDble9PlU9qh9Bl8+L8
EvQeRN5JwVobMzytlTExgMLeEu/TYDNFh7891M+MZ7pfIZ7cuLIUR76rtGc0Ypd6
8if3xwVPb+NFB0NwQTSbk2b/HRv5EqHhVNvd2NJug+tb+jyM/gJTwadUkfdj4JlT
oXd0WjiYy4VhBC+c6kGZiwrXCw/Pkw9lIcL2/ep3Rss745fyZVGwrblNIeI+fszb
P+nY029DGRDy2CCojwewUtZdHijAKz86VaCuMjtnIgG3wNcnew==
-----END CERTIFICATE-----
"""


# A combined certfile/keyfile pair signed with the above CA:
#   echo '{"CN": "localhost", "key":{"algo":"rsa","size":2048}}' | cfssl gencert -ca ca.crt -ca-key ca.key -
cert_data = """
-----BEGIN CERTIFICATE-----
MIIDMDCCAhigAwIBAgIUcDSxD40c8Xy5TueUD3ACkhpdDLcwDQYJKoZIhvcNAQEL
BQAwDzENMAsGA1UEAxMEdGVzdDAeFw0xNzA1MTgxOTAxMDBaFw0xODA1MTgxOTAx
MDBaMBQxEjAQBgNVBAMTCWxvY2FsaG9zdDCCASIwDQYJKoZIhvcNAQEBBQADggEP
ADCCAQoCggEBALRD6wlsp4JftPVdofYy6d1b/LNqQHxUlkmi4NgOoZiCFboQiHAK
2uk8cyvDhw3+7NgYDxRPSGdo2J+f/1JJqNzIu3AvkIpOG5/8Qke3zlEKPxUh3qyh
c+jsc+e7HP1GprehDgj8Vz6qv8g84ArSimt6YEjRbABvpiX7b4CuxO3THhFqRP5S
5fiKW3M1qlxA28PsY1/HGNzCIVWquH/ZS+yeBYjQRBo3ymttglm1DVps3Ip5zvCf
Kw2n8iqVtzU7j3an306BpA3FkSiZaInxv+uwW4/9nUzziskTZwO5V5DpOrAUJGkO
TOKbWij//lv+ul/k1ld/xoTPPxaoOGzOlK8CAwEAAaN/MH0wDgYDVR0PAQH/BAQD
AgWgMB0GA1UdJQQWMBQGCCsGAQUFBwMBBggrBgEFBQcDAjAMBgNVHRMBAf8EAjAA
MB0GA1UdDgQWBBQtbCodrp+r6ItvCdAwkyqrXSTztzAfBgNVHSMEGDAWgBR4ekZI
YbhhYTBANFvM4+LASmCyUzANBgkqhkiG9w0BAQsFAAOCAQEAdy+iG42bskp11N8j
9ph5kTq2CnE3k7kvARdJ7jYYGuWUrVdQKauCJxOyGswv4mYn1r5oXcFyhmL0Rh1r
3QhpUTkCBBggMMiR+9Xv3q/DkZFpGwsDR5uDJJRC/MuE+VKlXWV+R5YHwMPmLcje
HIGN2KnLqeoLMGR5Aoc/lm8SA64ykMFfAMiD9BrO0xJOb76ktPT148uq1sFO3E2j
1aAIX4f3zVjhk1oR9kEmN08Xoj/7BBBmtpZ4VsfssdzGQk8HNvUEXtWzigZTofNJ
Cqu2dS26wawGGYzQKlWpcEGCBV1/+XeH4RX6JlFACPzvewHDg5qWAv+/1TkQVO76
nNJTWw==
-----END CERTIFICATE-----
-----BEGIN RSA PRIVATE KEY-----
MIIEpgIBAAKCAQEAtEPrCWyngl+09V2h9jLp3Vv8s2pAfFSWSaLg2A6hmIIVuhCI
cAra6TxzK8OHDf7s2BgPFE9IZ2jYn5//Ukmo3Mi7cC+Qik4bn/xCR7fOUQo/FSHe
rKFz6Oxz57sc/Uamt6EOCPxXPqq/yDzgCtKKa3pgSNFsAG+mJftvgK7E7dMeEWpE
/lLl+IpbczWqXEDbw+xjX8cY3MIhVaq4f9lL7J4FiNBEGjfKa22CWbUNWmzcinnO
8J8rDafyKpW3NTuPdqffToGkDcWRKJloifG/67Bbj/2dTPOKyRNnA7lXkOk6sBQk
aQ5M4ptaKP/+W/66X+TWV3/GhM8/Fqg4bM6UrwIDAQABAoIBAQCfpwNz/lpBGniP
U1UNUrxTg5PEZxcjxlqwbuQKFrNB+fw6JUhhSwvkw9gQ64QifiPPo0c/qpQqme45
OaAMhhZbLCDt1AKEq3bF88nT8NN2bMe/9JZdeETLBxgEJXEgVEF1ottmU+8FHn7q
XhfjHeLgG6tI8slffYK+Yvi3FJJvOi4A2iGe8b92PuYyRRKapwb30quGJxx3nYsd
Tb0VMvdo3NySc0rEOwjahH97lKpj/CYs5/QObGvjtPn5AV70hP+Yhbx2bkZdX2Ra
NpkgpFJ8gq5/c1wlPv9trK62Gsc6NWslrTsIsI5GDMQU10/8/NSbnaLZt4dsqOka
9qvnvKLpAoGBANhfkYMgck8nuzoFQXrn/RowmKiUf2A2SLmhNOsv9DWWrE5KGsgh
fmzI+kgyMQ4GDl8cgCsC9ZXTark+nJ/yg2io0+h9lOXuDS6Ya2WBAcigEO1Vjn+l
ZpWyzMCjW5sCnj4iQ5GUGAmbElUlRXcevR+OReCJ1BM8KUvDXvr/a38LAoGBANVH
dtv2pAkGtEA7Wupz5nUmjmxicrL4gopdDZWDzDWO/j1hfawsAG/CZx2petdc6hCO
Oo8ayM266rCMaJ/VPLR2m8Go5WHlon4NI46yjic77w3Ae9Qoxh6DGKjgzYdTRdnj
B18FlduV2kvPQmHIptLaQXNbMIJmr9TCzqHkjpdtAoGBAJY67K5NlfBtlqo3QfqT
HoHTofrSeAoWRrJUQojVF8spXWNSQnwX/U6M0HHWH4csH0hcYoT6ngcz7lLGLTtE
x4agSdmPcBWhDhf/DfpA8zsYIAiZMcJg1fQ0W8OY6J6c18AuTBnE6FerCrSBl1SY
zBkf0FaRe+ULDWUkNksxkrJ3AoGBALr2HKGSQhWPhO9RmM8xrnI/zFYCrx1ob7au
/7tzf83rfb98+Ne28uMFfbMo4IBt+NludLMB/ckq85S0YPrLyJ1B5CQN1JbO4HSz
O9pZd/e4uERL2cEPxSz2KuXPuxvHydHJDKslkEqfwG74Tu69IFBx9zISXCHTtotC
AjU00DK5AoGBANJ2nwyvSHLueUWc5GCkcjS5MRClmTjhlyzJJ7oze0yuKF4mbZM6
Rf9tGnsvgbfyGLLyPV084u+EMitxLs+tn+5Fuq1am39x5LcD5Hu2FRWIJ23X0z1y
z+FLR64JyQ+BNk0UZfB6P16AavFS/GKF6QaaUO2ITsI8k6gKxGsZiBY6
-----END RSA PRIVATE KEY-----
"""


@contextlib.contextmanager
def tmpfile(data):
    with tempfile.NamedTemporaryFile() as tmp:
        tmp.write(data)
        tmp.flush()
        yield tmp.name


@idiokit.stream
def create_https_server(host):
    sock = idiokit.socket.Socket()
    try:
        yield sock.bind((host, 0))
        _, port = yield sock.getsockname()
        yield sock.listen(1)
    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        yield sock.close()
        raise exc_type, exc_value, exc_traceback

    @idiokit.stream
    def _server():
        try:
            conn, addr = yield sock.accept()
        finally:
            yield sock.close()

        try:
            with tmpfile(cert_data) as certfile:
                ssl_conn = yield idiokit.ssl.wrap_socket(conn, server_side=True, certfile=certfile)

            try:
                yield ssl_conn.sendall("HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\nok")
            finally:
                yield ssl_conn.close()
        finally:
            yield conn.close()

    idiokit.stop(_server(), "https://{0}:{1}/".format(host, port))


class TestFetchUrl(unittest.TestCase):
    def test_should_raise_TypeError_when_passing_in_an_opener(self):
        sock = socket.socket()
        try:
            sock.bind(("localhost", 0))
            sock.listen(1)
            _, port = sock.getsockname()

            opener = urllib2.build_opener()
            fetch = utils.fetch_url("http://localhost:{0}".format(port), opener=opener)
            self.assertRaises(TypeError, idiokit.main_loop, fetch)
        finally:
            sock.close()

    def test_should_verify_certificates_by_default(self):
        @idiokit.stream
        def test():
            server, url = yield create_https_server("localhost")
            try:
                yield idiokit.pipe(server, utils.fetch_url(url))
            except utils.FetchUrlFailed:
                return
            self.fail("fetch_url should fail due to a certificate verification error")
        idiokit.main_loop(test())

    def test_should_verify_certificates_when_verify_is_True(self):
        @idiokit.stream
        def test():
            server, url = yield create_https_server("localhost")
            try:
                yield idiokit.pipe(server, utils.fetch_url(url, verify=True))
            except utils.FetchUrlFailed:
                return
            self.fail("fetch_url should fail due to a certificate verification error")
        idiokit.main_loop(test())

    def test_should_allow_passing_custom_ca_certs_for_verification(self):
        @idiokit.stream
        def test():
            server, url = yield create_https_server("localhost")

            with tmpfile(ca_data) as ca_certs:
                _, fileobj = yield idiokit.pipe(server, utils.fetch_url(url, verify=ca_certs))
            self.assertEqual(fileobj.read(), "ok")
        idiokit.main_loop(test())

    def test_should_allow_passing_Request_objects_as_url_parameter(self):
        @idiokit.stream
        def test():
            server, url = yield create_https_server("localhost")
            request = urllib2.Request(url)

            with tmpfile(ca_data) as ca_certs:
                _, fileobj = yield idiokit.pipe(server, utils.fetch_url(request, verify=ca_certs))
            self.assertEqual(fileobj.read(), "ok")
        idiokit.main_loop(test())

    def test_should_check_hostname_when_verifying_certificates(self):
        @idiokit.stream
        def test():
            server, url = yield create_https_server("127.0.0.1")
            with tmpfile(ca_data) as ca_certs:
                try:
                    yield idiokit.pipe(server, utils.fetch_url(url, verify=ca_certs))
                except idiokit.ssl.SSLCertificateError:
                    return
            self.fail("fetch_url should fail due to a wrong hostname")
        idiokit.main_loop(test())

    def test_should_allow_disabling_certificate_verification(self):
        @idiokit.stream
        def test():
            server, url = yield create_https_server("localhost")
            _, fileobj = yield idiokit.pipe(server, utils.fetch_url(url, verify=False))
            self.assertEqual(fileobj.read(), "ok")
        idiokit.main_loop(test())


class TestCompressedCollection(unittest.TestCase):
    def test_collection_can_be_pickled_and_unpickled(self):
        original = utils.CompressedCollection()
        original.append("ab")
        original.append("cd")

        unpickled = pickle.loads(pickle.dumps(original))
        self.assertEqual(["ab", "cd"], list(unpickled))

    def test_objects_can_be_appended_to_an_unpickled_collection(self):
        original = utils.CompressedCollection()
        original.append("ab")

        unpickled = pickle.loads(pickle.dumps(original))
        self.assertEqual(["ab"], list(unpickled))

        unpickled.append("cd")
        self.assertEqual(["ab", "cd"], list(unpickled))

    def test_objects_can_be_appended_a_collection_after_pickling(self):
        original = utils.CompressedCollection()
        original.append("ab")

        pickle.dumps(original)

        original.append("cd")
        self.assertEqual(["ab", "cd"], list(original))
