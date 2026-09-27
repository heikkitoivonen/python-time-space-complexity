"""Tests for docs/stdlib/asynchat.md.

The page prices the module by the bytes it copies: a read is walked once and
sliced at each terminator, a push is chunked once, and a send step moves one
chunk. The module exists on Python 3.10 and 3.11 only, so every runtime test
takes the `asynchat` fixture, which skips from 3.12, and CI's 3.10 and 3.11
jobs are where they run; availability itself is asserted on every version.
The released Lib/asynchat.py differs between v3.10.19 and v3.11.14 only in how
its import-time DeprecationWarning is raised. Copies are settled by observation
rather than timing: a proper slice of a `bytes` object two or more bytes long
is a new object of that length, so the length of each such remainder the
channel creates is the number of bytes it copied. Channels are built on `socket.socketpair()` with a private map, and
`recv` and `send` are replaced on the instance where a test needs to choose
what arrives or how much leaves.

Measurement scope:

* `handle_read()` is fed one read of m two-byte messages (`b"x\\n" * m`) for m
  of 10, 100 and 1,000. `found_terminator()` records the length of the input
  buffer it sees, which is the slice made for that terminator: they sum to
  exactly m·(m − 1) bytes, quadratic in m at a fixed message size, and every
  message reaches `collect_incoming_data()` as its own piece. A read of
  65,536 bytes with no terminator reaches `collect_incoming_data()` as one
  piece with nothing kept.
* Between reads the channel keeps only a partial terminator: with
  `b"\\r\\n.\\r\\n"` and input ending `b"\\r\\n."`, those three bytes are kept and
  the rest collected. A message split across two reads reaches
  `collect_incoming_data()` in two calls and `found_terminator()` once.
* An int terminator is observed to fire after that many bytes, to be left at
  0, and to collect everything after it, including across a later read;
  `None` collects everything; a negative count raises `ValueError`.
* `find_prefix_at_end()` is called with a `bytes` subclass whose `endswith`
  counts its calls: on a miss against a 1,000-byte needle it tries all 999
  proper prefixes, longest first, which with each prefix up to t bytes long
  is the O(t²) bound; a hit returns the matched length.
* `push()` over 3·b + 5 bytes with a `send` that accepts nothing queues four
  chunks of b, b, b and 5 bytes, none of them the pushed object, after one
  `send`; data of exactly b bytes is queued as the same object; `str` raises
  `TypeError`, with `use_encoding` set too.
* `initiate_send()` is observed to call `send` once per call on a queue of
  blocked `bytes` chunks, not at all once the queue is empty, and once after
  calling `more()` on an exhausted producer and on the live one behind it in
  the same call. A producer returning one chunk of 4·b bytes, drained by a `send` that
  accepts b, leaves a new head of 3·b, 2·b and b bytes after successive calls,
  so each step copies the chunk's remainder. `push_with_producer()` calls
  `more()` once when the producer reaches the head and not at all while
  pushed data is ahead of it.
* `simple_producer.more()` over 100,000 `bytes` leaves a new `bytes` object of
  the remaining 99,488 bytes; over a `memoryview` of the same data it leaves a
  view of the original object and returns a view.
* A channel built with a socket is the only entry in its map, and one built
  without is not registered. `close_when_done()` behind a blocked send leaves
  the channel registered, and closes it and empties its map once the queue
  drains; `discard_buffers()` empties the queue and the kept partial
  terminator. The two buffer sizes are 65536; `readable()` is always true and
  `writable()` follows the queue; `use_encoding` encodes a `str` terminator
  with Latin-1, so `set_terminator()` then costs O(t) for the encoding.
* Every fenced Python block runs in its own subprocess. The four that import
  `asynchat` run on 3.10 and 3.11 only; the `asyncio` one runs everywhere and
  carries the runner's mutation check.

Not settled here:

* The deprecation in 3.6 and the removal in 3.12 come from the 3.11
  documentation and PEP 594. The import warning is asserted on 3.10 and 3.11;
  that it starts at 3.10 is read from Lib/asynchat.py at v3.9.0 and v3.10.0,
  since 3.9 is not supported. `ModuleNotFoundError` from 3.12 is asserted.
* The `t²` term of `handle_read()` is `find_prefix_at_end()`, settled by its
  own test above; `handle_read()` is not varied in t, the r·m copying is
  observed for bytes terminators only (an int terminator slices the rest of
  the read the same way in Lib/asynchat.py), and `bytes.find` is taken as
  linear in the bytes it scans.
* Construction, `set_terminator()`, `get_terminator()`, `close_when_done()`,
  `readable()`, `writable()` and `handle_close()` are O(1) by
  Lib/asynchat.py and Lib/asyncore.py: each is a fixed number of attribute,
  dict and deque operations, except that `set_terminator()` encodes a `str`
  terminator when `use_encoding` is set. `discard_buffers()` is O(q) as
  `deque.clear()`; it also empties the list filled by the private
  `_collect_incoming_data()` helper, which the page does not document and
  which stays empty unless a subclass calls that helper.
* The kernel's cost for `send()` and `recv()` is outside the bounds. The page's
  examples rely on a small send over a Linux `AF_UNIX` socket pair being
  accepted whole and read back in one `recv()`, which is the only platform
  they run on here. Socket buffer sizes, non-`bytes` data other than `memoryview`, and the
  cost of the caller's callbacks are not varied.
* The module imports `asyncore` and `collections.deque`; those names are not
  part of its API. Inherited `asyncore.dispatcher` methods belong to
  docs/stdlib/asyncore.md.
"""

from __future__ import annotations

import importlib
import importlib.util
import pathlib
import re
import socket
import subprocess
import sys
import textwrap
import warnings
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "asynchat.md"
EXPECTED_BLOCKS = 5
BUFFER = 65536


def test_the_module_exists_only_before_3_12() -> None:
    assert (importlib.util.find_spec("asynchat") is not None) == (sys.version_info < (3, 12))


@pytest.fixture
def asynchat() -> Iterator[Any]:
    if sys.version_info >= (3, 12):
        pytest.skip("asynchat was removed in Python 3.12")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        yield importlib.import_module("asynchat")


@pytest.fixture
def channel(asynchat: Any) -> Iterator[Callable[..., Any]]:
    """Build a recording `async_chat` on one end of a socket pair."""
    built: list[Any] = []

    class Recorder(asynchat.async_chat):
        def __init__(self, sock: socket.socket, channels: dict[int, Any]) -> None:
            super().__init__(sock, channels)
            self.pieces: list[bytes] = []
            self.buffers: list[int] = []

        def collect_incoming_data(self, data: bytes) -> None:
            self.pieces.append(data)

        def found_terminator(self) -> None:
            self.buffers.append(len(self.ac_in_buffer))

    def build(terminator: Any = b"\n") -> Any:
        ours, theirs = socket.socketpair()
        chat = Recorder(ours, {})
        chat.set_terminator(terminator)
        built.append((chat, theirs))
        return chat

    yield build
    for chat, theirs in built:
        chat.close()
        theirs.close()


def feed(chat: Any, *reads: bytes) -> None:
    """Run one `handle_read()` per argument, each receiving exactly those bytes."""
    for data in reads:
        chat.recv = lambda size, data=data: data
        chat.handle_read()


def blocked_send(chat: Any, accept: int = 0) -> list[bytes]:
    """Replace `send` with one that records its argument and accepts `accept` bytes."""
    sent: list[bytes] = []

    def send(data: bytes) -> int:
        sent.append(data)
        return min(accept, len(data))

    chat.send = send
    return sent


