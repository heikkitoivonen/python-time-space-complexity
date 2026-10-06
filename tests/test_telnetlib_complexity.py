"""Tests for docs/stdlib/telnetlib.md.

The page prices the client by the bytes its read methods copy: every
`recv()` asks for 50 bytes, and each chunk's data is appended to the cooked
queue by building a new `bytes`, so a method that keeps reading until it
returns copies the queue once per chunk. That is settled by observation, not
by a stopwatch: a `Telnet` subclass turns the cooked queue into a property
that adds up the length of every value assigned to it. In the read loops each
of those values is a concatenation the method has just built, so the sum
stands in for the bytes copied; it is a proxy, not an allocation count. The
module exists on Python 3.10, 3.11 and
3.12 only, so every runtime test takes the `telnetlib` fixture, which skips
from 3.13; availability itself is asserted on every version. Lib/telnetlib.py
differs between v3.10.19 and v3.12.12 only in the import-time
DeprecationWarning, which 3.11 adds, and in a class-level `sock = None`, which
3.12 adds. Connections are real loopback TCP connections built with
`socket.create_server()`; the copy counts use an in-memory socket that serves
the data 50 bytes at a time, with the descriptor of a socket that always has
a byte waiting, so `select()` reports it ready.

Measurement scope:

* Every `recv()` the read methods make asks for 50 bytes: reading 1,000
  bytes from a real connection makes at least 20 calls, each asking for 50.
* The cooked queue: reading 16,384 and 65,536 bytes, `read_all()`,
  `read_until()`, `read_very_eager()` and `expect()` each copy more than
  12x as much at the larger size, where linear gives 4x and quadratic 16x,
  and more than n²/200 bytes at 65,536. A `read_some()` loop over the same
  65,536 bytes copies at most twice the data, and no call returns more
  than 50 bytes.
* Searching: `read_until()`'s `find()` calls, observed through a `bytes`
  subclass the cooked-queue property returns, cover at most 50 bytes plus
  the length of the match per chunk, over 65,536 bytes. With the expected
  bytes split across two chunks and more data after them, `read_until()`
  stops after the second `recv()`, returns up to the match and leaves the
  rest of the chunk queued. `expect()` with three
  patterns, the matching one last, searches the whole queue with each of them
  after every chunk until one matches: the three totals are equal, and grow more than 12x from
  16,384 to 65,536 bytes. Given one chunk in which the second pattern's
  match comes before the first pattern's, the first pattern wins.
  A `str` pattern raises `TypeError`; on timeout `expect()` returns
  `(-1, None, data)`.
* `read_until()` on a timeout returns the partial data without raising; at
  end of file it returns what is queued, and raises `EOFError` only when
  nothing is. `read_some()` returns `b''` at end of file, and reads on past
  a 50-byte chunk holding only commands to the data after it. `read_all()`
  returns only once the peer closes, with data that arrives 0.3 seconds
  after the call. `read_very_eager()`
  and `read_eager()` raise `EOFError` at end of file with nothing queued;
  `read_eager()` returns at most 50 bytes when more is waiting. With
  data already cooked, `read_eager()` returns it without a `recv()`, and
  `read_very_eager()` goes on to read everything ready.
* `read_lazy()` and `read_very_lazy()` make no `recv()` call; given a raw
  queue holding data and a `DO`, `read_lazy()` returns the data and sends
  the `WONT`.
  `read_very_lazy()` returns the cooked queue object itself, and
  `read_sb_data()` the subnegotiation store object itself, and both leave
  `b''` behind.
* `write()` hands `sendall()` the caller's object when it holds no 255 byte,
  a buffer twice as long when every byte is 255, and `b"a\\xff\\xffb\\xff\\xff"`
  for `b"a\\xffb\\xff"`; a `str` raises
  `TypeError`.
* Negotiation: without a callback, `DO` and `DONT` are answered `WONT`,
  `WILL` and `WONT` are answered `DONT`. With a callback, it receives each
  negotiation, `SB` and `SE` with `NOOPT`, and `NOP`; `read_sb_data()` holds
  the subnegotiation bytes when the callback sees `SE`; nothing is sent to
  the peer within half a second.
* NUL and `\\x11` are dropped from received data, and a doubled 255 arrives as
  one.
* Debugging: at level 1 a `write()` and a received chunk each print their
  `repr()`; at level 0 `msg()` neither prints nor formats its arguments.
* Connections: `Telnet()` with no host has no socket; `open()` with port 0
  connects to 23, observed through a replaced `socket.create_connection()`;
  the timeout reaches the socket; `close()` and the `with` block close the socket and clear `sock`, and
  collecting an unreferenced `Telnet` closes its socket; a `Telnet` registers
  with a selector.
* `interact()` sends each line of standard input and returns at its end,
  prints what arrives and returns when the peer closes, and raises
  `UnicodeDecodeError` on a non-ASCII byte. `mt_interact()` returns at the
  end of standard input while its listener thread calls `read_eager()` more
  than 100 times in half a second with nothing arriving, prints what
  arrives, then prints the closed message and stops once the peer closes.
  That each poll has a zero timeout, so the loop never waits for data, is
  read from Lib/telnetlib.py (`sock_avail()` calls `select(0)`).
* The constants, and the import, which warns on 3.11 and 3.12, not on 3.10,
  and raises `ModuleNotFoundError` from 3.13.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* Time is not measured: the O(n²) rows follow from the bytes copied and
  searched, which are counted. The counts use data with no Telnet commands in
  it and chunks of exactly 50 bytes; a peer that sends less per segment makes
  the chunks smaller and the copying greater. The per-byte walk over the raw
  queue, which builds its output a byte at a time within one chunk, is read
  from Lib/telnetlib.py: a chunk is at most 50 bytes, so it is O(1) per byte.
* `write()`'s O(m) is the scan for a 255 byte and the `replace()`; that it
  blocks until `sendall()` returns is read from source. Name resolution,
  connection set-up and the kernel's cost for each system call are outside
  every bound. The examples, and the tests that compare one `recv()` with
  one `sendall()`, rely on a small send over loopback TCP being read back
  in one call; replies sent by separate `sendall()` calls are read until
  all their bytes have arrived.
* `interact()` and `mt_interact()` on Windows: `interact()` hands off to
  `mt_interact()` there, which is read from source; the tests that need
  `interact()`'s own loop to return when the peer closes, or to raise in the
  calling thread, are guarded off Windows. The suite runs these versions on
  Linux only.
* The deprecation in 3.11 and the removal in 3.13 come from the 3.12
  documentation and PEP 594.
* The page-scoped audit, run on 3.12, reports no missing names. Its
  classification list holds `Telnet.sock` and `Telnet.listener`, which the
  page prices, and these, which it leaves out: the helpers the read methods
  are built from (`fill_rawq()`, `process_rawq()`, `rawq_getchar()`,
  `sock_avail()`), and `test()`, the command-line entry point.
"""

