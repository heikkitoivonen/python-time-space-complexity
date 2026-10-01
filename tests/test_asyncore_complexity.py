"""Tests for docs/stdlib/asyncore.md.

The page prices the module by the pass: every pass of `loop()` asks every
channel whether it wants to read or write and builds its `select()` or `poll()`
request from scratch, and `dispatcher_with_send` copies its output buffer on
every append and every partial send. The module exists on Python 3.10 and 3.11
only, so every runtime test takes the `asyncore` fixture, which skips from
3.12; run them with a 3.10 or 3.11 environment. CI's full-suite jobs use the
newest supported Python and its 3.10 and 3.11 jobs run only timing tests, so
those tests run locally only. Availability and the asyncio comparison run
everywhere. The released Lib/asyncore.py differs between v3.10.19 and v3.11.14
only in how its import-time DeprecationWarning is raised. Everything is settled
by observation: counting predicates, recording sockets, identity and length
of the output buffer, and the map's contents. Channels are built on
`socket.socketpair()` with a private map unless a test is about the global one.

Measurement scope:

* A pass over c idle channels, for c of 10 and 100, calls `readable()` and
  `writable()` exactly c times each, with `select()` and with `use_poll=True`,
  though no channel is ready; three passes call them 3·c times.
* A channel left with the default `writable()` is returned writable by
  `select()` on each of five passes with a 30-second timeout, which
  `select()` does only once the descriptor is ready rather than after the
  timeout, and gets `handle_write()` on each. A listening channel is not in
  the write list handed to `select()`. The default `handle_read()`, `handle_write()`, `handle_expt()` and
  `handle_connect()` write nothing to stdout or stderr.
* A socket duplicated to the lowest free descriptor from 1100 makes a
  `select()` pass raise `ValueError` and a `use_poll=True` pass succeed (not
  on Windows, whose `select()` limits the socket count rather than descriptor numbers).
* `loop()` without `count` returns once `recv()` has seen end of stream and
  the default `handle_close()` has removed the channel; `recv()` returns
  `b''` there. `close_all()` empties the map and closes every socket.
  `close()` removes the channel from its map. A channel built on a socket
  with no map is in `socket_map`, and a loop with no map runs it.
* `dispatcher(sock)` and `create_socket()` leave the socket non-blocking and
  the channel registered. `accept()` returns `None` with nothing pending.
  Three pending connections reach `handle_accepted()` one per pass.
  `connect()` to a loopback listener calls `handle_connect()` once. One
  `send()` of 10 MB on a socket whose send buffer is set to 65,536 bytes
  returns fewer bytes than that, and a `send()` to a full socket returns 0.
  `recv(10_000_000)` returning one byte peaks above 9 MB of traced
  allocation.
* A handler that raises reaches `handle_error()`, whose default prints one
  line naming each of the handler's recursive frames (5 and 50 deep) and
  removes the channel; `ExitNow`, `KeyboardInterrupt` and `SystemExit` leave
  `loop()` with the channel still registered.
* `dispatcher_with_send.send()` with a socket that accepts nothing leaves a
  new buffer object of u + n bytes after each call, distinct from the data
  once the buffer was non-empty. With a socket that accepts 65,536 bytes a
  call, a 4·65,536-byte buffer becomes new objects of
  3, 2 and 1 times 65,536 bytes after successive `handle_write()` calls, each
  send being at most 65,536 bytes. `writable()` follows the buffer once
  connected and is true before.
* `file_dispatcher` (POSIX only) over a pipe registers a duplicate of the
  descriptor, accepts an object with `fileno()`, leaves the original
  non-blocking, and reads and writes through the duplicate; an unclosed
  `file_wrapper` warns with `ResourceWarning`.
* asyncio: a `SelectorEventLoop` over a counting selector, with 20 idle
  stream connections open, makes no register, modify or unregister call over
  50 passes while calling `select()` on each; on Linux `DefaultSelector` is
  `EpollSelector`.
* Every fenced Python block runs in its own subprocess. The four that import
  `asyncore` run on 3.10 and 3.11 only; the `asyncio` one runs everywhere and
  carries the runner's mutation check.

Not settled here:

* The deprecation in 3.6 and the removal in 3.12 come from the 3.11
  documentation and PEP 594. The import warning is asserted on 3.10 and 3.11;
  that it starts at 3.10 is read from Lib/asyncore.py at v3.9.0 and v3.10.0,
  since 3.9 is not supported. `ModuleNotFoundError` from 3.12 is asserted.
* The O(c) space of a pass and of `close_all()` is read from Lib/asyncore.py:
  each copies the map's items into a list and builds descriptor lists or a
  `poll` object over them. The O(u + n) and O(u) bounds of
  `dispatcher_with_send` follow from the buffer copies observed above, with
  `bytes` concatenation and slicing taken as linear in their length.
* That `connect()` resolves a host name before returning is read from
  Modules/socketmodule.c, whose address parsing calls `getaddrinfo()`
  synchronously; no name service is queried here. That epoll reports only
  ready descriptors is the kernel's contract, not measured, and Windows'
  default proactor loop is not measured either.
* `handle_error()` is O(f) by `compact_traceback()`, which walks the
  traceback once; the frame count is observed, its time is not.
* The kernel's cost for `select()`, `poll()`, `send()` and `recv()` is
  outside the bounds, and socket buffer sizes are not varied beyond the one
  set for the partial send. The examples run on Linux only here.
* `poll`, `poll2`, `poll3`, `read`, `write`, `readwrite`,
  `compact_traceback`, the `dispatcher` helpers `add_channel`, `del_channel`,
  `set_socket`, `set_reuse_addr`, `log`, `log_info` and the `handle_*_event`
  dispatchers, and `dispatcher_with_send.initiate_send` are not in the
  official documentation; the page names only what a reader uses.
"""

