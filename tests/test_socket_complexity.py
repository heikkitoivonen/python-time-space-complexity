"""Tests for docs/stdlib/socket.md.

The page prices the Python side of each call: the bytes copied between the
caller's buffers and the kernel, and what the call allocates to do it. Waiting
is outside every bound, so the tests run over `socketpair()` and loopback,
never a remote host. Space claims are settled by traced allocation, which
separates an up-front `bufsize` buffer from a caller's reused one by orders of
magnitude; ordering, laziness and aliasing claims by observation; and the
claims that only elapsed time can show by ratios or deadlines far from both
outcomes.

Measurement scope:

* `recv()`, `recvfrom()` and `recvmsg()` with an 8 MiB `bufsize` and 5 bytes
  queued each peak above 8 MiB and return 5 bytes; `recv_into()`,
  `recvfrom_into()` and `recvmsg_into()` into a preallocated 8 MiB buffer peak
  under 1 KB. In a timing test, `recv()` of 5 bytes with a 1 GiB `bufsize`
  costs under 4x the same call with 64 MiB, where a bound in `b` predicts 16x.
  Both sizes are above glibc's mmap threshold ceiling; the untouched pages of
  the 1 GiB request are never written.
* `sendall()` of 32 MiB to a reader thread that receives into one buffer peaks
  under 10 KB; the reader allocates its buffer before tracing starts. A non-blocking `send()` of 4 MB returns a count above zero and
  below the length. `sendmsg()` of two 4 MiB buffers peaks under 10 KB; with
  1,000 one-byte buffers it peaks over 20x its peak with 10 (sizes stay under
  Linux's `IOV_MAX` of 1,024); with 200 descriptors of `SCM_RIGHTS` data it
  peaks at or above `CMSG_SPACE(800)`, and with one descriptor below it.
* The `sendall()` timeout is total: a reader that takes 64 KiB every 20 ms
  keeps a loop of single `send()` calls under a 0.3 s per-call timeout alive
  for 1.5 s, while `sendall()` of 256 MiB under the same timeout and the same
  reader raises `TimeoutError` within 5 s.
* `sendfile()` of a 32 MiB regular file calls `os.sendfile()` and peaks under
  64 KB, with the lazy `selectors` import done first; a 4 MiB `BytesIO`, which
  has no descriptor, goes through the block fallback, delivers every byte,
  and peaks under 64 KB.
* The page's `recv_exactly()` helper, copied, reads 8 MiB written in 64 KiB
  pieces by another thread and peaks between 8 MiB and 1.1x that: the one
  data buffer plus small views and counts.
* `makefile('rb')` peaks under four times `io.DEFAULT_BUFFER_SIZE` when built
  and `makefile('rb', buffering=8 MiB)` above 8 MiB; `buffering=0` returns a
  `RawIOBase` that is not buffered. `readline()` over 500 queued lines makes
  at most two `recv_into()` calls, counted on a `socket.socket` subclass.
* Collecting 256-byte chunks with `bytes +=` costs more than 64x going from
  500 to 8,000 chunks, where linear gives 16x and quadratic 256x; a list and
  one `b''.join()` costs under 64x over the same span.
* `create_connection()` is driven by a patched `getaddrinfo()`: with two
  refusing records before a listening one it connects to the listener; with
  a listener first, a second listener behind it receives no connection; with
  a refusing record and an unconvertible one (an IPv6 literal in an `AF_INET`
  record, which raises `gaierror`) it raises whichever came last, in both
  orders, and on 3.11+ with two refusing records and `all_errors=True` an
  `ExceptionGroup` of both.
* `setdefaulttimeout()` reaches a socket created afterwards and not one
  created before; `setblocking(False)` and `settimeout(0.0)` read back the same.
* Resolution is exercised offline only: numeric hosts for `getaddrinfo()`,
  `gethostbyname()`, `gethostbyname_ex()` and `getnameinfo()`; the local
  services and protocols databases for `getservbyname()`, `getservbyport()`
  and `getprotobyname()`; `if_nameindex()` against `if_nametoindex()` and
  `if_indextoname()`. `getaddrinfo()` returns a list, and filtering by family
  and type returns fewer records than not filtering. `getfqdn()` is observed
  to make one `gethostbyaddr()` call and return the first dotted alias.
* `detach()` leaves the descriptor open; `dup()`, `socket.dup()` and
  `fromfd()` return different descriptors; `connect_ex()` returns
  `ECONNREFUSED` for a refused connection and raises `gaierror` for an IPv6
  literal on an `AF_INET` socket; `sendto()` over loopback UDP delivers the
  datagram and `recvfrom()` the sender's address; `has_dualstack_ipv6()`
  returns a bool; the conversion, byte-order and `CMSG_*` functions and the
  exception aliases are asserted by value.
* Every fenced Python block runs in its own subprocess with a timeout, and a
  mutated assertion in one of them is asserted to fail.

Not settled here:

* Every waiting cost: network latency, blocking until a peer acts, and
  resolver backends (hosts file, DNS, NSS). That `create_connection()` gives
  each attempt the full timeout is read from Lib/socket.py, which sets it on
  every new socket; a timeout-bound failed attempt needs an unreachable
  network address. That `AI_NUMERICHOST` makes no lookup is getaddrinfo(3)'s
  contract; only its rejection of a host name is observed.
* The O(r) bounds on `create_connection()`, `getaddrinfo()`,
  `gethostbyname_ex()`, `gethostbyaddr()` and `getfqdn()`, and O(i) on
  `if_nameindex()`, follow from the lists they build; r and i are not varied,
  because the local resolver and interfaces fix them.
* `recv_fds()`'s O(b + f) and `recvmsg_into()`'s O(v + c) are read from
  Lib/socket.py and Modules/socketmodule.c; only `recvmsg()`'s `b` term and
  `recvmsg_into()`'s zero-allocation data path are measured. `c` is not varied.
* `sendmsg_afalg()` is checked to encrypt two gathered buffers as one message
  where the kernel offers `AF_ALG` and `ecb(aes)`, and skipped otherwise; its
  O(v) space is the iovec construction it shares with `sendmsg()`, read from
  Modules/socketmodule.c.
* `sendfile()`'s O(n) time is not timed; each path moves the file once.
* `sethostname()` needs administrator rights and is not called.
* `socket.ioctl()`, `socket.share()` and `socket.fromshare()` are Windows-only.
  No run this project performs reaches them; the audit reports them as
  unresolved on Linux for the same reason.
* `socket.SocketIO`, the raw object behind `makefile(buffering=0)`, is not in
  the official inventory and the page does not document it.
* Kernel buffer sizes, IPv6, UDP message boundaries and TLS are not varied.
"""

