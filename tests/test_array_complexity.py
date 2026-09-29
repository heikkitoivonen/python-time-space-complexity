"""Tests for docs/stdlib/array.md.

The page prices `array.array` as a list with packed storage: a contiguous,
over-allocated buffer, so the end is cheap and the middle shifts, and every
read builds a Python object from a stored value. Growth classes are settled
by timing across a size step; space, laziness of copies, call counts and the
buffer-management notes are settled by observation - traced allocation,
`sys.getsizeof()`, identity, a counting `__eq__` and a recording file - which
needs no tolerance.

Measurement scope:

* Linear rows are timed at n = 20,000 and n = 2,000,000 (a 100x step) with
  the fastest of several runs, and the ratio is asserted between 20 and
  1,000, which excludes both O(1) (x1) and O(n^2) (x10,000). Constant rows
  are timed at n = 1,000 and n = 1,000,000 and asserted under 3x. Setup is
  outside the timed call; operations that mutate restore the size inside it
  with an O(1) partner (append/pop at the end) or pair two O(n) shifts.
  `extend()` is asserted O(k) by the same 100x step in k into an empty array,
  and independent of n by extending a 1,000- and a 1,000,000-item array by
  ten items and deleting them again, which reallocates neither time.
  Lists fed to an array, and the array `tolist()` converts, hold the values
  0 to 255, which CPython caches: two million distinct ints would take 64 MB
  on their own. Distinct values are not timed on those rows.
* `a == b` for unequal lengths is timed like a constant row against equal
  arrays, which are timed like a linear row.
* `x in a`, `index()`, `remove()` and `count()` are counted with an object
  whose `__eq__` records calls: a match at position 5 of 1,000 costs 6
  comparisons for the first three and 1,000 for `count()`.
* Reads building new objects: `a[0] is not a[0]` for a value outside the
  small-int cache, and `tolist()` items are fresh objects. `sum()` over a
  1,000,000-item `'q'` array is timed against the same list and asserted not
  10% or more faster (over 0.9x the list's time).
* `tofile()` writes an 8 MB array to a sink that keeps nothing with a traced
  peak under 200 KB, against `tobytes()` over 8 MB. `fromfile()` is observed
  to call `read()` once with k·itemsize, and to append 1,000 items before
  raising `EOFError` when asked for 2,000.
* `copy.deepcopy()` of a 1,000,000-item `'q'` array peaks under 1.1x the
  8 MB buffer, so the copy holds no per-item objects.
* The buffer: 2,000 appends show more than one and far fewer than 2,000
  distinct `getsizeof()` values; 900 `pop()` calls leave `getsizeof()`
  unchanged while one `del a[10:]` shrinks it. `clear()` (3.13+) on 1,000
  items returns `getsizeof()` to an empty array's. A live `memoryview` sees an item write and makes `append()`,
  `pop()`, `extend()` and slice deletion raise `BufferError`.
* `fromlist()` leaves the array unchanged on a bad item, `extend()` keeps the
  items before it; `+=` and slice assignment reject a list, and `extend()`
  and `+=` reject an array of another type code. Item assignment out of
  range of an integer type code raises `OverflowError`. Slices are copies.
* Item sizes: `'b'`/`'B'` 1, `'f'` 4, `'d'` 8, and the C-type minimums for
  the other integer codes. The `'w'` code and `clear()` are asserted on
  3.13+, and the `'u'` `DeprecationWarning` on 3.13+.
* Memory against a list uses 10,000 ints from 1,000 up, so none is a cached
  small int: `getsizeof()` of an `'i'` array is under the list's, the list's
  reachable size is over twice its `getsizeof()`, and an array built from a
  list holds at least len·itemsize bytes of payload.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* That a reallocating call can move the items already there follows from
  `array_resize()` calling `PyMem_Realloc`; whether it moves is the
  allocator's choice and is not observed.
* `clear()` and `memoryview()` are O(1) and `buffer_info()`, `typecode` and
  `itemsize` are attribute reads, from Modules/arraymodule.c on the 3.10-3.14
  release branches (`clear()` resizes to zero and frees the buffer; the
  allocator's cost for that free is not measured).
* `a < b` follows the same comparison loop as `==`, which is what is timed;
  ordering comparisons are not timed separately.
* `byteswap()`, `reverse()`, `tounicode()`, `fromunicode()` and `a * m` are
  timed only in n (and not in m); the tounicode/fromunicode timings use `'w'`
  on 3.13+ and skip the deprecated `'u'`.
* Element comparison cost is priced O(1); arrays hold only numbers and
  characters, so only a caller's custom `__eq__` can change that, and the
  counting object above is the only such case exercised.
* Item width is varied only by the itemsize checks; the timings use `'q'`,
  `'i'` or `'d'` throughout.
"""

