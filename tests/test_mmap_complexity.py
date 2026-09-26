"""Tests for docs/stdlib/mmap.md.

The page prices a mapping by the bytes and pages a call touches: building one
reads nothing, the calls that return data copy exactly what they return, the
calls that write copy in place, and the calls that hand pages back to the
kernel cost the pages the process touched. Laziness is settled by counting
minor page faults, which separates "no page" from "every page" with no
tolerance; copies are settled by traced allocation; the search and scan bounds
by timing at sizes chosen so the excluded shape would differ by orders of
magnitude; behaviour rows by observation.

Measurement scope:

* Construction faults no page: `mmap.mmap(-1, 256 MiB)` and a map over a
  sparse 256 MiB file each add fewer than 64 minor faults, against the 65,536
  pages the length spans. Touching every page of a 16 MiB map advised
  `MADV_NOHUGEPAGE` adds at least one fault per two pages, which is the
  control. `MAP_POPULATE` construction over 16 MiB adds at least one fault per
  two pages. A timing test maps 1 MiB and 1 GiB of anonymous memory and asserts
  the larger costs under 10x the smaller, where touching them would cost
  1,024x. Linux only: the fault counter is `ru_minflt`.
* `close()` over 256 MiB with every page touched costs over 8x `close()` over
  16 MiB touched the same way, and over 20x `close()` over 256 MiB untouched,
  so the bound is the touched pages, not the length. Measured on Linux with
  `MADV_NOHUGEPAGE`.
* `read(k)`, `mm[i:j]` and `readline()` peak within 4 KiB of the bytes they
  return, measured at 1 MiB and 64 KiB; `write()` and `move()` of 1 MiB, and
  `find()` over 16 MiB, peak under 4 KiB. `memoryview(mm)` and a slice of it
  peak under 4 KiB over a 16 MiB map, and `re.search()` over a 16 MiB map
  under 16 KiB. The scanning pattern's loop over a 1.2 MB file peaks under
  64 KiB.
* `readline()` returning a 4-byte line costs under 4x across 64 KiB and
  16 MiB maps, where scanning the map would cost 256x; a 1 MiB line costs over
  64x a 1 KiB one.
* `find()` over 1 MiB of `a` for `a`*(s-1) + `b` costs under 3x from s = 10 to
  s = 1,000 on 3.11+, and over 20x on 3.10, where the scan is naive.
  `rfind()` for `a`*(s/2) + `b` + `a`*(s/2) costs over 20x across the same
  step on every version, which is the O(r·s) worst case. On random bytes
  both cost over 8x and under 64x from 64 KiB to 1 MiB, the r term, where
  quadratic growth would cost 256x.
* `resize()` doubles a 256 MiB private anonymous map with every page touched
  in under a tenth of the time `bytes(mm)` takes to copy it, and keeps the
  contents; on a file it resizes the file too. Growing a shared anonymous
  map raises `ValueError` on 3.13+, and before 3.13 a subprocess that grows
  one and touches the new page dies of `SIGBUS`. Linux only.
* `x in mm` is `True` for a single byte present and `False` for a two-byte
  needle present; iteration yields `bytes` of length 1. Over 1 MiB a missing
  single byte costs over 8x what it costs over 64 KiB.
* `write()` past the end raises `ValueError` and leaves the tail untouched;
  `mm[i:j] = data` of the wrong length raises `IndexError`; `mm[i]` reads and
  writes `int`. `size()` raises `OSError` on Unix for anonymous memory and for
  `trackfd=False` (3.13+), and exceeds `len(mm)` for a map over part of a
  file. `length=0` maps the whole file at offset 0 and from `offset` to the
  end otherwise. Slicing leaves the position where it was. A `length` past the end
  of the file raises `ValueError` on Unix, and an `offset` that is not a
  multiple of `ALLOCATIONGRANULARITY` raises `OSError`. `close()` and `resize()` raise `BufferError` under a live
  `memoryview`; `close()` leaves the file open. `ACCESS_COPY` writes and
  `flush()` leave the file unchanged; `ACCESS_DEFAULT` writes reach it.
  `find()` without `start` begins at, and does not move, the position.
  `seek()` returns the new position on 3.13+ and `None` before; `seekable()`
  is `True` on 3.13+. `mmap.error is OSError`.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* Disk and page-cache costs: the time to fault a page in from storage, and
  what `flush()` waits for, depend on the filesystem and device. `flush()` is
  priced O(q), the pages of the range it passes to `msync(MS_SYNC)` in
  Modules/mmapmodule.c, and is only observed to reach the file.
* `madvise()`'s O(q) is the kernel's work for the option given; only that the
  call succeeds is observed.
* `resize()` time is asserted only against a copy of the mapping. O(p) is
  the kernel's page-table work behind `mremap()` and is not measured across
  sizes.
* Platform rows, which no run of this project reaches: the Windows
  constructor with `tagname` and its file growth, Windows `resize()` copying
  anonymous memory, `SystemError` from `resize()` on Unix without `mremap()`,
  the macOS flush at construction, and `flush()` on Windows. They follow the
  released Modules/mmapmodule.c and the official documentation. The
  Linux-only tests here are guarded on `sys.platform` and skip elsewhere.
* The `MAP_*`, `PROT_*` and `MADV_*` sets vary by OS; only the ones this
  build exposes are asserted to be integers.
* Element cost, file-backed versus anonymous memory for the search and read
  bounds, and huge pages are not varied.
"""