from __future__ import annotations

import array
import errno
import io
import os
import pathlib
import re
import selectors
import socket
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import tracemalloc
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "socket.md"
EXPECTED_BLOCKS = 12
MIB = 1 << 20

needs_fd_passing = pytest.mark.skipif(
    not hasattr(socket, "send_fds"), reason="descriptor passing is Unix-only"
)


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 1) -> float:
    """Fastest of `repeats` runs, in nanoseconds per call."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        for _ in range(inner):
            func()
        elapsed = (time.perf_counter_ns() - start) / inner
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


@pytest.fixture
def pair() -> Iterator[tuple[socket.socket, socket.socket]]:
    left, right = socket.socketpair()
    try:
        yield left, right
    finally:
        left.close()
        right.close()


def drain_into_buffer(sock: socket.socket, total: int) -> threading.Thread:
    """Receive `total` bytes into one reused buffer on a background thread.

    Returns once the thread has allocated its buffer, so a traced peak started
    afterwards does not count it."""
    ready = threading.Event()

    def run() -> None:
        buffer = bytearray(65536)
        ready.set()
        received = 0
        while received < total:
            count = sock.recv_into(buffer)
            if not count:
                return
            received += count

    thread = threading.Thread(target=run)
    thread.start()
    ready.wait()
    return thread


def drain_queued(sock: socket.socket) -> None:
    """Discard whatever is queued without blocking."""
    sock.setblocking(False)
    try:
        while sock.recv(MIB):
            pass
    except BlockingIOError:
        pass
    finally:
        sock.setblocking(True)


def refusing_address() -> tuple[socket.socket, tuple[str, int]]:
    """A loopback port that is bound but not listening, so connecting is refused."""
    holder = socket.socket()
    holder.bind(("127.0.0.1", 0))
    return holder, holder.getsockname()


def stream_record(address: tuple[str, int]) -> tuple[Any, ...]:
    return (socket.AF_INET, socket.SOCK_STREAM, 6, "", address)


class TestReceivingAllocatesBufsize:
    """`recv(bufsize)` | O(k) | O(b): the result is allocated at `bufsize` and
    shrunk; the `_into` forms fill a caller's buffer and allocate nothing."""

    BUFSIZE = 8 * MIB

    @pytest.mark.parametrize(
        "receive",
        [
            lambda sock, size: sock.recv(size),
            lambda sock, size: sock.recvfrom(size)[0],
            lambda sock, size: sock.recvmsg(size)[0],
        ],
        ids=["recv", "recvfrom", "recvmsg"],
    )
    def test_the_whole_bufsize_is_allocated_for_five_bytes(
        self, pair: tuple[socket.socket, socket.socket], receive: Any
    ) -> None:
        left, right = pair
        left.sendall(b"hello")
        result: list[bytes] = []

        peak = peak_bytes(lambda: result.append(receive(right, self.BUFSIZE)))

        assert result == [b"hello"]
        assert peak > self.BUFSIZE, f"8 MiB bufsize for 5 bytes peaked at {peak}"

    @pytest.mark.parametrize(
        "receive",
        [
            lambda sock, buffer: sock.recv_into(buffer),
            lambda sock, buffer: sock.recvfrom_into(buffer)[0],
            lambda sock, buffer: sock.recvmsg_into([buffer])[0],
        ],
        ids=["recv_into", "recvfrom_into", "recvmsg_into"],
    )
    def test_receiving_into_a_buffer_allocates_nothing(
        self, pair: tuple[socket.socket, socket.socket], receive: Any
    ) -> None:
        left, right = pair
        buffer = bytearray(self.BUFSIZE)
        left.sendall(b"warm!")
        receive(right, buffer)
        left.sendall(b"hello")
        counts: list[int] = []

        peak = peak_bytes(lambda: counts.append(receive(right, buffer)))

        assert counts == [5] and buffer[:5] == b"hello"
        assert peak < 1_000, f"receiving into an 8 MiB buffer peaked at {peak}"

    @pytest.mark.timing
    def test_recv_time_does_not_follow_bufsize(
        self, pair: tuple[socket.socket, socket.socket]
    ) -> None:
        left, right = pair

        def receive(size: int) -> Callable[[], Any]:
            def run() -> None:
                left.send(b"hello")
                right.recv(size)

            return run

        # Both sizes are over glibc's 32 MiB ceiling for its dynamic mmap threshold, so
        # neither is served from a heap that an earlier free has grown.
        small = best_ns(receive(64 * MIB), repeats=20)
        large = best_ns(receive(1024 * MIB), repeats=20)

        ratio = large / small
        assert ratio < 4, f"16x the bufsize for 5 bytes cost x{ratio:.2f}; O(b) time predicts 16"