from __future__ import annotations

import array
import copy
import io
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import warnings
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "array.md"
EXPECTED_BLOCKS = 10

SMALL = 20_000
LARGE = 2_000_000

# The Windows heap hands a block above about 1 MB to VirtualAlloc and returns it
# on free, so each call that allocates one pays for freshly committed,
# zero-filled pages, while a 160 KB result at SMALL stays cache-resident. A row
# whose work is one bulk copy into a new buffer then costs about x2,000 for the
# 100x step, and x10 for each further 10x step above the threshold.
FRESH_PAGES_ON_WINDOWS = pytest.mark.skipif(
    sys.platform == "win32",
    reason="on Windows a new buffer above about 1 MB is freshly committed, zero-filled pages, "
    "so the 100x step crosses from cache-resident to page-faulting memory",
)
BULK_COPY_ROWS = {
    "slice",
    "a + b",
    "a * 2",
    "copy.copy",
    "copy.deepcopy",
    "tobytes",
    "frombytes",
    "fromfile",
    "fromunicode",
}


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


class DiscardingSink:
    """A binary file-like object that keeps nothing it is given."""

    def write(self, data: bytes) -> int:
        return len(data)


class CountingEq:
    """Equal to one value; records every comparison made against it."""

    def __init__(self, target: int) -> None:
        self.target = target
        self.calls = 0

    def __eq__(self, other: object) -> bool:
        self.calls += 1
        return other == self.target

    __hash__ = None  # type: ignore[assignment]


def _wide(n: int) -> array.array[int]:
    return array.array("q", range(10**9, 10**9 + n))


def _cached(n: int) -> list[int]:
    """n values from 0 to 255, which CPython caches, so the list holds no ints of its own."""
    return [i & 255 for i in range(n)]


def _unicode(n: int) -> array.array[str]:
    return array.array("w", "x" * n)  # pyright: ignore[reportArgumentType]


# Each builder returns the operation to time on an n-item input.
LINEAR: dict[str, Callable[[int], Callable[[], Any]]] = {
    "array(typecode, list)": lambda n: (lambda src: lambda: array.array("q", src))(_cached(n)),
    "array(typecode, iterator)": lambda n: lambda: array.array("q", iter(range(n))),
    "extend(k items) into an empty array": (
        lambda n: (lambda src: lambda: array.array("q").extend(src))(_cached(n))
    ),
    "slice": lambda n: (lambda a: lambda: a[1:])(_wide(n)),
    "x in a, missing": lambda n: (lambda a: lambda: -1 in a)(_wide(n)),
    "index(last)": lambda n: (lambda a: lambda: a.index(a[-1]))(_wide(n)),
    "count": lambda n: (lambda a: lambda: a.count(-1))(_wide(n)),
    "== on equal arrays": lambda n: (lambda a, b: lambda: a == b)(_wide(n), _wide(n)),
    "insert(0) + pop(0)": lambda n: (lambda a: lambda: (a.insert(0, 1), a.pop(0)))(_wide(n)),
    "remove(last) + append": (
        lambda n: (lambda a: lambda: (a.remove(a[-1]), a.append(10**9 + n - 1)))(_wide(n))
    ),
    "del a[0] + insert(0)": lambda n: (lambda a: lambda: (a.__delitem__(0), a.insert(0, 1)))(
        _wide(n)
    ),
    "reverse": lambda n: (lambda a: a.reverse)(_wide(n)),
    "byteswap": lambda n: (lambda a: a.byteswap)(_wide(n)),
    "a + b": lambda n: (lambda a: lambda: a + a)(_wide(n)),
    "a * 2": lambda n: (lambda a: lambda: a * 2)(_wide(n)),
    "copy.copy": lambda n: (lambda a: lambda: copy.copy(a))(_wide(n)),
    "copy.deepcopy": lambda n: (lambda a: lambda: copy.deepcopy(a))(_wide(n)),
    "tolist": lambda n: (lambda a: a.tolist)(array.array("q", _cached(n))),
    "fromlist": lambda n: (lambda src: lambda: array.array("q").fromlist(src))(_cached(n)),
    "tobytes": lambda n: (lambda a: a.tobytes)(_wide(n)),
    "frombytes": lambda n: (lambda raw: lambda: array.array("q").frombytes(raw))(
        _wide(n).tobytes()
    ),
    "tofile": lambda n: (lambda a: lambda: a.tofile(DiscardingSink()))(_wide(n)),
    "fromfile": lambda n: (lambda raw: lambda: array.array("q").fromfile(io.BytesIO(raw), n))(
        _wide(n).tobytes()
    ),
}

