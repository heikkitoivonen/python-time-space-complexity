"""Tests for docs/stdlib/socketserver.md.

The page prices the module a request at a time: accepting and dispatching is
a constant number of system calls, and what varies is where the handler runs.
A plain server runs it in the serving thread, `ThreadingMixIn` scans the t
handler threads it tracks on every request, and `ForkingMixIn` makes one
`waitpid()` per tracked child on every loop wakeup. Those claims are settled
by observation - a thread subclass counting `is_alive()`, a patched
`os.waitpid`, a recording selector, a socket subclass counting send and
receive calls -
and servers are exercised over loopback with a client connected before
`handle_request()`, so most tests need no serving thread.

Measurement scope:

* Construction: `BaseServer()` makes no socket; `TCPServer()` is listening
  with a nonzero port read back into `server_address`, and with
  `bind_and_activate=False` is unbound and not listening; `UDPServer()` is
  bound and not listening. `fileno()` is the socket's descriptor. The class
  attribute defaults the page quotes are asserted by value.
* A stream server leaves the request to the handler: a 100,000-byte request
  reaches `rfile.read()` whole.
* One request at a time: with the first handler blocked, a second connected
  client's handler has not started after 0.5 s under `TCPServer`, and starts
  within 10 s under `ThreadingTCPServer`.
* `serve_forever()`: a recording selector sees every `select()` called with
  `poll_interval`, `service_actions()` runs after every wakeup but the one
  that sees the shutdown, and a
  `timeout` of 0.01 s on the server never reaches `handle_timeout()`.
  `shutdown()` called from a handler of a single-threaded server has not
  returned 0.5 s after the handler entered it (in a subprocess, which then
  exits). A timing test finds `shutdown()` 0.1 s after the loop's first
  `select()` with a 2 s `poll_interval` taking over 0.5 s, and under 0.5 s
  with a 0.02 s one.
* `handle_request()`: with no client, `handle_timeout()` runs once for a
  server `timeout`, and for a socket timeout smaller than the server's; a
  refused request builds no handler and closes the connection; a handler
  that raises reaches `handle_error()`, which prints the traceback, and the
  next request is served; `finish()` runs after `handle()` raises.
* `ThreadingMixIn`: with 10 and then 200 handler threads blocked, the next
  `process_request()` calls `is_alive()` exactly 10 and 200 times and tracks
  11 and 201 threads; with `daemon_threads` it calls it 0 times and tracks
  none. `server_close()` has not returned 0.2 s after it starts while a
  handler is blocked, and returns at once with `block_on_close` false or
  `daemon_threads` true. A raising handler reaches `handle_error()` and the
  request is shut down.
* `ForkingMixIn` with `os.waitpid` patched: `collect_children()`,
  `service_actions()` and `handle_timeout()` each call it once per tracked
  pid, at 10 and 1,000 pids; at `max_children` one blocking `waitpid(-1, 0)`
  comes first; `server_close()` waits with flags 0, reaping every child, or
  with `WNOHANG` when `block_on_close` is false, leaving running ones
  tracked. A real fork is exercised by the page's
  `ForkingTCPServer` example, which runs in a subprocess.
* `StreamRequestHandler` over loopback TCP, its side a socket subclass that
  counts calls: 1,000 one-byte writes are 1,000 `sendall()` calls and all
  1,000 bytes reach the peer before the handler returns; with `wbufsize` set
  they are at most two `send()` calls and nothing arrives before `finish()`.
  1,000 short lines, sent before the handler starts, are read in at most 10
  `recv_into()` calls. `readline()` returns a whole 1,000,000-byte line,
  and `readline(64)` 64 bytes. `timeout` and `disable_nagle_algorithm` reach
  the connection in `setup()`.
* Datagrams: 10,000 bytes arrive as 8,192 under the default
  `max_packet_size` and whole at 20,000; receiving a 10-byte datagram with
  `max_packet_size` at 1,000,000 peaks over 900 KB, so the receive buffer is
  the limit, not the datagram; two writes come back as one
  datagram, sent only after `handle()` returns; `setup()` succeeds over a
  socket object that has only `sendto()`, and handling a 10,000,000-byte
  datagram with an empty `handle()` peaks under 100 KB, so neither the
  `BytesIO` nor `setup()` copies it.
* The predefined servers are asserted to combine the mix-in and the server
  class; `ForkingUnixStreamServer` and `ForkingUnixDatagramServer` to exist
  from 3.12 and not before; `allow_reuse_port` to exist from 3.11 and to set
  `SO_REUSEPORT`; a `UnixStreamServer`'s socket file to survive
  `server_close()`.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* Kernel and network costs: each system call is priced O(1) by the page's
  cost model, so `accept()`, `fork()` and thread start-up are not timed.
  That `listen()` is passed `request_queue_size` is read from
  Lib/socketserver.py; the kernel does not report the backlog back.
* `handle_error()`'s O(f) is `traceback.print_exc()`'s, read from source;
  only that the traceback is printed is observed.
* `ForkingMixIn` and the `Forking*` servers exist only where `os.fork` does,
  and the `Unix*` servers only where `AF_UNIX` does; their tests skip
  elsewhere, and no run this project performs is on such a platform. That
  Windows fails an oversized datagram's receive rather than truncating it,
  so the request is dropped, is read from the Winsock `WSAEMSGSIZE`
  contract and the `OSError` guard in `_handle_request_noblock()`; the
  truncation test skips there.
* The audit's API inventory lists `max_children`, `block_on_close` and
  `daemon_threads` under `ThreadingMixIn`, following the official docs'
  shared directive for both mix-ins; `max_children` exists only on
  `ForkingMixIn`, and the page prices each attribute on the class that has
  it. `BaseServer.fileno()`, `get_request()` and `server_bind()` are
  documented on `BaseServer` but defined on `TCPServer`, so the audit lists
  them as unresolved; the page keeps the documented names.
* Handler cost, request size on a stream, and the number of simultaneous
  clients beyond the counts above are not varied.
"""

