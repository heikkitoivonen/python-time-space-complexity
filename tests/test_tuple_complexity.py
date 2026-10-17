"""Tests for docs/builtins/tuple.md.

A tuple never changes, so the page's distinctive claims are about what
CPython does *not* do: copying an exact tuple returns it, and from 3.14 a
computed hash is kept in the tuple. Both are settled by observation - an
identity check, and a count of the elements' `__hash__` calls - so they need no
tolerance. Comparisons, `index()` with bounds, and `min()` and `max()` are
settled by counting `__eq__` or ordering calls; repetition by output length
and a timing ratio.

The rows for `len()`, `t[k]`, `in`, `index()`, `count()`, concatenation,
slicing and `tuple(list)` are timed by `TestTupleComplexity` in
tests/test_builtin_complexity.py; this file covers the rest of the table and
the page's examples.

Measurement scope:

* `tuple(t)`, `copy.copy(t)` and `t[:]` return `t` for an exact tuple, and
  `tuple` has no `copy` attribute. `tuple()`, `copy.copy()` and `[:]` of a
  tuple subclass instance, and `tuple()` of a list, build a new object;
  `tuple()` of a subclass gives a plain tuple and `copy.copy()` keeps the
  subclass.
* `hash(t)` over 100 elements with a counting `__hash__` calls it 100 times on
  the first call. On the second call it calls it 0 times on 3.14 and later and
  100 times on 3.11 to 3.13, which is the version boundary of the cache. An
  equal tuple built separately calls it 100 times on its own first hash.
  `hash()` of 50 counted elements followed by a list raises `TypeError` and
  calls `__hash__` 50 times on each of two attempts, so a failure caches
  nothing.
* `t1 == t2` on 999 and 1,000 counted elements with an equal prefix makes 999
  `__eq__` calls, where the same lists make none. `<`, `<=`, `>` and `>=`
  between a 10-element tuple and a 1,000-element one sharing its prefix make
  exactly 10 `__eq__` calls. Equal 1,000-element tuples make 1,000; tuples
  differing at index 5 make 6, and `<` between them makes 6 `__eq__` calls
  and one `__lt__`.
* `t.index(x, i, j)` on 1,000 counted elements, with `x` absent from
  `t[100:110]`, makes exactly 10 `__eq__` calls before raising `ValueError`.
* `t * k`: the result has n·k elements, k of 0 and -1 give `()`, and 100x k
  at n = 100, or 100x n at k = 10, costs over 20x more. `t1 + t2` of two
  non-empty tuples is a new object equal to their concatenation.
* `min()` and `max()` make exactly n - 1 comparisons on 1,000 elements.
  Iteration costs the same per step on a 1,000- and a 1,000,000-element tuple
  (the first 1,000 steps, under 3x apart).
* `reversed()` over a 1,000,000-element tuple allocates under 1 KB, and its
  first item is the last element.
* Building a tuple with `t += (x,)` is timed against collecting a list and
  converting once: from 1,000 to 10,000 items the first must grow more than
  40x (quadratic predicts 100x) and the second less than 40x (linear predicts
  10x).
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* Element hashing and comparison are held at O(1) by the cost model; the
  hash test uses a constant-cost `__hash__`, and string elements, which cache
  their own hash, are not varied.
* `tuple(iterable)` for iterables other than a list is priced on the
  tuple() page and not measured here.
"""

from __future__ import annotations

import copy
import pathlib
import random
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from itertools import islice
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "tuple.md"
EXPECTED_BLOCKS = 4

SMALL = 1_000
LARGE = 1_000_000


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 20) -> float:
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


class Counted:
    """An element whose comparisons and hashes are counted."""

    comparisons = 0
    hashes = 0

    __slots__ = ("value",)

    def __init__(self, value: int) -> None:
        self.value = value

    def __lt__(self, other: Counted) -> bool:
        Counted.comparisons += 1
        return self.value < other.value

    def __gt__(self, other: Counted) -> bool:
        Counted.comparisons += 1
        return self.value > other.value

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Counted) and self.value == other.value

    def __hash__(self) -> int:
        Counted.hashes += 1
        return self.value


class Equal:
    """An element whose `==` calls are counted; equal values are distinct objects."""

    calls = 0

    __slots__ = ("value",)
    __hash__ = None  # type: ignore[assignment]

    def __init__(self, value: int) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        Equal.calls += 1
        return isinstance(other, Equal) and self.value == other.value


def equals(values: range) -> tuple[Equal, ...]:
    return tuple(Equal(value) for value in values)


class OrderedEqual:
    """An element whose `==` and `<` calls are counted separately."""

    equalities = 0
    orderings = 0

    __slots__ = ("value",)
    __hash__ = None  # type: ignore[assignment]

    def __init__(self, value: int) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        OrderedEqual.equalities += 1
        return isinstance(other, OrderedEqual) and self.value == other.value

    def __lt__(self, other: OrderedEqual) -> bool:
        OrderedEqual.orderings += 1
        return self.value < other.value

    @classmethod
    def wrap(cls, values: tuple[int, ...]) -> tuple[OrderedEqual, ...]:
        return tuple(cls(value) for value in values)