from __future__ import annotations

import asyncio
import contextlib
import importlib
import importlib.util
import io
import os
import pathlib
import re
import selectors
import socket
import subprocess
import sys
import textwrap
import tracemalloc
import warnings
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "asyncore.md"
EXPECTED_BLOCKS = 5
CHUNK = 65536


def test_the_module_exists_only_before_3_12() -> None:
    assert (importlib.util.find_spec("asyncore") is not None) == (sys.version_info < (3, 12))


@pytest.fixture
def asyncore() -> Iterator[Any]:
    if sys.version_info >= (3, 12):
        pytest.skip("version: asyncore was removed in Python 3.12")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        yield importlib.import_module("asyncore")


@pytest.fixture
def pairs() -> Iterator[Callable[[], tuple[socket.socket, socket.socket]]]:
    """Make socket pairs and close both ends of each afterwards."""
    made: list[socket.socket] = []

    def make() -> tuple[socket.socket, socket.socket]:
        ours, theirs = socket.socketpair()
        made.extend((ours, theirs))
        return ours, theirs

    yield make
    for sock in made:
        sock.close()


class FakeSocket:
    """Stands in for a channel's socket: records each send, accepts `accept`."""

    def __init__(self, accept: int) -> None:
        self.accept = accept
        self.sent: list[int] = []

    def send(self, data: bytes) -> int:
        self.sent.append(len(data))
        return min(self.accept, len(data))


class TestAvailability:
    """`import asyncore` works on 3.10 and 3.11 and fails from 3.12."""

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="the module exists before 3.12")
    def test_importing_it_from_3_12_raises(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("asyncore")

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="asyncore was removed in 3.12")
    def test_importing_it_warns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delitem(sys.modules, "asyncore", raising=False)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            importlib.import_module("asyncore")
        assert any(
            issubclass(w.category, DeprecationWarning) and "asyncore" in str(w.message)
            for w in caught
        )


class TestAPassVisitsEveryChannel:
    """`loop()` is O(c) per pass: every channel's `readable()` and `writable()`
    are called on every pass, ready or not. A loop that visited only ready
    channels would call neither here, since nothing is ready."""

    @pytest.mark.parametrize("use_poll", [False, True])
    @pytest.mark.parametrize("count", [10, 100])
    def test_idle_channels_are_all_asked(
        self,
        asyncore: Any,
        pairs: Callable[[], tuple[socket.socket, socket.socket]],
        count: int,
        use_poll: bool,
    ) -> None:
        asked = {"readable": 0, "writable": 0}

        class Idle(asyncore.dispatcher):
            def readable(self) -> bool:
                asked["readable"] += 1
                return True

            def writable(self) -> bool:
                asked["writable"] += 1
                return False

            def handle_read(self) -> None:
                raise AssertionError("nothing was sent")

        channels: dict[int, Any] = {}
        for _ in range(count):
            Idle(pairs()[0], channels)
        asyncore.loop(timeout=0, map=channels, count=1, use_poll=use_poll)
        assert asked == {"readable": count, "writable": count}
        asyncore.loop(timeout=0, map=channels, count=2, use_poll=use_poll)
        assert asked == {"readable": 3 * count, "writable": 3 * count}