from __future__ import annotations

import mmap
import os
import pathlib
import random
import re
import signal
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "mmap.md"
EXPECTED_BLOCKS = 7
MIB = 1 << 20

linux_only = pytest.mark.skipif(sys.platform != "linux", reason="Linux-only probe")


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


def minor_faults() -> int:
    import resource  # noqa: PLC0415 - unavailable on Windows

    return resource.getrusage(resource.RUSAGE_SELF).ru_minflt


def touch_every_page(mm: mmap.mmap) -> None:
    for offset in range(0, len(mm), mmap.PAGESIZE):
        mm[offset] = 1


def anonymous(size: int, **kwargs: Any) -> mmap.mmap:
    """An anonymous map advised against huge pages, so one fault is one page."""
    mm = mmap.mmap(-1, size, **kwargs)
    if hasattr(mmap, "MADV_NOHUGEPAGE"):
        mm.madvise(mmap.MADV_NOHUGEPAGE)
    return mm


def read_at(handle: Any, size: int) -> bytes:
    """The first `size` bytes of the file behind `handle`, read past its buffer."""
    os.lseek(handle.fileno(), 0, os.SEEK_SET)
    return os.read(handle.fileno(), size)


@pytest.fixture
def file_of(tmp_path: pathlib.Path) -> Iterator[Callable[[bytes], Any]]:
    """Open a temporary file holding the given bytes, read-write."""
    opened: list[Any] = []

    def make(data: bytes) -> Any:
        path = tmp_path / f"data{len(opened)}"
        path.write_bytes(data)
        handle = path.open("r+b")
        opened.append(handle)
        return handle

    yield make
    for handle in opened:
        handle.close()


