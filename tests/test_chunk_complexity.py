"""Tests for docs/stdlib/chunk.md.

The page prices a `Chunk` by the bytes it touches: building one reads the
8-byte header, `read()` reads what it returns, and `skip()` and `close()` are
one seek on a seekable file and a read of the rest of the body on an
unseekable one. Every one of those is settled by observation - a recording
file that counts the bytes read and the `seek()` and `tell()` calls made
through it - and the O(1) and O(k) space of skipping and reading by a
`tracemalloc` peak, so nothing here is timed. The module exists on Python
3.10, 3.11 and 3.12 only, so every test that touches it takes the `chunk`
fixture, which skips from 3.13; run them with one of those interpreters. Lib/chunk.py differs between
v3.10.19, v3.11.14 and v3.12.12 only in the import-time DeprecationWarning
added in 3.11: no bound moves.

Measurement scope:

* Building a `Chunk` reads exactly 4 + 4 bytes and makes one `tell()`; a
  file ending after 0, 3, 4 or 6 bytes raises `EOFError`. `getsize()` is the
  header's size, big- or little-endian, and 8 less with `inclheader=True`;
  `getname()` is the 4-byte ID as `bytes`.
* A file with no `tell()`, or one whose `tell()` raises `OSError`, makes
  `seek()` raise `OSError`, and `skip()` then reads the rest of the body; a
  file whose `tell()` and `seek()` work does not. A file whose `tell()` works
  and whose `seek()` raises `OSError` makes `Chunk.seek()` raise it, and
  `skip()` falls back to reading the rest of the body.
* On a seekable file, `skip()` over a 1,000,000-byte body reads nothing and
  makes one `seek()`; walking 10 and 1,000 chunks with bodies from 1 byte to
  100,000 bytes reads 8 bytes per chunk and seeks once per chunk. An
  odd-sized body is followed by its pad byte with `align=True` and not with
  `align=False`, on both kinds of file, whether or not `read()` consumed the
  body first.
* On an unseekable file, `skip()` after reading 1,000 of 1,000,000 body
  bytes reads exactly the other 999,000, asking for no more than 8,192
  bytes at a time, and a 10,000,000-byte skip through a reader that keeps
  no record peaks under 64 KB of traced allocation. A body cut short raises
  `EOFError`.
* `read(size)` returns min(size, r) bytes and reads that many from the
  file, plus the pad byte when it finishes an odd-sized body with
  `align=True`; `read()` returns the rest and then `b''`. Reading a
  10,000,000-byte body in 4,096-byte calls peaks under 64 KB; `read()`
  peaks over 10,000,000 bytes.
* `seek()` makes one file `seek()` and reads nothing, takes `whence` 0, 1
  and 2 relative to the body, and raises `RuntimeError` below 0 or past c.
  `tell()` after construction makes no file call.
* `close()` on a seekable file makes one `seek()` and reads nothing, on an
  unseekable one reads the rest of the body; it leaves the file open, can be
  called twice, and makes `read()`, `skip()`, `seek()`, `tell()` and
  `isatty()` raise `ValueError`. `isatty()` is `False` on an open chunk.
* The import warns on 3.11 and 3.12, not on 3.10, and raises
  `ModuleNotFoundError` from 3.13.
* Every fenced Python block runs in its own subprocess on 3.10 to 3.12, and a
  mutated assertion in one of them is asserted to fail.

Not settled here:

* The deprecation in 3.11 and the removal in 3.13 come from the 3.12
  documentation and PEP 594.
* What a particular file object's `read()`, `seek()` or `tell()` costs is
  the caller's and is not measured; only `io.BytesIO`-backed files are used,
  so a raw file's short reads are not exercised.
"""

from __future__ import annotations

import gc
import importlib
import importlib.util
import io
import pathlib
import re
import struct
import subprocess
import sys
import textwrap
import tracemalloc
import warnings
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "chunk.md"
EXPECTED_BLOCKS = 4


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs, with the collector held off."""
    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
        if was_enabled:
            gc.enable()


def make_chunk(name: bytes, body: bytes, *, big: bool = True) -> bytes:
    pad = b"\0" if len(body) % 2 else b""
    return name + struct.pack(">L" if big else "<L", len(body)) + body + pad


class Recorder:
    """A file over `data` that records every read, seek and tell made on it."""

    def __init__(self, data: bytes) -> None:
        self._f = io.BytesIO(data)
        self.reads: list[int] = []
        self.requests: list[int] = []
        self.seeks = 0
        self.tells = 0

    @property
    def closed(self) -> bool:
        return self._f.closed

    @property
    def bytes_read(self) -> int:
        return sum(self.reads)

    def read(self, size: int = -1) -> bytes:
        data = self._f.read(size)
        self.requests.append(size)
        self.reads.append(len(data))
        return data

    def seek(self, pos: int, whence: int = 0) -> int:
        self.seeks += 1
        return self._f.seek(pos, whence)

    def tell(self) -> int:
        self.tells += 1
        return self._f.tell()


class Stream:
    """A file with `read()` only, keeping no record of its calls."""

    def __init__(self, data: bytes) -> None:
        self._f = io.BytesIO(data)

    def read(self, size: int = -1) -> bytes:
        return self._f.read(size)


class Pipe(Recorder):
    """A Recorder without `tell()` or `seek()`."""

    def __getattribute__(self, name: str) -> Any:
        if name in ("tell", "seek"):
            raise AttributeError(name)
        return super().__getattribute__(name)


def test_the_module_exists_only_before_3_13() -> None:
    assert (importlib.util.find_spec("chunk") is not None) == (sys.version_info < (3, 13))


@pytest.fixture
def chunk() -> Iterator[Any]:
    if sys.version_info >= (3, 13):
        pytest.skip("version: chunk was removed in Python 3.13")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        yield importlib.import_module("chunk")


class TestAvailability:
    """`import chunk` works on 3.10 to 3.12, warning from 3.11, and fails
    from 3.13."""

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="the module exists before 3.13")
    def test_importing_it_from_3_13_raises(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("chunk")

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="chunk was removed in 3.13")
    def test_importing_it_warns_from_3_11(self) -> None:
        result = subprocess.run(
            [sys.executable, "-W", "error::DeprecationWarning", "-c", "import chunk"],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        assert (result.returncode != 0) == (sys.version_info >= (3, 11)), result.stderr
        if sys.version_info >= (3, 11):
            assert "DeprecationWarning" in result.stderr
            assert "chunk" in result.stderr


class TestConstructionReadsTheHeader:
    """`chunk.Chunk(file, ...)` | O(1) | O(1): reads the 8-byte header and
    nothing of the body, and raises `EOFError` when the header is short."""

    def test_only_the_header_is_read(self, chunk: Any) -> None:
        f = Recorder(make_chunk(b"SSND", bytes(1_000_000)))
        ck = chunk.Chunk(f)

        assert f.reads == [4, 4]
        assert f.tells == 1
        assert f.seeks == 0
        assert ck.getname() == b"SSND"
        assert ck.getsize() == 1_000_000

    @pytest.mark.parametrize("length", [0, 3, 4, 6])
    def test_a_short_header_raises_eof(self, chunk: Any, length: int) -> None:
        with pytest.raises(EOFError):
            chunk.Chunk(io.BytesIO(make_chunk(b"SSND", b"")[:length]))

    def test_byte_order_and_inclheader(self, chunk: Any) -> None:
        little = make_chunk(b"data", bytes(300), big=False)
        assert chunk.Chunk(io.BytesIO(little), bigendian=False).getsize() == 300
        swapped = struct.unpack(">L", struct.pack("<L", 300))[0]
        assert chunk.Chunk(io.BytesIO(little)).getsize() == swapped
        with_header = b"FORM" + struct.pack(">L", 308) + bytes(300)
        assert chunk.Chunk(io.BytesIO(with_header), inclheader=True).getsize() == 300

    def test_getname_is_the_id_as_bytes(self, chunk: Any) -> None:
        name = chunk.Chunk(io.BytesIO(make_chunk(b"fmt ", b""))).getname()
        assert type(name) is bytes
        assert name == b"fmt "


class TestTellDecidesSeekability:
    """A file whose `tell()` fails or is missing is treated as unseekable:
    `seek()` then raises `OSError`."""

    def test_a_file_without_tell_is_unseekable(self, chunk: Any) -> None:
        ck = chunk.Chunk(Pipe(make_chunk(b"SSND", bytes(10))))
        with pytest.raises(OSError, match="cannot seek"):
            ck.seek(0)

    def test_a_file_whose_tell_fails_is_unseekable(self, chunk: Any) -> None:
        class Failing(Recorder):
            def tell(self) -> int:
                raise OSError("no tell")

        f = Failing(make_chunk(b"SSND", bytes(10)))
        ck = chunk.Chunk(f)
        with pytest.raises(OSError, match="cannot seek"):
            ck.seek(0)
        ck.skip()
        assert f.seeks == 0
        assert f.bytes_read == 8 + 10

    def test_a_file_whose_seek_fails_falls_back_to_reading(self, chunk: Any) -> None:
        class NoSeek(Recorder):
            def seek(self, pos: int, whence: int = 0) -> int:
                self.seeks += 1
                raise OSError("no seek")

        ck = chunk.Chunk(NoSeek(make_chunk(b"SSND", bytes(10))))
        with pytest.raises(OSError, match="no seek"):
            ck.seek(0)

        f = NoSeek(make_chunk(b"SSND", bytes(100_000)))
        chunk.Chunk(f).skip()
        assert f.seeks == 1
        assert f.bytes_read == 8 + 100_000

    def test_a_file_with_tell_is_seekable(self, chunk: Any) -> None:
        ck = chunk.Chunk(Recorder(make_chunk(b"SSND", bytes(10))))
        ck.seek(5)
        assert ck.tell() == 5


class TestSkipOnASeekableFile:
    """`Chunk.skip()` | O(1) seekable: one seek, no body read, so walking n
    chunks reads 8n bytes whatever the bodies weigh."""

    def test_a_large_body_is_not_read(self, chunk: Any) -> None:
        f = Recorder(make_chunk(b"SSND", bytes(1_000_000)) + make_chunk(b"NEXT", b""))
        chunk.Chunk(f).skip()

        assert f.bytes_read == 8
        assert f.seeks == 1
        assert chunk.Chunk(f).getname() == b"NEXT"

    @pytest.mark.parametrize("count", [10, 1_000])
    def test_walking_reads_only_headers(self, chunk: Any, count: int) -> None:
        sizes = [1 + (i * 7919) % 100_000 for i in range(count)]
        f = Recorder(b"".join(make_chunk(b"ABCD", bytes(size)) for size in sizes))

        seen = []
        while True:
            try:
                ck = chunk.Chunk(f)
            except EOFError:
                break
            seen.append(ck.getsize())
            ck.skip()

        assert seen == sizes
        assert f.bytes_read == 8 * count
        assert f.seeks == count

    @pytest.mark.parametrize("seekable", [True, False])
    def test_the_pad_byte_follows_align(self, chunk: Any, seekable: bool) -> None:
        data = make_chunk(b"ODD ", b"abc") + make_chunk(b"NEXT", b"")
        kind = Recorder if seekable else Pipe
        f = kind(data)
        chunk.Chunk(f).skip()
        assert chunk.Chunk(f).getname() == b"NEXT"

        h = kind(data)
        ck = chunk.Chunk(h)
        assert ck.read() == b"abc"
        ck.skip()
        assert chunk.Chunk(h).getname() == b"NEXT"

        unpadded = b"ODD " + struct.pack(">L", 3) + b"abc" + make_chunk(b"NEXT", b"")
        g = kind(unpadded)
        chunk.Chunk(g, align=False).skip()
        assert chunk.Chunk(g).getname() == b"NEXT"


class TestSkipOnAnUnseekableFile:
    """`Chunk.skip()` | O(r) unseekable | O(1): the rest of the body is read
    in blocks of at most 8,192 bytes and discarded."""

    def test_it_reads_exactly_the_rest(self, chunk: Any) -> None:
        f = Pipe(make_chunk(b"SSND", bytes(1_000_000)))
        ck = chunk.Chunk(f)
        ck.read(1_000)
        before = len(f.reads)
        ck.skip()

        assert sum(f.reads[before:]) == 999_000
        assert max(f.requests[before:]) <= 8_192

    def test_the_peak_is_one_block(self, chunk: Any) -> None:
        data = make_chunk(b"SSND", bytes(10_000_000))

        def run() -> None:
            ck = chunk.Chunk(Stream(data))
            ck.skip()

        assert peak_bytes(run) < 64 * 1024

    def test_a_truncated_body_raises_eof(self, chunk: Any) -> None:
        ck = chunk.Chunk(Pipe(make_chunk(b"SSND", bytes(100))[:50]))
        with pytest.raises(EOFError):
            ck.skip()


class TestRead:
    """`Chunk.read(size=-1)` | O(k) | O(k), k ≤ r: it reads what it returns."""

    def test_a_sized_read_reads_what_it_returns(self, chunk: Any) -> None:
        f = Recorder(make_chunk(b"SSND", bytes(range(100))))
        ck = chunk.Chunk(f)
        before = f.bytes_read

        assert ck.read(30) == bytes(range(30))
        assert f.bytes_read - before == 30
        assert ck.read(1_000) == bytes(range(30, 100))
        assert f.bytes_read - before == 100
        assert ck.read() == b""
        assert ck.read(5) == b""

    def test_finishing_an_odd_body_also_reads_the_pad_byte(self, chunk: Any) -> None:
        f = Recorder(make_chunk(b"ODD ", b"abc") + make_chunk(b"NEXT", b""))
        ck = chunk.Chunk(f)
        before = f.bytes_read

        assert ck.read() == b"abc"
        assert f.bytes_read - before == 4
        assert chunk.Chunk(f).getname() == b"NEXT"

    def test_read_without_size_returns_the_rest(self, chunk: Any) -> None:
        f = Recorder(make_chunk(b"SSND", bytes(range(100))) + make_chunk(b"NEXT", b""))
        ck = chunk.Chunk(f)
        ck.read(40)
        assert ck.read() == bytes(range(40, 100))
        assert ck.read() == b""
        assert chunk.Chunk(f).getname() == b"NEXT"

    def test_sized_reads_hold_one_block(self, chunk: Any) -> None:
        data = make_chunk(b"SSND", bytes(10_000_000))

        def blocks() -> None:
            ck = chunk.Chunk(io.BytesIO(data))
            while ck.read(4_096):
                pass

        def whole() -> None:
            chunk.Chunk(io.BytesIO(data)).read()

        assert peak_bytes(blocks) < 64 * 1024
        assert peak_bytes(whole) > 10_000_000


class TestSeekAndTell:
    """`Chunk.seek(pos, whence=0)` and `Chunk.tell()` | O(1) | O(1): one
    file seek and no read; tell() is the chunk's own count."""

    def test_seek_is_one_file_seek(self, chunk: Any) -> None:
        f = Recorder(make_chunk(b"SSND", bytes(range(200))))
        ck = chunk.Chunk(f)
        reads = len(f.reads)

        ck.seek(150)
        assert f.seeks == 1
        assert len(f.reads) == reads
        assert ck.tell() == 150
        assert ck.read(2) == bytes([150, 151])

    def test_whence_is_relative_to_the_body(self, chunk: Any) -> None:
        ck = chunk.Chunk(io.BytesIO(make_chunk(b"SSND", bytes(range(200)))))
        ck.seek(10)
        ck.seek(5, 1)
        assert ck.tell() == 15
        ck.seek(-10, 2)
        assert ck.tell() == 190
        assert ck.read() == bytes(range(190, 200))

    @pytest.mark.parametrize("pos", [-1, 201])
    def test_outside_the_body_raises_runtime_error(self, chunk: Any, pos: int) -> None:
        ck = chunk.Chunk(io.BytesIO(make_chunk(b"SSND", bytes(200))))
        with pytest.raises(RuntimeError):
            ck.seek(pos)

    def test_tell_makes_no_file_call(self, chunk: Any) -> None:
        f = Recorder(make_chunk(b"SSND", bytes(200)))
        ck = chunk.Chunk(f)
        ck.read(20)
        calls = (len(f.reads), f.seeks, f.tells)
        assert ck.tell() == 20
        assert (len(f.reads), f.seeks, f.tells) == calls


class TestClose:
    """`Chunk.close()`: calls `skip()`, leaves the file open, and makes the
    other I/O methods raise `ValueError`."""

    def test_close_skips_and_leaves_the_file_open(self, chunk: Any) -> None:
        f = Recorder(make_chunk(b"SSND", bytes(1_000)) + make_chunk(b"NEXT", b""))
        ck = chunk.Chunk(f)
        ck.close()
        ck.close()

        assert f.bytes_read == 8
        assert f.seeks == 1
        assert not f.closed
        assert chunk.Chunk(f).getname() == b"NEXT"

    def test_close_on_a_pipe_reads_the_rest(self, chunk: Any) -> None:
        f = Pipe(make_chunk(b"SSND", bytes(100_000)))
        chunk.Chunk(f).close()
        assert f.bytes_read == 8 + 100_000

    @pytest.mark.parametrize(
        "call",
        [
            lambda ck: ck.read(),
            lambda ck: ck.skip(),
            lambda ck: ck.seek(0),
            lambda ck: ck.tell(),
            lambda ck: ck.isatty(),
        ],
    )
    def test_io_after_close_raises(self, chunk: Any, call: Callable[[Any], Any]) -> None:
        ck = chunk.Chunk(io.BytesIO(make_chunk(b"SSND", bytes(10))))
        ck.close()
        with pytest.raises(ValueError):
            call(ck)

    def test_isatty_is_false(self, chunk: Any) -> None:
        assert chunk.Chunk(io.BytesIO(make_chunk(b"SSND", b""))).isatty() is False


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
    """Each block runs in its own subprocess and asserts its own result, on
    the versions that still have the module."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        assert all("import chunk" in source for _, source in blocks)

    def test_every_block_runs(self, chunk: Any, tmp_path: pathlib.Path) -> None:
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
        self, chunk: Any, tmp_path: pathlib.Path
    ) -> None:
        line, source = next((n, s) for n, s in _blocks() if "== 8 + len(body)" in s)
        mutated = source.replace("== 8 + len(body)", "== len(body)", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