class TestSendingCopiesNothing:
    """`send` may be partial; `sendall` and `sendmsg` work through the caller's
    buffers, so their space is O(1) in k and O(v + a) for `sendmsg`."""

    def test_a_non_blocking_send_can_be_partial(
        self, pair: tuple[socket.socket, socket.socket]
    ) -> None:
        left, _ = pair
        payload = b"x" * 4_000_000
        left.setblocking(False)

        sent = left.send(payload)

        assert 0 < sent < len(payload)

    def test_sendall_holds_no_copy_of_the_data(
        self, pair: tuple[socket.socket, socket.socket]
    ) -> None:
        left, right = pair
        payload = b"x" * (32 * MIB)
        reader = drain_into_buffer(right, len(payload))

        peak = peak_bytes(lambda: left.sendall(payload))
        reader.join()

        assert peak < 10_000, f"sendall of 32 MiB peaked at {peak}"

    def test_sendmsg_does_not_join_its_buffers(
        self, pair: tuple[socket.socket, socket.socket]
    ) -> None:
        left, right = pair
        buffers = [b"a" * (4 * MIB), b"b" * (4 * MIB)]
        reader = drain_into_buffer(right, 8 * MIB)
        sent: list[int] = []

        peak = peak_bytes(lambda: sent.append(left.sendmsg(buffers)))
        left.sendall(memoryview(b"".join(buffers))[sent[0] :])
        reader.join()

        assert sent[0] > 0
        assert peak < 10_000, f"sendmsg of two 4 MiB buffers peaked at {peak}"

    def test_sendmsg_space_follows_the_buffer_count(
        self, pair: tuple[socket.socket, socket.socket]
    ) -> None:
        left, right = pair
        peaks = []
        for count in (10, 1_000):
            buffers = [b"x"] * count
            left.sendmsg(buffers)  # warm
            drain_queued(right)
            peaks.append(peak_bytes(lambda b=buffers: left.sendmsg(b)))  # type: ignore[misc]
            drain_queued(right)

        assert peaks[1] > peaks[0] * 20, f"10 and 1,000 buffers peaked at {peaks}"

    @needs_fd_passing
    def test_sendmsg_space_follows_the_ancillary_data(
        self, pair: tuple[socket.socket, socket.socket]
    ) -> None:
        left, right = pair
        opened = [os.open(os.devnull, os.O_RDONLY) for _ in range(200)]
        try:
            peaks = []
            for count in (1, 200):
                packed = array.array("i", opened[:count]).tobytes()
                ancdata = [(socket.SOL_SOCKET, socket.SCM_RIGHTS, packed)]
                for measured in (False, True):
                    if measured:
                        peaks.append(peak_bytes(lambda a=ancdata: left.sendmsg([b"x"], a)))  # type: ignore[misc]
                    else:
                        left.sendmsg([b"x"], ancdata)
                    _, received, _, _ = right.recvmsg(16, socket.CMSG_SPACE(4 * count))
                    for _, _, data in received:
                        for fd in array.array("i", data):
                            os.close(fd)
        finally:
            for fd in opened:
                os.close(fd)

        packed_200 = socket.CMSG_SPACE(4 * 200)
        assert peaks[0] < packed_200 <= peaks[1], f"1 and 200 descriptors peaked at {peaks}"


