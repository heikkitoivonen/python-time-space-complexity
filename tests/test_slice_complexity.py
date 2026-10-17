"""Tests for docs/builtins/slice.md.

A slice object is built by PySlice_New in Objects/sliceobject.c, which stores
its three arguments with new references and no conversion, and
slice.indices() resolves them with integer arithmetic. Applying a slice is the
sequence's own subscript: list_subscript, tuplesubscript, unicode_subscript,
bytes_subscript and bytearray_subscript copy the selected items,
range_subscript computes a new range, and memory_subscript builds a new view
on the same buffer. An exact tuple, str or bytes returns itself for a full
slice. List assignment and deletion go through list_ass_slice. slicehash was
added in v3.12.0 and `slice.__class_getitem__` in 3.15; PySlice_New,
slice_indices and slice_richcompare do the same work in the v3.11.14,
v3.12.12, v3.13.11, v3.14.2 and v3.15.0rc3 tags.

Behaviour is settled by observation: identity, a recording `__getitem__`, a
counting generator and clamping results. The bounds on `indices()` and on
applying a slice are timed; building, reading, comparing and hashing a slice
are checked by behaviour only.

Measurement scope:

* building a slice stores the objects given (identity), and missing parts
  are None; `slice(5)` sets only the stop.
* `indices()`: fixed cases with defaults, negative steps and out-of-range
  bounds, a zero step raising ValueError, and agreement of
  `range(*s.indices(len(seq)))` with `seq[s]` for every slice with start and
  stop in -12..12 and step in -4..4 except 0, on a 10-item list. A length of
  10**18 costs under x3 a length of 10.
* comparison: over 25 pairs of int-part slices, == and < agree with their
  tuples, and a None part against an int raises TypeError as a tuple does. From
  3.12, equal slices hash equal and an unhashable part raises TypeError;
  before 3.12 hashing any slice raises TypeError.
* copying: on a 1,000,000-item list, tuple, str, bytes and bytearray, a
  10-item slice costs under x5 what it costs on a 1,000-item sequence; on a
  list and a str of 2,000,000 items, slicing 1,000,000 costs x20-x400
  slicing 10,000. A stepped slice over the whole 1,000,000-item list selecting 100,000 items costs x20-x400 one
  selecting 1,000, so the cost follows k, not j - i.
* no copy: `[:]` returns the object itself for an exact tuple, str and bytes,
  and not for a list or a tuple subclass. A range slice is a range, and
  10**11 items cost under x5 ten; a memoryview slice sees a later write to
  the underlying bytearray, and 9,000,000 bytes cost under x5 ten.
* list assignment and deletion, on a fresh 2,000,000-item list each time:
  `del lst[:10]` costs more than x10 `del lst[-10:]`, and replacing
  `lst[0:10]` with 11 items costs more than x10 replacing it with 10.
* a custom `__getitem__` receives the very slice object used, and
  `obj[1:2, 3:4]` passes a tuple of two slices.
* islice over a counting generator takes start + k items for
  `islice(gen, 100, 110)`.
* every fenced block runs in its own subprocess and asserts its own results,
  and a mutated assertion in one is asserted to fail.

Not settled here:

* Space columns: that a copying slice allocates k items and that the
  range, memoryview and full-slice rows allocate O(1) follow from the
  results (a new object of k items, or an identical or view object); the
  O(j - i + len(t)) and O(j - i) temporary space of list assignment and
  deletion is read from list_ass_slice, not measured.
* "Amortized" on list assignment that grows the list is the list page's
  claim and is not varied here.
* Index arithmetic on ints wider than a machine word is not priced: the page
  treats indices as machine-size, and huge ints are not varied.
* The cost of comparing or hashing a slice whose parts are not ints or None
  is the parts' own; the page's cost model excludes it.
* Not varied in the timings: element types (ints, one-byte characters), steps
  other than 1, 10 and 1,000, and the items selected from a tuple, bytes or
  bytearray (only list and str vary k). Sequence subclasses are checked only
  by the tuple identity test.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap
import time
from collections.abc import Callable, Iterator
from itertools import islice
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "slice.md"
EXPECTED_BLOCKS = 8


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


def best_fresh_ns(make: Callable[[], Any], act: Callable[[Any], Any], repeats: int = 5) -> float:
    """Fastest of `repeats` runs of act() on a fresh make() each time."""
    best: float | None = None
    for _ in range(repeats):
        target = make()
        start = time.perf_counter_ns()
        act(target)
        elapsed = float(time.perf_counter_ns() - start)
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


class TestBuildingASlice:
    """`slice(start, stop, step)` is O(1): it stores the objects given,
    without checking or converting them."""

    def test_the_parts_are_stored_as_given(self) -> None:
        start, stop = ["a"], object()
        s = slice(start, stop)

        assert s.start is start
        assert s.stop is stop
        assert s.step is None

    def test_one_argument_is_the_stop(self) -> None:
        s = slice(5)
        assert (s.start, s.stop, s.step) == (None, 5, None)

    def test_nothing_is_checked_until_a_sequence_uses_it(self) -> None:
        s: Any = slice(1.5, 2)
        items: list[int] = [1, 2, 3]
        with pytest.raises(TypeError, match="slice indices must be integers"):
            items[s]


class TestIndices:
    """`slice.indices(length)` fills in defaults and clamps in O(1), and
    `range(*s.indices(len(seq)))` visits the positions `seq[s]` selects."""

    @pytest.mark.parametrize(
        ("s", "length", "expected"),
        [
            (slice(1, 10, 2), 5, (1, 5, 2)),
            (slice(None, None, -1), 5, (4, -1, -1)),
            (slice(-100, 100), 5, (0, 5, 1)),
            (slice(None), 0, (0, 0, 1)),
            (slice(-2, None), 5, (3, 5, 1)),
        ],
    )
    def test_defaults_and_clamping(
        self, s: slice, length: int, expected: tuple[int, int, int]
    ) -> None:
        assert s.indices(length) == expected

    def test_a_zero_step_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="cannot be zero"):
            slice(0, 5, 0).indices(5)

    def test_indices_select_what_the_list_selects(self) -> None:
        data = list(range(10))
        bounds: list[int | None] = [None, *range(-12, 13)]
        steps: list[int | None] = [None, *range(-4, 0), *range(1, 5)]
        checked = 0
        for start in bounds:
            for stop in bounds:
                for step in steps:
                    s = slice(start, stop, step)
                    assert [data[i] for i in range(*s.indices(len(data)))] == data[s], s
                    checked += 1
        assert checked == 26 * 26 * 9

    @pytest.mark.timing
    def test_the_length_does_not_change_the_cost(self) -> None:
        s = slice(None, None, None)

        small_ns = best_ns(lambda: s.indices(10), inner=10_000)
        large_ns = best_ns(lambda: s.indices(10**18), inner=10_000)

        ratio = large_ns / small_ns
        assert ratio < 3, f"indices(10**18) cost x{ratio:.2f} indices(10)"


class TestComparisonAndHashing:
    """Slices compare as the tuple `(start, stop, step)`; from 3.12 they hash
    when all three parts do."""

    def test_comparison_follows_the_tuple(self) -> None:
        parts: list[Any] = [(1, 2, 1), (1, 3, 1), (0, 9, 2), (1, 2, 3), (2, 0, -1)]
        assert slice(1, 2) == slice(1, 2, None)
        for a in parts:
            for b in parts:
                left: Any = slice(*a)
                right: Any = slice(*b)
                assert (left < right) == (a < b), (a, b)
                assert (left == right) == (a == b), (a, b)

    def test_ordering_mixed_parts_raises_as_a_tuple_does(self) -> None:
        left: Any = slice(1, 2, None)
        right: Any = slice(1, 2, 3)
        with pytest.raises(TypeError, match="not supported"):
            _ = left < right
        with pytest.raises(TypeError, match="not supported"):
            _ = (1, 2, None) < (1, 2, 3)  # type: ignore[operator]

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="version: slices hash from 3.12")
    def test_equal_slices_hash_equal(self) -> None:
        assert hash(slice(0, 10)) == hash(slice(0, 10))
        key: Any = slice(0, 10)
        assert {key: "x"}[slice(0, 10)] == "x"

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="version: slices hash from 3.12")
    def test_an_unhashable_part_raises(self) -> None:
        with pytest.raises(TypeError, match="unhashable"):
            hash(slice([], 1))

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="version: slices hash from 3.12")
    def test_slices_do_not_hash_before_3_12(self) -> None:
        with pytest.raises(TypeError, match="unhashable"):
            hash(slice(0, 10))


class TestCopyingFollowsTheSelection:
    """`seq[s]` on a list, tuple, str, bytes or bytearray is O(k): it grows
    with the items selected and not with the sequence's length or the span."""

    @staticmethod
    def _make(kind: str, size: int) -> Any:
        if kind == "list":
            return list(range(size))
        if kind == "tuple":
            return tuple(range(size))
        if kind == "str":
            return "x" * size
        if kind == "bytes":
            return b"x" * size
        return bytearray(size)

    @pytest.mark.timing
    @pytest.mark.parametrize("kind", ["list", "tuple", "str", "bytes", "bytearray"])
    def test_a_short_slice_does_not_grow_with_the_sequence(self, kind: str) -> None:
        small = self._make(kind, 1_000)
        large = self._make(kind, 1_000_000)
        s = slice(500, 510)

        small_ns = best_ns(lambda: small[s], inner=1_000)
        large_ns = best_ns(lambda: large[s], inner=1_000)

        ratio = large_ns / small_ns
        assert ratio < 5, (
            f"a 10-item slice of a 1,000,000-item {kind} cost x{ratio:.2f} its cost on "
            f"1,000 ({small_ns:.0f}ns to {large_ns:.0f}ns); a cost linear in n predicts x1,000"
        )

    @pytest.mark.timing
    @pytest.mark.parametrize("kind", ["list", "str"])
    def test_the_cost_grows_with_the_items_selected(self, kind: str) -> None:
        data = self._make(kind, 2_000_000)
        few, many = slice(0, 10_000), slice(0, 1_000_000)

        few_ns = best_ns(lambda: data[few], inner=100)
        many_ns = best_ns(lambda: data[many], inner=3)

        ratio = many_ns / few_ns
        assert 20 < ratio < 400, (
            f"100x the items cost x{ratio:.1f} ({few_ns:.0f}ns to {many_ns:.0f}ns); "
            "linear predicts x100"
        )

    @pytest.mark.timing
    def test_a_step_prices_the_items_not_the_span(self) -> None:
        data = list(range(1_000_000))
        sparse, dense = slice(None, None, 1_000), slice(None, None, 10)
        assert len(data[sparse]) == 1_000 and len(data[dense]) == 100_000

        sparse_ns = best_ns(lambda: data[sparse], inner=100)
        dense_ns = best_ns(lambda: data[dense], inner=3)

        ratio = dense_ns / sparse_ns
        assert 20 < ratio < 400, (
            f"the same 1,000,000-item span selecting 100x the items cost x{ratio:.1f}; "
            "a cost in k predicts x100, a cost in j - i x1"
        )


class TestSlicesThatCopyNothing:
    """A full slice of an exact tuple, str or bytes is the object itself, and
    range and memoryview slices are O(1) at any size."""

    @pytest.mark.parametrize("value", [(1, 2, 3), "abc", b"abc"], ids=["tuple", "str", "bytes"])
    def test_a_full_slice_of_an_immutable_is_itself(self, value: Any) -> None:
        assert value[:] is value
        assert value[slice(None)] is value

    def test_a_list_or_a_subclass_is_copied(self) -> None:
        class Pair(tuple[int, ...]):
            pass

        items = [1, 2, 3]
        assert items[:] is not items and items[:] == items
        pair = Pair((1, 2))
        assert pair[:] is not pair and pair[:] == (1, 2)

    @pytest.mark.timing
    def test_a_range_slice_does_not_produce_items(self) -> None:
        r = range(10**12)
        few, many = slice(0, 10), slice(0, 10**11)
        assert isinstance(r[many], range) and len(r[many]) == 10**11

        few_ns = best_ns(lambda: r[few], inner=1_000)
        many_ns = best_ns(lambda: r[many], inner=1_000)

        ratio = many_ns / few_ns
        assert ratio < 5, f"slicing 10**11 items of a range cost x{ratio:.2f} slicing 10"

    def test_a_memoryview_slice_shares_the_buffer(self) -> None:
        buffer = bytearray(b"abcdef")
        view = memoryview(buffer)[1:4]
        buffer[1] = ord("B")

        assert bytes(view) == b"Bcd"

    @pytest.mark.timing
    def test_a_memoryview_slice_does_not_copy(self) -> None:
        view = memoryview(bytes(10_000_000))
        few, many = slice(0, 10), slice(0, 9_000_000)

        few_ns = best_ns(lambda: view[few], inner=1_000)
        many_ns = best_ns(lambda: view[many], inner=1_000)

        ratio = many_ns / few_ns
        assert ratio < 5, f"a 9,000,000-byte view slice cost x{ratio:.2f} a 10-byte one"


class TestListAssignmentAndDeletion:
    """`del lst[i:j]` is O(n - i), and `lst[i:j] = t` is O(j - i) when the
    lengths match and O(n - i + len(t)) otherwise."""

    SIZE = 2_000_000

    def _fresh(self) -> list[int]:
        return list(range(self.SIZE))

    @pytest.mark.timing
    def test_deleting_at_the_front_moves_the_rest(self) -> None:
        def delete_front(lst: list[int]) -> None:
            del lst[:10]

        def delete_back(lst: list[int]) -> None:
            del lst[-10:]

        front_ns = best_fresh_ns(self._fresh, delete_front)
        back_ns = best_fresh_ns(self._fresh, delete_back)

        ratio = front_ns / back_ns
        assert ratio > 10, (
            f"del lst[:10] cost x{ratio:.1f} del lst[-10:] on {self.SIZE:,} items; "
            "O(n - i) predicts a gap of orders of magnitude, a cost in j - i x1"
        )

    @pytest.mark.timing
    def test_only_a_length_change_moves_the_rest(self) -> None:
        ten, eleven = list(range(10)), list(range(11))

        def same_length(lst: list[int]) -> None:
            lst[0:10] = ten

        def one_longer(lst: list[int]) -> None:
            lst[0:10] = eleven

        same_ns = best_fresh_ns(self._fresh, same_length)
        longer_ns = best_fresh_ns(self._fresh, one_longer)
        grown = self._fresh()
        one_longer(grown)
        assert len(grown) == self.SIZE + 1 and grown[11:13] == [10, 11]

        ratio = longer_ns / same_ns
        assert ratio > 10, (
            f"replacing 10 items with 11 cost x{ratio:.1f} replacing them with 10 on "
            f"{self.SIZE:,} items; O(n - i + len(t)) against O(j - i)"
        )

    def test_results(self) -> None:
        lst: list[Any] = list(range(10))
        lst[0:3] = ["a", "b", "c"]
        assert lst[:4] == ["a", "b", "c", 3] and len(lst) == 10
        lst[0:3] = ["x"]
        assert lst[:2] == ["x", 3] and len(lst) == 8
        del lst[-2:]
        assert lst == ["x", 3, 4, 5, 6, 7]


class TestCustomGetitem:
    """A custom `__getitem__` receives the slice object, or a tuple of slices
    for `obj[a:b, c:d]`."""

    class Recorder:
        def __init__(self) -> None:
            self.keys: list[Any] = []

        def __getitem__(self, key: Any) -> Any:
            self.keys.append(key)
            return key

    def test_it_receives_the_slice_object_itself(self) -> None:
        recorder = self.Recorder()
        s = slice(1, 4)

        assert recorder[s] is s
        assert recorder.keys == [s]

    def test_slice_syntax_builds_an_equal_slice(self) -> None:
        recorder = self.Recorder()
        assert recorder[1:4:2] == slice(1, 4, 2)

    def test_several_slices_arrive_as_a_tuple(self) -> None:
        recorder = self.Recorder()
        assert recorder[1:2, 3:4] == (slice(1, 2), slice(3, 4))


class TestIsliceStepsPastStart:
    """`islice(iterable, start, stop)` takes the `start` skipped items as
    well as the k it yields."""

    def test_it_takes_start_plus_k_items(self) -> None:
        taken: list[int] = []

        def numbers() -> Iterator[int]:
            for value in range(1_000):
                taken.append(value)
                yield value

        assert list(islice(numbers(), 100, 110)) == list(range(100, 110))
        assert len(taken) == 110


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
    """Each block runs in its own subprocess and asserts its own results."""

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
        line, source = next((n, s) for n, s in _blocks() if "assert len(taken) == 110" in s)
        mutated = source.replace("len(taken) == 110", "len(taken) == 10", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
