from __future__ import absolute_import

import os
import sys
import errno
import struct
import cPickle
import idiokit
import subprocess
import contextlib
import socket as native_socket
from idiokit import socket, select
from . import events, rules, taskfarm, bot


class _ConnectionLost(Exception):
    pass


@contextlib.contextmanager
def wrapped_socket_errnos(*errnos):
    try:
        yield
    except (native_socket.error, socket.SocketError) as error:
        socket_errno = error.args[0]
        if socket_errno in errnos:
            raise _ConnectionLost(os.strerror(socket_errno))
        raise


def _recvall_blocking(conn, amount):
    data = []
    while amount > 0:
        with wrapped_socket_errnos(errno.ECONNRESET):
            piece = conn.recv(amount)

        if not piece:
            raise _ConnectionLost("could not recv() all bytes")
        data.append(piece)
        amount -= len(piece)
    return "".join(data)


def send_encoded(conn, obj):
    msg_bytes = cPickle.dumps(obj, cPickle.HIGHEST_PROTOCOL)
    data = struct.pack("!I", len(msg_bytes)) + msg_bytes

    with wrapped_socket_errnos(errno.ECONNRESET, errno.EPIPE):
        conn.sendall(data)


def recv_decoded(sock):
    length_bytes = _recvall_blocking(sock, 4)
    length, = struct.unpack("!I", length_bytes)

    msg_bytes = _recvall_blocking(sock, length)
    return cPickle.loads(msg_bytes)


@idiokit.stream
def _recvall_stream(sock, amount, timeout=None):
    data = []
    while amount > 0:
        with wrapped_socket_errnos(errno.ECONNRESET):
            piece = yield sock.recv(amount, timeout=timeout)

        if not piece:
            raise _ConnectionLost("could not recv() all bytes")
        data.append(piece)
        amount -= len(piece)
    idiokit.stop("".join(data))


@idiokit.stream
def distribute_encode(socks):
    writable = []

    while True:
        to_all, msg = yield idiokit.next()
        msg_bytes = cPickle.dumps(msg, cPickle.HIGHEST_PROTOCOL)
        data = struct.pack("!I", len(msg_bytes)) + msg_bytes

        if to_all:
            for sock in socks:
                yield sock.sendall(data)
            writable = []
        else:
            while not writable:
                _, writable, _ = yield select.select((), socks, ())
                writable = list(writable)
            yield writable.pop().sendall(data)


@idiokit.stream
def collect_decode(socks):
    readable = []

    while True:
        while not readable:
            readable, _, _ = yield select.select(socks, (), ())
            readable = list(readable)

        sock = readable.pop()

        length_bytes = yield _recvall_stream(sock, 4)
        length, = struct.unpack("!I", length_bytes)

        msg_bytes = yield _recvall_stream(sock, length)
        yield idiokit.send(cPickle.loads(msg_bytes))