from __future__ import annotations

import contextlib
import gc
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
import threading
import time
import warnings
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "telnetlib.md"
EXPECTED_BLOCKS = 5
CHUNK = 50


def test_the_module_exists_only_before_3_13() -> None:
    assert (importlib.util.find_spec("telnetlib") is not None) == (sys.version_info < (3, 13))


@pytest.fixture
def telnetlib() -> Iterator[Any]:
    if sys.version_info >= (3, 13):
        pytest.skip("version: telnetlib was removed in Python 3.13")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        yield importlib.import_module("telnetlib")


@pytest.fixture
def connect(telnetlib: Any) -> Iterator[Callable[..., tuple[Any, socket.socket]]]:
    """Builds `(tn, peer)` over loopback TCP, `tn` of the class given."""
    opened: list[Any] = []

    def make(cls: Any = None) -> tuple[Any, socket.socket]:
        with socket.create_server(("127.0.0.1", 0)) as server:
            tn = (cls or telnetlib.Telnet)("127.0.0.1", server.getsockname()[1], timeout=5)
            peer, _ = server.accept()
        peer.settimeout(5)
        opened.extend([tn, peer])
        return tn, peer

    yield make
    for item in opened:
        item.close()


class Tracked(bytes):
    """The cooked queue as the read methods see it: records each `find()`."""

    finds: list[tuple[int, int]]

    def find(self, sub: Any, start: Any = None, *args: Any) -> int:  # type: ignore[override]
        self.finds.append((len(self), start or 0))
        return super().find(sub, start, *args)


