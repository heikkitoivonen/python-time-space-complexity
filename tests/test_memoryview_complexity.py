"""Tests for docs/builtins/memoryview_func.md.

A memoryview holds a Py_buffer, a shape/strides/suboffsets array of 3 * ndim
entries, and a pointer to a managed buffer that every view derived from it -
by slicing, casting, toreadonly() or memoryview(view) - shares; a second
memoryview(exporter) call acquires the exporter's buffer again into a managed
buffer of its own (Objects/memoryobject.c). Creating, slicing and toreadonly() go
through mbuf_add_view and cast() through mbuf_add_incomplete_view; each copies
only those arrays, never the data. The tests settle the O(1) rows by
observation:

* `mv.obj is b` for a fresh view and for a slice of it, and writes through a
  slice land in the exporter;
* `sys.getsizeof()` of a 1-D view is the same 184 bytes over a 100,000-byte
  buffer and a 10,000,000-byte one (208 for two dimensions, 232 for three),
  and tracemalloc attributes under a kilobyte to creating, slicing, casting or
  toreadonly()-ing the larger;
* `bytes(mv)` and `tolist()` trace allocations that grow a hundredfold when the
  view does (10,000,033 bytes for a 10,000,000-byte copy), which is the O(n)
  space column for the copying rows.

Behavioural notes are checked directly: the length and format checks on slice
assignment and the O(k) temporary a strided side costs it (10,000,000 bytes
traced for a 10,000,000-element strided copy, none for a contiguous one), the
one-dimension limits on `mv[i]` and slice assignment, equality by value across
formats and for signed zero and NaN, the read-only and released-view errors,
the resize refusal a live view imposes on a bytearray, the hash restrictions
(writable views, non-byte formats, and a bytearray exporter, which is
unhashable itself), the O(n) temporaries a non-contiguous view costs hash()
and hex() (5,000,000 bytes over the contiguous case for a 5,000,000-element
view), the `()` suboffsets, the fresh tuple on each `shape` access, and the
cast restrictions on contiguity, byte size, byte formats and dimensions. Hash
caching is observed on 3.12+ through a Python exporter whose bytes change
under a view that has already been hashed.

Timing settles the rows a call counter cannot reach, framed at a hundredfold
step in size (100,000 to 10,000,000 bytes) on the pinned interpreter
(aarch64, CPython 3.14):

* copying rows scale: x208 for `bytes(mv)`, x134 for slice assignment, x102
  for `==`, x101 for a first `hash()`, x103 for iteration and `in`, x103 for
  `count()` and a missing `index()`;
* the exporter's hash is part of a first `hash()`: a two-byte slice of a fresh
  `bytes` costs x100 more over a 10,000,000-byte exporter than over a
  100,000-byte one, and x0.4 once the exporter's own hash is cached;
* view rows do not scale: x1.0 for `memoryview()`, slicing, `cast()`, a cached
  `hash()`, and `==` between views whose shapes differ.

Thresholds sit at x30 to x1,000 for the linear rows and below x3 for the
constant ones, far from the measured values and from the x10,000 a quadratic
copy would show, so a slower runner still separates them.

Not varied: the growth measurements use format 'B' only (other formats appear
in value and error checks), dimensions above three, and exporters beyond
bytes, bytearray, array.array and one Python `__buffer__` class. The 'B'
format goes through the native unpacking path; a format the struct module has
to decode costs more per element but does not change the growth class. A
Python exporter's `__buffer__()` can do arbitrary work, which is why the page
scopes its bounds to the built-in exporters. count() and index() exist from
3.14 only, so their tests skip before it and one test asserts their absence
there. The hash row's O(n) temporary applies to any view that is not
C-contiguous; the built-in exporters cannot produce a view that is
Fortran-contiguous without also being C-contiguous, so that wording follows
memory_hash()'s MV_C_CONTIGUOUS check and only the strided case is measured.
"""

import array
import math
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "memoryview_func.md"

SMALL = 100_000
LARGE = 10_000_000
"""A hundredfold step in buffer size; the small end already costs microseconds
for the copying rows, so fixed overhead does not blur the ratio."""

LINEAR_FLOOR = 30.0
LINEAR_CEILING = 1_000.0
"""A hundredfold step: constant predicts x1, linear x100, quadratic x10,000."""
FLAT_CEILING = 3.0


