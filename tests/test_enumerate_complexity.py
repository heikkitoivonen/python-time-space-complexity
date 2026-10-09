"""Tests for docs/builtins/enumerate.md.

enumerate() is enum_new_impl in Objects/enumobject.c: it converts `start` with
PyNumber_Index, calls PyObject_GetIter on the iterable once, and takes no item.
enum_next takes one item from that iterator per call and pairs it with a
Py_ssize_t counter; a start beyond PY_SSIZE_T_MAX, or a counter that reaches
it, switches to int addition (enum_next_long). The supported releases
(v3.11.14, v3.12.12, v3.13.11, v3.14.2) differ there only in free-threading
locks and tuple recycling helpers, not in the work done per call.

Construction, per-step work and laziness are settled by counting calls on the
underlying iterable; per-step space by a traced allocation peak; the
range(len(...)) comparison and the start scope by timing ratios.

Measurement scope:

* construction: a counting iterable is asserted to have `__iter__` called once
  and to yield no item; a non-iterable raises TypeError at construction.
* `next()`: each call takes exactly one item from the underlying iterator, and
  a loop that breaks after k pairs has taken k items.
* iteration time: consuming enumerate(range(N)) for N = 20,000, 200,000 and
  2,000,000; each 10x step is asserted between x4 and x25 (linear predicts
  x10, quadratic x100).
* iteration space: the traced peak while consuming 200,000 pairs is under
  20 KB, and `list(enumerate(...))` over the same input holds 200,000 tuples.
* `start`: an object with `__index__` is accepted and a float is not; a start
  of sys.maxsize - 200,000 costs under 3x a start of 0 over 200,000 items
  (measured x1.25), and the counter crosses sys.maxsize without error.
* range(len(...)) on a deque: 5,000 to 80,000 items (16x) costs more than x80
  for indexed access (quadratic predicts x256) and under x48 for enumerate()
  (linear predicts x16). Measured x165 and x16 on the pinned interpreter
  (aarch64, CPython 3.14).
* `enumerate[T]` is a types.GenericAlias.
* every fenced block runs in a subprocess.

Not settled here:

* "the same bounds on every supported version" is read from the diffs of
  Objects/enumobject.c between the releases named above.
* Not varied: underlying iterators that do more than O(1) work per item (the
  page adds their cost rather than pricing it), a start outside the machine
  word in either direction (its per-step int addition grows with the
  counter's size), and threads
  sharing one enumerate object.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import types
from collections import deque
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "enumerate.md"
EXPECTED_BLOCKS = 10


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


class TestConstructionIsLazy:
    """Row: `enumerate(iterable, start=0)` - O(1); calls `iter(iterable)` once
    and takes no items."""

    def test_building_calls_iter_once_and_takes_nothing(self) -> None:
        source = CountingIterable(1_000)

        enumerate(source)

        assert source.iter_calls == 1
        assert source.items_taken == 0

    def test_a_non_iterable_raises_at_construction(self) -> None:
        with pytest.raises(TypeError, match="not iterable"):
            enumerate(42)  # type: ignore[call-overload]


class TestEachStepTakesOneItem:
    """Rows: `next()` on an enumerate object, and stopping early - one item from
    the underlying iterator per pair."""

    def test_next_takes_exactly_one_item(self) -> None:
        source = CountingIterable(1_000)
        pairs = enumerate(source)

        for expected in range(5):
            assert next(pairs) == (expected, expected)
            assert source.items_taken == expected + 1

    def test_breaking_after_k_pairs_takes_k_items(self) -> None:
        source = CountingIterable(1_000_000)

        for index, _ in enumerate(source):
            if index == 9:
                break

        assert source.items_taken == 10


@pytest.mark.timing
class TestIterationIsLinear:
    """Row: iterating an enumerate object - O(n)."""

    def test_ten_times_the_items_costs_about_ten_times(self) -> None:
        sizes = (20_000, 200_000, 2_000_000)
        times = [best_time(lambda n=n: consume(enumerate(range(n)))) for n in sizes]

        for small, large in zip(times, times[1:], strict=False):
            ratio = large / small
            assert 4 < ratio < 25, f"x{ratio:.1f} for x10 items: {times}"


class TestIterationSpace:
    """Rows: iterating is O(1) space; `list(enumerate(iterable))` is O(n)."""

    def test_consuming_does_not_accumulate(self) -> None:
        items = list(range(200_000))
        pairs = enumerate(items)
        tracemalloc.start()
        try:
            consume(pairs)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        assert peak < 20_000, f"peak {peak} bytes over 200,000 pairs"

    def test_list_holds_every_pair(self) -> None:
        items = list(range(200_000))

        pairs = list(enumerate(items))

        assert len(pairs) == len(items)
        assert pairs[-1] == (199_999, 199_999)
        assert len({id(pair) for pair in pairs}) == len(pairs)


class TestStart:
    """Custom Start Index: `start` is an int or has `__index__`; each index is O(1)
    for a start that fits in a machine word."""

    def test_index_objects_are_accepted_and_floats_are_not(self) -> None:
        class Three:
            def __index__(self) -> int:
                return 3

        assert list(enumerate("ab", Three())) == [(3, "a"), (4, "b")]  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="cannot be interpreted as an integer"):
            enumerate("ab", 1.5)  # type: ignore[arg-type]

    def test_the_counter_crosses_maxsize(self) -> None:
        pairs = list(enumerate("abc", start=sys.maxsize - 1))

        assert [index for index, _ in pairs] == [sys.maxsize - 1, sys.maxsize, sys.maxsize + 1]

    @pytest.mark.timing
    def test_a_start_near_maxsize_costs_the_same_per_item(self) -> None:
        items = list(range(200_000))

        from_zero = best_time(lambda: consume(enumerate(items)))
        near_max = best_time(lambda: consume(enumerate(items, sys.maxsize - 200_000)))

        ratio = near_max / from_zero
        assert ratio < 3, f"start near sys.maxsize cost x{ratio:.2f}"


@pytest.mark.timing
class TestRangeLenOnADeque:
    """enumerate() vs range(len(...)): indexing a deque makes the indexed loop
    O(n^2); enumerate() stays O(n)."""

    SMALL = 5_000
    LARGE = 80_000

    def _ratio(self, loop: Callable[[deque[int]], object]) -> float:
        small = deque(range(self.SMALL))
        large = deque(range(self.LARGE))
        return best_time(lambda: loop(large)) / best_time(lambda: loop(small))

    def test_indexed_loop_is_quadratic(self) -> None:
        ratio = self._ratio(lambda d: [d[i] for i in range(len(d))])

        assert ratio > 80, f"x{ratio:.1f} for x16 items"

    def test_enumerate_is_linear(self) -> None:
        ratio = self._ratio(lambda d: [x for _, x in enumerate(d)])

        assert ratio < 48, f"x{ratio:.1f} for x16 items"


class TestGenericAlias:
    """Row: `enumerate[T]` - a generic alias for type hints."""

    def test_subscripting_gives_a_generic_alias(self) -> None:
        alias = enumerate[int]

        assert isinstance(alias, types.GenericAlias)
        assert alias.__origin__ is enumerate


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
        block = next(source for _, source in _blocks() if "assert taken == [0, 1, 2, 3]" in source)
        broken = block.replace("assert taken == [0, 1, 2, 3]", "assert taken == []", 1)
        assert broken != block, "the mutation did not change the block"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "AssertionError" in result.stderr
