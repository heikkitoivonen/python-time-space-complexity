"""Tests for docs/builtins/iter.md.

iter() is builtin_iter in Python/bltinmodule.c: PyObject_GetIter for one
argument, which calls the type's tp_iter or, for a type with only
`__getitem__`, wraps it in a seqiterobject (Objects/iterobject.c); and
PyCallIter_New for two, which stores the callable and the sentinel and calls
nothing. next() is builtin_next: it calls tp_iternext once and substitutes the
default when that ends with StopIteration. calliter_iternext calls the callable
once, compares with PyObject_RichCompareBool(sentinel, result, Py_EQ), and
clears both references on a match. builtin_iter, builtin_next, iter_iternext
and calliter_iternext do the same work in the v3.11.14, v3.12.12, v3.13.11,
v3.14.2 and v3.15.0rc3 tags, so no version is treated apart.

Most rows are settled by observation: identity, a counting `__getitem__`,
callable, predicate or function, and mutation seen through an iterator. The
per-call O(1) of container iterators and the sparse-table cost of dict and set
iterators need a stopwatch.

Measurement scope:

* `iter()` does not copy: an item appended to a list after `iter()` is
  yielded, and `iter()` on a list_iterator, a generator, a map, a filter, an
  enumerate and an io.StringIO returns the same object. A for loop over a
  counting iterable calls `__iter__` once.
* the `__getitem__` fallback: `iter()` makes no `__getitem__` call, the first
  `next()` makes one with index 0, and draining four items makes five, the
  last raising IndexError.
* `iter(callable, sentinel)`: building it calls nothing; each next() makes
  one call; a sentinel of 1 stops at a result of 1.0, so the comparison is
  `==`; the sentinel is not yielded, and next() after it makes no call.
* `next()` on a list, tuple, str, bytes, range, dict and set iterator: one
  `iter()` plus `next()` costs under x5 from a 1,000-item container to a
  1,000,000-item one, where a cost linear in the container predicts x1,000.
* a full pass over a list: 10,000 to 1,000,000 items, a hundredfold step,
  costs between x20 and x400; linear predicts x100 and quadratic x10,000.
* a dict or a set of 1,000,000 keys with all but the last deleted: one next()
  on a fresh iterator costs more than x20 what it costs on the same container
  built from 10,000 keys with all but the last deleted, linear in the former
  size predicting x100. After `dict(d)` or `set(s)` it costs under a tenth of
  the sparse one.
* filter and map: a counting predicate is called on exactly the items next()
  examines, and a counting function once per next(); neither is called when
  the iterator is built. A map over three counting iterators takes one item
  from each per next(), which is the m term; m is not varied further.
* memory: tracemalloc's peak while draining a generator of 1,000,000 ints is
  under 10 KB, while list() of the same range peaks over 1 MB; reading a
  1,000,000-character io.StringIO in 1,024-character chunks through
  `iter(partial(f.read, 1024), '')` peaks under 50 KB. These run serially,
  since xdist's I/O thread allocates while tracemalloc is tracing.
* `next()` on a list or a range raises TypeError naming "is not an
  iterator", `next(it, default)` returns the default once exhausted, and
  `iter()` on a range returns a fresh iterator each time.
* every fenced block runs in its own subprocess and asserts its own results,
  and a mutated assertion in one is asserted to fail.

Not settled here:

* The cost of a user `__iter__`, `__next__`, `__getitem__`, predicate,
  function or callable is the caller's; the page names it once and the tests
  hold each at O(1).
* "Until a later insertion triggers a resize" is read from the official
  time-complexity page's footnote and Objects/dictobject.c; only a rebuild
  with dict() and set() is measured.
* Not varied: element types inside containers (ints and one-character
  strings only), the position at which deletions happen (all but the last
  key), and dict views, which share the dict iterators.
"""

from __future__ import annotations

import io
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable, Iterator
from functools import partial
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "iter.md"
EXPECTED_BLOCKS = 21


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


def drain(iterator: Iterator[Any]) -> None:
    for _ in iterator:
        pass


class TestIterDoesNotCopy:
    """`iter(iterable)` and `iter(iterator)` are O(1): a container's iterator
    reads the container itself, and an iterator is returned as it is."""

    def test_a_list_iterator_sees_later_appends(self) -> None:
        items = [1, 2]
        it = iter(items)
        items.append(3)

        assert list(it) == [1, 2, 3], "a copy taken by iter() would miss the append"

    @pytest.mark.parametrize(
        "make",
        [
            lambda: iter([1, 2]),
            lambda: (x for x in [1, 2]),
            lambda: map(str, [1, 2]),
            lambda: filter(None, [1, 2]),
            lambda: enumerate([1, 2]),
            lambda: io.StringIO("a\nb\n"),
        ],
        ids=["list_iterator", "generator", "map", "filter", "enumerate", "StringIO"],
    )
    def test_an_iterator_is_its_own_iterator(self, make: Callable[[], Any]) -> None:
        iterator = make()
        assert iter(iterator) is iterator

    def test_a_for_loop_calls_iter_once(self) -> None:
        calls = 0

        class Counted:
            def __iter__(self) -> Iterator[int]:
                nonlocal calls
                calls += 1
                return iter([1, 2, 3])

        seen = []
        for item in Counted():
            seen.append(item)
        assert seen == [1, 2, 3]
        assert calls == 1