def best_time(func: Callable[[], Any], repeats: int = 5, loops: int = 1) -> float:
    """The fastest of several runs of `loops` calls."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        for _ in range(loops):
            func()
        times.append(time.perf_counter() - start)
    return min(times)


def growth(small: Callable[[], Any], large: Callable[[], Any], loops: int = 1) -> float:
    return best_time(large, loops=loops) / best_time(small, loops=loops)


def traced_peak(func: Callable[[], Any]) -> int:
    """Peak bytes tracemalloc attributes to one call, after a warm-up call."""
    func()
    tracemalloc.start()
    try:
        func()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak


@pytest.fixture(scope="module")
def buffers() -> tuple[bytes, bytes]:
    return bytes(SMALL), bytes(LARGE)


class TestCreation:
    """Row: memoryview(obj) is O(1) time and space and shares the buffer."""

    def test_the_view_holds_the_exporter_itself(self) -> None:
        b = b"hello"
        mv = memoryview(b)
        assert mv.obj is b

    def test_a_view_of_a_view_shares_the_buffer(self) -> None:
        ba = bytearray(b"hello")
        outer = memoryview(ba)
        inner = memoryview(outer)

        inner[0] = 72

        assert ba == bytearray(b"Hello")
        assert outer[0] == 72
        assert inner.obj is ba

    def test_the_view_object_has_one_size(self, buffers: tuple[bytes, bytes]) -> None:
        small, large = buffers
        assert sys.getsizeof(memoryview(small)) == sys.getsizeof(memoryview(large))

    def test_creation_allocates_no_copy(self, buffers: tuple[bytes, bytes]) -> None:
        _, large = buffers
        assert traced_peak(lambda: memoryview(large)) < 1024

    def test_a_non_exporter_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="a bytes-like object is required"):
            memoryview("text")  # pyright: ignore[reportArgumentType]

    @pytest.mark.timing
    def test_creation_time_is_flat(self, buffers: tuple[bytes, bytes]) -> None:
        small, large = buffers
        ratio = growth(lambda: memoryview(small), lambda: memoryview(large), loops=1_000)
        assert ratio < FLAT_CEILING, f"x100 in buffer size cost x{ratio:.2f}"


class TestIndexing:
    """Rows: mv[i] and mv[i] = v are O(1); the read-only view raises."""

    def test_read_and_write_one_element(self) -> None:
        ba = bytearray(b"test")
        mv = memoryview(ba)
        assert mv[0] == 116
        mv[0] = 84
        assert ba == bytearray(b"Test")
        assert mv[0] == 84

    def test_a_read_only_view_refuses_writes(self) -> None:
        mv = memoryview(b"hello")
        with pytest.raises(TypeError, match="cannot modify read-only memory"):
            mv[0] = 72

    def test_a_multi_dimensional_view_needs_a_full_index_tuple(self) -> None:
        grid = memoryview(bytearray(6)).cast("B", (2, 3))
        with pytest.raises(NotImplementedError, match="sub-views are not implemented"):
            grid[0]
        with pytest.raises(NotImplementedError, match="sub-views are not implemented"):
            grid[0] = 1
        grid[1, 2] = 9
        assert grid[1, 2] == 9
        assert grid.tolist() == [[0, 0, 0], [0, 0, 9]]

    def test_array_elements_come_back_as_the_exporters_type(self) -> None:
        arr = array.array("i", [1, 2, 3, 4, 5])
        mv = memoryview(arr)
        assert mv[0] == 1
        assert mv.format == "i"
        assert mv.itemsize == 4
        assert mv.nbytes == 20

    @pytest.mark.timing
    def test_index_time_is_flat(self, buffers: tuple[bytes, bytes]) -> None:
        small, large = memoryview(buffers[0]), memoryview(buffers[1])
        ratio = growth(lambda: small[50], lambda: large[50], loops=1_000)
        assert ratio < FLAT_CEILING, f"x100 in buffer size cost x{ratio:.2f}"


class TestSlicing:
    """Row: mv[a:b] is O(1) and a view, whatever k is."""

    def test_a_slice_is_a_view_of_the_same_exporter(self) -> None:
        ba = bytearray(b"hello world")
        world = memoryview(ba)[6:11]

        assert world.obj is ba
        world[0] = 87

        assert ba == bytearray(b"hello World")

    def test_a_stepped_slice_is_still_a_view(self) -> None:
        b = bytes(range(10))
        every_other = memoryview(b)[::2]
        assert every_other.obj is b
        assert every_other.tolist() == [0, 2, 4, 6, 8]
        assert not every_other.contiguous

    def test_slicing_allocates_no_copy(self, buffers: tuple[bytes, bytes]) -> None:
        large = memoryview(buffers[1])
        assert traced_peak(lambda: large[10:-10]) < 1024

    def test_a_bytes_slice_copies_but_a_view_slice_does_not(self) -> None:
        data = b"x" * 10**6
        assert traced_peak(lambda: data[100:200]) >= 100
        assert traced_peak(lambda: memoryview(data)[100:200]) < 1024

    @pytest.mark.timing
    def test_slice_time_is_flat(self, buffers: tuple[bytes, bytes]) -> None:
        small, large = memoryview(buffers[0]), memoryview(buffers[1])
        ratio = growth(lambda: small[10:-10], lambda: large[10:-10], loops=1_000)
        assert ratio < FLAT_CEILING, f"x100 in slice length cost x{ratio:.2f}"


class TestSliceAssignment:
    """Row: mv[a:b] = data copies k elements and insists on exactly k."""

    def test_copies_the_bytes_in(self) -> None:
        buffer = bytearray(1024)
        view = memoryview(buffer)
        view[0:4] = b"HEAD"
        assert bytes(view[0:4]) == b"HEAD"
        assert buffer[:5] == bytearray(b"HEAD\x00")

    def test_length_mismatch_is_an_error(self) -> None:
        view = memoryview(bytearray(1024))
        with pytest.raises(ValueError, match="different structures"):
            view[0:4] = b"HEADER"

    def test_format_mismatch_is_an_error_even_at_equal_counts_and_bytes(self) -> None:
        unsigned = memoryview(bytearray(2))
        signed = memoryview(bytes(2)).cast("b")
        assert len(unsigned) == len(signed) == 2
        assert unsigned.nbytes == signed.nbytes == 2
        with pytest.raises(ValueError, match="different structures"):
            unsigned[0:2] = signed

    def test_only_one_dimensional_views_accept_slice_assignment(self) -> None:
        grid = memoryview(bytearray(6)).cast("B", (2, 3))
        with pytest.raises(NotImplementedError, match="restricted to ndim = 1"):
            grid[0:1] = b"abc"

    def test_a_contiguous_copy_allocates_nothing_but_a_strided_one_allocates_k(self) -> None:
        """copy_single mallocs shape[0] * itemsize when either side has a
        stride other than the item size; a contiguous pair is one memmove."""
        k = 1_000_000
        dst = memoryview(bytearray(2 * k))
        contiguous_src = bytes(k)
        strided_src = memoryview(bytes(2 * k))[::2]

        assert traced_peak(lambda: dst.__setitem__(slice(0, k), contiguous_src)) < 1024
        assert traced_peak(lambda: dst.__setitem__(slice(0, 2 * k, 2), contiguous_src)) >= k
        assert traced_peak(lambda: dst.__setitem__(slice(0, k), strided_src)) >= k

    @pytest.mark.timing
    def test_time_is_linear_in_the_slice_length(self) -> None:
        small_dst, large_dst = memoryview(bytearray(SMALL)), memoryview(bytearray(LARGE))
        small_src, large_src = bytes(SMALL), bytes(LARGE)

        ratio = growth(
            lambda: small_dst.__setitem__(slice(None), small_src),
            lambda: large_dst.__setitem__(slice(None), large_src),
        )

        assert LINEAR_FLOOR < ratio < LINEAR_CEILING, f"x100 in k cost x{ratio:.1f}"

    @pytest.mark.timing
    def test_time_does_not_depend_on_the_buffer_behind_the_slice(self) -> None:
        small_dst, large_dst = memoryview(bytearray(SMALL)), memoryview(bytearray(LARGE))
        chunk = bytes(1_000)

        ratio = growth(
            lambda: small_dst.__setitem__(slice(0, 1_000), chunk),
            lambda: large_dst.__setitem__(slice(0, 1_000), chunk),
            loops=1_000,
        )

        assert ratio < FLAT_CEILING, f"x100 in buffer size, same k, cost x{ratio:.2f}"


class TestLength:
    """Row: len(mv) is the first dimension."""

    def test_first_dimension(self) -> None:
        assert len(memoryview(b"")) == 0
        assert len(memoryview(b"hello")) == 5
        assert len(memoryview(bytes(6)).cast("B", (2, 3))) == 2
        assert len(memoryview(bytes(8)).cast("i")) == 2


class TestCopyingOut:
    """Rows: bytes(mv), tobytes(), tolist() and hex() are O(n) time and space."""

    def test_bytes_is_an_independent_copy(self) -> None:
        ba = bytearray(b"hello")
        copy = bytes(memoryview(ba))
        ba[0] = 72
        assert copy == b"hello"
        assert bytes(memoryview(ba)) == b"Hello"

    def test_bytes_allocation_is_the_views_size(self, buffers: tuple[bytes, bytes]) -> None:
        small, large = memoryview(buffers[0]), memoryview(buffers[1])
        small_peak = traced_peak(lambda: bytes(small))
        large_peak = traced_peak(lambda: bytes(large))
        assert small_peak >= SMALL
        assert large_peak >= LARGE
        assert 50 < large_peak / small_peak < 200, (
            f"x100 in n allocated x{large_peak / small_peak:.1f}"
        )

    def test_a_non_contiguous_view_copies_its_elements(self) -> None:
        b = bytes(range(10))
        assert bytes(memoryview(b)[::2]) == b[::2]
        assert memoryview(b)[::2].tobytes() == b[::2]

    def test_tobytes_order_changes_layout_not_size(self) -> None:
        grid = memoryview(bytes(range(6))).cast("B", (2, 3))
        assert grid.tobytes("C") == bytes([0, 1, 2, 3, 4, 5])
        assert grid.tobytes("F") == bytes([0, 3, 1, 4, 2, 5])
        assert len(grid.tobytes("F")) == grid.nbytes

    def test_tolist_makes_one_object_per_element(self) -> None:
        assert memoryview(b"hello").tolist() == [104, 101, 108, 108, 111]
        assert memoryview(bytes(range(6))).cast("B", (2, 3)).tolist() == [[0, 1, 2], [3, 4, 5]]
        assert list(memoryview(b"hello")) == [104, 101, 108, 108, 111]

    def test_tolist_allocation_grows_with_the_elements(self) -> None:
        small, large = memoryview(bytes(range(256)) * 40), memoryview(bytes(range(256)) * 4_000)
        small_peak = traced_peak(small.tolist)
        large_peak = traced_peak(large.tolist)
        assert 50 < large_peak / small_peak < 200, (
            f"x100 in n allocated x{large_peak / small_peak:.1f}"
        )

    def test_hex_is_two_characters_per_byte(self) -> None:
        assert memoryview(b"hello").hex() == "68656c6c6f"
        assert memoryview(b"hello").hex(":", 2) == "68:656c:6c6f"
        assert len(memoryview(bytes(10)).hex()) == 20
        assert memoryview(bytes(range(10)))[::2].hex() == bytes(range(10))[::2].hex()

    def test_hex_of_a_non_contiguous_view_copies_first(self, buffers: tuple[bytes, bytes]) -> None:
        large = memoryview(buffers[1])
        contiguous, strided = large[: LARGE // 2], large[::2]
        assert contiguous.nbytes == strided.nbytes
        extra = traced_peak(strided.hex) - traced_peak(contiguous.hex)
        assert extra >= strided.nbytes, f"the strided hex() allocated only {extra} bytes more"

    @pytest.mark.timing
    def test_bytes_time_is_linear(self, buffers: tuple[bytes, bytes]) -> None:
        small, large = memoryview(buffers[0]), memoryview(buffers[1])
        ratio = growth(lambda: bytes(small), lambda: bytes(large))
        assert LINEAR_FLOOR < ratio < LINEAR_CEILING, f"x100 in n cost x{ratio:.1f}"


class TestEquality:
    """Row: == walks every element, O(1) False on a shape mismatch, no ordering."""

    def test_compares_against_any_exporter(self) -> None:
        b = b"hello"
        assert memoryview(b) == b
        assert memoryview(b) == memoryview(bytearray(b))
        assert memoryview(b) == array.array("B", b)
        assert memoryview(b) != memoryview(b"hellO")

    def test_compares_values_not_bytes(self) -> None:
        assert memoryview(array.array("i", [1, 2])) == memoryview(array.array("h", [1, 2]))
        zero, negative_zero = array.array("d", [0.0]), array.array("d", [-0.0])
        assert zero.tobytes() != negative_zero.tobytes()
        assert memoryview(zero) == memoryview(negative_zero)
        nan = memoryview(array.array("d", [math.nan]))
        assert nan != nan
        assert nan != memoryview(array.array("d", [math.nan]))

    def test_different_shapes_are_unequal(self) -> None:
        assert memoryview(b"hello") != memoryview(b"hell")
        assert memoryview(bytes(6)) != memoryview(bytes(6)).cast("B", (2, 3))

    def test_ordering_is_not_defined(self) -> None:
        with pytest.raises(TypeError, match="not supported"):
            _ = memoryview(b"a") < memoryview(b"b")  # pyright: ignore[reportOperatorIssue]

    @pytest.mark.timing
    def test_equal_views_cost_linear_time(self, buffers: tuple[bytes, bytes]) -> None:
        small, large = buffers
        small_a, small_b = memoryview(small), memoryview(small)
        large_a, large_b = memoryview(large), memoryview(large)
        ratio = growth(lambda: small_a == small_b, lambda: large_a == large_b)
        assert LINEAR_FLOOR < ratio < LINEAR_CEILING, f"x100 in n cost x{ratio:.1f}"

    @pytest.mark.timing
    def test_a_shape_mismatch_costs_flat_time(self, buffers: tuple[bytes, bytes]) -> None:
        small, large = buffers
        small_a, small_b = memoryview(small), memoryview(small[:-1])
        large_a, large_b = memoryview(large), memoryview(large[:-1])
        ratio = growth(lambda: small_a == small_b, lambda: large_a == large_b, loops=1_000)
        assert ratio < FLAT_CEILING, f"x100 in n cost x{ratio:.2f} for unequal shapes"


class TestHashing:
    """Row: hash() is O(n) once, restricted to read-only byte views, then cached."""

    def test_matches_the_bytes_hash(self) -> None:
        b = b"hello"
        assert hash(memoryview(b)) == hash(b)
        assert hash(memoryview(b)[1:3]) == hash(b"el")
        assert hash(memoryview(bytes(range(10)))[::2]) == hash(bytes(range(10))[::2])

    def test_a_writable_view_is_unhashable(self) -> None:
        with pytest.raises(ValueError, match="cannot hash writable memoryview"):
            hash(memoryview(bytearray(b"hello")))

    def test_a_non_byte_format_is_unhashable(self) -> None:
        with pytest.raises(ValueError, match="restricted to formats 'B', 'b' or 'c'"):
            hash(memoryview(bytes(8)).cast("i"))

    def test_the_exporter_must_be_hashable_too(self) -> None:
        read_only = memoryview(bytearray(b"hello")).toreadonly()
        with pytest.raises(TypeError, match="unhashable type: 'bytearray'"):
            hash(read_only)

    def test_a_non_contiguous_view_gathers_a_temporary(self, buffers: tuple[bytes, bytes]) -> None:
        large = buffers[1]
        hash(large)
        strided = memoryview(large)[::2]
        assert traced_peak(lambda: hash(memoryview(large)[::2])) >= strided.nbytes
        assert traced_peak(lambda: hash(memoryview(large)[: LARGE // 2])) < 1024

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="__buffer__ exporters are 3.12+")
    def test_the_hash_is_cached(self) -> None:
        """A Python exporter lets the bytes change under a view already hashed:
        the view keeps returning the first result, a fresh view does not."""

        class Exporter:
            def __init__(self, data: bytearray) -> None:
                self.data = data

            def __buffer__(self, flags: int) -> memoryview:
                return memoryview(self.data).toreadonly()

            def __release_buffer__(self, view: memoryview) -> None:
                view.release()

            def __hash__(self) -> int:
                return 1

        exporter = Exporter(bytearray(b"hello"))
        view = memoryview(exporter)
        first = hash(view)
        assert first == hash(b"hello")

        exporter.data[0] = ord("j")

        assert hash(view) == first
        assert hash(memoryview(exporter)) == hash(b"jello")
        assert hash(b"jello") != first

    @pytest.mark.timing
    def test_a_first_hash_pays_for_the_exporters_hash(self) -> None:
        """Fresh bytes objects, because bytes caches its own hash: a two-byte slice
        over a 10,000,000-byte exporter against one over 100,000 bytes."""

        def fresh(size: int, copies: int = 5) -> list[bytes]:
            return [bytes(bytearray(size)) for _ in range(copies)]

        def first_slice_hash(exporters: list[bytes]) -> float:
            """One two-byte view per fresh exporter, timed on its own: the
            exporter's hash is the work being measured."""
            best = float("inf")
            for exporter in exporters:
                view = memoryview(exporter)[0:2]
                start = time.perf_counter()
                hash(view)
                best = min(best, time.perf_counter() - start)
            return best

        def slice_hashes_over_a_hashed_exporter(exporter: bytes, views: int = 2_000) -> float:
            """Many fresh views over one already-hashed exporter, built before
            the clock starts, so each sample is thousands of view hashes."""
            hash(exporter)
            fresh_views = [memoryview(exporter)[0:2] for _ in range(views)]
            start = time.perf_counter()
            for view in fresh_views:
                hash(view)
            return time.perf_counter() - start

        uncached = first_slice_hash(fresh(LARGE)) / first_slice_hash(fresh(SMALL))
        cached = min(slice_hashes_over_a_hashed_exporter(bytes(LARGE)) for _ in range(5)) / min(
            slice_hashes_over_a_hashed_exporter(bytes(SMALL)) for _ in range(5)
        )

        assert LINEAR_FLOOR < uncached < LINEAR_CEILING, (
            f"x100 in exporter size cost x{uncached:.1f}"
        )
        assert cached < FLAT_CEILING, f"x100 in exporter size cost x{cached:.2f} once hashed"

    @pytest.mark.timing
    def test_first_hash_is_linear_and_the_cached_one_flat(
        self, buffers: tuple[bytes, bytes]
    ) -> None:
        small, large = buffers
        first = growth(lambda: hash(memoryview(small)), lambda: hash(memoryview(large)))

        cached_small, cached_large = memoryview(small), memoryview(large)
        hash(cached_small)
        hash(cached_large)
        cached = growth(lambda: hash(cached_small), lambda: hash(cached_large), loops=1_000)

        assert LINEAR_FLOOR < first < LINEAR_CEILING, (
            f"x100 in n cost x{first:.1f} for a first hash"
        )
        assert cached < FLAT_CEILING, f"x100 in n cost x{cached:.2f} for a cached hash"