class TestSendallTimeoutIsTotal:
    """A timeout bounds the whole `sendall()`, not each `send()` inside it.

    The reader frees buffer space often enough that no single `send()` waits
    anywhere near the timeout; the control loop proves that for this rig."""

    TIMEOUT = 0.3

    @staticmethod
    def trickle(sock: socket.socket, stop: threading.Event) -> threading.Thread:
        def run() -> None:
            while not stop.is_set():
                try:
                    sock.recv(65536)
                except OSError:
                    return
                time.sleep(0.02)

        thread = threading.Thread(target=run)
        thread.start()
        return thread

    @pytest.mark.timing
    def test_single_sends_survive_the_same_reader(
        self, pair: tuple[socket.socket, socket.socket]
    ) -> None:
        left, right = pair
        stop = threading.Event()
        reader = self.trickle(right, stop)
        left.settimeout(self.TIMEOUT)
        payload = memoryview(b"x" * (64 * MIB))
        sent = 0
        start = time.monotonic()
        try:
            while time.monotonic() - start < 1.5:
                sent += left.send(payload[sent : sent + 65536])
        finally:
            stop.set()
            right.shutdown(socket.SHUT_RDWR)
            reader.join()

        assert sent < len(payload), "the reader drained everything; the rig proves nothing"

    @pytest.mark.timing
    def test_sendall_times_out_while_the_reader_keeps_up(
        self, pair: tuple[socket.socket, socket.socket]
    ) -> None:
        left, right = pair
        stop = threading.Event()
        reader = self.trickle(right, stop)
        left.settimeout(self.TIMEOUT)
        start = time.monotonic()
        try:
            with pytest.raises(TimeoutError):
                left.sendall(b"x" * (256 * MIB))
            elapsed = time.monotonic() - start
        finally:
            stop.set()
            right.shutdown(socket.SHUT_RDWR)
            reader.join()

        assert elapsed < 5, f"sendall under a {self.TIMEOUT}s timeout ran {elapsed:.2f}s"