def counting_class(telnetlib: Any) -> Any:
    """A `Telnet` whose cooked queue adds up the bytes assigned to it."""

    class Counting(telnetlib.Telnet):
        copied = 0
        finds: list[tuple[int, int]]

        @property
        def cookedq(self) -> bytes:
            value = Tracked(self._cooked)
            value.finds = self.finds
            return value

        @cookedq.setter
        def cookedq(self, value: bytes) -> None:
            self._cooked = bytes(value)
            self.copied += len(value)

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.finds = []
            super().__init__(*args, **kwargs)

    return Counting


class MemorySocket:
    """Serves `data` 50 bytes at a time, then end of file. Its descriptor is a
    socket with a byte waiting, so a selector always finds it ready."""

    def __init__(self, data: bytes) -> None:
        self.data = data
        self.position = 0
        self.requests: list[int] = []
        self.sent: list[bytes] = []
        self._ready, self._feeder = socket.socketpair()
        self._feeder.sendall(b"!")

    def recv(self, size: int) -> bytes:
        self.requests.append(size)
        chunk = self.data[self.position : self.position + size]
        self.position += len(chunk)
        return chunk

    def sendall(self, data: bytes) -> None:
        self.sent.append(data)

    def fileno(self) -> int:
        return self._ready.fileno()

    def close(self) -> None:
        self._ready.close()
        self._feeder.close()


def over_memory(cls: Any, data: bytes) -> Any:
    tn = cls()
    tn.sock = MemorySocket(data)
    return tn


class RecordingSocket:
    """A real socket whose `recv()` sizes are recorded."""

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock
        self.requests: list[int] = []

    def recv(self, size: int) -> bytes:
        self.requests.append(size)
        return self.sock.recv(size)

    def sendall(self, data: bytes) -> None:
        self.sock.sendall(data)

    def fileno(self) -> int:
        return self.sock.fileno()

    def close(self) -> None:
        self.sock.close()


class Pattern:
    """A compiled pattern that records how much text each search covers."""

    def __init__(self, pattern: bytes) -> None:
        self.pattern = re.compile(pattern)
        self.searched = 0

    def search(self, text: bytes) -> re.Match[bytes] | None:
        self.searched += len(text)
        return self.pattern.search(text)