class TestIteration:
    """Row: iteration and `in` are linear scans over a 1-D view."""

    def test_iterates_the_elements(self) -> None:
        assert list(memoryview(b"abc")) == [97, 98, 99]
        assert 98 in memoryview(b"abc")
        assert 100 not in memoryview(b"abc")

    def test_there_is_no_contains_fast_path(self) -> None:
        assert "__contains__" not in memoryview.__dict__

    def test_a_multi_dimensional_view_cannot_be_iterated(self) -> None:
        grid = memoryview(bytes(6)).cast("B", (2, 3))
        with pytest.raises(NotImplementedError):
            iter(grid)

    @pytest.mark.timing
    def test_iteration_and_membership_are_linear(self, buffers: tuple[bytes, bytes]) -> None:
        small, large = memoryview(buffers[0]), memoryview(buffers[1])
        loop = growth(lambda: sum(1 for _ in small), lambda: sum(1 for _ in large))
        member = growth(lambda: 1 in small, lambda: 1 in large)
        assert LINEAR_FLOOR < loop < LINEAR_CEILING, f"x100 in n cost x{loop:.1f} to iterate"
        assert LINEAR_FLOOR < member < LINEAR_CEILING, (
            f"x100 in n cost x{member:.1f} for a missing member"
        )


class TestCast:
    """Row: cast() is O(1), C-contiguous only, byte size preserved."""

    def test_reinterprets_the_same_memory(self) -> None:
        raw = bytes(8)
        as_ints = memoryview(raw).cast("i")
        assert as_ints.obj is raw
        assert len(as_ints) == 2
        assert as_ints.nbytes == 8
        assert as_ints.tolist() == [0, 0]

    def test_a_shape_adds_dimensions_without_copying(self) -> None:
        raw = bytes(range(6))
        grid = memoryview(raw).cast("B", (2, 3))
        assert grid.obj is raw
        assert grid.shape == (2, 3)
        assert grid.strides == (3, 1)
        assert grid.tolist() == [[0, 1, 2], [3, 4, 5]]

    def test_the_byte_size_must_not_change(self) -> None:
        with pytest.raises(TypeError, match="product\\(shape\\) \\* itemsize != buffer size"):
            memoryview(b"abcd").cast("i", (3,))

    def test_one_side_must_be_a_byte_format(self) -> None:
        ints = memoryview(bytes(8)).cast("i")
        with pytest.raises(TypeError, match="cannot cast between two non-byte formats"):
            ints.cast("h")
        assert ints.cast("B").shape == (8,)

    def test_either_the_source_or_the_new_shape_must_be_one_dimensional(self) -> None:
        grid = memoryview(bytes(range(6))).cast("B", (2, 3))
        with pytest.raises(TypeError, match="cast must be 1D -> ND or ND -> 1D"):
            grid.cast("B", (3, 2))
        assert grid.cast("B").shape == (6,)
        assert grid.cast("B", (6,)).shape == (6,)
        assert grid.cast("B", (6,)).cast("B", (3, 2)).tolist() == [[0, 1], [2, 3], [4, 5]]

    def test_a_non_contiguous_view_cannot_be_cast(self) -> None:
        with pytest.raises(TypeError, match="C-contiguous"):
            memoryview(bytes(10))[::2].cast("H")

    def test_cast_allocates_no_copy(self, buffers: tuple[bytes, bytes]) -> None:
        large = memoryview(buffers[1])
        assert traced_peak(lambda: large.cast("c")) < 1024
        assert traced_peak(lambda: large.cast("B", (1_000, 10_000))) < 1024

    @pytest.mark.timing
    def test_cast_time_is_flat(self, buffers: tuple[bytes, bytes]) -> None:
        small, large = memoryview(buffers[0]), memoryview(buffers[1])
        ratio = growth(lambda: small.cast("c"), lambda: large.cast("c"), loops=1_000)
        assert ratio < FLAT_CEILING, f"x100 in n cost x{ratio:.2f}"