class TestSendfileHoldsNoCopy:
    """`sendfile` | O(n) | O(1): `os.sendfile()` for a regular file, fixed-size
    blocks for anything without a descriptor."""

    SIZE = 32 * MIB

    def test_a_regular_file_goes_through_os_sendfile(
        self, pair: tuple[socket.socket, socket.socket], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        if not hasattr(os, "sendfile"):
            pytest.skip("os.sendfile is unavailable")
        left, right = pair
        calls: list[int] = []
        original = os.sendfile

        def counting(*args: Any) -> int:
            calls.append(args[3])
            return original(*args)

        monkeypatch.setattr(os, "sendfile", counting)
        assert selectors.PollSelector  # the lazy import inside sendfile is already done
        with tempfile.TemporaryFile() as file:
            file.write(b"x" * self.SIZE)
            file.seek(0)
            reader = drain_into_buffer(right, self.SIZE)
            sent: list[int] = []

            peak = peak_bytes(lambda: sent.append(left.sendfile(file)))
            reader.join()

        assert sent == [self.SIZE]
        assert calls, "os.sendfile was not called"
        assert peak < 64_000, f"sendfile of 32 MiB peaked at {peak}"

    def test_a_file_without_a_descriptor_is_sent_in_blocks(
        self, pair: tuple[socket.socket, socket.socket]
    ) -> None:
        left, right = pair
        size = 4 * MIB
        source = io.BytesIO(b"y" * size)
        reader = drain_into_buffer(right, size)
        sent: list[int] = []

        peak = peak_bytes(lambda: sent.append(left.sendfile(source)))
        reader.join()

        assert sent == [size] and source.tell() == size
        assert peak < 64_000, f"sending a 4 MiB BytesIO peaked at {peak}"


class TestMakefileBuffers:
    """`makefile()` | O(1) | O(buffering): the buffer is allocated when the
    file object is built, and serves many short lines from one receive."""

    def test_the_buffer_is_allocated_when_built(
        self, pair: tuple[socket.socket, socket.socket]
    ) -> None:
        _, right = pair
        streams: list[Any] = []

        default = peak_bytes(lambda: streams.append(right.makefile("rb")))
        large = peak_bytes(lambda: streams.append(right.makefile("rb", buffering=8 * MIB)))
        for stream in streams:
            stream.close()

        assert default < io.DEFAULT_BUFFER_SIZE * 4, f"the default buffer peaked at {default}"
        assert large > 8 * MIB, f"an 8 MiB buffer peaked at {large}"

    def test_buffering_zero_returns_the_raw_stream(
        self, pair: tuple[socket.socket, socket.socket]
    ) -> None:
        _, right = pair

        with right.makefile("rb", buffering=0) as raw:
            assert isinstance(raw, io.RawIOBase)
            assert not isinstance(raw, io.BufferedIOBase)

    def test_five_hundred_lines_take_at_most_two_receives(self) -> None:
        class Counting(socket.socket):
            __slots__ = ()
            receives = 0

            def recv_into(self, buffer: Any, nbytes: int = 0, flags: int = 0) -> int:
                type(self).receives += 1
                return super().recv_into(buffer, nbytes, flags)

        left, right = socket.socketpair()
        counted = Counting(fileno=right.detach())
        try:
            left.sendall(b"".join(b"line %04d\n" % index for index in range(500)))
            with counted.makefile("rb") as stream:
                lines = [stream.readline() for _ in range(500)]
        finally:
            left.close()
            counted.close()

        assert lines[-1] == b"line 0499\n"
        assert Counting.receives <= 2, f"500 lines took {Counting.receives} receives"


class TestRecvExactlyUsesOneBuffer:
    """The page's `recv_exactly()` pattern: slices of one preallocated buffer,
    however the stream is chunked. The helper is the page's, copied."""

    @staticmethod
    def recv_exactly(sock: socket.socket, size: int) -> bytearray:
        buffer = bytearray(size)
        view = memoryview(buffer)
        filled = 0
        while filled < size:
            count = sock.recv_into(view[filled:])
            if not count:
                raise ConnectionError("peer closed mid-message")
            filled += count
        return buffer

    def test_the_peak_is_the_one_data_buffer(
        self, pair: tuple[socket.socket, socket.socket]
    ) -> None:
        left, right = pair
        size = 8 * MIB
        message = b"z" * size

        def send() -> None:
            view = memoryview(message)
            for start in range(0, size, 65536):
                left.sendall(view[start : start + 65536])

        writer = threading.Thread(target=send)
        writer.start()
        result: list[bytearray] = []
        peak = peak_bytes(lambda: result.append(self.recv_exactly(right, size)))
        writer.join()

        assert result[0] == message
        assert size <= peak < size * 1.1, f"an 8 MiB exact read peaked at {peak}"


class TestJoinOnce:
    """Collecting chunks with `bytes +=` is O(n²); a list and one join is O(n)."""

    CHUNK = b"x" * 256
    SIZES = (500, 8_000)

    @classmethod
    def concatenate(cls, count: int) -> bytes:
        data = b""
        for _ in range(count):
            data += cls.CHUNK
        return data

    @classmethod
    def join(cls, count: int) -> bytes:
        chunks = []
        for _ in range(count):
            chunks.append(cls.CHUNK)
        return b"".join(chunks)

    def test_both_build_the_same_bytes(self) -> None:
        assert self.concatenate(100) == self.join(100) == self.CHUNK * 100

    @pytest.mark.timing
    def test_concatenation_grows_quadratically(self) -> None:
        durations = [best_ns(lambda n=n: self.concatenate(n), repeats=5) for n in self.SIZES]
        span = durations[-1] / durations[0]

        assert span > 64, f"16x the chunks cost x{span:.1f}; linear gives 16, quadratic 256"

    @pytest.mark.timing
    def test_joining_grows_linearly(self) -> None:
        durations = [best_ns(lambda n=n: self.join(n), repeats=5) for n in self.SIZES]
        span = durations[-1] / durations[0]

        assert span < 64, f"16x the chunks cost x{span:.1f}; linear gives 16, quadratic 256"


class TestCreateConnectionTriesInOrder:
    """`create_connection` | O(r): each resolved address in turn, stopping at
    the first that connects."""

    @pytest.fixture
    def listeners(self) -> Iterator[list[socket.socket]]:
        servers = [socket.create_server(("127.0.0.1", 0)) for _ in range(2)]
        try:
            yield servers
        finally:
            for server in servers:
                server.close()

    @pytest.fixture
    def refusing(self) -> Iterator[list[tuple[str, int]]]:
        held = [refusing_address() for _ in range(2)]
        try:
            yield [address for _, address in held]
        finally:
            for holder, _ in held:
                holder.close()

    @staticmethod
    def resolve_to(monkeypatch: pytest.MonkeyPatch, addresses: list[tuple[str, int]]) -> None:
        records = [stream_record(address) for address in addresses]
        monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: records)

    def test_refused_records_are_skipped(
        self,
        monkeypatch: pytest.MonkeyPatch,
        listeners: list[socket.socket],
        refusing: list[tuple[str, int]],
    ) -> None:
        good = listeners[0].getsockname()
        self.resolve_to(monkeypatch, [*refusing, good])

        with socket.create_connection(("example.test", 0), timeout=5) as client:
            assert client.getpeername() == good

    def test_later_records_are_never_tried(
        self, monkeypatch: pytest.MonkeyPatch, listeners: list[socket.socket]
    ) -> None:
        first, second = (server.getsockname() for server in listeners)
        self.resolve_to(monkeypatch, [first, second])

        with socket.create_connection(("example.test", 0), timeout=5):
            listeners[0].settimeout(5)
            accepted, _ = listeners[0].accept()
            accepted.close()
            listeners[1].setblocking(False)
            with pytest.raises(BlockingIOError):
                listeners[1].accept()

    # An IPv6 literal in an AF_INET record fails address conversion with
    # gaierror, before any lookup, so the two failures can be told apart.
    UNCONVERTIBLE = ("::1", 80)

    @pytest.mark.parametrize("unconvertible_first", [True, False])
    def test_total_failure_raises_the_last_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
        refusing: list[tuple[str, int]],
        unconvertible_first: bool,
    ) -> None:
        order = [self.UNCONVERTIBLE, refusing[0]]
        if not unconvertible_first:
            order.reverse()
        self.resolve_to(monkeypatch, order)
        expected = ConnectionRefusedError if unconvertible_first else socket.gaierror

        with pytest.raises(OSError) as caught:
            socket.create_connection(("example.test", 0), timeout=5)

        assert type(caught.value) is expected

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="all_errors was added in 3.11")
    def test_all_errors_collects_every_attempt(
        self, monkeypatch: pytest.MonkeyPatch, refusing: list[tuple[str, int]]
    ) -> None:
        self.resolve_to(monkeypatch, refusing)

        with pytest.raises(Exception) as caught:
            socket.create_connection(
                ("example.test", 0),
                timeout=5,
                all_errors=True,  # type: ignore[call-arg]
            )

        assert type(caught.value).__name__ == "ExceptionGroup"
        errors = caught.value.exceptions  # type: ignore[attr-defined]
        assert len(errors) == 2
        assert all(isinstance(error, ConnectionRefusedError) for error in errors)


class TestTimeouts:
    """Timeout accessors are O(1); the default reaches only later sockets."""

    @pytest.fixture(autouse=True)
    def _restore_default(self) -> Iterator[None]:
        original = socket.getdefaulttimeout()
        yield
        socket.setdefaulttimeout(original)

    def test_the_default_reaches_new_sockets_only(self) -> None:
        with socket.socket() as before:
            socket.setdefaulttimeout(2.5)
            with socket.socket() as after:
                assert socket.getdefaulttimeout() == 2.5
                assert after.gettimeout() == 2.5
                assert before.gettimeout() is None

    def test_blocking_is_shorthand_for_timeouts(
        self, pair: tuple[socket.socket, socket.socket]
    ) -> None:
        left, _ = pair

        left.setblocking(False)
        assert left.gettimeout() == 0.0 and left.getblocking() is False
        left.settimeout(None)
        assert left.getblocking() is True
        left.settimeout(1.0)
        assert left.getblocking() is True and left.gettimeout() == 1.0

    def test_a_positive_timeout_raises_timeout_error(
        self, pair: tuple[socket.socket, socket.socket]
    ) -> None:
        _, right = pair
        right.settimeout(0.05)

        with pytest.raises(TimeoutError):
            right.recv(1)


class TestNameResolutionOffline:
    """Resolution rows, exercised without a network: numeric hosts and the
    local services, protocols and interface tables."""

    def test_getaddrinfo_returns_a_list_and_filters_shrink_it(self) -> None:
        everything = socket.getaddrinfo("127.0.0.1", 80, flags=socket.AI_NUMERICHOST)
        streams = socket.getaddrinfo(
            "127.0.0.1", 80, socket.AF_INET, socket.SOCK_STREAM, flags=socket.AI_NUMERICHOST
        )

        assert isinstance(everything, list) and isinstance(streams, list)
        assert len(streams) < len(everything)
        assert streams[0][4] == ("127.0.0.1", 80)

    def test_numeric_host_rejects_a_name(self) -> None:
        with pytest.raises(socket.gaierror):
            socket.getaddrinfo("example.invalid", 80, flags=socket.AI_NUMERICHOST)

    def test_the_legacy_lookups_accept_numeric_hosts(self) -> None:
        assert socket.gethostbyname("127.0.0.1") == "127.0.0.1"
        name, aliases, addresses = socket.gethostbyname_ex("127.0.0.1")
        assert addresses == ["127.0.0.1"] and isinstance(aliases, list)
        flags = socket.NI_NUMERICHOST | socket.NI_NUMERICSERV
        assert socket.getnameinfo(("127.0.0.1", 80), flags) == ("127.0.0.1", "80")

    def test_services_and_protocols(self) -> None:
        assert socket.getservbyname("http", "tcp") == 80
        assert socket.getservbyport(80, "tcp") == "http"
        assert socket.getprotobyname("tcp") == 6

    def test_interfaces_round_trip(self) -> None:
        interfaces = socket.if_nameindex()

        assert interfaces
        for index, name in interfaces:
            assert socket.if_nametoindex(name) == index
            assert socket.if_indextoname(index) == name

    def test_gethostname_is_a_string(self) -> None:
        assert isinstance(socket.gethostname(), str)

    def test_getfqdn_makes_one_lookup_and_takes_the_first_dotted_alias(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []

        def fake(name: str) -> tuple[str, list[str], list[str]]:
            calls.append(name)
            return "short", ["alias", "first.example", "second.example"], ["192.0.2.1"]

        monkeypatch.setattr(socket, "gethostbyaddr", fake)

        assert socket.getfqdn("host") == "first.example"
        assert calls == ["host"]


class TestDescriptorsAndAttributes:
    """The O(1) socket-object rows, checked by what they return."""

    def test_detach_leaves_the_descriptor_open(self) -> None:
        sock = socket.socket()
        fd = sock.detach()
        try:
            assert sock.fileno() == -1
            os.fstat(fd)
        finally:
            os.close(fd)

    def test_every_duplicate_is_a_new_descriptor(
        self, pair: tuple[socket.socket, socket.socket]
    ) -> None:
        left, _ = pair
        copies = [left.dup(), socket.fromfd(left.fileno(), left.family, left.type)]
        raw = socket.dup(left.fileno())
        try:
            assert len({left.fileno(), raw, *(c.fileno() for c in copies)}) == 4
        finally:
            for copy in copies:
                copy.close()
            os.close(raw)

    def test_inheritable_flag_round_trips(self, pair: tuple[socket.socket, socket.socket]) -> None:
        left, _ = pair

        assert left.get_inheritable() is False
        left.set_inheritable(True)
        assert left.get_inheritable() is True

    def test_family_and_type_are_enum_members(self) -> None:
        with socket.socket() as sock:
            assert isinstance(sock.family, socket.AddressFamily)
            assert isinstance(sock.type, socket.SocketKind)
            assert sock.family == socket.AF_INET and isinstance(sock.proto, int)

    def test_socket_type_is_the_c_base_class(self) -> None:
        assert socket.SocketType is not socket.socket
        assert issubclass(socket.socket, socket.SocketType)

    def test_accept_returns_a_new_socket_and_the_peer(self) -> None:
        with socket.create_server(("127.0.0.1", 0)) as server:
            with socket.create_connection(server.getsockname(), timeout=5) as client:
                connection, address = server.accept()
                with connection:
                    assert address == client.getsockname()
                    assert connection.getpeername() == client.getsockname()

    def test_connect_ex_returns_the_error_number(self) -> None:
        holder, address = refusing_address()
        try:
            with socket.socket() as sock:
                assert sock.connect_ex(address) == errno.ECONNREFUSED
        finally:
            holder.close()

    def test_connect_ex_still_raises_for_a_bad_address(self) -> None:
        with socket.socket() as sock:  # AF_INET, handed an IPv6 literal
            with pytest.raises(socket.gaierror):
                sock.connect_ex(("::1", 80))

    def test_has_dualstack_ipv6_answers_a_bool(self) -> None:
        assert isinstance(socket.has_dualstack_ipv6(), bool)

    def test_sendto_and_recvfrom_carry_the_address(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
            receiver.bind(("127.0.0.1", 0))
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                sender.bind(("127.0.0.1", 0))
                assert sender.sendto(b"hello", receiver.getsockname()) == 5
                receiver.settimeout(5)
                assert receiver.recvfrom(1024) == (b"hello", sender.getsockname())

    def test_shutdown_ends_the_stream(self, pair: tuple[socket.socket, socket.socket]) -> None:
        left, right = pair

        left.shutdown(socket.SHUT_WR)

        assert right.recv(10) == b""

    def test_socket_options_round_trip(self) -> None:
        with socket.socket() as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            assert sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR) != 0
            raw = sock.getsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 4)
            assert isinstance(raw, bytes) and len(raw) == 4