class TestAvailability:
    """`import asynchat` works on 3.10 and 3.11 and fails from 3.12."""

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="the module exists before 3.12")
    def test_importing_it_from_3_12_raises(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("asynchat")

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="asynchat was removed in 3.12")
    def test_importing_it_warns(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delitem(sys.modules, "asynchat", raising=False)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            importlib.import_module("asynchat")
        assert any(
            issubclass(w.category, DeprecationWarning) and "asynchat" in str(w.message)
            for w in caught
        )


class TestReadingKeepsNoMessage:
    """Input reaches `collect_incoming_data()` as it arrives; between reads the
    channel keeps at most a partial terminator, not the message."""

    def test_a_split_message_arrives_in_two_pieces(self, channel: Callable[..., Any]) -> None:
        chat = channel(b"\r\n")
        feed(chat, b"HELLO\r\nWOR")
        assert chat.pieces == [b"HELLO", b"WOR"] and chat.buffers == [3]
        feed(chat, b"LD\r\n")
        assert chat.pieces == [b"HELLO", b"WOR", b"LD"] and len(chat.buffers) == 2
        assert chat.ac_in_buffer == b""

    def test_only_a_partial_terminator_is_kept(self, channel: Callable[..., Any]) -> None:
        chat = channel(b"\r\n.\r\n")
        feed(chat, b"line one\r\nline two\r\n.")
        assert chat.pieces == [b"line one\r\nline two"]
        assert chat.ac_in_buffer == b"\r\n."
        feed(chat, b"\r\n")
        assert chat.buffers == [0]

    def test_a_read_without_a_terminator_is_passed_on_whole(
        self, channel: Callable[..., Any]
    ) -> None:
        chat = channel(b"\r\n")
        data = b"x" * BUFFER
        feed(chat, data)
        assert chat.pieces == [data] and chat.ac_in_buffer == b""

    def test_none_collects_everything(self, channel: Callable[..., Any]) -> None:
        chat = channel(None)
        feed(chat, b"a\r\nb\r\n")
        assert chat.pieces == [b"a\r\nb\r\n"] and chat.buffers == []


class TestIntTerminatorsCountDown:
    """An int terminator counts down, fires once, and is left at 0, which then
    collects everything until another terminator is set."""

    def test_it_fires_after_the_count_and_is_left_at_zero(
        self, channel: Callable[..., Any]
    ) -> None:
        chat = channel(5)
        feed(chat, b"abc")
        assert chat.get_terminator() == 2 and chat.buffers == []
        feed(chat, b"defgh")
        assert chat.pieces == [b"abc", b"de", b"fgh"] and len(chat.buffers) == 1
        assert chat.get_terminator() == 0
        feed(chat, b"\r\nmore")
        assert chat.pieces[3:] == [b"\r\nmore"] and len(chat.buffers) == 1

    def test_a_negative_count_is_rejected(self, channel: Callable[..., Any]) -> None:
        chat = channel()
        with pytest.raises(ValueError, match="positive"):
            chat.set_terminator(-1)
        assert chat.get_terminator() == b"\n"


class TestManySmallMessagesCopyTheRest:
    """`handle_read()` is O(r·(m + 1) + t²): each terminator matched slices the
    rest of the read into a new buffer. The recorded buffer lengths are those
    slices, so their sum is the bytes copied; for m two-byte messages it is
    m·(m − 1), which a single pass over r would keep at O(m)."""

    @pytest.mark.parametrize("messages", [10, 100, 1_000])
    def test_the_copied_bytes_grow_with_messages_times_the_read(
        self, channel: Callable[..., Any], messages: int
    ) -> None:
        chat = channel(b"\n")
        feed(chat, b"x\n" * messages)
        assert chat.pieces == [b"x"] * messages
        assert chat.buffers == [2 * (messages - k) for k in range(1, messages + 1)]
        assert sum(chat.buffers) == messages * (messages - 1)


class TestFindPrefixAtEnd:
    """O(t²): it tries each proper prefix of the needle, longest first."""

    class CountingBytes(bytes):
        calls: list[int]

        def endswith(self, suffix: Any, *args: Any) -> bool:
            self.calls.append(len(suffix))
            return super().endswith(suffix, *args)

    def _haystack(self, data: bytes) -> CountingBytes:
        haystack = self.CountingBytes(data)
        haystack.calls = []
        return haystack

    def test_a_miss_tries_every_proper_prefix(self, asynchat: Any) -> None:
        needle = bytes(range(250)) * 4
        haystack = self._haystack(b"no match here")
        assert asynchat.find_prefix_at_end(haystack, needle) == 0
        assert haystack.calls == list(range(len(needle) - 1, 0, -1))

    def test_a_hit_returns_the_matched_length(self, asynchat: Any) -> None:
        haystack = self._haystack(b"data\r\n.")
        assert asynchat.find_prefix_at_end(haystack, b"\r\n.\r\n") == 3
        assert haystack.calls == [4, 3]
        assert asynchat.find_prefix_at_end(b"data\r", b"\r\n") == 1


class TestPushChunksOnce:
    """`push()` is O(n): bytes longer than b are copied into b-byte chunks up
    front, shorter data is queued as is, and one send is attempted."""

    def test_long_data_is_copied_into_chunks(self, channel: Callable[..., Any]) -> None:
        chat = channel()
        sent = blocked_send(chat)
        data = b"y" * (3 * BUFFER + 5)
        chat.push(data)
        assert [len(chunk) for chunk in chat.producer_fifo] == [BUFFER] * 3 + [5]
        assert all(chunk is not data for chunk in chat.producer_fifo)
        assert len(sent) == 1

    def test_short_data_is_queued_as_is(self, channel: Callable[..., Any]) -> None:
        chat = channel()
        blocked_send(chat)
        data = b"y" * BUFFER
        chat.push(data)
        assert list(chat.producer_fifo) == [data] and chat.producer_fifo[0] is data

    def test_str_is_rejected(self, channel: Callable[..., Any]) -> None:
        chat = channel()
        with pytest.raises(TypeError):
            chat.push("text")
        chat.use_encoding = 1
        with pytest.raises(TypeError):
            chat.push("text")


class TestSendingMovesOneChunk:
    """`initiate_send()` and `handle_write()` are O(b) per call: at most one send
    each; a producer chunk longer than b is re-sliced after every send."""

    def test_one_send_per_call(self, channel: Callable[..., Any]) -> None:
        chat = channel()
        sent = blocked_send(chat)
        chat.push(b"y" * (4 * BUFFER))
        for calls in range(2, 5):
            chat.initiate_send()
            assert len(sent) == calls
        chat.handle_write()
        assert len(sent) == 5 and all(len(data) == BUFFER for data in sent)
        chat.discard_buffers()
        chat.initiate_send()
        assert len(sent) == 5

    def test_exhausted_producers_are_skipped_before_the_one_send(
        self, channel: Callable[..., Any]
    ) -> None:
        calls: list[str] = []

        class Empty:
            def more(self) -> bytes:
                calls.append("empty")
                return b""

        class Live:
            def more(self) -> bytes:
                calls.append("live")
                return b"data"

        chat = channel()
        blocked_send(chat)
        chat.push(b"ahead")
        chat.push_with_producer(Empty())
        chat.push_with_producer(Live())
        sent = blocked_send(chat, accept=BUFFER)
        chat.initiate_send()
        assert sent == [b"ahead"] and calls == []
        chat.initiate_send()
        assert sent == [b"ahead", b"data"] and calls == ["empty", "live"]

    def test_a_long_producer_chunk_is_re_sliced_after_each_send(
        self, channel: Callable[..., Any]
    ) -> None:
        class OneChunk:
            def __init__(self, data: bytes) -> None:
                self.data = data

            def more(self) -> bytes:
                data, self.data = self.data, b""
                return data

        chat = channel()
        sent = blocked_send(chat, accept=BUFFER)
        chunk = b"z" * (4 * BUFFER)
        chat.push_with_producer(OneChunk(chunk))
        heads = [chat.producer_fifo[0]]
        for _ in range(2):
            chat.initiate_send()
            heads.append(chat.producer_fifo[0])
        assert [len(head) for head in heads] == [3 * BUFFER, 2 * BUFFER, BUFFER]
        assert all(head is not chunk for head in heads)
        assert len({id(head) for head in heads}) == len(heads)
        assert [len(data) for data in sent] == [BUFFER] * 3

    def test_more_is_called_only_at_the_head_of_the_queue(
        self, channel: Callable[..., Any]
    ) -> None:
        calls: list[int] = []

        class Counting:
            def more(self) -> bytes:
                calls.append(1)
                return b"p" * 10 if len(calls) < 3 else b""

        chat = channel()
        sent = blocked_send(chat)
        chat.push(b"ahead")
        chat.push_with_producer(Counting())
        assert calls == [] and len(sent) == 2
        blocked_send(chat, accept=BUFFER)
        chat.initiate_send()
        assert calls == []
        chat.initiate_send()
        assert calls == [1]
        chat.initiate_send()
        assert calls == [1, 1]


class TestSimpleProducerCopiesTheRemainder:
    """`simple_producer.more()` is O(n) on bytes: the unsent remainder becomes a
    new object. Over a `memoryview` the remainder is a view."""

    def test_bytes_are_copied(self, asynchat: Any) -> None:
        data = b"z" * 100_000
        producer = asynchat.simple_producer(data, buffer_size=512)
        assert producer.data is data
        assert producer.more() == b"z" * 512
        assert type(producer.data) is bytes and producer.data is not data
        assert len(producer.data) == 100_000 - 512

    def test_a_memoryview_is_not_copied(self, asynchat: Any) -> None:
        data = b"z" * 100_000
        producer = asynchat.simple_producer(memoryview(data), buffer_size=512)
        first = producer.more()
        assert isinstance(first, memoryview) and first.obj is data
        assert isinstance(producer.data, memoryview) and producer.data.obj is data
        assert len(producer.data) == 100_000 - 512

    def test_it_ends_with_empty_bytes(self, asynchat: Any) -> None:
        producer = asynchat.simple_producer(b"abc", buffer_size=2)
        assert [producer.more() for _ in range(3)] == [b"ab", b"c", b""]


class TestQueueAndAttributes:
    """Registration, closing when drained, discarding the queue, the buffer
    sizes, the readiness predicates and `use_encoding`, observed."""

    def test_close_when_done_closes_after_the_queue(self, asynchat: Any) -> None:
        channels: dict[int, Any] = {}
        ours, theirs = socket.socketpair()
        try:
            chat = asynchat.async_chat(ours, channels)
            assert list(channels.values()) == [chat]
            blocked = blocked_send(chat)
            chat.push(b"last words")
            chat.close_when_done()
            assert list(chat.producer_fifo) == [b"last words", None]
            chat.initiate_send()
            assert len(blocked) == 2 and list(channels.values()) == [chat]
            del chat.send
            chat.initiate_send()
            assert list(channels.values()) == [chat]
            chat.initiate_send()
            assert channels == {} and theirs.recv(100) == b"last words"
        finally:
            ours.close()
            theirs.close()

    def test_discard_buffers_empties_everything(self, channel: Callable[..., Any]) -> None:
        chat = channel(b"\r\n")
        blocked_send(chat)
        chat.push(b"y" * (3 * BUFFER))
        feed(chat, b"partial\r")
        assert chat.ac_in_buffer == b"\r" and len(chat.producer_fifo) == 3
        chat.discard_buffers()
        assert chat.ac_in_buffer == b"" and len(chat.producer_fifo) == 0

    def test_buffer_sizes(self, asynchat: Any) -> None:
        assert asynchat.async_chat.ac_in_buffer_size == BUFFER
        assert asynchat.async_chat.ac_out_buffer_size == BUFFER

    def test_readiness(self, channel: Callable[..., Any]) -> None:
        chat = channel()
        assert chat.readable() and not chat.writable()
        blocked_send(chat)
        chat.push(b"x")
        assert chat.writable()
        chat.discard_buffers()
        assert not chat.writable()
        chat.handle_close()
        assert chat.readable() and chat.writable()

    def test_use_encoding_encodes_a_str_terminator(self, channel: Callable[..., Any]) -> None:
        chat = channel()
        assert chat.use_encoding == 0 and chat.encoding == "latin-1"
        chat.set_terminator("\r\n")
        assert chat.get_terminator() == "\r\n"
        chat.use_encoding = 1
        chat.set_terminator("é\n")
        assert chat.get_terminator() == b"\xe9\n"

    def test_a_channel_without_a_socket_is_not_registered(self, asynchat: Any) -> None:
        channels: dict[int, Any] = {}
        asynchat.async_chat(map=channels)
        assert channels == {}

    def test_the_default_callbacks_raise(self, asynchat: Any) -> None:
        chat = asynchat.async_chat(map={})
        with pytest.raises(NotImplementedError):
            chat.collect_incoming_data(b"x")
        with pytest.raises(NotImplementedError):
            chat.found_terminator()


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
    blocks that import `asynchat` need 3.10 or 3.11."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        assert sum("import asynchat" in source for _, source in blocks) == EXPECTED_BLOCKS - 1

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            if "import asynchat" in source and sys.version_info >= (3, 12):
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
        line, source = next((n, s) for n, s in _blocks() if "readuntil" in s)
        mutated = source.replace(r'[b"HELLO\r\n", b"WORLD\r\n"]', r'[b"HELLO\r\n"]', 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