class TestToReadOnly:
    """Row: toreadonly() is a new O(1) view of the same buffer."""

    def test_a_read_only_twin(self) -> None:
        ba = bytearray(b"hello")
        writable = memoryview(ba)
        frozen = writable.toreadonly()

        assert frozen.obj is ba
        assert frozen.readonly
        assert not writable.readonly
        with pytest.raises(TypeError, match="read-only"):
            frozen[0] = 72
        writable[0] = 72
        assert frozen[0] == 72

    def test_allocates_no_copy(self, buffers: tuple[bytes, bytes]) -> None:
        large = memoryview(buffers[1])
        assert traced_peak(large.toreadonly) < 1024


class TestRelease:
    """Row: release() ends the view; until then a bytearray cannot be resized."""

    def test_a_live_view_pins_the_size(self) -> None:
        ba = bytearray(b"test")
        mv = memoryview(ba)
        with pytest.raises(BufferError, match="cannot be re-sized"):
            ba.append(33)
        mv.release()
        ba.append(33)
        assert ba == bytearray(b"test!")

    def test_reading_and_writing_afterwards_raise(self) -> None:
        mv = memoryview(bytearray(b"test"))
        mv.release()
        with pytest.raises(ValueError, match="released memoryview"):
            mv[0]
        with pytest.raises(ValueError, match="released memoryview"):
            mv[0] = 1
        with pytest.raises(ValueError, match="released memoryview"):
            len(mv)
        with pytest.raises(ValueError, match="released memoryview"):
            bytes(mv)

    def test_release_is_idempotent_and_equality_and_a_cached_hash_survive(self) -> None:
        mv = memoryview(b"test")
        cached = hash(mv)
        mv.release()
        mv.release()
        assert mv == mv
        assert mv != memoryview(b"test")
        assert hash(mv) == cached

        fresh = memoryview(b"test")
        fresh.release()
        with pytest.raises(ValueError, match="released memoryview"):
            hash(fresh)

    def test_the_context_manager_releases(self) -> None:
        ba = bytearray(b"test")
        with memoryview(ba) as mv:
            assert mv[0] == 116
        ba.append(33)
        assert len(ba) == 5


