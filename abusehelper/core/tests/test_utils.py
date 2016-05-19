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
MIIDEjCCAfqgAwIBAgIUOxgJbLT0GWM57OLAqhV6ESrSCJwwDQYJKoZIhvcNAQEL
BQAwDzENMAsGA1UEAxMEdGVzdDAeFw0xNjA1MTMxOTM2MDBaFw0yMTA1MTIxOTM2
MDBaMA8xDTALBgNVBAMTBHRlc3QwggEiMA0GCSqGSIb3DQEBAQUAA4IBDwAwggEK
AoIBAQDwFk5X3fTPVFpVC5REqrzpjict5o+1JRYS1hBLGgGtO3OpkVGtu/qZ4YoK
SyM3Rcob+XdUMWEBM64j0gE9N10H3eiZS2solFdqhTuXowA50tQFo4QLQU8CXzuN
i90ixd8tOQJe+pBKqb4Oe3SMuvknkqa/wDsKlZU+z4hvhPt8H7hyA4uVKUeWTAAr
JniObTWtm+jzr79TWdFz9tZmjk18C2qSsDCBerEvmU/4F9mJWADzULMx+OK/f9wa
w9fTJU5MYtAsqkmyXbANKr4zQNVRglR8coW3YbJGTOGjH1h1SvUe3pz3/KnLWo3M
MVZI/ETBPKYyC6CcZG9iffbS/trtAgMBAAGjZjBkMA4GA1UdDwEB/wQEAwIBBjAS
BgNVHRMBAf8ECDAGAQH/AgECMB0GA1UdDgQWBBQG+4QvRPAT/G+wLJ85j6MI/mQv
7jAfBgNVHSMEGDAWgBQG+4QvRPAT/G+wLJ85j6MI/mQv7jANBgkqhkiG9w0BAQsF
AAOCAQEAUH1jaBJomriJq12PkaicLEGXf/AzEIRWh/DmTkOlCMwXMoJ3hb3NdaP7
4gyIvwRbv1jnu1GY1LiNVYT4bSxArCQfPhbkqj2ylA/k/3N+ait6eByJBrUBXtfq
4Tkx4ljZZsYe3/DhKjBHkzi/JzNdATGG8rhtQGuTMFMoiqXYN328BnQ9gzlfUPPA
o90Hv7hCokGg9goR6U3kmmqOyIZwO3NvuEUv4mkIy6a2XUQbNtL5kFnwlS0FUdud
9gjbb4F5UzVMOzN+scH+M1swemdnJYSZp/hNvo4j514obsyOACwqaKbLf27hNKgb
DWPHfIjL4JzZcVJAO1o+SgM7K6EEzA==
-----END CERTIFICATE-----
"""


# A combined certfile/keyfile pair signed with the above CA:
#   echo '{"CN": "localhost", "key":{"algo":"rsa","size":2048}}' | cfssl gencert -ca ca.crt -ca-key ca.key -
cert_data = """
-----BEGIN CERTIFICATE-----
MIIDMDCCAhigAwIBAgIUVVDoL/T47PuvwXLENJ1vJETxwlcwDQYJKoZIhvcNAQEL
BQAwDzENMAsGA1UEAxMEdGVzdDAeFw0xNjA1MTMxOTQxMDBaFw0xNzA1MTMxOTQx
MDBaMBQxEjAQBgNVBAMTCWxvY2FsaG9zdDCCASIwDQYJKoZIhvcNAQEBBQADggEP
ADCCAQoCggEBAKqqySYxVh3T4vS3T+Y53zqus2csPylx7C2b2WVebGUoHO5yPuql
vdBLbR4cY9pzjnCVLMgefqJLgQzAxzUAH8ie+3tCBjUdxTI71dr2SsbGmw6yvfPf
9AJ1Rdk2Qw5wG8nLnxy8ib38dAMibR4heTy6hzLa1PPxnO7FdCe2jUIE6B6IjBHA
/IsNHxjquJdwqPPzSq/IeHshFYiJsMLoPUPJDO0WH6Nz6dgyY4WJx5rhr4pUo+jQ
pR1e8tYaHzxGGfa9g+hqayqhysIVhdTmQ/DKghHvS7+e9mjzrqOdGE5K71c2WVI3
4AQXi8HukmET30uuXWG1lSyUvYA8WV8eDUkCAwEAAaN/MH0wDgYDVR0PAQH/BAQD
AgWgMB0GA1UdJQQWMBQGCCsGAQUFBwMBBggrBgEFBQcDAjAMBgNVHRMBAf8EAjAA
MB0GA1UdDgQWBBRd9bUDS3syjRN8CGsKPS9QwCXTsDAfBgNVHSMEGDAWgBQG+4Qv
RPAT/G+wLJ85j6MI/mQv7jANBgkqhkiG9w0BAQsFAAOCAQEAfmaR1K1awtsTVHCX
pxiIaLDZo2+1EBnpb0WsdCLnqWOmkrkg10svA9P2xXA+kGXLDVJ+Zky3oDal7TpK
LhuIjbwPkAoKeO4AKBC35LolN6vhR49Jn+UtM3hiLN3v+QWfBob60vAvinST7o+g
0I0Jm81NM/wb4h3W+Os9YXiub7MbiGD0gad5fwQfmfsPmyB1eGLBNPm05qR0iMtA
B9yYlv3l1BzlyiABgFK1POXZnC0XAWxaTnfHgWE0MZTPUSzMhVd2yqNKFBL5RyCT
EKt69V5fg1Wbj8nOx7Rkowbdg0HhQImaYutW9owza9sNzXUcYZEWj1e6lp9n6wPq
KYhtiQ==
-----END CERTIFICATE-----
-----BEGIN RSA PRIVATE KEY-----
MIIEowIBAAKCAQEAqqrJJjFWHdPi9LdP5jnfOq6zZyw/KXHsLZvZZV5sZSgc7nI+
6qW90EttHhxj2nOOcJUsyB5+okuBDMDHNQAfyJ77e0IGNR3FMjvV2vZKxsabDrK9
89/0AnVF2TZDDnAbycufHLyJvfx0AyJtHiF5PLqHMtrU8/Gc7sV0J7aNQgToHoiM
EcD8iw0fGOq4l3Co8/NKr8h4eyEViImwwug9Q8kM7RYfo3Pp2DJjhYnHmuGvilSj
6NClHV7y1hofPEYZ9r2D6GprKqHKwhWF1OZD8MqCEe9Lv572aPOuo50YTkrvVzZZ
UjfgBBeLwe6SYRPfS65dYbWVLJS9gDxZXx4NSQIDAQABAoIBAD+2dlVtwaps+aNF
8+wM2ss7gPoZSJMeVn9IWUZAk9LHwNU7jUVoDo5+OgQtsRFSZnCdIBStXbUU3t51
8WhV3Ye14khHg628qWtxbwrJO20to6E/FS7AAoYQZb0LRslTDOyuuX2u3PUyE9U/
uuCuumXzdJmFnE5deqqgyBYzTlTAh//HYs7EHR6xrQlk3NdVIcKaGo2/ujOnCAyV
eXuJJNSenihy6Ff77cYi+bQ+CbIOE08jK2c4kYogEgybLH+7L4UsHfih+AwyWJeA
so6y/aNaa9s7R0K/yvz/hJdOVWpPoec/yq7OIZMIWzVswC/mfvb9fKEtLvbklK9r
pxJU2AECgYEAyQJkVFWRueAtD1Wef3a4RC0sn1mWv3ZCbsrobV7F/80EtWKilf4o
mL+WMpnbTXznTGqRNq0SQZ5uqSsuDBRHMHk4LdxCs1QvKTViBnbdfJou6h7HPEWd
D3QRB/tqDERsdyXMW7sPqADtTLdzKILY/d120NJs39bMlvD6IfAWXYECgYEA2Vtj
qYjXTjCXJ5vEh6+MHyJaocunkC0OvqS1+vPFJyiBeNhvYsZgf1gYRNnwKuLyBecL
1BXjFi8rQhsetOQ8x7XcMS/rhmKs7OjJkyuq8D87URLetMdXtKPJtddmqph/Gljd
V0b/iGF71o4COrZ2KGDhuz2rsQtUDVJWLP3GI8kCgYBPA9Owmxp3uLm9x2hQrrhs
hF2AHlV12eTvbG/FXnXywgLR0n4a/Be1Q8qlBXoBkdHSZinDFnGQvdi+Qy0MroP1
eBEvZeAKYlNPnZ508BDMxEcg3QxwkuTUiEmRm7DqNZN1mrQkcvoKjqK5f3uTNyxZ
Ts8/8xe9PdCanQuWf6wrAQKBgBujCCgNUzsI6J9LqhCKnKl0x8tcxsCJSh+pd84h
4saY2uWPt5H6oVhvzh4rC+OYGafwecuMwOQYOUrdgekEQEowcH/8lNjwgQZajw7c
dY64q4UifhjEY/1++e3aJp64ZyjldbdcOq+PnZxpUBVBEAMQVoNlUwhe5WAQQQ7V
cbUpAoGBAL+SyFosySXgDEj0usLafYFGgGcby0w2HkjruwBGEIur4ObqTS9u9Jma
hOB7BjkV8wPrh+r4gn1r3en+TJR3fI+PB7h2Hk8ZTHYBJVx/lsiyoKuAFbShpuiG
4I3MLHOBy+/eg+k9vUVqVkBeUcmNZ7LdHXq0WRjgmy2awaTG07+H
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
    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        yield sock.close()
        raise exc_type, exc_value, exc_traceback

    @idiokit.stream
    def _server():
        yield sock.listen(1)
        conn, addr = yield sock.accept()

        try:
            with tmpfile(cert_data) as certfile:
                ssl_conn = yield idiokit.ssl.wrap_socket(conn, server_side=True, certfile=certfile)

            try:
                yield ssl_conn.sendall("HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\nok")
            finally:
                yield ssl_conn.close()
        finally:
            yield conn.close()
            yield sock.close()

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

    def test_should_check_hostname_when_verifyin_certificates(self):
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