class TestGetitemFallback:
    """`iter(sequence)` without `__iter__`: nothing is fetched until next(),
    which asks for index 0, 1, ... until IndexError."""

    class Counting:
        def __init__(self, count: int) -> None:
            self.count = count
            self.indexes: list[int] = []

        def __getitem__(self, index: int) -> int:
            self.indexes.append(index)
            if index >= self.count:
                raise IndexError(index)
            return index

    def test_iter_fetches_nothing(self) -> None:
        sequence = self.Counting(4)
        it = iter(sequence)

        assert sequence.indexes == []
        assert next(it) == 0
        assert sequence.indexes == [0]

    def test_a_pass_asks_for_each_index_then_stops_at_index_error(self) -> None:
        sequence = self.Counting(4)

        assert list(iter(sequence)) == [0, 1, 2, 3]
        assert sequence.indexes == [0, 1, 2, 3, 4]


class TestCallableIterator:
    """`iter(callable, sentinel)` calls nothing when built and once per next();
    the result is compared with the sentinel by `==`, and after a match no
    further call is made."""

    def test_building_it_calls_nothing(self) -> None:
        calls: list[int] = []
        iter(lambda: calls.append(1), 0)
        assert calls == []

    def test_each_next_makes_one_call(self) -> None:
        source = [3, 1, 4, 0, 5]
        calls = 0

        def read() -> int:
            nonlocal calls
            calls += 1
            return source.pop(0)

        it = iter(read, 0)
        assert next(it) == 3
        assert calls == 1
        assert list(it) == [1, 4], "the sentinel itself is not yielded"
        assert calls == 4

        assert next(it, None) is None
        assert calls == 4, "next() after the sentinel calls nothing"
        assert source == [5]

    def test_the_sentinel_is_compared_by_equality(self) -> None:
        results = iter([2.0, 1.0, 7.0])
        assert list(iter(lambda: next(results), 1)) == [2.0]


class TestContainerIteratorsAreConstantPerCall:
    """`next(iterator)` is O(1) on list, tuple, str, bytes and range
    iterators, and on dict and set iterators over a compact table: the cost
    does not grow with the container."""

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
        if kind == "range":
            return range(size)
        if kind == "dict":
            return dict.fromkeys(range(size))
        return set(range(size))

    @pytest.mark.timing
    @pytest.mark.parametrize("kind", ["list", "tuple", "str", "bytes", "range", "dict", "set"])
    def test_one_next_does_not_grow_with_the_container(self, kind: str) -> None:
        small = self._make(kind, 1_000)
        large = self._make(kind, 1_000_000)

        small_ns = best_ns(lambda: next(iter(small)), inner=1_000)
        large_ns = best_ns(lambda: next(iter(large)), inner=1_000)

        ratio = large_ns / small_ns
        assert ratio < 5, (
            f"iter() plus next() on a {kind} of 1,000,000 cost x{ratio:.2f} its cost at "
            f"1,000 ({small_ns:.0f}ns to {large_ns:.0f}ns); a linear cost predicts x1,000"
        )

    @pytest.mark.timing
    def test_a_full_pass_is_linear(self) -> None:
        small = list(range(10_000))
        large = list(range(1_000_000))

        small_ns = best_ns(lambda: drain(iter(small)), inner=3)
        large_ns = best_ns(lambda: drain(iter(large)), repeats=5)

        ratio = large_ns / small_ns
        assert 20 < ratio < 400, (
            f"100x the items cost x{ratio:.1f} ({small_ns:.0f}ns to {large_ns:.0f}ns); "
            "linear predicts x100 and quadratic x10,000"
        )


