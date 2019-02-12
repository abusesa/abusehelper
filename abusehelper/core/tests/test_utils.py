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
MIIC7jCCAdagAwIBAgIUambudsroGsuHKzyBpzTOzZiXKDMwDQYJKoZIhvcNAQEL
BQAwDzENMAsGA1UEAxMEdGVzdDAeFw0xOTAyMTIwOTMxMDBaFw0yNDAyMTEwOTMx
MDBaMA8xDTALBgNVBAMTBHRlc3QwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEK
AoIBAQClcgZFdZYi2V422HIyTSNYC9Bzhj7OoRosE06K1NJ6/+vQDSNbP13Tex5p
R4SaIhjrMK+UklNR6aT4/GOxFNJz4USr90YC/BA1QTE8G2rk25z2L1z90OrNxRdj
33wj7XG+c+uX3GpTc/eiBk26kI0+Fsp+mNr/jTis4O7B4/ZGLp66uzMEAy0lt412
oS4OWns6x0UQdwHAoYSStAq7Ee1yTDZt4uKA0wiMg22TqEtG1zjSVlXKiQ1Kleir
TwvVTZIjsD3X7D7DwcoUYz4KNvxQLfMXWCrywLmJwbnNtmidVpKXqGVmgozW0KCB
4y2uOSAqN7mBBAyiZJT9VllBWvTpAgMBAAGjQjBAMA4GA1UdDwEB/wQEAwIBBjAP
BgNVHRMBAf8EBTADAQH/MB0GA1UdDgQWBBS3DJs+uG2CROiZf4QasL9pb2qxVjAN
BgkqhkiG9w0BAQsFAAOCAQEAlrlFPreEhYcV9XQSqjsqR/KGnRX/rwRN8smQVtqS
b7t0z9dVHg0BiVCdHmiSwfk4kE/uw+nJuDCPQ1JK1KWAkPUfaOqXnBmYoZUxQpKc
FqWtctAJf28UbQyXM8WHO3nMe+DFwrsvD6r62KXaR6kETKO3168bS0dseRwHAXUj
K7Bydyv4Sq0X9T9p7cQlnsJbH0RsjJsa07C/oKu9s+pxa29PKfoTuTic6nPHRod6
aZBN2q/7KTRlAVPU5pY8sW8c0SfhqLBi3PnPLTSZlzK3VslYFgSlpbf+eG+EHjpf
J3gzT8KClGMUfi5q99Z4NR7xP6aZ5XWdJnS7oXCb0Ojf0w==
-----END CERTIFICATE-----
"""


# A combined certfile/keyfile pair signed with the above CA:
#   echo '{"CN": "localhost", "key":{"algo":"rsa","size":2048}}' | cfssl gencert -ca ca.crt -ca-key ca.key -
cert_data = """
-----BEGIN CERTIFICATE-----
MIIDMDCCAhigAwIBAgIUBxvJNI5OVGWj9uUhhrdzUmhjrpowDQYJKoZIhvcNAQEL
BQAwDzENMAsGA1UEAxMEdGVzdDAeFw0xOTAyMTIwOTMzMDBaFw0yMDAyMTIwOTMz
MDBaMBQxEjAQBgNVBAMTCWxvY2FsaG9zdDCCASIwDQYJKoZIhvcNAQEBBQADggEP
ADCCAQoCggEBAMMHmuI/DBVdVG3RDxE5A7xk5TYq0Xst1AlOB1jwp/OvbPq3v1XQ
5eQQxUBju1Pm4B1s93V2CVRe/9QfAfOydBbxv1LdE1uYs46srYr1pSi0QxzpL9Xq
UHYCZLlI6OPzQt+YT8l+9MizvdGSAW8qZW4PY0vMwPy1E3XfwKgsOWbVPBeflW+N
VzhShnlgRhTKHqYji3I2Ky5w/DHsaBOvBi9AKV5q27SrdGfgGwJGm464FIXAMhZD
aMP4LVOta/+jfBqmO14RgdixZn7BCvLn2EqD4rf6/eOPkFVn0GgWfN0UGTaGr+zV
HCGDLSqRpPsvrQI+7HU2Q2CnxLakjq1aQxMCAwEAAaN/MH0wDgYDVR0PAQH/BAQD
AgWgMB0GA1UdJQQWMBQGCCsGAQUFBwMBBggrBgEFBQcDAjAMBgNVHRMBAf8EAjAA
MB0GA1UdDgQWBBRSoYl6ylw6Vd6DLTclIsvaP3b7oTAfBgNVHSMEGDAWgBS3DJs+
uG2CROiZf4QasL9pb2qxVjANBgkqhkiG9w0BAQsFAAOCAQEAJ/PP0zhgRLmGHtNB
91Ta0B3dbZYCqcAMteO1w7TIEw8eL7yzz+S/PKCa5EzXCK7RV5jQ8tHGwAF+JRiJ
ZQoi7kwQ43HMMlwTOQg51Svpu994hHOnAvl6xcNOFVLieC3yfyKzB6RJ+GNnpm73
VHp41w441rFUd3+bhYTZh2vteQSNZzzW0kLGz9yCdU4W/C7HvTSQ2E1NjveFph66
KS5iYjprPg58CU38/YLG0bRbhdiwbnkutV5pl+IHoV5VZvh5f64xU4OBeQyDNMKb
dC8yWn1itV0MhJbwZso7ejOhNKHsGTv4ao9m4ny3U+o9+PK5xMtPJ/un8J3/wci0
bvXjzw==
-----END CERTIFICATE-----
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEAwwea4j8MFV1UbdEPETkDvGTlNirRey3UCU4HWPCn869s+re/
VdDl5BDFQGO7U+bgHWz3dXYJVF7/1B8B87J0FvG/Ut0TW5izjqytivWlKLRDHOkv
1epQdgJkuUjo4/NC35hPyX70yLO90ZIBbyplbg9jS8zA/LUTdd/AqCw5ZtU8F5+V
b41XOFKGeWBGFMoepiOLcjYrLnD8MexoE68GL0ApXmrbtKt0Z+AbAkabjrgUhcAy
FkNow/gtU61r/6N8GqY7XhGB2LFmfsEK8ufYSoPit/r944+QVWfQaBZ83RQZNoav
7NUcIYMtKpGk+y+tAj7sdTZDYKfEtqSOrVpDEwIDAQABAoIBAAcHbSOeVhcnB/X1
RO+/+Ex/7mrnXCluW2gCce1YrxTvS6Q1nyW+o6p2mEVb0tKRTZ6B4OFQ4cEys1G3
1GAuHFT/XX/lC9+PP1lzC8YoWE2BQbH3DYxOJ5w5NdwfrpUYnV5lpOqEMtpQ8BRv
iLGy+3jeARwoQwRYmlzzNYRaI697C89Q4CDkMreabY0XkMlsGen1Qqdm5bGWpBsV
eQnvdP3gAJ+37i1W/QvQXFWiT446+6iCBMxo+QcBuPZLsBpbYilN0GD3kFr4v0du
HkvhyMJRR5z1B/gkspFNX9h9HGDaC2x5+3DLUn48rmX/4Kp2htoo1AmkG+oG9GJz
JAmAt9ECgYEA7K21FIXajIyEqlF7h+2z4OkYzHxbxyl4DprVcNhUMeFzHQ2k3caZ
xZ0JAhr/gmpiNlF0Y846tba2Va4IBGJ0jxVYDLmwdpiasZdyqozi6naS9pD5wugu
/YgF/hbTIOB/vQYMC7sRNqETeQbrt2SL2Lqi+XRnM0pLJ7KO7MUpbp0CgYEA0vN8
4WYWHNjEafjzfveE3Q38KAUTSAEIyPyU5Kd3jwLovXFx5fK2Knp8Cin4t4nwpoz8
+nR+5cbxpH0KX846W7afSW+2FuXLdj016WTtO2s9Oz7+9ltVAgDDBlshcy9Bvhxi
X2VF0PTtytNqPtasW3eMiZqyR/+B2jVXefPQcW8CgYAkRN5Z/cUnAqWV4BS5GNEW
50GYnHoIBC/UtR9+QnhsiGr2ic+4+KU55j2qJ+790kWoo0Tdwo22qQA6EwhBe8D2
6ENs98u18N7L1jSJNDvVyEPvKvpLRv9kdMLOVDsYb67Djbis14bkwzxTsJ7QpMTV
eoxdA9yIvJrVw4QpfnFB9QKBgQCKO1XM2bmJw53Jl4Hv5EBjHmPq0ZCV8V+RXLow
r3CP/ScH5MvvE8G9Si/39RLvKmvQp7iqYiY5ack0sV9X8mqZaK0uUQ6wKHrQC0JF
o4Y1Fou0RA6M3sJwopEpnBPqR8A71Ju9yT4btDQSYcFQVhnxggBMt1s2BL9RfvzI
hDVF7wKBgQDquC9TIDU+sb5V6F+sM1+kPY6Bvh4H5l8dgB7VA340WNH8P8nbBhOh
vHCsp79Kr8wvuQ6z7XF78kq3U3Gh9RfDiIDHt7+s7Gki5Vozt09hFwqASBdrl814
kdv7NNEprM/8qI4Yeq4lw+CMzaQnLkamgkGrf6uM64Dh5fWo17rywA==
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