class TestAttributes:
    """The Attributes table."""

    def test_values_for_a_bytes_view(self) -> None:
        b = b"hello"
        mv = memoryview(b)
        assert mv.obj is b
        assert mv.nbytes == 5
        assert mv.readonly
        assert mv.format == "B"
        assert mv.itemsize == 1
        assert mv.ndim == 1
        assert mv.shape == (5,)
        assert mv.strides == (1,)
        assert mv.suboffsets == ()
        assert mv.contiguous and mv.c_contiguous and mv.f_contiguous

    def test_nbytes_is_elements_times_itemsize(self) -> None:
        mv = memoryview(array.array("i", [1, 2, 3]))
        assert mv.nbytes == len(mv) * mv.itemsize == 12

    def test_shape_and_strides_are_fresh_tuples_of_ndim_entries(self) -> None:
        grid = memoryview(bytes(24)).cast("B", (2, 3, 4))
        shape, strides = grid.shape, grid.strides
        assert grid.ndim == 3
        assert shape is not None and strides is not None
        assert len(shape) == len(strides) == 3
        assert grid.shape is not grid.shape
        assert grid.strides is not grid.strides
        assert grid.suboffsets == ()

    def test_a_scalar_view_shares_the_empty_tuple(self) -> None:
        scalar = memoryview(b"a").cast("B", ())
        assert scalar.ndim == 0
        assert scalar.shape == scalar.strides == scalar.suboffsets == ()
        assert scalar.shape is scalar.shape

    def test_contiguity_flags_follow_the_layout(self) -> None:
        stepped = memoryview(bytes(10))[::2]
        assert not stepped.contiguous
        assert not stepped.c_contiguous
        assert not stepped.f_contiguous
        assert stepped.strides == (2,)

        grid = memoryview(bytes(6)).cast("B", (2, 3))
        assert grid.c_contiguous
        assert not grid.f_contiguous
        assert grid.contiguous