class TestSparseHashTables:
    """`next()` on a dict or set iterator is O(1) amortized: the hash table is
    not shrunk by removal, so the first next() after deleting most entries
    walks the empty slots, and a rebuild restores O(1)."""

    @staticmethod
    def _sparse_dict(size: int) -> dict[int, int]:
        table = {i: i for i in range(size)}
        for i in range(size - 1):
            del table[i]
        return table

    @staticmethod
    def _sparse_set(size: int) -> set[int]:
        table = set(range(size))
        for i in range(size - 1):
            table.discard(i)
        return table

    @pytest.mark.timing
    @pytest.mark.parametrize("kind", ["dict", "set"])
    def test_one_next_costs_the_former_size(self, kind: str) -> None:
        make = self._sparse_dict if kind == "dict" else self._sparse_set
        small = make(10_000)
        large = make(1_000_000)
        assert len(small) == len(large) == 1

        small_ns = best_ns(lambda: next(iter(small)), inner=3)
        large_ns = best_ns(lambda: next(iter(large)), inner=3)

        ratio = large_ns / small_ns
        assert ratio > 20, (
            f"one next() on a one-item {kind} that held 1,000,000 cost x{ratio:.1f} the "
            f"one that held 10,000 ({small_ns:.0f}ns to {large_ns:.0f}ns); a cost linear "
            "in the former size predicts x100, an O(1) one x1"
        )

    @pytest.mark.timing
    @pytest.mark.parametrize("kind", ["dict", "set"])
    def test_rebuilding_makes_next_cheap_again(self, kind: str) -> None:
        sparse: Any = (
            self._sparse_dict(1_000_000) if kind == "dict" else self._sparse_set(1_000_000)
        )
        rebuilt = dict(sparse) if kind == "dict" else set(sparse)
        assert rebuilt == sparse

        sparse_ns = best_ns(lambda: next(iter(sparse)), inner=3)
        rebuilt_ns = best_ns(lambda: next(iter(rebuilt)), inner=1_000)

        assert rebuilt_ns * 10 < sparse_ns, (
            f"next() on the rebuilt {kind} cost {rebuilt_ns:.0f}ns against "
            f"{sparse_ns:.0f}ns on the sparse one"
        )


class TestLazyBuiltinIterators:
    """`next()` on a filter is O(k), plus one predicate call per examined
    item; on a map over m inputs it is O(m), one item from each, plus one call
    of the function. Building either calls nothing."""

    def test_filter_examines_the_skipped_items_and_the_returned_one(self) -> None:
        checked: list[int] = []

        def is_even(x: int) -> bool:
            checked.append(x)
            return x % 2 == 0

        it = filter(is_even, [1, 3, 5, 6, 7, 8])
        assert checked == []

        assert next(it) == 6
        assert checked == [1, 3, 5, 6]
        assert list(it) == [8]
        assert checked == [1, 3, 5, 6, 7, 8]

    def test_map_calls_the_function_once_per_next(self) -> None:
        calls: list[int] = []

        def square(x: int) -> int:
            calls.append(x)
            return x * x

        it = map(square, [1, 2, 3, 4])
        assert calls == []

        assert [next(it), next(it)] == [1, 4]
        assert calls == [1, 2]

    def test_map_takes_one_item_from_each_input(self) -> None:
        taken = [0, 0, 0]

        def counting(index: int) -> Iterator[int]:
            for value in range(10):
                taken[index] += 1
                yield value

        it = map(lambda a, b, c: a + b + c, counting(0), counting(1), counting(2))
        assert taken == [0, 0, 0]
        assert next(it) == 0
        assert taken == [1, 1, 1]
        assert next(it) == 3
        assert taken == [2, 2, 2]


@pytest.mark.serial
class TestConstantMemory:
    """Generators and chunked reads hold O(1) and O(chunk size) memory, where a
    list of the same items holds all of them."""

    def test_draining_a_generator_holds_almost_nothing(self) -> None:
        def stream() -> Iterator[int]:
            i = 0
            while i < 1_000_000:
                yield i
                i += 1

        drain(stream())
        gen_peak = peak_bytes(lambda: drain(stream()))
        list_peak = peak_bytes(lambda: list(range(1_000_000)))

        assert gen_peak < 10_000, f"draining 1,000,000 items peaked at {gen_peak} bytes"
        assert list_peak > 1_000_000, f"the list peaked at only {list_peak} bytes"

    def test_chunked_reads_hold_one_chunk(self) -> None:
        f = io.StringIO("x" * 1_000_000)

        def read_all() -> int:
            f.seek(0)
            total = 0
            for chunk in iter(partial(f.read, 1024), ""):
                total += len(chunk)
            return total

        assert read_all() == 1_000_000
        peak = peak_bytes(read_all)
        assert peak < 50_000, f"chunked reading of 1,000,000 characters peaked at {peak}"


class TestNextContract:
    """`next()` needs an iterator, and `next(iterator, default)` returns the
    default instead of raising. A range is a sequence, not an iterator."""

    @pytest.mark.parametrize("iterable", [[1, 2, 3], range(3)], ids=["list", "range"])
    def test_next_rejects_an_iterable(self, iterable: Any) -> None:
        with pytest.raises(TypeError, match="is not an iterator"):
            next(iterable)

    def test_the_default_replaces_stop_iteration(self) -> None:
        it = iter([1])
        assert next(it) == 1
        sentinel = object()
        assert next(it, sentinel) is sentinel
        with pytest.raises(StopIteration):
            next(it)

    def test_each_iter_over_a_range_starts_again(self) -> None:
        r = range(3)
        first = iter(r)
        assert next(first) == 0
        assert iter(r) is not first
        assert list(iter(r)) == [0, 1, 2]


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
        line, source = next((n, s) for n, s in _blocks() if "assert len(produced) == 102" in s)
        mutated = source.replace("len(produced) == 102", "len(produced) == 10_000", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