class TestMappingIsLazy:
    """`mmap.mmap(...)` | O(1) | O(1): no page is touched, whatever the length,
    unless `MAP_POPULATE` asks for all of them."""

    @linux_only
    @pytest.mark.serial
    def test_touching_every_page_faults_each_one(self) -> None:
        with anonymous(16 * MIB) as mm:
            before = minor_faults()
            touch_every_page(mm)
            faults = minor_faults() - before

        pages = 16 * MIB // mmap.PAGESIZE
        assert faults >= pages // 2, f"touching {pages} pages caused only {faults} faults"

    @linux_only
    @pytest.mark.serial
    def test_mapping_anonymous_memory_faults_nothing(self) -> None:
        before = minor_faults()
        mm = mmap.mmap(-1, 256 * MIB)
        faults = minor_faults() - before
        mm.close()

        assert faults < 64, f"mapping 65,536 pages caused {faults} faults"

    @linux_only
    @pytest.mark.serial
    def test_mapping_a_file_faults_nothing(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "sparse"
        with path.open("wb") as f:
            f.truncate(256 * MIB)

        with path.open("r+b") as f:
            before = minor_faults()
            mm = mmap.mmap(f.fileno(), 0)
            faults = minor_faults() - before
            assert len(mm) == 256 * MIB
            mm.close()

        assert faults < 64, f"mapping a 65,536-page file caused {faults} faults"

    @linux_only
    @pytest.mark.serial
    def test_map_populate_faults_every_page_at_construction(self) -> None:
        flags = mmap.MAP_SHARED | mmap.MAP_POPULATE  # type: ignore[attr-defined]
        before = minor_faults()
        mm = mmap.mmap(-1, 16 * MIB, flags=flags)
        faults = minor_faults() - before
        mm.close()

        pages = 16 * MIB // mmap.PAGESIZE
        assert faults >= pages // 2, f"MAP_POPULATE over {pages} pages faulted {faults}"

    @pytest.mark.timing
    def test_a_thousand_times_the_length_costs_about_the_same(self) -> None:
        small = best_ns(lambda: mmap.mmap(-1, MIB).close(), inner=20)
        large = best_ns(lambda: mmap.mmap(-1, 1024 * MIB).close(), inner=20)

        ratio = large / small
        assert ratio < 10, f"1,024x the length cost x{ratio:.2f} ({small:.0f}ns to {large:.0f}ns)"

    def test_length_zero_maps_the_whole_file(self, file_of: Callable[[bytes], Any]) -> None:
        f = file_of(b"x" * 10_000)

        with mmap.mmap(f.fileno(), 0) as mm:
            assert len(mm) == 10_000

    def test_length_zero_with_an_offset_maps_the_rest(
        self, file_of: Callable[[bytes], Any]
    ) -> None:
        offset = mmap.ALLOCATIONGRANULARITY
        f = file_of(b"x" * offset + b"y" * 10_000)

        with mmap.mmap(f.fileno(), 0, offset=offset) as mm:
            assert len(mm) == 10_000
            assert mm[:] == b"y" * 10_000

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows grows the file instead")
    def test_a_length_past_the_end_of_the_file_raises(
        self, file_of: Callable[[bytes], Any]
    ) -> None:
        f = file_of(b"x" * 100)

        with pytest.raises(ValueError, match="greater than file size"):
            mmap.mmap(f.fileno(), 200)

    def test_offset_must_be_a_multiple_of_the_granularity(
        self, file_of: Callable[[bytes], Any]
    ) -> None:
        f = file_of(b"x" * (4 * mmap.ALLOCATIONGRANULARITY))

        with pytest.raises(OSError):
            mmap.mmap(f.fileno(), 10, offset=1)
        with mmap.mmap(f.fileno(), 10, offset=mmap.ALLOCATIONGRANULARITY) as mm:
            assert len(mm) == 10

    def test_anonymous_memory_starts_zeroed(self) -> None:
        with mmap.mmap(-1, 3 * mmap.PAGESIZE) as mm:
            assert mm[:] == bytes(3 * mmap.PAGESIZE)


class TestCloseReleasesTouchedPages:
    """`close()` | O(p) | O(1): p = pages touched; the file stays open."""

    @staticmethod
    def close_ns(size: int, touch: bool) -> int:
        durations = []
        for _ in range(3):
            mm = anonymous(size)
            if touch:
                touch_every_page(mm)
            start = time.perf_counter_ns()
            mm.close()
            durations.append(time.perf_counter_ns() - start)
        return min(durations)

    @linux_only
    @pytest.mark.serial
    @pytest.mark.timing
    def test_the_cost_follows_touched_pages(self) -> None:
        small = self.close_ns(16 * MIB, touch=True)
        large = self.close_ns(256 * MIB, touch=True)
        untouched = self.close_ns(256 * MIB, touch=False)

        assert large > small * 8, f"16x the touched pages: {small}ns to {large}ns"
        assert large > untouched * 20, f"256 MiB touched {large}ns, untouched {untouched}ns"

    def test_closing_leaves_the_file_open(self, file_of: Callable[[bytes], Any]) -> None:
        f = file_of(b"abc")

        with mmap.mmap(f.fileno(), 0) as mm:
            pass

        assert mm.closed
        assert not f.closed
        assert read_at(f, 3) == b"abc"

    def test_a_closed_map_refuses_further_calls(self) -> None:
        mm = mmap.mmap(-1, 10)
        assert mm.closed is False

        mm.close()

        assert mm.closed is True
        with pytest.raises(ValueError, match="closed"):
            len(mm)


class TestReadingCopiesWhatItReturns:
    """`read(n)`, `mm[i:j]` and `readline()` | O(k) | O(k); `readline()`
    stops at the first newline."""

    @pytest.fixture
    def mm(self) -> Iterator[mmap.mmap]:
        with mmap.mmap(-1, 16 * MIB) as mm:
            yield mm

    def test_read_allocates_the_bytes_it_returns(self, mm: mmap.mmap) -> None:
        results: list[bytes] = []

        peak = peak_bytes(lambda: results.append(mm.read(MIB)))

        assert len(results[0]) == MIB and mm.tell() == MIB
        assert MIB <= peak < MIB + 4096, f"read(1 MiB) peaked at {peak}"

    def test_a_slice_leaves_the_position(self, mm: mmap.mmap) -> None:
        mm.seek(10)

        assert mm[0:4] == bytes(4)
        assert mm.tell() == 10

    def test_a_slice_allocates_its_length(self, mm: mmap.mmap) -> None:
        peak = peak_bytes(lambda: mm[0:MIB])

        assert MIB <= peak < MIB + 4096, f"a 1 MiB slice peaked at {peak}"

    def test_read_without_n_reads_to_the_end(self, mm: mmap.mmap) -> None:
        mm.seek(len(mm) - 5)

        assert mm.read() == bytes(5)
        assert mm.read(10) == b""

    def test_readline_allocates_the_line(self, mm: mmap.mmap) -> None:
        mm[64 * 1024 - 1] = ord("\n")

        peak = peak_bytes(mm.readline)

        assert mm.tell() == 64 * 1024
        assert 64 * 1024 <= peak < 64 * 1024 + 4096, f"a 64 KiB line peaked at {peak}"

    def test_readline_without_a_newline_reads_to_the_end(self) -> None:
        with mmap.mmap(-1, 8) as mm:
            mm.write(b"ab\ncdefg")
            mm.seek(0)

            assert mm.readline() == b"ab\n"
            assert mm.readline() == b"cdefg"
            assert mm.readline() == b""

    @pytest.mark.timing
    def test_readline_does_not_scan_past_the_newline(self) -> None:
        durations = []
        for size in (64 * 1024, 16 * MIB):
            mm = mmap.mmap(-1, size)
            mm.write(b"abc\n")

            def read_line(m: mmap.mmap = mm) -> None:
                m.seek(0)
                m.readline()

            durations.append(best_ns(read_line, inner=100))
            mm.close()

        ratio = durations[1] / durations[0]
        assert ratio < 4, f"a 4-byte line in 256x the map: {durations} ns, x{ratio:.2f}"

    @pytest.mark.timing
    def test_readline_cost_follows_the_line(self, mm: mmap.mmap) -> None:
        durations = []
        for line in (1024, MIB):
            mm[line - 1] = ord("\n")

            def read_line() -> None:
                mm.seek(0)
                mm.readline()

            durations.append(best_ns(read_line, inner=5))
            mm[line - 1] = 0

        ratio = durations[1] / durations[0]
        assert ratio > 64, f"a 1,024x longer line: {durations} ns, x{ratio:.2f}"

    def test_items_are_ints_and_read_byte_advances(self, mm: mmap.mmap) -> None:
        mm[3] = 0x41

        assert mm[3] == 0x41 and mm[-1] == 0
        with pytest.raises(TypeError):
            mm[3] = b"A"  # type: ignore[call-overload]
        mm.seek(3)
        assert mm.read_byte() == 0x41
        assert mm.tell() == 4

    def test_a_stepped_slice_is_a_copy(self, mm: mmap.mmap) -> None:
        mm[0:6] = b"abcdef"

        assert mm[0:6:2] == b"ace"


class TestWritingCopiesInPlace:
    """`write()`, `mm[i:j] = data` and `move()` | O(k) | O(1); the mapping
    never grows."""

    @pytest.fixture
    def mm(self) -> Iterator[mmap.mmap]:
        with mmap.mmap(-1, 4 * MIB) as mm:
            yield mm

    def test_write_allocates_nothing(self, mm: mmap.mmap) -> None:
        data = b"y" * MIB
        written: list[int] = []

        peak = peak_bytes(lambda: written.append(mm.write(data)))

        assert written == [MIB] and mm.tell() == MIB
        assert mm[MIB - 1] == ord("y")
        assert peak < 4096, f"writing 1 MiB peaked at {peak}"

    def test_move_allocates_nothing(self, mm: mmap.mmap) -> None:
        mm[0:3] = b"abc"

        peak = peak_bytes(lambda: mm.move(MIB, 0, MIB))

        assert mm[MIB : MIB + 3] == b"abc"
        assert peak < 4096, f"moving 1 MiB peaked at {peak}"

    def test_move_handles_overlap(self, mm: mmap.mmap) -> None:
        mm[0:6] = b"abcdef"

        mm.move(2, 0, 4)

        assert mm[0:6] == b"ababcd"

    def test_a_write_that_does_not_fit_writes_nothing(self, mm: mmap.mmap) -> None:
        mm.seek(len(mm) - 4)

        with pytest.raises(ValueError, match="out of range"):
            mm.write(b"too long")

        assert mm[len(mm) - 4 :] == bytes(4)
        assert len(mm) == 4 * MIB

    def test_slice_assignment_must_keep_the_length(self, mm: mmap.mmap) -> None:
        with pytest.raises(IndexError, match="wrong size"):
            mm[0:2] = b"abc"

    def test_write_byte_advances_and_refuses_the_end(self, mm: mmap.mmap) -> None:
        mm.seek(len(mm) - 1)
        mm.write_byte(7)

        assert mm[-1] == 7
        with pytest.raises(ValueError):
            mm.write_byte(8)

    def test_a_read_only_map_refuses_writes(self, file_of: Callable[[bytes], Any]) -> None:
        f = file_of(b"abc")

        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mm:
            with pytest.raises(TypeError, match="readonly"):
                mm.write(b"x")


class TestPosition:
    """`seek()`, `tell()` and `seekable()` | O(1) | O(1)."""

    def test_seek_and_tell(self) -> None:
        with mmap.mmap(-1, 100) as mm:
            mm.seek(10)
            mm.seek(5, os.SEEK_CUR)
            assert mm.tell() == 15
            mm.seek(-1, os.SEEK_END)
            assert mm.tell() == 99
            with pytest.raises(ValueError):
                mm.seek(101)

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="returns None before 3.13")
    def test_seek_returns_the_position_on_313(self) -> None:
        with mmap.mmap(-1, 100) as mm:
            assert mm.seek(40) == 40
            assert mm.seekable() is True  # type: ignore[attr-defined]

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="returns the position from 3.13")
    def test_seek_returns_none_before_313(self) -> None:
        with mmap.mmap(-1, 100) as mm:
            assert mm.seek(40) is None  # type: ignore[func-returns-value]
            assert not hasattr(mm, "seekable")