def count(view: memoryview, value: int) -> int:
    return view.count(value)  # pyright: ignore[reportOptionalCall]


def index(view: memoryview, value: int, *bounds: int) -> int:
    return view.index(value, *bounds)  # pyright: ignore[reportOptionalCall]


@pytest.mark.skipif(sys.version_info < (3, 14), reason="count() and index() are 3.14+")
class TestCountAndIndex:
    """Rows: count() and index() scan linearly; index() stops at the first hit."""

    def test_stated_behaviour(self) -> None:
        mv = memoryview(b"abcb")
        assert count(mv, 98) == 2
        assert index(mv, 98) == 1
        assert index(mv, 98, 2) == 3
        with pytest.raises(ValueError, match="not found"):
            index(mv, 1)

    def test_one_dimensional_views_only(self) -> None:
        grid = memoryview(bytes(6)).cast("B", (2, 3))
        with pytest.raises(NotImplementedError, match="not implemented"):
            count(grid, 0)
        with pytest.raises(NotImplementedError, match="not implemented"):
            index(grid, 0)

    @pytest.mark.timing
    def test_both_scan_linearly(self, buffers: tuple[bytes, bytes]) -> None:
        small, large = memoryview(buffers[0]), memoryview(buffers[1])

        def missing(view: memoryview) -> None:
            try:
                index(view, 1)
            except ValueError:
                pass

        counting = growth(lambda: count(small, 1), lambda: count(large, 1))
        searching = growth(lambda: missing(small), lambda: missing(large))
        assert LINEAR_FLOOR < counting < LINEAR_CEILING, (
            f"x100 in n cost x{counting:.1f} for count()"
        )
        assert LINEAR_FLOOR < searching < LINEAR_CEILING, (
            f"x100 in n cost x{searching:.1f} for a missing index()"
        )

    @pytest.mark.timing
    def test_an_early_hit_costs_flat_time(self, buffers: tuple[bytes, bytes]) -> None:
        small = memoryview(b"\x01" + buffers[0][1:])
        large = memoryview(b"\x01" + buffers[1][1:])
        ratio = growth(lambda: index(small, 1), lambda: index(large, 1), loops=1_000)
        assert ratio < FLAT_CEILING, f"x100 in n cost x{ratio:.2f} for a hit at index 0"