UNICODE_LINEAR: dict[str, Callable[[int], Callable[[], Any]]] = {
    "tounicode": lambda n: (lambda a: a.tounicode)(_unicode(n)),
    "fromunicode": lambda n: (lambda s: lambda: array.array("w").fromunicode(s))("x" * n),
}

CONSTANT: dict[str, Callable[[int], Callable[[], Any]]] = {
    "a[i]": lambda n: (lambda a: lambda: a[n // 2])(_wide(n)),
    "a[i] = x": lambda n: (lambda a: lambda: a.__setitem__(n // 2, 7))(_wide(n)),
    "len": lambda n: (lambda a: lambda: len(a))(_wide(n)),
    "append + pop()": lambda n: (lambda a: lambda: (a.append(1), a.pop()))(_wide(n)),
    "extend(10) + del a[-10:]": (
        lambda n: (lambda a, src: lambda: (a.extend(src), a.__delitem__(slice(-10, None))))(
            _wide(n), list(range(10))
        )
    ),
    "== on unequal lengths": lambda n: (lambda a, b: lambda: a == b)(_wide(n), _wide(n + 1)),
    "memoryview": lambda n: (lambda a: lambda: memoryview(a).release())(_wide(n)),
    "buffer_info": lambda n: (lambda a: a.buffer_info)(_wide(n)),
}


def _rows(builders: dict[str, Callable[[int], Callable[[], Any]]]) -> list[Any]:
    """One parameter per row, the bulk copies marked to skip on Windows."""
    return [
        pytest.param(name, marks=FRESH_PAGES_ON_WINDOWS) if name in BULK_COPY_ROWS else name
        for name in builders
    ]


def _growth(builder: Callable[[int], Callable[[], Any]], small: int, large: int) -> float:
    operations = [builder(small), builder(large)]
    for operation in operations:
        operation()
    durations = [best_ns(operation, repeats=7, inner=3) for operation in operations]
    return durations[1] / durations[0]


class TestLinearRows:
    """Every O(n) or O(k) row: 100x the items costs between x20 and x1,000,
    which a constant (x1) and a quadratic (x10,000) both miss."""

    @pytest.mark.timing
    @pytest.mark.parametrize("name", _rows(LINEAR))
    def test_a_hundred_times_the_items_costs_about_a_hundred_times(self, name: str) -> None:
        ratio = _growth(LINEAR[name], SMALL, LARGE)

        assert 20 < ratio < 1_000, f"{name}: 100x the items cost x{ratio:.1f}"

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 13), reason="'w' was added in 3.13")
    @pytest.mark.parametrize("name", _rows(UNICODE_LINEAR))
    def test_the_unicode_conversions_are_linear(self, name: str) -> None:
        ratio = _growth(UNICODE_LINEAR[name], SMALL, LARGE)

        assert 20 < ratio < 1_000, f"{name}: 100x the characters cost x{ratio:.1f}"


class TestConstantRows:
    """Every O(1) row, and `==` between arrays of different lengths: 1,000x
    the items costs under x3."""

    @pytest.mark.timing
    @pytest.mark.parametrize("name", list(CONSTANT))
    def test_a_thousand_times_the_items_costs_the_same(self, name: str) -> None:
        ratio = _growth(CONSTANT[name], 1_000, 1_000_000)

        assert ratio < 3, f"{name}: 1,000x the items cost x{ratio:.2f}"


class TestSearchStopsAtTheFirstMatch:
    """`x in a`, `index()` and `remove()` stop at the first match;
    `count()` compares every item."""

    @staticmethod
    def _values() -> array.array[int]:
        return array.array("q", range(1_000))

    def test_in_stops_at_the_match(self) -> None:
        probe = CountingEq(5)

        assert probe in self._values()
        assert probe.calls == 6

    def test_index_stops_at_the_match(self) -> None:
        probe = CountingEq(5)

        assert self._values().index(probe) == 5  # pyright: ignore[reportArgumentType]
        assert probe.calls == 6

    def test_remove_stops_at_the_match(self) -> None:
        values = self._values()
        probe = CountingEq(5)

        values.remove(probe)  # pyright: ignore[reportArgumentType]

        assert probe.calls == 6
        assert len(values) == 999
        assert 5 not in values

    def test_count_compares_every_item(self) -> None:
        probe = CountingEq(5)

        assert self._values().count(probe) == 1  # pyright: ignore[reportArgumentType]
        assert probe.calls == 1_000


class TestReadsBuildObjects:
    """`a[i]`, iteration and `tolist()` build a Python object from the stored
    value each time; the array holds no objects."""

    def test_each_read_is_a_new_object(self) -> None:
        values = array.array("q", [10**12])

        assert values[0] == 10**12
        assert values[0] is not values[0]

    @pytest.mark.timing
    def test_reading_every_item_is_no_faster_than_from_a_list(self) -> None:
        """The page's "the saving is in storage, not in element access": `sum()`
        over a 1,000,000-item `'q'` array against the same values in a list.
        Boxing each read made the array about 2x slower here; the assertion
        only excludes the array being 10% or more faster."""
        values = list(range(10**9, 10**9 + 1_000_000))
        packed = array.array("q", values)

        list_ns = best_ns(lambda: sum(values), repeats=5)
        array_ns = best_ns(lambda: sum(packed), repeats=5)

        assert array_ns > list_ns * 0.9, f"array {array_ns:.0f}ns against list {list_ns:.0f}ns"

    def test_tolist_builds_fresh_objects(self) -> None:
        values = array.array("q", [10**12, 10**12])

        first, second = values.tolist(), values.tolist()

        assert first == second
        assert first[0] is not second[0]

    def test_a_slice_is_a_copy(self) -> None:
        values = array.array("i", [1, 2, 3])

        window = values[1:]
        window[0] = 0

        assert values.tolist() == [1, 2, 3]
        assert type(window) is array.array


class TestBufferGrowthAndShrinking:
    """`append()` is O(1) amortized: the buffer grows in steps. Popping one
    item at a time never shrinks it; one call removing a run does."""

    def test_append_reallocates_occasionally(self) -> None:
        values = array.array("i")
        sizes: set[int] = set()
        for _ in range(2_000):
            values.append(0)
            sizes.add(sys.getsizeof(values))

        assert 1 < len(sizes) < 200, f"{len(sizes)} distinct sizes over 2,000 appends"

    def test_popping_one_at_a_time_keeps_the_buffer(self) -> None:
        values = array.array("i", range(1_000))
        full = sys.getsizeof(values)

        for _ in range(900):
            values.pop()

        assert len(values) == 100
        assert sys.getsizeof(values) == full

    def test_deleting_a_run_shrinks_it(self) -> None:
        values = array.array("i", range(1_000))
        full = sys.getsizeof(values)

        del values[10:]

        assert sys.getsizeof(values) < full // 10

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="clear() was added in 3.13")
    def test_clear_empties_it(self) -> None:
        values = array.array("i", range(1_000))

        values.clear()  # pyright: ignore[reportAttributeAccessIssue]

        assert len(values) == 0
        assert sys.getsizeof(values) == sys.getsizeof(array.array("i"))


class TestFilesAndBytes:
    """`tofile()` writes in blocks, O(1) extra space; `tobytes()` copies the
    whole buffer; `fromfile()` makes one `read()` and keeps a short read."""

    SIZE = 1_000_000

    def test_tofile_needs_no_copy_of_the_array(self) -> None:
        values = array.array("d", [0.5]) * self.SIZE
        sink = DiscardingSink()
        values.tofile(sink)  # warm

        peak = peak_bytes(lambda: values.tofile(sink))

        assert peak < 200_000, f"tofile() of an 8 MB array peaked at {peak} bytes"

    def test_tobytes_copies_the_whole_buffer(self) -> None:
        values = array.array("d", [0.5]) * self.SIZE

        peak = peak_bytes(values.tobytes)

        assert peak > self.SIZE * values.itemsize, f"tobytes() peaked at only {peak} bytes"

    def test_tofile_writes_every_byte(self) -> None:
        values = array.array("i", range(100_000))
        stream = io.BytesIO()

        values.tofile(stream)

        assert stream.getvalue() == values.tobytes()

    def test_fromfile_makes_one_read_of_k_items(self) -> None:
        raw = array.array("q", range(1_000)).tobytes()
        requests: list[int] = []

        class Recording(io.BytesIO):
            def read(self, size: int | None = -1, /) -> bytes:
                requests.append(-1 if size is None else size)
                return super().read(size)

        values = array.array("q")
        values.fromfile(Recording(raw), 1_000)

        assert requests == [8_000]
        assert values.tolist() == list(range(1_000))

    def test_a_short_file_appends_what_it_had_then_raises(self) -> None:
        stream = io.BytesIO(array.array("d", [0.5] * 1_000).tobytes())
        values = array.array("d")

        with pytest.raises(EOFError):
            values.fromfile(stream, 2_000)

        assert len(values) == 1_000

    def test_frombytes_needs_whole_items(self) -> None:
        with pytest.raises(ValueError, match="multiple of item size"):
            array.array("i").frombytes(b"\x00" * 3)

    def test_round_trip_and_byteswap(self) -> None:
        values = array.array("h", [1, 256])
        restored = array.array("h")
        assert values.tobytes()[:2] == (1).to_bytes(2, sys.byteorder), "native byte order"

        restored.frombytes(values.tobytes())
        assert restored == values

        restored.byteswap()
        assert restored.tolist() == [256, 1]


class TestCopies:
    """`copy.copy()` and `copy.deepcopy()` are the same buffer copy: the items
    are values, so there is nothing to recurse into."""

    def test_deepcopy_allocates_only_the_buffer(self) -> None:
        values = array.array("q", range(1_000_000))
        buffer = len(values) * values.itemsize
        copy.deepcopy(values)  # warm

        peak = peak_bytes(lambda: copy.deepcopy(values))

        assert buffer < peak < buffer * 1.1, f"deepcopy of a {buffer}-byte buffer peaked at {peak}"

    def test_both_copies_are_independent(self) -> None:
        values = array.array("i", [1, 2, 3])

        shallow, deep = copy.copy(values), copy.deepcopy(values)
        values[0] = 9

        assert shallow.tolist() == deep.tolist() == [1, 2, 3]


class TestAddingItems:
    """`extend()` converts one item at a time; `fromlist()` is all or
    nothing; `+=` and slice assignment take only an array of the same code."""

    def test_extend_keeps_items_before_a_bad_one(self) -> None:
        values = array.array("i", [1])

        with pytest.raises(TypeError):
            values.extend([2, "x"])  # type: ignore[list-item]

        assert values.tolist() == [1, 2]

    def test_fromlist_keeps_nothing_on_a_bad_item(self) -> None:
        values = array.array("i", [1])

        with pytest.raises(TypeError):
            values.fromlist([2, "x"])  # pyright: ignore[reportArgumentType]

        assert values.tolist() == [1]

    def test_fromlist_takes_only_a_list(self) -> None:
        with pytest.raises(TypeError, match="must be list"):
            array.array("i").fromlist((1, 2))  # type: ignore[arg-type]

    def test_extend_takes_any_iterable_but_an_array_must_match(self) -> None:
        values = array.array("i")

        values.extend(range(3))
        values.extend(array.array("i", [3]))

        assert values.tolist() == [0, 1, 2, 3]
        with pytest.raises(TypeError, match="same kind"):
            values.extend(array.array("d", [1.0]))  # type: ignore[arg-type]

    def test_inplace_add_needs_an_array_of_the_same_code(self) -> None:
        values = array.array("i", [1])

        values += array.array("i", [2])

        assert values.tolist() == [1, 2]
        with pytest.raises(TypeError, match="array"):
            values += [3]  # type: ignore[operator]
        with pytest.raises(TypeError):
            values += array.array("d", [3.0])  # type: ignore[operator]

    def test_slice_assignment_needs_an_array(self) -> None:
        values = array.array("i", [1, 2, 3])

        values[1:2] = array.array("i", [7, 8, 9])

        assert values.tolist() == [1, 7, 8, 9, 3]
        with pytest.raises(TypeError, match="can only assign array"):
            values[0:1] = [5]  # type: ignore[call-overload]

    def test_a_value_out_of_range_raises(self) -> None:
        values = array.array("b", [0])

        with pytest.raises(OverflowError):
            values[0] = 128


class TestMemoryview:
    """`memoryview(a)` shares the buffer, and a live view blocks resizing."""

    def test_the_view_shares_memory(self) -> None:
        values = array.array("i", [1, 2, 3])
        view = memoryview(values)

        values[0] = 10

        assert view[0] == 10
        view.release()

    @pytest.mark.parametrize(
        "resize",
        [
            lambda a: a.append(4),
            lambda a: a.pop(),
            lambda a: a.extend([4]),
            lambda a: a.__delitem__(slice(0, 1)),
        ],
        ids=["append", "pop", "extend", "del slice"],
    )
    def test_a_live_view_blocks_resizing(self, resize: Callable[[Any], Any]) -> None:
        values = array.array("i", [1, 2, 3])
        view = memoryview(values)

        with pytest.raises(BufferError, match="exporting buffers"):
            resize(values)

        view.release()
        resize(values)


class TestTypeCodes:
    """The type code fixes `itemsize`; the C integer codes fix only minimums."""

    MINIMUMS = {"h": 2, "H": 2, "i": 2, "I": 2, "l": 4, "L": 4, "q": 8, "Q": 8}

    def test_fixed_and_minimum_sizes(self) -> None:
        assert array.array("b").itemsize == array.array("B").itemsize == 1
        assert array.array("f").itemsize == 4
        assert array.array("d").itemsize == 8
        for code, minimum in self.MINIMUMS.items():
            assert array.array(code).itemsize >= minimum, code

    def test_typecodes_lists_the_numeric_codes(self) -> None:
        assert set("bBhHiIlLqQfd") <= set(array.typecodes)
        assert array.ArrayType is array.array

    def test_typecode_and_itemsize_are_fixed(self) -> None:
        values = array.array("d", [1.0])

        values.extend([2.0] * 1_000)

        assert values.typecode == "d"
        assert values.itemsize == 8

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="'w' was added in 3.13")
    def test_w_is_a_four_byte_character(self) -> None:
        values = _unicode(3)

        assert "w" in array.typecodes
        assert values.itemsize == 4
        assert values.tounicode() == "xxx"
        values.fromunicode("é")
        assert values.tounicode() == "xxxé"

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="deprecated with a warning in 3.13")
    def test_u_warns(self) -> None:
        with pytest.warns(DeprecationWarning, match="'u' type code"):
            array.array("u")

    def test_unicode_conversions_need_a_unicode_array(self) -> None:
        with pytest.raises(ValueError, match="unicode type arrays"):
            array.array("i").tounicode()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert array.array("u", "ab").tounicode() == "ab"


class TestMemoryAgainstAList:
    """`getsizeof()` of a list counts pointers, not the objects they reach;
    an array's counts its packed items."""

    VALUES = list(range(1_000, 11_000))

    def test_the_values_are_distinct_objects(self) -> None:
        def fresh(value: int) -> int:
            return int(str(value))

        assert fresh(1_000) is not fresh(1_000), "1,000 is outside the small-int cache"

    def test_an_int_array_is_smaller_than_the_list_s_pointers(self) -> None:
        packed = array.array("i", self.VALUES)

        assert sys.getsizeof(packed) < sys.getsizeof(self.VALUES)

    def test_getsizeof_leaves_out_the_list_s_objects(self) -> None:
        shallow = sys.getsizeof(self.VALUES)
        reachable = shallow + sum(sys.getsizeof(value) for value in self.VALUES)

        assert reachable > 2 * shallow

    def test_an_array_s_payload_is_its_items(self) -> None:
        packed = array.array("i", self.VALUES)
        payload = sys.getsizeof(packed) - sys.getsizeof(array.array("i"))

        assert len(packed) * packed.itemsize <= payload < len(packed) * packed.itemsize * 1.1


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
    """Each block runs in its own subprocess and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "sys.getsizeof(values) == full" in s)
        mutated = source.replace(
            "sys.getsizeof(values) == full", "sys.getsizeof(values) != full", 1
        )

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