class TestDefaultPredicates:
    """`readable()` and `writable()` are always true, so a default channel is
    ready on every pass; the default event handlers are silent; an accepting
    channel is never polled for writing."""

    def test_both_are_true(self, asyncore: Any) -> None:
        channel = asyncore.dispatcher(map={})
        assert channel.readable() is True and channel.writable() is True

    def test_a_default_writable_channel_never_waits(
        self,
        asyncore: Any,
        pairs: Callable[[], tuple[socket.socket, socket.socket]],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        writes: list[int] = []
        ready: list[list[int]] = []
        real_select = asyncore.select.select

        def recording(r: list[int], w: list[int], e: list[int], timeout: float) -> Any:
            result = real_select(r, w, e, timeout)
            ready.append(list(result[1]))
            return result

        class Spinning(asyncore.dispatcher):
            def handle_write(self) -> None:
                writes.append(1)

        channels: dict[int, Any] = {}
        ours, _ = pairs()
        Spinning(ours, channels)
        monkeypatch.setattr(asyncore.select, "select", recording)
        asyncore.loop(timeout=30, map=channels, count=5)
        assert ready == [[ours.fileno()]] * 5 and len(writes) == 5

    def test_the_default_handlers_are_silent(self, asyncore: Any) -> None:
        channel = asyncore.dispatcher(map={})
        assert "warning" in channel.ignore_log_types
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            channel.handle_read()
            channel.handle_write()
            channel.handle_expt()
            channel.handle_connect()
        assert output.getvalue() == ""

    def test_an_accepting_channel_is_not_polled_for_writing(
        self, asyncore: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        requests: list[tuple[list[int], list[int]]] = []
        real_select = asyncore.select.select

        def recording(r: list[int], w: list[int], e: list[int], timeout: float) -> Any:
            requests.append((list(r), list(w)))
            return real_select(r, w, e, timeout)

        channels: dict[int, Any] = {}
        server = asyncore.dispatcher(map=channels)
        server.create_socket()
        try:
            server.bind(("127.0.0.1", 0))
            server.listen(5)
            monkeypatch.setattr(asyncore.select, "select", recording)
            asyncore.loop(timeout=0, map=channels, count=1)
            assert requests == [([server.socket.fileno()], [])]
        finally:
            server.close()


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows FD_SETSIZE limits the socket count, not descriptor numbers",
)
def test_select_rejects_a_high_descriptor_and_poll_does_not(
    asyncore: Any, pairs: Callable[[], tuple[socket.socket, socket.socket]]
) -> None:
    import fcntl
    import resource

    soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft <= 1100:
        pytest.skip(f"missing open-files: open-file limit {soft} is too low for descriptor 1100")
    ours, _ = pairs()
    high = fcntl.fcntl(ours.fileno(), fcntl.F_DUPFD, 1100)  # lowest free descriptor >= 1100
    sock = socket.socket(fileno=high)
    channels: dict[int, Any] = {}
    channel = asyncore.dispatcher(sock, channels)
    try:
        with pytest.raises(ValueError, match="out of range"):
            asyncore.loop(timeout=0, map=channels, count=1)
        asyncore.loop(timeout=0, map=channels, count=1, use_poll=True)
    finally:
        channel.close()


class TestStoppingAndClosing:
    """`loop()` without `count` runs until the map is empty; `recv()` at end of
    stream closes the channel through `handle_close()`; `close()` and
    `close_all()` remove channels; `socket_map` is the default map."""

    def test_end_of_stream_closes_the_channel_and_ends_the_loop(
        self, asyncore: Any, pairs: Callable[[], tuple[socket.socket, socket.socket]]
    ) -> None:
        reads: list[bytes] = []

        class Reader(asyncore.dispatcher):
            def writable(self) -> bool:
                return False

            def handle_read(self) -> None:
                reads.append(self.recv(4096))

        channels: dict[int, Any] = {}
        ours, theirs = pairs()
        Reader(ours, channels)
        theirs.sendall(b"hello")
        theirs.close()
        asyncore.loop(timeout=1, map=channels)
        assert reads == [b"hello", b""] and channels == {}
        assert ours.fileno() == -1

    def test_close_removes_the_channel(
        self, asyncore: Any, pairs: Callable[[], tuple[socket.socket, socket.socket]]
    ) -> None:
        channels: dict[int, Any] = {}
        ours, _ = pairs()
        channel = asyncore.dispatcher(ours, channels)
        assert list(channels.values()) == [channel]
        channel.close()
        assert channels == {} and ours.fileno() == -1

    def test_close_all_closes_every_channel(
        self, asyncore: Any, pairs: Callable[[], tuple[socket.socket, socket.socket]]
    ) -> None:
        channels: dict[int, Any] = {}
        socks = [pairs()[0] for _ in range(5)]
        for sock in socks:
            asyncore.dispatcher(sock, channels)
        asyncore.close_all(channels)
        assert channels == {} and all(sock.fileno() == -1 for sock in socks)

    def test_the_global_map_is_the_default(
        self, asyncore: Any, pairs: Callable[[], tuple[socket.socket, socket.socket]]
    ) -> None:
        ours, theirs = pairs()
        reads: list[bytes] = []

        class Reader(asyncore.dispatcher):
            def writable(self) -> bool:
                return False

            def handle_read(self) -> None:
                reads.append(self.recv(10))

        channel = Reader(ours)
        try:
            assert asyncore.socket_map[ours.fileno()] is channel
            theirs.sendall(b"x")
            asyncore.loop(timeout=1, count=1)
            assert reads == [b"x"]
        finally:
            channel.close()
        assert channel not in asyncore.socket_map.values()


class TestDispatcherSocketCalls:
    """Construction and `create_socket()` leave a non-blocking registered
    socket; `accept()`, `handle_accept()`, `connect()`, `send()` and `recv()`
    behave as their rows say."""

    def test_construction_makes_the_socket_non_blocking(
        self, asyncore: Any, pairs: Callable[[], tuple[socket.socket, socket.socket]]
    ) -> None:
        ours, _ = pairs()
        assert ours.gettimeout() is None
        asyncore.dispatcher(ours, {})
        assert ours.gettimeout() == 0.0

    def test_create_socket_registers_a_non_blocking_socket(self, asyncore: Any) -> None:
        channels: dict[int, Any] = {}
        channel = asyncore.dispatcher(map=channels)
        assert channels == {}
        channel.create_socket()
        try:
            assert channel.socket.gettimeout() == 0.0
            assert channels == {channel.socket.fileno(): channel}
        finally:
            channel.close()

    def test_accept_returns_none_with_nothing_pending(self, asyncore: Any) -> None:
        server = asyncore.dispatcher(map={})
        server.create_socket()
        try:
            server.bind(("127.0.0.1", 0))
            server.listen(5)
            assert server.accept() is None
        finally:
            server.close()

    def test_one_connection_is_accepted_per_pass(self, asyncore: Any) -> None:
        accepted: list[socket.socket] = []

        class Server(asyncore.dispatcher):
            def handle_accepted(self, sock: socket.socket, addr: Any) -> None:
                accepted.append(sock)

        channels: dict[int, Any] = {}
        server = Server(map=channels)
        server.create_socket()
        clients: list[socket.socket] = []
        try:
            server.bind(("127.0.0.1", 0))
            server.listen(5)
            for _ in range(3):
                clients.append(socket.create_connection(server.socket.getsockname()))
            for passes in range(1, 4):
                asyncore.loop(timeout=1, map=channels, count=1)
                assert len(accepted) == passes
        finally:
            server.close()
            for sock in clients + accepted:
                sock.close()

    def test_connect_reports_completion_once(self, asyncore: Any) -> None:
        connected: list[int] = []

        class Client(asyncore.dispatcher):
            def handle_connect(self) -> None:
                connected.append(1)

            def handle_write(self) -> None:
                pass

        listener = socket.create_server(("127.0.0.1", 0))
        channels: dict[int, Any] = {}
        client = Client(map=channels)
        client.create_socket()
        try:
            client.connect(listener.getsockname())
            for _ in range(3):
                asyncore.loop(timeout=1, map=channels, count=1)
            assert connected == [1] and client.connected
        finally:
            client.close()
            listener.close()

    def test_send_takes_what_the_socket_accepts(
        self, asyncore: Any, pairs: Callable[[], tuple[socket.socket, socket.socket]]
    ) -> None:
        ours, _ = pairs()
        ours.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, CHUNK)
        channel = asyncore.dispatcher(ours, {})
        data = b"x" * 10_000_000
        sent = channel.send(data)
        assert 0 < sent < len(data)
        while sent:
            sent = channel.send(data)
        assert sent == 0

    def test_recv_allocates_the_requested_size(
        self, asyncore: Any, pairs: Callable[[], tuple[socket.socket, socket.socket]]
    ) -> None:
        ours, theirs = pairs()
        channel = asyncore.dispatcher(ours, {})
        theirs.sendall(b"x")
        if tracemalloc.is_tracing():
            pytest.skip("missing untraced-process: a peak would include the earlier traces")
        tracemalloc.start()
        try:
            data = channel.recv(10_000_000)
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        assert data == b"x" and peak > 9_000_000, peak


