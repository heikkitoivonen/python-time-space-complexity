"""Tests for docs/builtins/map.md.

map() is the mapobject in Python/bltinmodule.c. map_new and map_vectorcall
call PyObject_GetIter once per input and store the iterators in a tuple;
neither reads an item nor calls the function. map_next calls tp_iternext once
per input, stopping at the first that ends, and then makes one vectorcall of
the function with the items taken; its argument array is a small stack array
or an m-slot allocation. From v3.14.0, `strict=True` makes map_next, on the
first input that ends, raise ValueError if that input is not the first, or
else take one more item from every later input and raise ValueError if any
yields one. map_new, map_vectorcall and map_next do the same work in the
v3.11.14, v3.12.12 and v3.13.11 tags, and in v3.14.2 and v3.15.0rc3 apart
from `strict`.

Every row is settled by observation: counting `__iter__` calls, items
taken and function calls, and tracemalloc for space. No row needs a stopwatch.

Measurement scope:

* building a map over three counting iterables calls `__iter__` once on each
  and takes no item and calls the function not at all; a map over
  range(10**9) calls the function only when next() asks.
* one next() over three counting iterators takes exactly one item from each
  and calls the function once; over m = 1, 3 and 10 inputs the items taken
  per next() are 1, 3 and 10.
* a full pass over inputs of lengths 1,000, 2,000 and 3,000 calls the
  function 1,000 times. In a two-input map whose second input is shorter,
  the item taken from the first input in the final step is gone from it
  afterwards.
* strict=True (3.14+): equal lengths yield every result; a shorter later input
  raises ValueError naming "shorter", a longer later input raises naming
  "longer".
* space: tracemalloc's peak while summing a two-stage map chain over
  range(1,000,000) is under 10 KB, while list() of one map over the same range
  peaks over 1 MB. These run serially, since xdist's I/O thread allocates
  while tracemalloc is tracing.
* a second pass over an exhausted map yields nothing.
* every fenced block runs in its own subprocess and asserts its own results,
  and a mutated assertion in one is asserted to fail.

Not settled here:

* The cost of the function and of each input's own `__next__` is the
  caller's; the page names it once and the tests hold both at O(1).
* The O(m) space of one next() is read from map_next's argument array; m is
  not varied in the allocation measurement.
* Not varied: element types (ints only) and the position of the shortest
  input beyond first and last.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap
import tracemalloc
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "map.md"
EXPECTED_BLOCKS = 8


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def strict_map(function: Callable[..., Any], *iterables: Any) -> Iterator[Any]:
    """`map(..., strict=True)`, which the 3.11 signatures pyright checks against lack."""
    build: Any = map
    return build(function, *iterables, strict=True)


class Counting:
    """An iterable that records each `__iter__` and each item taken."""

    def __init__(self, count: int) -> None:
        self.count = count
        self.iter_calls = 0
        self.taken = 0

    def __iter__(self) -> Iterator[int]:
        self.iter_calls += 1
        return self._items()

    def _items(self) -> Iterator[int]:
        for i in range(self.count):
            self.taken += 1
            yield i


class TestBuildingReadsNothing:
    """`map(function, iterable, *iterables)` is O(m): one `iter()` per input,
    no item read and no call made."""

    def test_one_iter_per_input_and_no_items(self) -> None:
        inputs = [Counting(10), Counting(10), Counting(10)]
        calls: list[tuple[int, ...]] = []

        map(lambda *args: calls.append(args), *inputs)

        assert [i.iter_calls for i in inputs] == [1, 1, 1]
        assert [i.taken for i in inputs] == [0, 0, 0]
        assert calls == []

    def test_a_huge_input_is_not_read(self) -> None:
        calls: list[int] = []
        squares = map(lambda x: calls.append(x) or x * x, range(10**9))
        assert calls == []
        assert next(squares) == 0
        assert calls == [0]


class TestNextTakesOneItemPerInput:
    """`next()` on a map is O(m): one item from each input, then one call."""

    @pytest.mark.parametrize("m", [1, 3, 10])
    def test_items_taken_per_next_equal_the_inputs(self, m: int) -> None:
        inputs = [Counting(100) for _ in range(m)]
        calls = 0

        def total(*args: int) -> int:
            nonlocal calls
            calls += 1
            return sum(args)

        mapped = map(total, *inputs)
        assert next(mapped) == 0
        assert [i.taken for i in inputs] == [1] * m
        assert calls == 1
        assert next(mapped) == m
        assert [i.taken for i in inputs] == [2] * m
        assert calls == 2


class TestAFullPassStopsAtTheShortestInput:
    """Iterating to the end is O(n·m) plus n calls, n being the shortest
    input's length; when a later input ends, items already taken from the
    inputs before it in that step are discarded."""

    def test_the_function_runs_once_per_result(self) -> None:
        calls = 0

        def pick(a: int, b: int, c: int) -> int:
            nonlocal calls
            calls += 1
            return a

        results = list(map(pick, range(1_000), range(2_000), range(3_000)))
        assert len(results) == 1_000
        assert calls == 1_000

    def test_an_item_taken_before_a_later_input_ends_is_lost(self) -> None:
        longer = iter([1, 2, 3])
        pairs = list(map(lambda a, b: (a, b), longer, [10, 20]))

        assert pairs == [(1, 10), (2, 20)]
        assert list(longer) == [], "3 was taken in the final step and discarded"

    def test_a_second_pass_is_empty(self) -> None:
        doubled = map(lambda x: 2 * x, [1, 2, 3])
        assert list(doubled) == [2, 4, 6]
        assert list(doubled) == []


@pytest.mark.skipif(sys.version_info < (3, 14), reason="version: strict= is new in 3.14")
class TestStrict:
    """`map(..., strict=True)` (3.14+) raises ValueError when the inputs'
    lengths differ, and yields every result when they match."""

    @staticmethod
    def power(base: int, exp: int) -> int:
        return base**exp

    def test_equal_lengths_yield_every_result(self) -> None:
        assert list(strict_map(self.power, [2, 3], [5, 2])) == [32, 9]

    def test_a_shorter_later_input_raises(self) -> None:
        with pytest.raises(ValueError, match="shorter"):
            list(strict_map(self.power, [2, 3, 4], [5, 2]))

    def test_a_longer_later_input_raises(self) -> None:
        with pytest.raises(ValueError, match="longer"):
            list(strict_map(self.power, [2, 3], [5, 2, 1]))


@pytest.mark.serial
class TestSpace:
    """Iterating a map holds O(m), so a chain of maps over a stream builds no
    list; `list(map(...))` holds all n results."""

    def test_a_chain_of_maps_holds_no_list(self) -> None:
        def run() -> int:
            return sum(map(lambda x: x + 1, map(lambda x: x * x, range(1_000_000))))

        assert run() == sum(x * x + 1 for x in range(1_000_000))
        chain_peak = peak_bytes(run)
        list_peak = peak_bytes(lambda: list(map(lambda x: x, range(1_000_000))))

        assert chain_peak < 10_000, f"the map chain peaked at {chain_peak} bytes"
        assert list_peak > 1_000_000, f"list(map(...)) peaked at only {list_peak} bytes"


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
        line, source = next((n, s) for n, s in _blocks() if "assert list(longer) == []" in s)
        mutated = source.replace("assert list(longer) == []", "assert list(longer) == [3]", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