from __future__ import annotations

import contextlib
import io
import os
import pathlib
import re
import socket
import socketserver
import subprocess
import sys
import textwrap
import threading
import time
import tracemalloc
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "socketserver.md"
EXPECTED_BLOCKS = 9
LOOPBACK = ("127.0.0.1", 0)

HAS_FORK = hasattr(os, "fork")
HAS_UNIX = hasattr(socket, "AF_UNIX")


class FakeRequest:
    """Stands in for an accepted connection, recording what the server does to it."""

    def __init__(self) -> None:
        self.events: list[str] = []

    def shutdown(self, how: int) -> None:
        self.events.append("shutdown")

    def close(self) -> None:
        self.events.append("close")


class CountingSocket(socket.socket):
    """A socket that counts the send and receive calls made on it."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.calls: dict[str, int] = {"sendall": 0, "send": 0, "recv_into": 0}

    def sendall(self, data: Any, *args: Any) -> None:
        self.calls["sendall"] += 1
        super().sendall(data, *args)

    def send(self, data: Any, *args: Any) -> int:
        self.calls["send"] += 1
        return super().send(data, *args)

    def recv_into(self, buffer: Any, *args: Any) -> int:  # type: ignore[override]
        self.calls["recv_into"] += 1
        return super().recv_into(buffer, *args)


@contextlib.contextmanager
def counting_pair() -> Iterator[tuple[CountingSocket, socket.socket]]:
    """A connected loopback TCP pair: a counting server side and a plain peer.

    TCP rather than `socketpair()`: an AF_UNIX stream charges each one-byte
    write a whole buffer entry, so a thousand unread writes would block."""
    with socket.create_server(LOOPBACK) as listener:
        right = socket.create_connection(listener.getsockname())
        left, _ = listener.accept()
    counted = CountingSocket(left.family, left.type, left.proto, left.detach())
    try:
        yield counted, right
    finally:
        counted.close()
        right.close()


def connect(server: socketserver.TCPServer) -> socket.socket:
    """A client connected to a loopback server."""
    host, port = server.socket.getsockname()
    return socket.create_connection((host, port))


def run_handler(handler: type[socketserver.BaseRequestHandler], request: Any) -> None:
    """Handle one request the way `finish_request()` does, with no server behind it."""
    handler(request, ("peer", 0), None)  # type: ignore[arg-type]


def wait_for(predicate: Callable[[], bool], limit: float = 5.0) -> bool:
    deadline = time.monotonic() + limit
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


class TestConstruction:
    """Server classes | O(1): make, bind and listen; `BaseServer` makes nothing."""

    def test_base_server_makes_no_socket(self) -> None:
        server = socketserver.BaseServer(LOOPBACK, socketserver.BaseRequestHandler)

        assert not hasattr(server, "socket")
        assert server.server_address == LOOPBACK

    def test_tcp_server_binds_and_listens(self) -> None:
        with socketserver.TCPServer(LOOPBACK, socketserver.BaseRequestHandler) as server:
            listening = server.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN)

            assert listening == 1
            assert server.server_address[1] != 0
            assert server.server_address == server.socket.getsockname()
            assert server.fileno() == server.socket.fileno()

    def test_without_bind_and_activate_only_the_socket_exists(self) -> None:
        server = socketserver.TCPServer(
            LOOPBACK, socketserver.BaseRequestHandler, bind_and_activate=False
        )
        try:
            assert server.socket.getsockname()[1] == 0
            assert server.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN) == 0
        finally:
            server.server_close()

    def test_udp_server_binds_without_listening(self) -> None:
        with socketserver.UDPServer(LOOPBACK, socketserver.BaseRequestHandler) as server:
            assert server.socket.type == socket.SOCK_DGRAM
            assert server.server_address[1] != 0
            assert server.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ACCEPTCONN) == 0

    def test_class_attribute_defaults(self) -> None:
        assert socketserver.TCPServer.request_queue_size == 5
        assert socketserver.TCPServer.address_family == socket.AF_INET
        assert socketserver.TCPServer.socket_type == socket.SOCK_STREAM
        assert socketserver.TCPServer.allow_reuse_address is False
        assert socketserver.BaseServer.timeout is None
        assert socketserver.UDPServer.max_packet_size == 8192
        assert socketserver.ThreadingMixIn.daemon_threads is False
        assert socketserver.ThreadingMixIn.block_on_close is True
        assert socketserver.StreamRequestHandler.rbufsize == -1
        assert socketserver.StreamRequestHandler.wbufsize == 0
        assert socketserver.StreamRequestHandler.timeout is None
        assert socketserver.StreamRequestHandler.disable_nagle_algorithm is False

    @pytest.mark.skipif(not HAS_FORK, reason="ForkingMixIn needs os.fork")
    def test_forking_defaults(self) -> None:
        assert socketserver.ForkingMixIn.max_children == 40
        assert socketserver.ForkingMixIn.timeout == 300
        assert socketserver.ForkingMixIn.block_on_close is True
        assert socketserver.ForkingMixIn.active_children is None


class TestTheHandlerReadsTheRequest:
    """A stream server reads nothing from the connection itself."""

    def test_every_byte_reaches_the_handler(self) -> None:
        received: list[bytes] = []

        class Read(socketserver.StreamRequestHandler):
            def handle(self) -> None:
                received.append(self.rfile.read())

        payload = os.urandom(100_000)
        with socketserver.TCPServer(LOOPBACK, Read) as server:
            client = connect(server)

            def send() -> None:
                client.sendall(payload)
                client.shutdown(socket.SHUT_WR)

            sender = threading.Thread(target=send)
            sender.start()
            server.handle_request()
            sender.join()
            client.close()

        assert received == [payload]


class TestOneRequestAtATime:
    """The plain classes run the handler in the serving thread; `ThreadingMixIn`
    does not, so a blocked handler delays the next client only without it."""

    @staticmethod
    def started_behind_a_blocked_handler(
        server_class: type[socketserver.TCPServer], limit: float
    ) -> int:
        release = threading.Event()
        started: list[int] = []

        class Block(socketserver.BaseRequestHandler):
            def handle(self) -> None:
                started.append(1)
                release.wait(60)

        server = server_class(LOOPBACK, Block)
        loop = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        loop.start()
        clients = []
        try:
            clients.append(connect(server))
            assert wait_for(lambda: len(started) == 1)
            clients.append(connect(server))
            wait_for(lambda: len(started) == 2, limit=limit)
            return len(started)
        finally:
            release.set()
            server.shutdown()
            loop.join()
            server.server_close()
            for client in clients:
                client.close()

    def test_a_plain_server_holds_the_second_client(self) -> None:
        assert self.started_behind_a_blocked_handler(socketserver.TCPServer, limit=0.5) == 1

    def test_a_threading_server_does_not(self) -> None:
        assert self.started_behind_a_blocked_handler(socketserver.ThreadingTCPServer, 10) == 2


class RecordingSelector(socketserver._ServerSelector):  # type: ignore[name-defined]  # noqa: SLF001
    timeouts: list[float | None] = []

    def select(self, timeout: float | None = None) -> Any:
        RecordingSelector.timeouts.append(timeout)
        return super().select(timeout)


class TestServeForever:
    """`serve_forever(poll_interval)` | O(1) per wakeup: it waits at most
    `poll_interval`, calls `service_actions()` after each wakeup but the one
    that sees the shutdown, and ignores `timeout`."""

    def test_it_polls_at_the_interval_and_ignores_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(socketserver, "_ServerSelector", RecordingSelector)
        RecordingSelector.timeouts = []

        class Counting(socketserver.TCPServer):
            timeout = 0.01
            actions = 0
            timeouts = 0

            def service_actions(self) -> None:
                self.actions += 1

            def handle_timeout(self) -> None:
                self.timeouts += 1

        server = Counting(LOOPBACK, socketserver.BaseRequestHandler)
        loop = threading.Thread(target=server.serve_forever, args=(0.02,))
        loop.start()
        time.sleep(0.3)
        server.shutdown()
        loop.join()
        server.server_close()

        selects = len(RecordingSelector.timeouts)
        assert selects >= 3
        assert set(RecordingSelector.timeouts) == {0.02}
        assert server.actions in (selects - 1, selects)
        assert server.timeouts == 0

    def test_shutdown_from_the_serving_thread_never_returns(self, tmp_path: pathlib.Path) -> None:
        script = textwrap.dedent(
            """
            import os, socket, socketserver, sys, threading

            entered = threading.Event()
            returned = threading.Event()

            class Stop(socketserver.BaseRequestHandler):
                def handle(self):
                    entered.set()
                    self.server.shutdown()
                    returned.set()

            server = socketserver.TCPServer(("127.0.0.1", 0), Stop)
            threading.Thread(target=server.serve_forever, daemon=True).start()
            client = socket.create_connection(server.server_address)
            if not entered.wait(30):
                print("never entered", flush=True)
            else:
                print("returned" if returned.wait(0.5) else "blocked", flush=True)
            os._exit(0)
            """
        )
        result = _run_block(script, tmp_path)

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "blocked"

    @staticmethod
    def shutdown_seconds(poll_interval: float) -> float:
        """Seconds `shutdown()` takes 0.1 s after the loop's first `select()`."""
        RecordingSelector.timeouts = []
        server = socketserver.TCPServer(LOOPBACK, socketserver.BaseRequestHandler)
        loop = threading.Thread(target=server.serve_forever, args=(poll_interval,))
        loop.start()
        try:
            assert wait_for(lambda: bool(RecordingSelector.timeouts))
            time.sleep(0.1)
        finally:
            start = time.perf_counter()
            server.shutdown()
            elapsed = time.perf_counter() - start
            loop.join()
            server.server_close()
        return elapsed

    @pytest.mark.timing
    def test_shutdown_waits_for_the_poll_interval(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(socketserver, "_ServerSelector", RecordingSelector)
        long = self.shutdown_seconds(2.0)
        short = self.shutdown_seconds(0.02)

        assert long > 0.5, f"shutdown 0.1 s into a 2 s poll took {long:.3f} s"
        assert short < 0.5, f"shutdown with a 0.02 s poll took {short:.3f} s"


class TestHandleRequest:
    """`handle_request()`: one request, `timeout` honoured, refusals and
    failures handled without stopping the server."""

    @staticmethod
    def timing_out_server(timeout: float | None) -> Any:
        class Quiet(socketserver.TCPServer):
            timed_out = 0

            def handle_timeout(self) -> None:
                self.timed_out += 1

        Quiet.timeout = timeout
        return Quiet(LOOPBACK, socketserver.BaseRequestHandler)

    def test_the_server_timeout_ends_the_wait(self) -> None:
        with self.timing_out_server(0.05) as server:
            server.handle_request()

            assert server.timed_out == 1

    def test_the_smaller_of_the_two_timeouts_wins(self) -> None:
        with self.timing_out_server(30.0) as server:
            server.socket.settimeout(0.05)
            start = time.monotonic()
            server.handle_request()

            assert server.timed_out == 1
            assert time.monotonic() - start < 10

    def test_a_refused_request_builds_no_handler(self) -> None:
        built: list[int] = []

        class Record(socketserver.BaseRequestHandler):
            def setup(self) -> None:
                built.append(1)

        class Refuse(socketserver.TCPServer):
            def verify_request(self, request: Any, client_address: Any) -> bool:
                return False

        with Refuse(LOOPBACK, Record) as server:
            client = connect(server)
            server.handle_request()

            assert built == []
            assert client.recv(1) == b""
            client.close()

    def test_a_failing_handler_is_reported_and_the_server_continues(self) -> None:
        calls: list[str] = []

        class Flaky(socketserver.BaseRequestHandler):
            def handle(self) -> None:
                calls.append("handle")
                if len(calls) == 1:
                    raise ValueError("handler failed")

            def finish(self) -> None:
                calls.append("finish")

        with socketserver.TCPServer(LOOPBACK, Flaky) as server:
            first = connect(server)
            second = connect(server)
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                server.handle_request()
                server.handle_request()
            first.close()
            second.close()

        assert calls == ["handle", "finish", "handle", "finish"]
        assert "ValueError: handler failed" in stderr.getvalue()
        assert "Exception occurred during processing of request" in stderr.getvalue()

    def test_handler_attributes_are_set_before_setup(self) -> None:
        seen: list[tuple[Any, Any, Any]] = []

        class Look(socketserver.BaseRequestHandler):
            def setup(self) -> None:
                seen.append((self.request, self.client_address, self.server))

        request = FakeRequest()
        Look(request, ("peer", 1), "server")  # type: ignore[arg-type]

        assert seen == [(request, ("peer", 1), "server")]

    def test_a_stream_request_is_shut_down_then_closed(self) -> None:
        server = socketserver.TCPServer(
            LOOPBACK, socketserver.BaseRequestHandler, bind_and_activate=False
        )
        request = FakeRequest()
        try:
            server.process_request(request, ("peer", 0))  # type: ignore[arg-type]
        finally:
            server.server_close()

        assert request.events == ["shutdown", "close"]

    def test_a_datagram_request_is_left_alone(self) -> None:
        with socketserver.UDPServer(LOOPBACK, socketserver.BaseRequestHandler) as server:
            server.shutdown_request(object())  # type: ignore[arg-type]
            server.close_request(object())  # type: ignore[arg-type]


class CountingThread(threading.Thread):
    alive_checks = 0

    def is_alive(self) -> bool:
        CountingThread.alive_checks += 1
        return super().is_alive()


class TestThreadingMixIn:
    """`ThreadingMixIn.process_request` | O(t): it drops finished threads from
    the t it tracks before starting one more; `daemon_threads` stops tracking."""

    @pytest.fixture()
    def blocked(self, monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[..., Any]]:
        monkeypatch.setattr(threading, "Thread", CountingThread)
        release = threading.Event()
        servers: list[socketserver.ThreadingTCPServer] = []

        class Block(socketserver.BaseRequestHandler):
            def handle(self) -> None:
                release.wait(60)

        def make(**attributes: Any) -> socketserver.ThreadingTCPServer:
            server = socketserver.ThreadingTCPServer(LOOPBACK, Block, bind_and_activate=False)
            for name, value in attributes.items():
                setattr(server, name, value)
            servers.append(server)
            return server

        yield make
        release.set()
        for server in servers:
            server.block_on_close = True
            server.server_close()

    @pytest.mark.parametrize("threads", [10, 200])
    def test_each_request_checks_every_tracked_thread(
        self, blocked: Callable[..., Any], threads: int
    ) -> None:
        server = blocked()
        for _ in range(threads):
            server.process_request(FakeRequest(), ("peer", 0))

        CountingThread.alive_checks = 0
        server.process_request(FakeRequest(), ("peer", 0))

        assert CountingThread.alive_checks == threads
        assert len(server._threads) == threads + 1  # noqa: SLF001

    def test_daemon_threads_are_not_tracked(self, blocked: Callable[..., Any]) -> None:
        server = blocked(daemon_threads=True)
        for _ in range(50):
            server.process_request(FakeRequest(), ("peer", 0))

        CountingThread.alive_checks = 0
        server.process_request(FakeRequest(), ("peer", 0))

        assert CountingThread.alive_checks == 0
        assert len(server._threads) == 0  # noqa: SLF001

    @staticmethod
    def close_returns_within(server: socketserver.ThreadingTCPServer, seconds: float) -> bool:
        closer = threading.Thread(target=server.server_close)
        closer.start()
        closer.join(seconds)
        return not closer.is_alive()

    def test_server_close_waits_for_a_running_handler(self, blocked: Callable[..., Any]) -> None:
        server = blocked()
        server.process_request(FakeRequest(), ("peer", 0))

        assert not self.close_returns_within(server, 0.2)

    @pytest.mark.parametrize(
        "attributes", [{"block_on_close": False}, {"daemon_threads": True}], ids=str
    )
    def test_server_close_can_skip_the_wait(
        self, blocked: Callable[..., Any], attributes: dict[str, bool]
    ) -> None:
        server = blocked(**attributes)
        server.process_request(FakeRequest(), ("peer", 0))

        assert self.close_returns_within(server, 5)

    def test_a_failing_thread_is_reported_and_shut_down(self) -> None:
        class Fail(socketserver.BaseRequestHandler):
            def handle(self) -> None:
                raise ValueError("thread failed")

        server = socketserver.ThreadingTCPServer(LOOPBACK, Fail, bind_and_activate=False)
        request = FakeRequest()
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr):
                server.process_request_thread(request, ("peer", 0))  # type: ignore[arg-type]
        finally:
            server.server_close()

        assert "ValueError: thread failed" in stderr.getvalue()
        assert request.events == ["shutdown", "close"]


@pytest.mark.skipif(not HAS_FORK, reason="ForkingMixIn needs os.fork")
class TestForkingMixIn:
    """`collect_children()` and the hooks calling it are O(c): one `waitpid()`
    per tracked child, with a blocking wait first at `max_children`."""

    @pytest.fixture()
    def server(self, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
        calls: list[tuple[int, int]] = []
        server: Any

        def waitpid(pid: int, flags: int) -> tuple[int, int]:
            calls.append((pid, flags))
            if pid == -1:
                return next(iter(server.active_children or ())), 0
            return (pid, 0) if flags == 0 else (0, 0)  # a blocking wait reaps it

        monkeypatch.setattr(os, "waitpid", waitpid)
        server = socketserver.ForkingTCPServer(  # type: ignore[attr-defined]
            LOOPBACK, socketserver.BaseRequestHandler, bind_and_activate=False
        )
        server.calls = calls
        yield server
        server.active_children = None
        server.socket.close()

    @pytest.mark.parametrize("children", [10, 1_000])
    @pytest.mark.parametrize("hook", ["collect_children", "service_actions", "handle_timeout"])
    def test_one_waitpid_per_child(self, server: Any, hook: str, children: int) -> None:
        server.max_children = children + 1
        server.active_children = set(range(10_000, 10_000 + children))

        getattr(server, hook)()

        assert len(server.calls) == children
        assert all(flags == os.WNOHANG for _, flags in server.calls)

    def test_at_max_children_it_blocks_for_one_first(self, server: Any) -> None:
        server.active_children = set(range(10_000, 10_000 + server.max_children))

        server.collect_children()

        assert server.calls[0] == (-1, 0)
        assert len(server.active_children) == server.max_children - 1
        assert len(server.calls) == server.max_children

    @pytest.mark.parametrize("block", [True, False])
    def test_server_close_waits_unless_told_not_to(self, server: Any, block: bool) -> None:
        flags = 0 if block else os.WNOHANG
        server.block_on_close = block
        server.active_children = {10_000, 10_001}

        server.server_close()

        assert sorted(server.calls) == [(10_000, flags), (10_001, flags)]
        assert server.active_children == (set() if block else {10_000, 10_001})


class TestStreamRequestHandler:
    """`rfile` is buffered and `wfile` is not: each write is one `sendall()`
    unless `wbufsize` is set."""

    @staticmethod
    def arrived_before_finish(peer: socket.socket, expected: int) -> bytes:
        """What reaches the peer, up to `expected` bytes, while the handler still runs."""
        received = b""
        peer.settimeout(0.5)
        with contextlib.suppress(TimeoutError):
            while len(received) < expected:
                chunk = peer.recv(65536)
                if not chunk:
                    break
                received += chunk
        return received

    def test_each_write_is_one_sendall_sent_at_once(self) -> None:
        early: list[bytes] = []
        with counting_pair() as (connection, peer):

            class Write(socketserver.StreamRequestHandler):
                def handle(self) -> None:
                    for _ in range(1000):
                        self.wfile.write(b"x")
                    early.append(TestStreamRequestHandler.arrived_before_finish(peer, 1000))

            run_handler(Write, connection)

            assert connection.calls["sendall"] == 1000
        assert early == [b"x" * 1000]

    def test_wbufsize_batches_writes_until_finish(self) -> None:
        early: list[bytes] = []
        with counting_pair() as (connection, peer):

            class Buffered(socketserver.StreamRequestHandler):
                wbufsize = 65536

                def handle(self) -> None:
                    for _ in range(1000):
                        self.wfile.write(b"x")
                    early.append(TestStreamRequestHandler.arrived_before_finish(peer, 1000))

            run_handler(Buffered, connection)

            assert connection.calls["sendall"] == 0
            assert connection.calls["send"] <= 2
            assert TestStreamRequestHandler.arrived_before_finish(peer, 1000) == b"x" * 1000
        assert early == [b""]

    def test_rfile_reads_in_blocks(self) -> None:
        lines: list[bytes] = []
        with counting_pair() as (connection, peer):
            peer.sendall(b"line\n" * 1000)
            peer.shutdown(socket.SHUT_WR)

            class Read(socketserver.StreamRequestHandler):
                def handle(self) -> None:
                    lines.extend(self.rfile)

            run_handler(Read, connection)

            assert len(lines) == 1000
            assert connection.calls["recv_into"] <= 10

    def test_readline_holds_the_whole_line_unless_limited(self) -> None:
        lengths: list[int] = []
        with counting_pair() as (connection, peer):
            line = b"x" * 1_000_000 + b"\n"
            sender = threading.Thread(target=peer.sendall, args=(line + b"y" * 100,))
            sender.start()

            class Read(socketserver.StreamRequestHandler):
                def handle(self) -> None:
                    lengths.append(len(self.rfile.readline()))
                    lengths.append(len(self.rfile.readline(64)))

            run_handler(Read, connection)
            peer.close()
            sender.join()

        assert lengths == [1_000_001, 64]

    def test_timeout_and_nagle_reach_the_connection(self) -> None:
        seen: list[tuple[Any, int]] = []

        class Tuned(socketserver.StreamRequestHandler):
            timeout = 7.0
            disable_nagle_algorithm = True

            def handle(self) -> None:
                connection = self.connection
                nodelay = connection.getsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY)
                seen.append((connection.gettimeout(), nodelay))

        with socketserver.TCPServer(LOOPBACK, Tuned) as server:
            client = connect(server)
            server.handle_request()
            client.close()

        assert seen[0][0] == 7.0
        assert seen[0][1] != 0


class TestDatagrams:
    """A datagram is cut at `max_packet_size`; `DatagramRequestHandler` holds
    it and the reply in memory and sends the reply once, from `finish()`."""

    @staticmethod
    def received_length(max_packet_size: int, sent: int) -> int:
        lengths: list[int] = []

        class Size(socketserver.DatagramRequestHandler):
            def handle(self) -> None:
                lengths.append(len(self.rfile.read()))

        class Server(socketserver.UDPServer):
            pass

        Server.max_packet_size = max_packet_size
        with Server(LOOPBACK, Size) as server:
            client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client.sendto(b"x" * sent, server.server_address)
            server.handle_request()
            client.close()
        return lengths[0]

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows fails the receive instead")
    def test_a_long_datagram_is_truncated(self) -> None:
        assert self.received_length(8192, 10_000) == 8192

    def test_a_larger_limit_admits_it(self) -> None:
        assert self.received_length(20_000, 10_000) == 10_000

    def test_the_receive_buffer_is_max_packet_size_whatever_arrives(self) -> None:
        class Server(socketserver.UDPServer):
            max_packet_size = 1_000_000

        with Server(LOOPBACK, socketserver.BaseRequestHandler) as server:
            client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client.sendto(b"x" * 10, server.socket.getsockname())
            tracemalloc.start()
            try:
                (data, _), _ = server.get_request()
                peak = tracemalloc.get_traced_memory()[1]
            finally:
                tracemalloc.stop()
            client.close()

        assert data == b"x" * 10
        assert peak > 900_000, f"a 10-byte datagram at a 1 MB limit peaked at {peak} bytes"

    def test_the_reply_is_one_datagram_sent_after_handle(self) -> None:
        before_finish: list[bool] = []

        with socketserver.UDPServer(LOOPBACK, socketserver.DatagramRequestHandler) as server:
            client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client.setblocking(False)

            class Reply(socketserver.DatagramRequestHandler):
                def handle(self) -> None:
                    self.wfile.write(b"one ")
                    self.wfile.write(b"two")
                    try:
                        client.recv(64)
                    except BlockingIOError:
                        before_finish.append(False)
                    else:
                        before_finish.append(True)

            server.RequestHandlerClass = Reply
            client.sendto(b"ping", server.server_address)
            server.handle_request()
            client.settimeout(5)
            reply = client.recv(64)
            client.close()

        assert before_finish == [False]
        assert reply == b"one two"

    def test_setup_makes_no_system_call(self) -> None:
        class OnlySendto:
            def __init__(self) -> None:
                self.sent: list[bytes] = []

            def sendto(self, data: bytes, address: Any) -> None:
                self.sent.append(data)

        sock = OnlySendto()

        class Echo(socketserver.DatagramRequestHandler):
            def handle(self) -> None:
                self.wfile.write(self.rfile.read())

        run_handler(Echo, (b"payload", sock))

        assert sock.sent == [b"payload"]

    def test_setup_does_not_copy_the_datagram(self) -> None:
        class Discard:
            def sendto(self, data: bytes, address: Any) -> None:
                pass

        packet = b"x" * 10_000_000
        tracemalloc.start()
        try:
            run_handler(socketserver.DatagramRequestHandler, (packet, Discard()))
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()

        assert peak < 100_000, f"handling a 10 MB datagram peaked at {peak} bytes"


class TestServerFamilies:
    """The predefined servers combine a mix-in with a server class, and the
    version and platform boundaries the page names."""

    def test_threading_servers(self) -> None:
        for name in ("TCP", "UDP"):
            server = getattr(socketserver, f"Threading{name}Server")
            assert issubclass(server, socketserver.ThreadingMixIn)
            assert issubclass(server, getattr(socketserver, f"{name}Server"))

    @pytest.mark.skipif(not HAS_UNIX, reason="needs AF_UNIX")
    def test_threading_unix_servers(self) -> None:
        for name in ("UnixStream", "UnixDatagram"):
            server = getattr(socketserver, f"Threading{name}Server")
            assert issubclass(server, socketserver.ThreadingMixIn)
            assert issubclass(server, getattr(socketserver, f"{name}Server"))

    @pytest.mark.skipif(not HAS_FORK, reason="needs os.fork")
    def test_forking_servers(self) -> None:
        for name in ("TCP", "UDP"):
            server = getattr(socketserver, f"Forking{name}Server")
            assert issubclass(server, socketserver.ForkingMixIn)  # type: ignore[attr-defined]
            assert issubclass(server, getattr(socketserver, f"{name}Server"))

    @pytest.mark.skipif(not (HAS_FORK and HAS_UNIX), reason="needs os.fork and AF_UNIX")
    def test_forking_unix_servers_arrive_in_312(self) -> None:
        for name in ("UnixStream", "UnixDatagram"):
            present = hasattr(socketserver, f"Forking{name}Server")
            assert present == (sys.version_info >= (3, 12))

    def test_allow_reuse_port_arrives_in_311(self) -> None:
        present = hasattr(socketserver.TCPServer, "allow_reuse_port")
        assert present == (sys.version_info >= (3, 11))

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="added in 3.11")
    @pytest.mark.skipif(not hasattr(socket, "SO_REUSEPORT"), reason="needs SO_REUSEPORT")
    def test_allow_reuse_port_sets_the_option(self) -> None:
        class Reusing(socketserver.TCPServer):
            allow_reuse_port = True

        with Reusing(LOOPBACK, socketserver.BaseRequestHandler) as server:
            assert server.socket.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT) != 0

    @pytest.mark.skipif(not HAS_UNIX, reason="needs AF_UNIX")
    def test_a_unix_socket_file_survives_close(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "server.sock"

        with socketserver.UnixStreamServer(  # type: ignore[attr-defined]
            str(path), socketserver.BaseRequestHandler
        ) as server:
            assert server.server_address == str(path)

        assert path.exists()


def _blocks() -> list[tuple[int, str]]:
    """Every fenced python block on the page, with its 1-based line number."""
    lines = PAGE.read_text(encoding="utf-8").splitlines()
    found: list[tuple[int, str]] = []
    index = 0
    while index < len(lines):
        if re.match(r"^\s*```python\s*$", lines[index]):
            start = index + 1
            end = start
            while not re.match(r"^\s*```\s*$", lines[end]):
                end += 1
            found.append((start + 1, textwrap.dedent("\n".join(lines[start:end]))))
            index = end
        index += 1
    return found


def _run_block(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess, with its own loopback ports, and
    asserts its own result."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if 'reply == b"8192 bytes"' in s)
        mutated = source.replace('reply == b"8192 bytes"', 'reply == b"10000 bytes"', 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