class TestCopyingReturnsTheSameTuple:
    """`tuple(t)`, `copy.copy(t)` | O(1): an exact tuple is returned as is."""

    def test_an_exact_tuple_is_returned_unchanged(self) -> None:
        data = tuple(range(SMALL))

        assert tuple(data) is data
        assert copy.copy(data) is data
        assert data[:] is data

    def test_tuples_have_no_copy_method(self) -> None:
        assert not hasattr(tuple, "copy")

    def test_a_subclass_or_a_list_is_copied(self) -> None:
        class Pair(tuple[int, ...]):
            pass

        pair = Pair((1, 2))
        items = [1, 2]

        assert tuple(pair) is not pair and type(tuple(pair)) is tuple
        assert copy.copy(pair) is not pair and copy.copy(pair) == pair
        assert type(copy.copy(pair)) is Pair
        assert pair[:] is not pair and pair[:] == pair
        assert tuple(items) == (1, 2)


class TestHashability:
    """The page's example: a tuple of hashable elements is hashable, so it can
    be a dict key; one holding an unhashable element is not."""

    def test_hashability_follows_the_elements(self) -> None:
        assert {(1, 2): "point"}[(1, 2)] == "point"
        with pytest.raises(TypeError):
            hash(([],))


class TestHashIsCachedFrom314:
    """`hash()` | O(n) first call; O(1) after it on 3.14+.

    Counting the elements' `__hash__` calls separates a cached hash (no calls)
    from a recomputed one (one per element) exactly.
    """

    def test_the_second_hash_recomputes_only_before_314(self) -> None:
        data = tuple(Counted(value) for value in range(100))

        Counted.hashes = 0
        first = hash(data)
        first_calls = Counted.hashes
        Counted.hashes = 0
        second = hash(data)
        second_calls = Counted.hashes

        assert first == second
        assert first_calls == 100
        expected = 0 if sys.version_info >= (3, 14) else 100
        assert second_calls == expected, (
            f"the second hash() called __hash__ {second_calls} times on "
            f"{sys.version_info[:2]}, expected {expected}"
        )

    def test_a_failed_hash_caches_nothing(self) -> None:
        data = (*(Counted(value) for value in range(50)), [])

        for _ in range(2):
            Counted.hashes = 0
            with pytest.raises(TypeError):
                hash(data)
            assert Counted.hashes == 50

    def test_an_equal_tuple_pays_its_own_first_hash(self) -> None:
        elements = [Counted(value) for value in range(100)]
        hashed = tuple(elements)
        hash(hashed)
        twin = tuple(elements)

        Counted.hashes = 0
        twin_hash = hash(twin)
        assert Counted.hashes == 100
        assert twin_hash == hash(hashed)


class TestComparisonsWalkThePrefix:
    """`t1 == t2` | O(min(len(t1), len(t2))): unlike a list, a tuple compares its
    common prefix even when the lengths differ. Ordering stops at the first
    unequal pair. Counting `__eq__` calls separates the two exactly."""

    def test_unequal_lengths_still_compare_the_prefix(self) -> None:
        short, long = equals(range(999)), equals(range(1_000))

        Equal.calls = 0
        assert short != long
        assert Equal.calls == 999

    def test_a_list_answers_unequal_lengths_without_comparing(self) -> None:
        short, long = list(equals(range(999))), list(equals(range(1_000)))

        Equal.calls = 0
        assert short != long
        assert Equal.calls == 0

    def test_equal_tuples_compare_every_pair(self) -> None:
        first, second = equals(range(1_000)), equals(range(1_000))

        Equal.calls = 0
        assert first == second
        assert Equal.calls == 1_000

    def test_equality_stops_at_the_first_unequal_pair(self) -> None:
        first = equals(range(1_000))
        second = equals(range(5)) + equals(range(-1, -996, -1))

        Equal.calls = 0
        assert first != second
        assert Equal.calls == 6

    def test_ordering_compares_the_shorter_length(self) -> None:
        short = equals(range(10))
        long = equals(range(10)) + equals(range(10, 1_000))

        for compare in (
            lambda: short < long,
            lambda: short <= long,
            lambda: long > short,
            lambda: long >= short,
        ):
            Equal.calls = 0
            assert compare()
            assert Equal.calls == 10

    def test_ordering_stops_at_the_first_unequal_pair(self) -> None:
        first = (*range(5), -1, *range(6, 1_000))
        second = tuple(range(1_000))
        ordered = OrderedEqual.wrap(first), OrderedEqual.wrap(second)

        OrderedEqual.equalities = OrderedEqual.orderings = 0
        assert ordered[0] < ordered[1]
        assert (OrderedEqual.equalities, OrderedEqual.orderings) == (6, 1)


class TestIndexWithBoundsSearchesTheRegion:
    """`t.index(x, i, j)` | O(j-i): only `t[i:j]` is searched."""

    def test_a_bounded_search_compares_only_the_region(self) -> None:
        data = equals(range(1_000))

        Equal.calls = 0
        with pytest.raises(ValueError):
            data.index(Equal(5), 100, 110)
        assert Equal.calls == 10


class TestReversedIsLazy:
    """`reversed()` | O(1): an iterator over the tuple, not a reversed copy."""

    def test_reversing_a_large_tuple_copies_nothing(self) -> None:
        data = tuple(range(LARGE))

        tracemalloc.start()
        try:
            backwards = reversed(data)
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()

        assert peak < 1_000, f"reversed() over 1,000,000 elements allocated {peak} bytes"
        assert next(backwards) == LARGE - 1


class TestRepetitionScalesWithBothFactors:
    """`t * k` | O(nk): the result holds n·k references, and both factors move
    the cost."""

    def test_the_result_has_n_times_k_elements(self) -> None:
        base = tuple(range(100))
        assert len(base * 1_000) == 100_000
        assert (base * 3)[200:] == base

    def test_a_count_of_zero_or_less_gives_an_empty_tuple(self) -> None:
        base = tuple(range(100))
        assert base * 0 == () and base * -1 == ()

    def test_concatenation_builds_a_new_tuple(self) -> None:
        first, second = tuple(range(3)), tuple(range(3, 6))
        joined = first + second
        assert joined == tuple(range(6))
        assert joined is not first and joined is not second

    @pytest.mark.timing
    def test_a_hundred_times_k_costs_far_more(self) -> None:
        base = tuple(range(100))

        few_ns = best_ns(lambda: base * 10, inner=100)
        many_ns = best_ns(lambda: base * 1_000)

        ratio = many_ns / few_ns
        assert ratio > 20, f"100x k cost only x{ratio:.1f}: {few_ns:.0f} vs {many_ns:.0f} ns"

    @pytest.mark.timing
    def test_a_hundred_times_n_costs_far_more(self) -> None:
        short = tuple(range(10))
        long = tuple(range(1_000))

        short_ns = best_ns(lambda: short * 10, inner=100)
        long_ns = best_ns(lambda: long * 10)

        ratio = long_ns / short_ns
        assert ratio > 20, f"100x n cost only x{ratio:.1f}: {short_ns:.0f} vs {long_ns:.0f} ns"


class TestIterationAndMinMax:
    """`for x in t` | O(n), O(1) per step; `min(t)`, `max(t)` | O(n), n-1 comparisons."""

    def test_min_and_max_compare_n_minus_one_times(self) -> None:
        values = tuple(Counted(value) for value in random.Random(7).sample(range(10_000), SMALL))

        Counted.comparisons = 0
        min(values)
        min_comparisons = Counted.comparisons
        Counted.comparisons = 0
        max(values)
        max_comparisons = Counted.comparisons

        assert (min_comparisons, max_comparisons) == (SMALL - 1, SMALL - 1)

    @pytest.mark.timing
    def test_a_step_costs_the_same_on_a_longer_tuple(self) -> None:
        small = tuple(range(SMALL))
        large = tuple(range(LARGE))

        def first_thousand(data: tuple[int, ...]) -> Callable[[], None]:
            def walk() -> None:
                for _ in islice(data, SMALL):
                    pass

            return walk

        small_ns = best_ns(first_thousand(small), inner=100)
        large_ns = best_ns(first_thousand(large), inner=100)

        ratio = large_ns / small_ns
        assert ratio < 3, f"1,000 steps cost x{ratio:.1f} on 1,000x the length"


class TestBuildingByConcatenationIsQuadratic:
    """`t += (x,)` in a loop copies the tuple every step, O(n²) in total;
    collecting a list and converting once is O(n). A 10x step separates them:
    quadratic predicts 100x, linear 10x, and 40x sits between."""

    @staticmethod
    def concatenating(n: int) -> Callable[[], None]:
        def build() -> None:
            result: tuple[int, ...] = ()
            for i in range(n):
                result += (i,)

        return build

    @staticmethod
    def collecting(n: int) -> Callable[[], None]:
        def build() -> None:
            items: list[int] = []
            for i in range(n):
                items.append(i)
            tuple(items)

        return build

    @pytest.mark.timing
    def test_concatenating_grows_quadratically(self) -> None:
        small_ns = best_ns(self.concatenating(1_000), repeats=5, inner=5)
        large_ns = best_ns(self.concatenating(10_000), repeats=5, inner=1)

        ratio = large_ns / small_ns
        assert ratio > 40, f"10x the items cost only x{ratio:.1f}"

    @pytest.mark.timing
    def test_collecting_grows_linearly(self) -> None:
        small_ns = best_ns(self.collecting(1_000), repeats=5, inner=50)
        large_ns = best_ns(self.collecting(10_000), repeats=5, inner=5)

        ratio = large_ns / small_ns
        assert ratio < 40, f"10x the items cost x{ratio:.1f}"


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
    """Each block runs in its own subprocess, and every block asserts its
    results."""

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
        line, source = next((n, s) for n, s in _blocks() if "assert tuple(t) is t" in s)
        mutated = source.replace("assert tuple(t) is t", "assert tuple(t) is not t", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