class TestViewsShareMemory:
    """`memoryview(mm)` | O(1) | O(1); while it lives, `close()` and
    `resize()` raise `BufferError`."""

    def test_a_view_copies_nothing(self) -> None:
        with mmap.mmap(-1, 16 * MIB) as mm:

            def view_slice() -> None:
                with memoryview(mm) as view:
                    view[0:MIB].release()

            peak = peak_bytes(view_slice)

        assert peak < 4096, f"a view over 16 MiB peaked at {peak}"

    def test_writes_show_through_the_view(self) -> None:
        mm = mmap.mmap(-1, 10)
        view = memoryview(mm)

        mm[0] = 9

        assert view[0] == 9
        view.release()
        mm.close()

    def test_close_and_resize_wait_for_the_view(self) -> None:
        mm = mmap.mmap(-1, mmap.PAGESIZE)
        view = memoryview(mm)

        with pytest.raises(BufferError):
            mm.close()
        with pytest.raises(BufferError):
            mm.resize(2 * mmap.PAGESIZE)

        view.release()
        mm.close()
        assert mm.closed


class TestIterationIsNotASubstringTest:
    """Iterating and `x in mm` | O(n) | O(1): one-byte `bytes` items, so a
    longer needle is never found."""

    def test_items_are_one_byte_bytes(self) -> None:
        with mmap.mmap(-1, 3) as mm:
            mm.write(b"abc")

            assert list(mm) == [b"a", b"b", b"c"]

    def test_only_a_single_byte_is_found(self) -> None:
        with mmap.mmap(-1, 64) as mm:
            mm.write(b"needle")

            assert b"n" in mm
            assert b"needle" not in mm
            assert mm.find(b"needle", 0) == 0

    @pytest.mark.timing
    def test_a_miss_walks_the_whole_map(self) -> None:
        durations = []
        for size in (64 * 1024, MIB):
            with mmap.mmap(-1, size) as mm:
                durations.append(best_ns(lambda m=mm: b"\x01" in m, repeats=3))  # type: ignore[misc]

        ratio = durations[1] / durations[0]
        assert ratio > 8, f"16x the map for a missing byte: {durations} ns, x{ratio:.2f}"