class RoomGraphBot(bot.ServiceBot):
    concurrency = bot.IntParam("""
        the number of worker processes used for rule matching
        (default: %default)
        """, default=1)

    def __init__(self, *args, **keys):
        bot.ServiceBot.__init__(self, *args, **keys)

        self._rooms = taskfarm.TaskFarm(self._handle_room, grace_period=0.0)
        self._srcs = {}
        self._ready = idiokit.Event()
        self._stats = {}

    def _inc_stats(self, room, seen=0, sent=0):
        seen_count, sent_count = self._stats.get(room, (0, 0))
        self._stats[room] = seen_count + seen, sent_count + sent

    @idiokit.stream
    def _log_stats(self, interval=15.0):
        while True:
            yield idiokit.sleep(interval)

            for room, (seen, sent) in self._stats.iteritems():
                self.log.info(
                    u"Room {0}: seen {1}, sent {2} events".format(room, seen, sent),
                    event=events.Event({
                        "type": "room",
                        "service": self.bot_name,
                        "seen events": unicode(seen),
                        "sent events": unicode(sent),
                        "room": unicode(room)
                    })
                )
            self._stats.clear()

    @idiokit.stream
    def _distribute(self):
        while True:
            src, event, dsts = yield idiokit.next()

            count = 0
            for dst in dsts:
                dst_room = self._rooms.get(dst)
                if dst_room is not None:
                    count += 1
                    yield dst_room.send(event.to_elements())

            if count > 0:
                self._inc_stats(src, sent=1)

    @idiokit.stream
    def _handle_room(self, room_name):
        room = yield self.xmpp.muc.join(room_name, self.bot_name)
        distributor = yield self._ready.fork()
        yield idiokit.pipe(
            room,
            idiokit.map(self._map, room_name),
            distributor.fork(),
            idiokit.Event()
        )

    def _map(self, elements, room_name):
        if room_name not in self._srcs:
            return

        for event in events.Event.from_elements(elements):
            self._inc_stats(room_name, seen=1)
            yield False, ("event", (room_name, event))

    @idiokit.stream
    def session(self, _, src_room, dst_room, rule=None, **keys):
        rule = rules.Anything() if rule is None else rules.rule(rule)
        src_room = yield self.xmpp.muc.get_full_room_jid(src_room)
        dst_room = yield self.xmpp.muc.get_full_room_jid(dst_room)

        distributor = yield self._ready.fork()
        yield distributor.send(True, ("inc_rule", (src_room, rule, dst_room)))
        try:
            self._srcs[src_room] = self._srcs.get(src_room, 0) + 1
            try:
                yield self._rooms.inc(src_room) | self._rooms.inc(dst_room)
            finally:
                self._srcs[src_room] = self._srcs[src_room] - 1
                if self._srcs[src_room] <= 0:
                    del self._srcs[src_room]
        finally:
            distributor.send(True, ("dec_rule", (src_room, rule, dst_room)))

    def _start_worker(self):
        env = dict(os.environ)
        env["ABUSEHELPER_SUBPROCESS"] = ""

        # Find out the full package & module name. Don't refer to the
        # variable __loader__ directly to keep flake8 (version 2.5.0)
        # linter happy.
        fullname = globals()["__loader__"].fullname

        own_conn, other_conn = native_socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            process = subprocess.Popen(
                [sys.executable, "-m", fullname],
                preexec_fn=os.setpgrp,
                stdin=other_conn.fileno(),
                close_fds=True,
                env=env
            )

            try:
                conn = socket.fromfd(own_conn.fileno(), socket.AF_UNIX, socket.SOCK_STREAM)
            except:
                process.terminate()
                process.wait()
                raise
        finally:
            own_conn.close()
            other_conn.close()
        return process, conn

    @idiokit.stream
    def main(self, _):
        processes = []
        connections = []
        try:
            for _ in xrange(self.concurrency):
                process, connection = self._start_worker()
                processes.append(process)
                connections.append(connection)

            if self.concurrency == 1:
                self.log.info(u"Started 1 worker process")
            else:
                self.log.info(u"Started {0} worker processes".format(self.concurrency))

            self._ready.succeed(distribute_encode(connections))
            yield collect_decode(connections) | self._distribute() | self._log_stats()
        finally:
            for connection in connections:
                yield connection.close()

            for process in processes:
                process.terminate()
            for process in processes:
                process.wait()


def roomgraph(conn):
    srcs = {}

    while True:
        type_id, args = recv_decoded(conn)
        if type_id == "event":
            src, event = args
            if src in srcs:
                dsts = set(srcs[src].classify(event))
                if dsts:
                    send_encoded(conn, (src, event, dsts))
        elif type_id == "inc_rule":
            src, rule, dst = args
            if src not in srcs:
                srcs[src] = rules.Classifier()
            srcs[src].inc(rule, dst)
        elif type_id == "dec_rule":
            src, rule, dst = args
            if src in srcs:
                srcs[src].dec(rule, dst)
                if srcs[src].is_empty():
                    del srcs[src]
        else:
            raise RuntimeError("unknown type id {0!r}".format(type_id))


if __name__ == "__main__":
    if "ABUSEHELPER_SUBPROCESS" in os.environ:
        conn = native_socket.fromfd(0, native_socket.AF_UNIX, native_socket.SOCK_STREAM)
        try:
            rfd, wfd = os.pipe()
            os.dup2(rfd, 0)
            os.close(rfd)
            os.close(wfd)

            conn.setblocking(True)
            roomgraph(conn)
        except _ConnectionLost:
            pass
        finally:
            conn.close()
    else:
        RoomGraphBot.from_command_line().execute()
