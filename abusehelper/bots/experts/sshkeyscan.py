"""
An expert to do SSH key scanning. Uses Paramiko when around (in
Ubuntu, it's the package python-paramiko), defaults to ssh-keyscan
otherwise.

Maintainer: "Juhani Eronen" <exec@iki.fi>
"""
import socket

from subprocess import Popen, PIPE, STDOUT

import idiokit

from abusehelper.core import events
from abusehelper.bots.experts.combiner import Expert

has_paramiko = False
try:
    from paramiko.transport import Transport as _Transport
    has_paramiko = True

    class Transport(_Transport):
        _CLIENT_ID = "OpenSSH_5.5p1"

        def _parse_kex_init(self, m):
            cookie = m.get_bytes(16)
            kex_algo_list = m.get_list()
            server_key_algo_list = m.get_list()
            self.server_key_algo_list = server_key_algo_list
            m.rewind()
            super(Transport, self)._parse_kex_init(m)

    def handle_key(key):
        key = str(key)
        typ = key[4:11]
        key = key.encode('base64')
        key = key.replace('\n', '')

        return typ, key

except ImportError:
    pass

def _keyscan(hostname, port, keytype):
    p = Popen("ssh-keyscan -vv -p %s -t %s %s" %
              (port, keytype, hostname), shell=True,
              stdout=PIPE, stderr=STDOUT, close_fds=True)
    return p.stdout.read()

class SSHKeyScanExpert(Expert):
    def augment_keys(self, *args, **keys):
        yield (keys.get("resolve", ("ip",)))

    @idiokit.stream
    def ssh_keyscan(self, hostname, port=22, keytypes=["ssh-rsa"]):
        item = yield idiokit.thread(_keyscan, hostname, port, keytypes[0])
        if not item:
            return

        methods = list()
        gather_methods = False
        data = list()
        for line in item.split('\n'):
            # Nothing received
            if not line.startswith('debug'):
                if line.strip():
                    data.append(line)
            elif line.startswith("debug2: kex_parse_kexinit: reserved"):
                gather_methods = True
            elif gather_methods:
                if 'ssh-' in line:
                    methods.extend(line.split()[-1].split(','))
                    gather_methods = False

        if not data:
            idiokit.stop("", "", "")
        banner, key = data
        key = tuple(key.split())
        idiokit.stop(methods, banner, key)

    def ssh_keyscan_paramiko(self, hostname, port=22,
                             keytypes='ssh-rsa', timeout=10):
        for (family, socktype, proto, canonname, sockaddr) in \
                socket.getaddrinfo(hostname, port,
                                   socket.AF_UNSPEC, socket.SOCK_STREAM):
            if socktype == socket.SOCK_STREAM:
                af = family
                addr = sockaddr
                break
            else:
                af, _, _, _, addr = \
                    socket.getaddrinfo(hostname, port,
                                       socket.AF_UNSPEC, socket.SOCK_STREAM)

        sock = socket.socket(af, socket.SOCK_STREAM)
        if timeout is not None:
            try:
                sock.settimeout(timeout)
            except:
                pass
        try:
            sock.connect(addr)
        except socket.error:
            return "", "", ""
        t = Transport(sock)
        o = t.get_security_options()
        o._set_key_types(keytypes)
        t.start_client()
        server_keytypes = t.server_key_algo_list
        typ, key = handle_key(t.get_remote_server_key())
        banner = "# %s %s" % (hostname, t.remote_version)
        key = hostname, typ, key
        t.close()
        return server_keytypes, banner, key

    @idiokit.stream
    def augment(self, key):
        while True:
            eid, event = yield idiokit.next()

            got_keytypes = set()
            q_keytypes = 'ssh-rsa'

            for host in event.values(key):
                while True:
                    port = 22
                    if event.contains('port'):
                        try:
                            port = int(event.value('port'))
                        except ValueError:
                            pass

                    if has_paramiko:
                        kt, banner, sshkey = \
                            self.ssh_keyscan_paramiko(host, port=port,
                                                      keytypes=[q_keytypes])
                    else:
                        kt, banner, sshkey = \
                            yield self.ssh_keyscan(host, port=port,
                                                   keytypes=[q_keytypes])

                    if not sshkey:
                        break

                    new = events.Event()
                    new.add('%s key' % (sshkey[1]), sshkey[2])
                    new.add('ssh banner', banner)
                    yield idiokit.send(eid, new)

                    got_keytypes.add(sshkey[1])
                    kt = set(kt)
                    if got_keytypes != kt:
                        q_keytypes = list(kt - got_keytypes)[0]
                    else:
                        break


if __name__ == "__main__":
    SSHKeyScanExpert.from_command_line().execute()