class TestSearching:
    """`find()` | O(r + s) on 3.11+, O(r·s) worst on 3.10; `rfind()` |
    O(r·s) worst; both start at the position and leave it alone."""

    @staticmethod
    def search_ns(method: str, needle: bytes) -> float:
        with mmap.mmap(-1, MIB) as mm:
            mm.write(b"a" * MIB)
            search = getattr(mm, method)
            assert search(needle, 0) == -1
            return best_ns(lambda: search(needle, 0), repeats=3)

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 11), reason="naive scan on 3.10")
    def test_find_is_linear_in_the_needle_on_311(self) -> None:
        short = self.search_ns("find", b"a" * 9 + b"b")
        long = self.search_ns("find", b"a" * 999 + b"b")

        ratio = long / short
        assert ratio < 3, f"100x the needle: {short:.0f}ns to {long:.0f}ns, x{ratio:.2f}"

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="bytes.find's search from 3.11")
    def test_find_multiplies_the_needle_on_310(self) -> None:
        short = self.search_ns("find", b"a" * 9 + b"b")
        long = self.search_ns("find", b"a" * 999 + b"b")

        ratio = long / short
        assert ratio > 20, f"100x the needle: {short:.0f}ns to {long:.0f}ns, x{ratio:.2f}"

    @pytest.mark.timing
    def test_rfind_multiplies_the_needle_in_the_worst_case(self) -> None:
        short = self.search_ns("rfind", b"a" * 5 + b"b" + b"a" * 5)
        long = self.search_ns("rfind", b"a" * 500 + b"b" + b"a" * 500)

        ratio = long / short
        assert ratio > 20, f"~100x the needle: {short:.0f}ns to {long:.0f}ns, x{ratio:.2f}"

    @pytest.mark.timing
    @pytest.mark.parametrize("method", ["find", "rfind"])
    def test_typical_input_is_linear_in_the_range(self, method: str) -> None:
        rng = random.Random(1)
        durations = []
        for size in (64 * 1024, MIB):
            with mmap.mmap(-1, size) as mm:
                mm.write(rng.randbytes(size).replace(b"Z", b"Y"))
                search = getattr(mm, method)
                durations.append(best_ns(lambda s=search: s(b"ZZZZ", 0), repeats=5))  # type: ignore[misc]

        ratio = durations[1] / durations[0]
        assert 8 < ratio < 64, f"{method}: 16x the range cost x{ratio:.2f} ({durations} ns)"

    def test_find_allocates_nothing(self) -> None:
        with mmap.mmap(-1, 16 * MIB) as mm:
            needle = b"zz"
            mm.find(needle, 0)

            peak = peak_bytes(lambda: mm.find(needle, 0))

        assert peak < 4096, f"find over 16 MiB peaked at {peak}"

    def test_the_default_start_is_the_position(self) -> None:
        with mmap.mmap(-1, 64) as mm:
            mm.write(b"header;needle;tail;needle")

            assert mm.find(b"needle") == -1
            assert mm.rfind(b"needle") == -1
            assert mm.find(b"needle", 0) == 7
            assert mm.rfind(b"needle", 0) == 19
            assert mm.find(b"needle", 0, 12) == -1
            assert mm.tell() == 25

    def test_re_scans_the_map_in_place(self) -> None:
        with mmap.mmap(-1, 16 * MIB) as mm:
            mm[-6:] = b"needle"
            pattern = re.compile(rb"needle")
            pattern.search(mm)
            matches: list[Any] = []

            peak = peak_bytes(lambda: matches.append(pattern.search(mm)))

            assert matches[0].start() == 16 * MIB - 6
        assert peak < 16 * 1024, f"re.search over 16 MiB peaked at {peak}"