class TestFileDescriptorPassing:
    """`send_fds` / `recv_fds`: the receiver gets new descriptors for the
    same open files."""

    @needs_fd_passing
    def test_a_pipe_end_crosses_the_socket(self) -> None:
        left, right = socket.socketpair(socket.AF_UNIX)
        read_end, write_end = os.pipe()
        try:
            socket.send_fds(left, [b"fd"], [read_end])
            data, fds, _, _ = socket.recv_fds(right, 1024, maxfds=1)
            try:
                assert data == b"fd" and len(fds) == 1 and fds[0] != read_end
                os.write(write_end, b"ok")
                assert os.read(fds[0], 2) == b"ok"
            finally:
                for fd in fds:
                    os.close(fd)
        finally:
            os.close(read_end)
            os.close(write_end)
            left.close()
            right.close()


class TestAfAlg:
    """`sendmsg_afalg` gathers its buffers into one kernel crypto request."""

    def test_two_buffers_encrypt_as_one_message(self) -> None:
        if not hasattr(socket, "AF_ALG"):
            pytest.skip("AF_ALG is Linux-only")
        try:
            algorithm = socket.socket(socket.AF_ALG, socket.SOCK_SEQPACKET)
        except OSError as error:
            pytest.skip(f"AF_ALG unavailable: {error}")

        def run(op: int, buffers: list[bytes]) -> bytes:
            with socket.socket(socket.AF_ALG, socket.SOCK_SEQPACKET) as base:
                base.bind(("skcipher", "ecb(aes)"))
                base.setsockopt(socket.SOL_ALG, socket.ALG_SET_KEY, bytes(16))
                request, _ = base.accept()
                with request:
                    request.sendmsg_afalg(buffers, op=op)
                    return request.recv(16)

        try:
            with algorithm:
                algorithm.bind(("skcipher", "ecb(aes)"))
        except OSError as error:
            pytest.skip(f"ecb(aes) unavailable: {error}")

        ciphertext = run(socket.ALG_OP_ENCRYPT, [b"a" * 8, b"b" * 8])

        assert ciphertext == run(socket.ALG_OP_ENCRYPT, [b"a" * 8 + b"b" * 8])
        assert run(socket.ALG_OP_DECRYPT, [ciphertext]) == b"a" * 8 + b"b" * 8