@pytest.mark.skipif(sys.version_info >= (3, 14), reason="count() and index() exist here")
def test_count_and_index_are_absent_before_3_14() -> None:
    assert not hasattr(memoryview, "count")
    assert not hasattr(memoryview, "index")


class TestVersionNotes:
    """The Version Notes section."""

    def test_python_exporters_from_3_12(self) -> None:
        assert hasattr(memoryview, "__buffer__") == (sys.version_info >= (3, 12))
        assert hasattr(memoryview, "__release_buffer__") == (sys.version_info >= (3, 12))

    def test_zero_dimensional_length_from_3_12(self) -> None:
        scalar = memoryview(b"a").cast("B", ())
        assert scalar.ndim == 0
        assert scalar.tolist() == 97
        if sys.version_info >= (3, 12):
            with pytest.raises(TypeError, match="0-dim memory has no length"):
                len(scalar)
        else:
            assert len(scalar) == 1

    def test_generic_alias_from_3_14(self) -> None:
        if sys.version_info >= (3, 14):
            assert str(memoryview[int]) == "memoryview[int]"  # pyright: ignore[reportIndexIssue]
        else:
            with pytest.raises(TypeError):
                memoryview[int]  # pyright: ignore[reportIndexIssue]


class TestBestPractices:
    """Prose: a view object is bigger than a short bytes copy, and a view is not a list."""

    def test_the_view_object_outweighs_a_short_bytes_copy(self) -> None:
        view_size = sys.getsizeof(memoryview(b""))
        assert view_size > sys.getsizeof(bytes(100))
        assert view_size < sys.getsizeof(bytes(200))

    def test_no_concatenation_or_append(self) -> None:
        mv = memoryview(b"hello")
        with pytest.raises(TypeError):
            _ = mv + mv  # pyright: ignore[reportOperatorIssue]
        assert bytes(mv) + bytes(mv) == b"hellohello"
        assert not hasattr(mv, "append")