class TestSizeResizeAndFlush:
    """`size()` asks the file; `resize()` remaps on Linux without copying;
    `flush()` reaches the file except under `ACCESS_READ` and `ACCESS_COPY`."""

    def test_size_is_the_file_not_the_map(self, file_of: Callable[[bytes], Any]) -> None:
        f = file_of(b"x" * 10_000)

        with mmap.mmap(f.fileno(), 100) as mm:
            assert len(mm) == 100
            assert mm.size() == 10_000

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows reports the map's length")
    def test_size_of_anonymous_memory_raises_on_unix(self) -> None:
        with mmap.mmap(-1, 10) as mm, pytest.raises(OSError):
            mm.size()

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-only argument")
    @pytest.mark.skipif(sys.version_info < (3, 13), reason="trackfd arrived in 3.13")
    def test_size_without_a_tracked_descriptor_raises(
        self, file_of: Callable[[bytes], Any]
    ) -> None:
        f = file_of(b"x" * 100)

        with mmap.mmap(f.fileno(), 0, trackfd=False) as mm, pytest.raises(OSError):  # type: ignore[call-arg]
            mm.size()

    @linux_only
    def test_resize_changes_the_file_and_keeps_the_bytes(
        self, file_of: Callable[[bytes], Any]
    ) -> None:
        f = file_of(b"abcd" * 1024)

        with mmap.mmap(f.fileno(), 0) as mm:
            mm.resize(8192)

            assert len(mm) == 8192
            assert os.fstat(f.fileno()).st_size == 8192
            assert mm[0:4] == b"abcd" and mm[4096:] == bytes(4096)

    @linux_only
    @pytest.mark.serial
    @pytest.mark.timing
    def test_resize_does_not_copy_the_bytes(self) -> None:
        size = 256 * MIB
        durations = []
        copies = []
        for _ in range(3):
            mm = anonymous(size, flags=mmap.MAP_PRIVATE)  # type: ignore[attr-defined]
            touch_every_page(mm)
            copies.append(best_ns(lambda m=mm: bytes(m), repeats=1))  # type: ignore[misc]
            start = time.perf_counter_ns()
            mm.resize(size * 2)
            durations.append(time.perf_counter_ns() - start)
            assert mm[size - mmap.PAGESIZE] == 1 and mm[size] == 0
            mm.close()

        resize, copy = min(durations), min(copies)
        assert resize * 10 < copy, f"resize {resize}ns against a {copy}ns copy of 256 MiB"

    @linux_only
    @pytest.mark.skipif(sys.version_info < (3, 13), reason="the check arrived in 3.13")
    def test_shared_anonymous_memory_cannot_grow_on_313(self) -> None:
        with mmap.mmap(-1, mmap.PAGESIZE) as mm:
            with pytest.raises(ValueError, match="shared anonymous"):
                mm.resize(2 * mmap.PAGESIZE)
            mm.resize(mmap.PAGESIZE // 2)
            assert len(mm) == mmap.PAGESIZE // 2

    @linux_only
    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="raises ValueError from 3.13")
    def test_growing_shared_anonymous_memory_faults_before_313(
        self, tmp_path: pathlib.Path
    ) -> None:
        source = (
            "import mmap\n"
            "mm = mmap.mmap(-1, mmap.PAGESIZE)\n"
            "mm.resize(2 * mmap.PAGESIZE)\n"
            "mm[mmap.PAGESIZE] = 1\n"
        )

        result = _run_block(source, tmp_path)

        assert result.returncode == -signal.SIGBUS, result

    def test_resize_refuses_a_copy_on_write_map(self, file_of: Callable[[bytes], Any]) -> None:
        f = file_of(b"abcd")

        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_COPY) as mm, pytest.raises(TypeError):
            mm.resize(8)

    def test_flush_reaches_the_file(self, file_of: Callable[[bytes], Any]) -> None:
        f = file_of(b"abcd" * 1024)

        with mmap.mmap(f.fileno(), 0) as mm:
            mm[0:4] = b"WXYZ"
            assert mm.flush() is None
            assert mm.flush(0, mmap.PAGESIZE) is None

        assert read_at(f, 4) == b"WXYZ"

    def test_copy_on_write_never_reaches_the_file(self, file_of: Callable[[bytes], Any]) -> None:
        f = file_of(b"abcd" * 1024)

        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_COPY) as mm:
            mm[0:4] = b"WXYZ"
            mm.flush()
            assert mm[0:4] == b"WXYZ"

        assert read_at(f, 4) == b"abcd"

    @pytest.mark.skipif(not hasattr(mmap.mmap, "madvise"), reason="no madvise() here")
    def test_madvise_accepts_its_options(self) -> None:
        with mmap.mmap(-1, 4 * mmap.PAGESIZE) as mm:
            for name in ("MADV_NORMAL", "MADV_SEQUENTIAL", "MADV_WILLNEED"):
                assert mm.madvise(getattr(mmap, name)) is None  # type: ignore[func-returns-value]
            assert mm.madvise(mmap.MADV_RANDOM, mmap.PAGESIZE, mmap.PAGESIZE) is None  # type: ignore[attr-defined, func-returns-value]


class TestConstants:
    """Constants are plain integers; `mmap.error` is `OSError`."""

    def test_access_modes_and_sizes(self) -> None:
        modes = {mmap.ACCESS_READ, mmap.ACCESS_WRITE, mmap.ACCESS_COPY, mmap.ACCESS_DEFAULT}
        assert len(modes) == 4
        assert mmap.PAGESIZE > 0
        assert mmap.ALLOCATIONGRANULARITY % mmap.PAGESIZE == 0
        if sys.platform != "win32":
            assert mmap.ALLOCATIONGRANULARITY == mmap.PAGESIZE

    @pytest.mark.skipif(sys.platform == "win32", reason="Unix-only constants")
    def test_unix_flags_are_integers(self) -> None:
        names = [n for n in dir(mmap) if n.startswith(("MAP_", "PROT_", "MADV_"))]

        assert {"MAP_SHARED", "MAP_PRIVATE", "PROT_READ", "PROT_WRITE"} <= set(names)
        assert all(isinstance(getattr(mmap, n), int) for n in names)

    def test_error_is_oserror(self) -> None:
        assert mmap.error is OSError  # type: ignore[attr-defined]


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
    """Each block runs in its own subprocess and working directory, and
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

    def test_the_scanning_pattern_holds_no_copy_of_the_file(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "found == [42, 7]" in s)
        measured = source.replace(
            "    found = []\n",
            "    import tracemalloc\n    found = []\n    tracemalloc.start()\n",
            1,
        ).replace(
            "    assert found == [42, 7]",
            "    peak = tracemalloc.get_traced_memory()[1]\n"
            "    assert peak < 64 * 1024, peak\n"
            "    assert found == [42, 7]",
            1,
        )

        assert measured.count("tracemalloc") == 3, (
            f"the probe matched nothing in {PAGE.name}:{line}"
        )
        result = _run_block(measured, tmp_path)
        assert result.returncode == 0, result.stderr

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "mm.tell() == 11" in s)
        mutated = source.replace("mm.tell() == 11", "mm.tell() == 12", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