class TestAvailability:
    """`import telnetlib` works on 3.10 to 3.12, warning from 3.11, and fails
    from 3.13."""

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="the module exists before 3.13")
    def test_importing_it_from_3_13_raises(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("telnetlib")

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="telnetlib was removed in 3.13")
    def test_importing_it_warns_from_3_11(self) -> None:
        result = subprocess.run(
            [sys.executable, "-W", "error::DeprecationWarning", "-c", "import telnetlib"],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        assert (result.returncode != 0) == (sys.version_info >= (3, 11))
        assert ("DeprecationWarning" in result.stderr) == (sys.version_info >= (3, 11))


class TestEachRecvTakesFiftyBytes:
    """The intro and the `read_some()` row: every `recv()` asks for 50 bytes,
    so n bytes take at least n/50 calls."""

    def test_a_thousand_bytes_take_twenty_calls(
        self, connect: Callable[..., tuple[Any, socket.socket]]
    ) -> None:
        tn, peer = connect()
        recording = RecordingSocket(tn.sock)
        tn.sock = recording
        peer.sendall(b"x" * 1000)
        peer.close()

        assert tn.read_all() == b"x" * 1000
        assert len(recording.requests) >= 20
        assert set(recording.requests) == {CHUNK}


def copied_by(telnetlib: Any, n: int, read: Callable[[Any], Any]) -> int:
    tn = over_memory(counting_class(telnetlib), b"x" * n + b"END")
    try:
        read(tn)
        return tn.copied
    finally:
        tn.close()


def read_some_loop(tn: Any) -> list[bytes]:
    chunks: list[bytes] = []
    while chunk := tn.read_some():
        chunks.append(chunk)
    return chunks


class TestLongReadsAreQuadratic:
    """The O(n²) rows: `read_all()`, `read_until()`, `read_very_eager()` and
    `expect()` rebuild the cooked queue for every chunk, so the bytes they
    copy grow with the square of what they read. A `read_some()` loop, the
    page's alternative, copies each byte once."""

    @pytest.mark.parametrize(
        "read",
        [
            pytest.param(lambda tn: tn.read_all(), id="read_all"),
            pytest.param(lambda tn: tn.read_until(b"END"), id="read_until"),
            pytest.param(lambda tn: tn.read_very_eager(), id="read_very_eager"),
            pytest.param(lambda tn: tn.expect([b"END"]), id="expect"),
        ],
    )
    def test_four_times_the_data_copies_sixteen_times(
        self, telnetlib: Any, read: Callable[[Any], Any]
    ) -> None:
        small = copied_by(telnetlib, 16_384, read)
        large = copied_by(telnetlib, 65_536, read)

        assert large > 12 * small, (small, large)
        assert large > 65_536**2 / 200, large

    def test_a_read_some_loop_copies_each_byte_once(self, telnetlib: Any) -> None:
        tn = over_memory(counting_class(telnetlib), b"x" * 65_536)
        chunks = read_some_loop(tn)
        tn.close()

        assert b"".join(chunks) == b"x" * 65_536
        assert max(len(chunk) for chunk in chunks) <= CHUNK
        assert tn.copied <= 2 * 65_536, tn.copied


class TestSearching:
    """`read_until()` resumes its search near the end of the queue; `expect()`
    searches the whole queue with every pattern after every chunk, and the
    first pattern in the list that matches wins."""

    def test_read_until_stops_at_a_match_split_across_chunks(self, telnetlib: Any) -> None:
        data = b"x" * 48 + b"END" + b"y" * 200
        tn = over_memory(telnetlib.Telnet, data)
        assert tn.read_until(b"END") == b"x" * 48 + b"END"
        assert tn.sock.requests == [CHUNK, CHUNK]
        assert tn.read_very_lazy() == data[51:100]
        tn.close()

    def test_read_until_searches_each_chunk_plus_an_overlap(self, telnetlib: Any) -> None:
        tn = over_memory(counting_class(telnetlib), b"x" * 65_536 + b"END")
        assert tn.read_until(b"END").endswith(b"END")
        tn.close()

        searched = sum(length - start for length, start in tn.finds)
        assert len(tn.finds) > 65_536 // CHUNK
        assert searched <= len(tn.finds) * (CHUNK + len(b"END")), searched

    def test_expect_searches_the_whole_queue_with_every_pattern(self, telnetlib: Any) -> None:
        totals = []
        for n in (16_384, 65_536):
            patterns = [Pattern(b"never"), Pattern(b"nor this"), Pattern(b"END")]
            tn = over_memory(telnetlib.Telnet, b"x" * n + b"END")
            index, _, _ = tn.expect(patterns)
            tn.close()
            assert index == 2
            assert patterns[0].searched == patterns[1].searched == patterns[2].searched
            totals.append(patterns[0].searched)

        assert totals[1] > 12 * totals[0], totals

    def test_the_first_pattern_in_the_list_wins(self, telnetlib: Any) -> None:
        tn = over_memory(telnetlib.Telnet, b"error 42\r\n$ ")
        index, match, text = tn.expect([rb"\$ $", rb"error (\d+)"])
        tn.close()

        assert index == 0
        assert match.group() == b"$ "
        assert text == b"error 42\r\n$ "

    def test_a_str_pattern_raises(self, connect: Callable[..., tuple[Any, socket.socket]]) -> None:
        tn, _ = connect()
        with pytest.raises(TypeError, match="string pattern on a bytes-like object"):
            tn.expect(["login"], timeout=0)

    def test_expect_returns_minus_one_on_timeout(
        self, connect: Callable[..., tuple[Any, socket.socket]]
    ) -> None:
        tn, peer = connect()
        peer.sendall(b"partial")
        assert tn.expect([b"never"], timeout=0.5) == (-1, None, b"partial")


class TestWhatReadsReturn:
    """The Notes of the reading rows: what each method does at a timeout, at
    end of file, and how much it takes."""

    def test_read_until_returns_partial_data_on_timeout(
        self, connect: Callable[..., tuple[Any, socket.socket]]
    ) -> None:
        tn, peer = connect()
        peer.sendall(b"Password")
        assert tn.read_until(b"Password: ", timeout=0.5) == b"Password"

    def test_read_until_raises_at_end_of_file_only_with_nothing_queued(
        self, connect: Callable[..., tuple[Any, socket.socket]]
    ) -> None:
        tn, peer = connect()
        peer.sendall(b"last words")
        peer.close()

        assert tn.read_until(b"never") == b"last words"
        with pytest.raises(EOFError):
            tn.read_until(b"never")

    def test_read_some_reads_past_a_chunk_of_commands_only(self, telnetlib: Any) -> None:
        tn = over_memory(telnetlib.Telnet, (telnetlib.IAC + telnetlib.NOP) * 25 + b"data")
        assert tn.read_some() == b"data"
        assert tn.sock.requests == [CHUNK, CHUNK]
        tn.close()

    def test_read_all_waits_for_the_peer_to_close(
        self, connect: Callable[..., tuple[Any, socket.socket]]
    ) -> None:
        tn, peer = connect()
        peer.sendall(b"first")

        def finish() -> None:
            time.sleep(0.3)
            peer.sendall(b" second")
            peer.close()

        sender = threading.Thread(target=finish)
        sender.start()
        try:
            assert tn.read_all() == b"first second"
        finally:
            sender.join()

    def test_read_some_returns_empty_bytes_at_end_of_file(
        self, connect: Callable[..., tuple[Any, socket.socket]]
    ) -> None:
        tn, peer = connect()
        peer.close()
        assert tn.read_some() == b""
        assert tn.read_some() == b""

    @pytest.mark.parametrize("method", ["read_very_eager", "read_eager"])
    def test_eager_reads_raise_at_end_of_file(
        self, connect: Callable[..., tuple[Any, socket.socket]], method: str
    ) -> None:
        tn, peer = connect()
        peer.close()
        tn.read_some()  # reaches end of file
        with pytest.raises(EOFError):
            getattr(tn, method)()

    def test_read_eager_stops_at_the_first_chunk(self, telnetlib: Any) -> None:
        tn = over_memory(telnetlib.Telnet, b"x" * 1000)
        assert tn.read_eager() == b"x" * CHUNK
        tn.close()

    def test_with_data_cooked_read_eager_reads_nothing_and_read_very_eager_reads_on(
        self, telnetlib: Any
    ) -> None:
        tn = over_memory(telnetlib.Telnet, b"x" * 100)
        tn.cookedq = b"q"
        assert tn.read_eager() == b"q"
        assert tn.sock.requests == []
        tn.cookedq = b"q"
        assert tn.read_very_eager() == b"q" + b"x" * 100
        tn.close()

    def test_read_very_eager_reads_everything_ready(self, telnetlib: Any) -> None:
        tn = over_memory(telnetlib.Telnet, b"x" * 1000)
        assert tn.read_very_eager() == b"x" * 1000
        tn.close()


class TestQueuesWithoutIO:
    """`read_lazy()` and `read_very_lazy()` read nothing from the socket;
    `read_very_lazy()` and `read_sb_data()` hand over the stored object."""

    def test_lazy_reads_make_no_recv(self, telnetlib: Any) -> None:
        tn = over_memory(telnetlib.Telnet, b"x" * 1000)
        assert tn.read_lazy() == b""
        assert tn.read_very_lazy() == b""
        assert tn.sock.requests == []
        tn.close()

    def test_read_lazy_processes_the_raw_queue_and_answers_negotiation(
        self, telnetlib: Any
    ) -> None:
        t = telnetlib
        tn = over_memory(t.Telnet, b"never read")
        tn.rawq = b"ab" + t.IAC + t.DO + t.ECHO + b"c"
        assert tn.read_lazy() == b"abc"
        assert tn.sock.requests == []
        assert tn.sock.sent == [t.IAC + t.WONT + t.ECHO]
        tn.close()

    def test_read_very_lazy_returns_the_queue_itself(self, telnetlib: Any) -> None:
        tn = over_memory(telnetlib.Telnet, b"")
        queued = b"y" * 1000
        tn.cookedq = queued
        assert tn.read_very_lazy() is queued
        assert tn.cookedq == b""
        tn.close()

    def test_read_very_lazy_raises_when_closed_and_empty(self, telnetlib: Any) -> None:
        tn = over_memory(telnetlib.Telnet, b"")
        tn.close()
        with pytest.raises(EOFError):
            tn.read_very_lazy()

    def test_read_sb_data_returns_the_store_itself(self, telnetlib: Any) -> None:
        tn = over_memory(telnetlib.Telnet, b"")
        stored = b"z" * 1000
        tn.sbdataq = stored
        assert tn.read_sb_data() is stored
        assert tn.read_sb_data() == b""
        tn.close()


class TestWrite:
    """`write()`: copies only a buffer holding a 255 byte, and takes bytes."""

    def test_without_255_the_buffer_is_sent_as_it_is(self, telnetlib: Any) -> None:
        tn = over_memory(telnetlib.Telnet, b"")
        buffer = b"a" * 100_000
        tn.write(buffer)
        assert tn.sock.sent[0] is buffer
        tn.close()

    def test_only_the_255_bytes_are_doubled(self, telnetlib: Any) -> None:
        tn = over_memory(telnetlib.Telnet, b"")
        tn.write(b"a\xffb\xff")
        assert tn.sock.sent == [b"a\xff\xffb\xff\xff"]
        tn.close()

    def test_each_255_is_doubled(self, telnetlib: Any) -> None:
        tn = over_memory(telnetlib.Telnet, b"")
        tn.write(b"\xff" * 100_000)
        assert tn.sock.sent[0] == b"\xff" * 200_000
        tn.close()

    def test_a_str_raises(self, telnetlib: Any) -> None:
        tn = over_memory(telnetlib.Telnet, b"")
        with pytest.raises(TypeError):
            tn.write("text")
        tn.close()


class TestNegotiation:
    """`set_option_negotiation_callback()`: without a callback every option is
    refused; with one, it sees every command and nothing is sent for it."""

    def test_every_option_is_refused_by_default(
        self, telnetlib: Any, connect: Callable[..., tuple[Any, socket.socket]]
    ) -> None:
        t = telnetlib
        tn, peer = connect()
        peer.sendall(
            t.IAC + t.DO + t.ECHO + t.IAC + t.DONT + t.NAWS
            + t.IAC + t.WILL + t.SGA + t.IAC + t.WONT + t.TTYPE + b"ok"
        )  # fmt: skip
        assert tn.read_until(b"ok", timeout=5) == b"ok"

        expected = (
            t.IAC + t.WONT + t.ECHO + t.IAC + t.WONT + t.NAWS
            + t.IAC + t.DONT + t.SGA + t.IAC + t.DONT + t.TTYPE
        )  # fmt: skip
        received = b""
        while len(received) < len(expected):
            received += peer.recv(100)
        assert received == expected

    def test_a_callback_sees_every_command_and_nothing_is_sent(
        self, telnetlib: Any, connect: Callable[..., tuple[Any, socket.socket]]
    ) -> None:
        t = telnetlib
        tn, peer = connect()
        seen: list[tuple[bytes, bytes, bytes | None]] = []

        def callback(sock: Any, command: bytes, option: bytes) -> None:
            assert sock is tn.sock
            seen.append((command, option, tn.read_sb_data() if command == t.SE else None))

        tn.set_option_negotiation_callback(callback)
        peer.sendall(
            t.IAC + t.DO + t.ECHO + t.IAC + t.WILL + t.SGA
            + t.IAC + t.SB + t.TTYPE + b"\x01" + t.IAC + t.SE + t.IAC + t.NOP + b"ok"
        )  # fmt: skip
        assert tn.read_until(b"ok", timeout=5) == b"ok"

        assert seen == [
            (t.DO, t.ECHO, None),
            (t.WILL, t.SGA, None),
            (t.SB, t.NOOPT, None),
            (t.SE, t.NOOPT, t.TTYPE + b"\x01"),
            (t.NOP, t.NOOPT, None),
        ]
        peer.settimeout(0.5)
        with pytest.raises(TimeoutError):
            peer.recv(100)


class TestBytesTheClientRewrites:
    def test_nul_and_dc1_are_dropped_and_a_doubled_255_is_one(
        self, connect: Callable[..., tuple[Any, socket.socket]]
    ) -> None:
        tn, peer = connect()
        peer.sendall(b"\x00a\x00b\x11c\xff\xffd\x11!")
        assert tn.read_until(b"!", timeout=5) == b"abc\xffd!"


class TestDebugging:
    """`set_debuglevel()` and `msg()`."""

    def test_level_one_prints_each_send_and_chunk(
        self, connect: Callable[..., tuple[Any, socket.socket]]
    ) -> None:
        tn, peer = connect()
        tn.set_debuglevel(1)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            tn.write(b"abc")
            peer.sendall(b"zz")
            tn.read_until(b"zz", timeout=5)

        lines = out.getvalue().splitlines()
        assert [line.split(": ", 1)[1] for line in lines] == ["send b'abc'", "recv b'zz'"]

    def test_msg_formats_and_prints_only_above_zero(self, telnetlib: Any) -> None:
        class Unformattable:
            def __repr__(self) -> str:
                raise AssertionError("formatted at level 0")

        tn = telnetlib.Telnet()
        assert tn.debuglevel == telnetlib.DEBUGLEVEL == 0
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            tn.msg("value %r", Unformattable())
            assert out.getvalue() == ""
            tn.set_debuglevel(1)
            tn.msg("value %r", 42)
        assert out.getvalue().endswith(": value 42\n")


class TestConnections:
    """The constructor, `open()`, `close()` and the socket accessors."""

    def test_without_a_host_there_is_no_socket(self, telnetlib: Any) -> None:
        tn = telnetlib.Telnet()
        assert tn.sock is None
        assert tn.get_socket() is None

    def test_port_zero_means_23(self, telnetlib: Any, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[tuple[Any, ...]] = []
        monkeypatch.setattr(
            telnetlib.socket, "create_connection", lambda *args: calls.append(args) or None
        )
        telnetlib.Telnet("host.invalid")
        assert [address for address, _ in calls] == [("host.invalid", telnetlib.TELNET_PORT)]
        assert telnetlib.TELNET_PORT == 23

    def test_the_timeout_reaches_the_socket(
        self, connect: Callable[..., tuple[Any, socket.socket]]
    ) -> None:
        tn, _ = connect()
        assert tn.get_socket().gettimeout() == 5
        assert tn.fileno() == tn.sock.fileno()

    def test_close_and_with_close_the_socket(
        self, connect: Callable[..., tuple[Any, socket.socket]]
    ) -> None:
        tn, _ = connect()
        sock = tn.get_socket()
        tn.close()
        assert tn.sock is None
        assert sock.fileno() == -1

        tn, _ = connect()
        with tn as same:
            assert same is tn
            sock = tn.get_socket()
        assert tn.sock is None
        assert sock.fileno() == -1

    def test_garbage_collection_closes_the_socket(self, telnetlib: Any) -> None:
        with socket.create_server(("127.0.0.1", 0)) as server:
            tn = telnetlib.Telnet("127.0.0.1", server.getsockname()[1])
            sock = tn.get_socket()
            del tn
            gc.collect()
            assert sock.fileno() == -1

    def test_a_telnet_registers_with_a_selector(
        self, connect: Callable[..., tuple[Any, socket.socket]]
    ) -> None:
        tn, peer = connect()
        peer.sendall(b"ready")
        with selectors.DefaultSelector() as selector:
            selector.register(tn, selectors.EVENT_READ)
            assert [key.fileobj for key, _ in selector.select(5)] == [tn]


@pytest.fixture
def stdin_pipe(monkeypatch: pytest.MonkeyPatch) -> Iterator[int]:
    """Standard input as a pipe; yields the write end's descriptor."""
    read_end, write_end = os.pipe()
    stdin = os.fdopen(read_end, "r")
    monkeypatch.setattr(sys, "stdin", stdin)
    yield write_end
    stdin.close()
    with contextlib.suppress(OSError):
        os.close(write_end)


class TestInteract:
    """`interact()` and `mt_interact()`."""

    def test_interact_sends_each_line_and_returns_at_the_end_of_input(
        self, connect: Callable[..., tuple[Any, socket.socket]], stdin_pipe: int
    ) -> None:
        tn, peer = connect()
        os.write(stdin_pipe, b"one\ntwo\n")
        os.close(stdin_pipe)
        tn.interact()

        received = b""
        while len(received) < len(b"one\ntwo\n"):
            received += peer.recv(100)
        assert received == b"one\ntwo\n"

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="on Windows interact() runs mt_interact(), which reads in another thread",
    )
    def test_interact_prints_and_returns_when_the_peer_closes(
        self, connect: Callable[..., tuple[Any, socket.socket]], stdin_pipe: int
    ) -> None:
        tn, peer = connect()
        peer.sendall(b"hello")
        peer.close()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            tn.interact()
        assert out.getvalue() == "hello*** Connection closed by remote host ***\n"

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="on Windows interact() runs mt_interact(), which reads in another thread",
    )
    def test_interact_raises_on_a_non_ascii_byte(
        self, connect: Callable[..., tuple[Any, socket.socket]], stdin_pipe: int
    ) -> None:
        tn, peer = connect()
        peer.sendall(b"caf\xc3\xa9")
        with contextlib.redirect_stdout(io.StringIO()), pytest.raises(UnicodeDecodeError):
            tn.interact()

    def test_mt_interacts_listener_polls_until_the_peer_closes(
        self,
        telnetlib: Any,
        connect: Callable[..., tuple[Any, socket.socket]],
        stdin_pipe: int,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        class Polling(telnetlib.Telnet):
            polls = 0

            def read_eager(self) -> bytes:
                self.polls += 1
                return super().read_eager()

        out = io.StringIO()
        monkeypatch.setattr(sys, "stdout", out)
        tn, peer = connect(Polling)
        os.write(stdin_pipe, b"hi\n")
        os.close(stdin_pipe)
        tn.mt_interact()  # returns at the end of standard input
        assert peer.recv(100) == b"hi\n"

        before = tn.polls
        time.sleep(0.5)
        assert tn.polls - before > 100, tn.polls - before

        peer.sendall(b"data")
        deadline = time.monotonic() + 10
        while "data" not in out.getvalue() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert out.getvalue() == "data"
        peer.close()
        deadline = time.monotonic() + 10
        while "Connection closed" not in out.getvalue() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert out.getvalue() == "data*** Connection closed by remote host ***\n"
        settled = tn.polls
        time.sleep(0.2)
        assert tn.polls == settled


class TestConstants:
    def test_the_values(self, telnetlib: Any) -> None:
        t = telnetlib
        assert (t.TELNET_PORT, t.DEBUGLEVEL) == (23, 0)
        assert (t.IAC, t.NOOPT, t.ECHO) == (b"\xff", b"\x00", b"\x01")
        commands = [t.IAC, t.DO, t.DONT, t.WILL, t.WONT, t.SB, t.SE, t.NOP]
        commands += [t.DM, t.BRK, t.IP, t.AO, t.AYT, t.EC, t.EL, t.GA]
        options = [t.ECHO, t.SGA, t.TTYPE, t.NAWS, t.LINEMODE, t.NOOPT]
        assert all(type(code) is bytes and len(code) == 1 for code in commands + options)
        assert len(set(commands)) == len(commands)


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
    """Each block runs in its own subprocess and working directory on the
    versions that still have the module, and asserts its own result."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        assert all("import telnetlib" in source for _, source in blocks)

    def test_every_block_runs(self, telnetlib: Any, tmp_path: pathlib.Path) -> None:
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

    def test_the_runner_notices_a_broken_assertion(
        self, telnetlib: Any, tmp_path: pathlib.Path
    ) -> None:
        line, source = next((n, s) for n, s in _blocks() if "read_some()" in s)
        mutated = source.replace("<= 50", "< 50", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