class TestStatedExampleValues:
    """The values the page's comments give."""

    def test_protocol_parser(self) -> None:
        def parse_header(data: bytes) -> dict[str, int]:
            view = memoryview(data)
            return {
                "type": view[0],
                "length": int.from_bytes(view[1:3], "big"),
                "flags": view[3],
            }

        assert parse_header(b"\x01\x00\x10\xff" + b"payload...") == {
            "type": 1,
            "length": 16,
            "flags": 255,
        }

    def test_binary_protocol(self) -> None:
        view = memoryview(b"\x01\x02\x03\x04")
        assert view[0] == 1
        assert view[1] == 2
        assert bytes(view[2:4]) == b"\x03\x04"

    def test_batch_processing_sums_every_byte(self) -> None:
        data = b"x" * 1_000_000
        mv = memoryview(data)
        total = sum(sum(mv[i : i + 1024]) for i in range(0, len(mv), 1024))
        assert total == ord("x") * 1_000_000

    def test_file_header(self) -> None:
        data = b"MAGC\x02" + bytes(11) + b"payload"
        mv = memoryview(data)
        assert bytes(mv[0:4]) == b"MAGC"
        assert mv[4] == 2
        assert bytes(mv[16:]) == b"payload"

    def test_fill_buffer(self) -> None:
        buffer = bytearray(b"\xff" * 1000)
        view = memoryview(buffer)
        for i in range(len(view)):
            view[i] = 0
        assert buffer == bytearray(1000)


class TestPublicNamesAreDocumented:
    """The Methods and Attributes tables against dir(memoryview)."""

    VERSION_GATED = {"count": (3, 14), "index": (3, 14)}

    @staticmethod
    def documented_names() -> set[str]:
        text = PAGE.read_text(encoding="utf-8")
        start = text.index("## Methods")
        end = text.index("## Basic Usage")
        names: set[str] = set()
        for line in text[start:end].splitlines():
            if not line.startswith("| `"):
                continue
            first_cell = line.split("|")[1]
            names.update(re.findall(r"`(\w+)", first_cell))
        return names

    def test_the_extractor_sees_both_tables(self) -> None:
        assert {"tobytes", "suboffsets", "f_contiguous"} <= self.documented_names()

    def test_every_public_name_has_a_row(self) -> None:
        public = {name for name in dir(memoryview) if not name.startswith("_")}

        missing = public - self.documented_names()

        assert not missing, f"public names without a row: {sorted(missing)}"

    def test_every_row_names_something_that_exists(self) -> None:
        public = {name for name in dir(memoryview) if not name.startswith("_")}
        text = PAGE.read_text(encoding="utf-8")

        invented = self.documented_names() - public
        for name in invented:
            assert name in self.VERSION_GATED, f"no such attribute: {name}"
            assert sys.version_info < self.VERSION_GATED[name], f"{name} should exist here"
        for name, (major, minor) in self.VERSION_GATED.items():
            assert re.search(rf"^\| `{name}\(.*\| {major}\.{minor}\+\.", text, re.MULTILINE), name


EXPECTED_BLOCKS = 26


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


def _run(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "_block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, script.name],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Every block runs, under the interpreter running the tests."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []

        for line, source in _blocks():
            result = _run(source, tmp_path)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()}")

        assert not failures, "\n".join(failures)

    def test_every_block_binds_the_names_it_uses(self, tmp_path: pathlib.Path) -> None:
        """A block that leans on a name from its prose rather than binding it
        compiles and then dies at run time, so NameError gets its own check."""
        failures: list[str] = []

        for line, source in _blocks():
            result = _run(source, tmp_path)
            if "NameError" in result.stderr:
                failures.append(f"{PAGE.name}:{line}: {result.stderr.strip()}")

        assert not failures, "\n".join(failures)

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        batch = next(source for _, source in _blocks() if "process_chunks" in source)
        broken = batch.replace("def process_chunk(chunk):", "def process_chunk_(chunk):", 1)
        assert broken != batch, "the mutation did not rename the helper"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr
