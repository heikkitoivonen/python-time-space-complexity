"""Tests for docs/builtins/filter.md.

filter() is filter_new and filter_vectorcall in Python/bltinmodule.c: both
check for exactly two positional arguments, call PyObject_GetIter on the
iterable once, and take no item. filter_next loops taking one item from that
iterator, testing it with PyObject_IsTrue when the function is None or bool
and otherwise calling the function once and testing its result, and returns
the first item that passes. The supported releases (v3.11.14, v3.12.12,
v3.13.11, v3.14.2) differ there only in the docstring and in how the dealloc,
traverse, next and reduce slots are declared, not in the work done per call.

Construction, per-step work and laziness are settled by counting calls on the
underlying iterable and on the predicate; per-step space by a traced
allocation peak; linear iteration by a timing ratio.

Measurement scope:

* construction: a counting iterable is asserted to have `__iter__` called
  once and to yield no item, and a counting predicate to be called zero times;
  a non-iterable raises TypeError at construction, as does a keyword
  argument.
* `filter(None, ...)` and `filter(bool, ...)`: the same kept items from a
  mixed list of falsy and truthy values, and over objects with a counting
  `__bool__` each item's `__bool__` is called exactly once by either, counted
  per item.
* `next()`: with one match every 1,000 items, the third `next()` has taken
  2,001 items and called the predicate 2,001 times; with no match, one
  `next()` over 10,000 items takes all 10,000 and calls the predicate 10,000
  times before StopIteration.
* iteration: the predicate is called exactly once for each of 100,000
  distinct items, counted per value, whether it keeps all, none or half. Consuming
  filter(None, range(N)) for N = 20,000, 200,000 and 2,000,000; each 10x step
  is asserted between x4 and x25 (linear predicts x10, quadratic x100).
* iteration space: the traced peak while consuming filter(None, items) over
  200,000 pre-built ints that all pass is under 20 KB, and `list(filter(...))`
  over the same input keeping every other item holds those 100,000 items.
  `sum(filter(...))` over range(200,000) with a Python predicate peaks under
  20 KB after a warm-up call.
* the filter object is its own iterator, a second pass is empty, and `len()`
  raises.
* every fenced block runs in a subprocess; the blocks pin the stated results,
  including that filter(None, ...) drops 0 where `x is not None` keeps it and
  that a list comprehension, a loop and filter() keep the same items.

Not settled here:

* "the same bounds on every supported version" is read from the diffs of
  Python/bltinmodule.c between the releases named above.
* k = O(√v) for the page's trial-division predicate is read from that
  function's loop; the test only runs the block.
* That comprehensions and loops are O(n·k) and that a generator expression is
  lazy is language semantics; the block checks only that all three keep the
  same items and that the generator yields its first match.
* Getting the iterator is priced at O(1) by the page's cost model; the test
  counts one `__iter__` call, not its cost.
* Not varied: underlying iterators that do more than O(1) work per item, items
  whose truth test is not O(1) (the page prices both at O(1) and adds anything
  more to every step), predicates whose own cost grows with the item (the page
  names that cost k), and threads sharing one filter object.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections import Counter
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "filter.md"
EXPECTED_BLOCKS = 11


def best_time(func: Callable[[], Any], repeats: int = 5) -> float:
    """The fastest of several runs, the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return min(times)


def consume(iterator: Iterator[Any]) -> None:
    for _ in iterator:
        pass


def traced_peak(func: Callable[[], object]) -> int:
    tracemalloc.start()
    try:
        func()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak


class CountingIterable:
    """An iterable that records how often it is asked for an iterator and how many
    items it has yielded."""

    def __init__(self, size: int) -> None:
        self.size = size
        self.iter_calls = 0
        self.items_taken = 0

    def __iter__(self) -> Iterator[int]:
        self.iter_calls += 1
        return self._items()

    def _items(self) -> Iterator[int]:
        for value in range(self.size):
            self.items_taken += 1
            yield value


class CountingPredicate:
    """A predicate that records how often it is called, in total and per value."""

    def __init__(self, test: Callable[[int], bool]) -> None:
        self.test = test
        self.calls = 0
        self.per_value: Counter[int] = Counter()

    def __call__(self, value: int) -> bool:
        self.calls += 1
        self.per_value[value] += 1
        return self.test(value)


class TestConstructionIsLazy:
    """Row: `filter(function, iterable)` - O(1); calls `iter(iterable)` once, takes
    no items and does not call `function`."""

    def test_building_calls_iter_once_and_takes_nothing(self) -> None:
        source = CountingIterable(1_000)
        predicate = CountingPredicate(lambda x: True)

        filter(predicate, source)

        assert source.iter_calls == 1
        assert source.items_taken == 0
        assert predicate.calls == 0

    def test_a_non_iterable_raises_at_construction(self) -> None:
        with pytest.raises(TypeError, match="not iterable"):
            filter(None, 42)  # type: ignore[call-overload]

    def test_keyword_arguments_raise(self) -> None:
        with pytest.raises(TypeError, match="takes no keyword arguments"):
            filter(None, iterable=[1])  # type: ignore[call-overload]


class TruthCounter:
    """An item whose truth value is fixed and whose `__bool__` calls are counted."""

    def __init__(self, truth: bool) -> None:
        self.truth = truth
        self.calls = 0

    def __bool__(self) -> bool:
        self.calls += 1
        return self.truth


class TestFilteringWithNone:
    """Row: `filter(None, iterable)` keeps the truthy items, and `filter(bool,
    iterable)` gives the same result; each item's truth is tested once."""

    def test_none_and_bool_keep_the_same_items(self) -> None:
        values: list[object] = [0, 1, False, 2, None, 3, "", 4, [], "x", 0.0, [0]]

        assert list(filter(None, values)) == [1, 2, 3, 4, "x", [0]]
        assert list(filter(bool, values)) == list(filter(None, values))

    @pytest.mark.parametrize("function", [None, bool])
    def test_each_item_is_tested_once(self, function: Callable[[object], bool] | None) -> None:
        items = [TruthCounter(i % 3 == 0) for i in range(300)]

        kept = list(filter(function, items))

        assert kept == items[::3]
        assert all(item.calls == 1 for item in items)


class TestNextTakesUntilAMatch:
    """Row: `next()` on a filter object - O(s·k) for the s items taken to reach the
    next kept item, the whole rest of the input when none is left."""

    def test_next_takes_every_rejected_item_before_the_match(self) -> None:
        source = CountingIterable(1_000_000)
        predicate = CountingPredicate(lambda x: x % 1000 == 0)
        matches = filter(predicate, source)

        first = [next(matches) for _ in range(3)]

        assert first == [0, 1000, 2000]
        assert source.items_taken == 2001
        assert predicate.calls == 2001

    def test_next_with_no_match_takes_everything(self) -> None:
        source = CountingIterable(10_000)
        predicate = CountingPredicate(lambda x: False)
        none_kept = filter(predicate, source)

        with pytest.raises(StopIteration):
            next(none_kept)

        assert source.items_taken == 10_000
        assert predicate.calls == 10_000


class TestIterationCallsThePredicateOncePerItem:
    """Row: iterating a filter object - O(n·k): one predicate call per item taken,
    whatever fraction is kept."""

    @pytest.mark.parametrize(
        ("test", "expected_kept"),
        [(lambda x: True, 100_000), (lambda x: False, 0), (lambda x: x % 2 == 0, 50_000)],
        ids=["all-kept", "none-kept", "half-kept"],
    )
    def test_one_call_per_item(self, test: Callable[[int], bool], expected_kept: int) -> None:
        predicate = CountingPredicate(test)

        kept = list(filter(predicate, range(100_000)))

        assert len(kept) == expected_kept
        assert predicate.calls == 100_000
        assert set(predicate.per_value.values()) == {1}
        assert len(predicate.per_value) == 100_000

    @pytest.mark.timing
    def test_ten_times_the_items_costs_about_ten_times(self) -> None:
        sizes = (20_000, 200_000, 2_000_000)
        times = [best_time(lambda n=n: consume(filter(None, range(n)))) for n in sizes]

        for small, large in zip(times, times[1:], strict=False):
            ratio = large / small
            assert 4 < ratio < 25, f"x{ratio:.1f} for x10 items: {times}"


class TestIterationSpace:
    """Rows: iterating is O(1) space; `list(filter(...))` is O(m) for the m kept
    items."""

    def test_consuming_does_not_accumulate(self) -> None:
        items = list(range(1, 200_001))
        kept = filter(None, items)

        peak = traced_peak(lambda: consume(kept))

        assert peak < 20_000, f"peak {peak} bytes over 200,000 kept items"

    def test_summing_with_a_python_predicate_does_not_accumulate(self) -> None:
        def divisible_by_three(x: int) -> bool:
            return x % 3 == 0

        sum(filter(divisible_by_three, range(1_000)))  # warm the predicate's code object

        peak = traced_peak(lambda: sum(filter(divisible_by_three, range(200_000))))

        assert peak < 20_000, f"peak {peak} bytes over 200,000 items"

    def test_list_holds_every_kept_item(self) -> None:
        items = list(range(200_000))

        kept = list(filter(lambda x: x % 2 == 0, items))

        assert len(kept) == 100_000
        assert all(a is b for a, b in zip(kept, items[::2], strict=True))


class TestSinglePass:
    """Lazy, Single-Pass Iteration: the filter object is its own iterator, can be
    consumed once, and has no length."""

    def test_its_own_iterator_and_exhausted_after_one_pass(self) -> None:
        evens = filter(lambda x: x % 2 == 0, [1, 2, 3, 4])

        assert iter(evens) is evens
        assert list(evens) == [2, 4]
        assert list(evens) == []

    def test_len_raises(self) -> None:
        with pytest.raises(TypeError, match="has no len"):
            len(filter(None, [1, 2]))  # type: ignore[arg-type]


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
    """Every block runs, and its asserts pin the stated values."""

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

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        block = next(source for _, source in _blocks() if "assert len(tested) == 2001" in source)
        broken = block.replace("assert len(tested) == 2001", "assert len(tested) == 3", 1)
        assert broken != block, "the mutation did not change the block"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "AssertionError" in result.stderr