class TestHandleError:
    """An exception in a handler reaches `handle_error()`, which is O(f): the
    default prints one line naming every frame and closes the channel.
    `ExitNow`, `KeyboardInterrupt` and `SystemExit` propagate instead."""

    @staticmethod
    def raising(asyncore: Any, error: Callable[[], BaseException], depth: int = 1) -> Any:
        def recurse(level: int) -> None:
            if level:
                recurse(level - 1)
            else:
                raise error()

        class Failing(asyncore.dispatcher):
            def writable(self) -> bool:
                return False

            def handle_read(self) -> None:
                recurse(depth)

        return Failing

    @pytest.mark.parametrize("depth", [5, 50])
    def test_the_default_prints_every_frame_and_closes(
        self,
        asyncore: Any,
        pairs: Callable[[], tuple[socket.socket, socket.socket]],
        depth: int,
    ) -> None:
        channels: dict[int, Any] = {}
        ours, theirs = pairs()
        self.raising(asyncore, lambda: RuntimeError("bad input"), depth)(ours, channels)
        theirs.sendall(b"x")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            asyncore.loop(timeout=1, map=channels, count=1)
        text = output.getvalue()
        assert text.count("\n") == 1 and "bad input" in text
        assert text.count("|recurse|") == depth + 1
        assert channels == {}

    @pytest.mark.parametrize("error", ["ExitNow", "KeyboardInterrupt", "SystemExit"])
    def test_some_exceptions_leave_the_loop(
        self,
        asyncore: Any,
        pairs: Callable[[], tuple[socket.socket, socket.socket]],
        error: str,
    ) -> None:
        kind = {
            "ExitNow": asyncore.ExitNow,
            "KeyboardInterrupt": KeyboardInterrupt,
            "SystemExit": SystemExit,
        }[error]
        channels: dict[int, Any] = {}
        ours, theirs = pairs()
        channel = self.raising(asyncore, kind)(ours, channels)
        theirs.sendall(b"x")
        with pytest.raises(kind):
            asyncore.loop(timeout=1, map=channels)
        assert list(channels.values()) == [channel]


class TestDispatcherWithSendCopies:
    """`send()` is O(u + n): it concatenates onto the buffer. `handle_write()`
    is O(u): after a partial send the rest becomes a new buffer, so draining is
    O(u²). New objects of the stated lengths are the copies."""

    def test_each_send_builds_a_new_buffer(self, asyncore: Any) -> None:
        channel = asyncore.dispatcher_with_send(map={})
        channel.socket = FakeSocket(accept=0)
        lengths = []
        previous = channel.out_buffer
        for _ in range(4):
            data = b"y" * 1000
            channel.send(data)
            assert channel.out_buffer is not previous
            if previous:
                assert channel.out_buffer is not data
            previous = channel.out_buffer
            lengths.append(len(previous))
        assert lengths == [1000, 2000, 3000, 4000]
        assert channel.socket.sent == [1000, 2000, 3000, 4000]

    def test_each_partial_send_copies_the_rest(self, asyncore: Any) -> None:
        channel = asyncore.dispatcher_with_send(map={})
        channel.connected = True
        fake = FakeSocket(accept=0)
        channel.socket = fake
        channel.send(b"z" * (4 * CHUNK))
        fake.accept = CHUNK
        buffers = []
        for _ in range(3):
            channel.handle_write()
            buffers.append(channel.out_buffer)
        assert [len(buffer) for buffer in buffers] == [3 * CHUNK, 2 * CHUNK, CHUNK]
        assert len({id(buffer) for buffer in buffers}) == 3
        assert fake.sent == [CHUNK] * 4
        assert channel.writable()
        channel.handle_write()
        assert channel.out_buffer == b"" and not channel.writable()

    def test_it_is_writable_until_connected(self, asyncore: Any) -> None:
        channel = asyncore.dispatcher_with_send(map={})
        assert not channel.connected and channel.writable()


@pytest.mark.skipif(os.name != "posix", reason="file_dispatcher is defined only on POSIX")
class TestFileDispatcher:
    """`file_dispatcher` registers a duplicate descriptor wrapped in a
    `file_wrapper` whose `recv()` and `send()` are `os.read()` and
    `os.write()`."""

    def test_it_registers_a_non_blocking_duplicate(self, asyncore: Any) -> None:
        r, w = os.pipe()
        channels: dict[int, Any] = {}
        try:
            channel = asyncore.file_dispatcher(r, channels)
            duplicate = channel.socket.fileno()
            assert duplicate != r and channels == {duplicate: channel}
            assert not os.get_blocking(r) and not os.get_blocking(duplicate)
            os.write(w, b"data")
            assert channel.recv(10) == b"data"
            channel.close()
            assert channels == {}
        finally:
            os.close(r)
            os.close(w)

    def test_it_accepts_an_object_with_fileno(self, asyncore: Any) -> None:
        r, w = os.pipe()
        channels: dict[int, Any] = {}
        with open(w, "wb", buffering=0) as writer:
            try:
                channel = asyncore.file_dispatcher(writer, channels)
                assert channel.send(b"out") == 3
                assert os.read(r, 10) == b"out"
                channel.close()
            finally:
                os.close(r)

    def test_an_unclosed_wrapper_warns(self, asyncore: Any) -> None:
        r, w = os.pipe()
        try:
            wrapper = asyncore.file_wrapper(r)
            assert wrapper.fileno() != r
            with pytest.warns(ResourceWarning):
                del wrapper
        finally:
            os.close(r)
            os.close(w)


class CountingSelector(selectors.DefaultSelector):
    """The platform's default selector, counting the calls the loop makes."""

    def __init__(self) -> None:
        super().__init__()
        self.calls = {"register": 0, "modify": 0, "unregister": 0, "select": 0}

    def register(self, *args: Any, **kwargs: Any) -> Any:
        self.calls["register"] += 1
        return super().register(*args, **kwargs)

    def modify(self, *args: Any, **kwargs: Any) -> Any:
        self.calls["modify"] += 1
        return super().modify(*args, **kwargs)

    def unregister(self, *args: Any, **kwargs: Any) -> Any:
        self.calls["unregister"] += 1
        return super().unregister(*args, **kwargs)

    def select(self, *args: Any, **kwargs: Any) -> Any:
        self.calls["select"] += 1
        return super().select(*args, **kwargs)


async def _idle_passes(
    selector: CountingSelector, connections: int, passes: int
) -> tuple[dict[str, int], dict[str, int]]:
    """Open idle stream connections, then count the selector calls over idle passes."""
    writers = []
    for _ in range(connections):
        for sock in socket.socketpair():
            _, writer = await asyncio.open_connection(sock=sock)
            writers.append(writer)
    await asyncio.sleep(0)
    before = dict(selector.calls)
    for _ in range(passes):
        await asyncio.sleep(0)
    after = dict(selector.calls)
    for writer in writers:
        writer.close()
    for writer in writers:
        await writer.wait_closed()
    return before, after


class TestAsyncioRegistersOnce:
    """The migration section: asyncio keeps each socket registered between
    passes, so an idle pass makes no registration calls; on Linux the default
    selector is epoll."""

    @pytest.mark.skipif(sys.platform != "linux", reason="epoll is Linux's selector")
    def test_the_linux_default_selector_is_epoll(self) -> None:
        assert selectors.DefaultSelector is selectors.EpollSelector

    def test_idle_passes_make_no_registration_calls(self) -> None:
        selector = CountingSelector()
        loop = asyncio.SelectorEventLoop(selector)
        try:
            before, after = loop.run_until_complete(_idle_passes(selector, 20, 50))
        finally:
            loop.close()
        assert before["register"] >= 40
        for name in ("register", "modify", "unregister"):
            assert after[name] == before[name], name
        assert after["select"] - before["select"] >= 50


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
        [sys.executable, "-W", "ignore::DeprecationWarning", str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and asserts its own result. The
    blocks that import `asyncore` need 3.10 or 3.11."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        assert sum("import asyncore" in source for _, source in blocks) == EXPECTED_BLOCKS - 1

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            if "import asyncore" in source and sys.version_info >= (3, 12):
                continue
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == (1 if sys.version_info >= (3, 12) else EXPECTED_BLOCKS)
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "open_connection" in s)
        mutated = source.replace("== 1_000_000", "== 999_999", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