class TestConversionsAndConstants:
    """Address conversion, byte order, `CMSG_*` sizes, enums and exception
    aliases, asserted by value."""

    def test_ipv4_and_ipv6_conversions_round_trip(self) -> None:
        assert socket.inet_aton("192.168.0.1") == b"\xc0\xa8\x00\x01"
        assert socket.inet_ntoa(b"\xc0\xa8\x00\x01") == "192.168.0.1"
        packed = socket.inet_pton(socket.AF_INET6, "::1")
        assert len(packed) == 16 and socket.inet_ntop(socket.AF_INET6, packed) == "::1"

    def test_byte_order_round_trips_and_sixteen_bit_overflow(self) -> None:
        assert socket.ntohl(socket.htonl(0x01020304)) == 0x01020304
        assert socket.ntohs(socket.htons(8080)) == 8080
        with pytest.raises(OverflowError):
            socket.htons(70_000)
        with pytest.raises(OverflowError):
            socket.ntohs(70_000)

    @needs_fd_passing
    def test_cmsg_sizes_cover_their_payload(self) -> None:
        assert socket.CMSG_LEN(0) <= socket.CMSG_LEN(4) <= socket.CMSG_SPACE(4)
        assert socket.CMSG_LEN(4) - socket.CMSG_LEN(0) == 4

    def test_constants_belong_to_their_enums(self) -> None:
        assert isinstance(socket.AF_INET, socket.AddressFamily)
        assert isinstance(socket.SOCK_STREAM, socket.SocketKind)
        assert isinstance(socket.MSG_PEEK, socket.MsgFlag)
        assert isinstance(socket.AI_NUMERICHOST, socket.AddressInfo)
        assert isinstance(socket.SOL_SOCKET, int)

    def test_exception_aliases(self) -> None:
        assert socket.error is OSError
        assert socket.timeout is TimeoutError
        assert issubclass(socket.herror, OSError)
        assert issubclass(socket.gaierror, OSError)


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
        timeout=60,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess over `socketpair()` or loopback,
    with a timeout, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "len(lines) == 100" in s)
        mutated = source.replace("len(lines) == 100", "len(lines) == 99", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
