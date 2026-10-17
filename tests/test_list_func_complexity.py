"""Tests for docs/builtins/list_func.md.

The page prices `list()` by the items its argument yields: every call builds a
new list of references to those items, takes each item once, and shares the
items rather than copying them. Identity and a counting iterator settle those
without tolerance; the growth of the copy and the cost of a sparse hash table
are timed.

Measurement scope:

* `list(lst)` and `list(t)` are asserted to return a new list, even for a
  list, whose elements are the same objects as the source's; `lst.copy()`,
  `lst[:]` and `copy.copy(lst)` are asserted to do the same. Two `list()`
  calls return two distinct empty lists.
* A counting iterator over 1,000 and 100,000 items is asserted to have
  exactly n items taken by `list()`, and to be exhausted afterwards.
* `list(itertools.repeat(obj, n))` holds n references to the one object: the
  traced peak at n = 1,000,000 is asserted over 50x the peak at n = 10,000,
  and every element is asserted to be `obj`.
* `list(lst)` is timed at 10,000, 100,000 and 1,000,000 int elements; each
  10x step must cost more than 4x and less than 50x (linear predicts 10x, a
  constant-time copy 1x, a quadratic one 100x).
* A dict and a set of 200,000 ints with all but 10 removed, and that dict's
  `keys()`, `values()` and `items()` views, must cost more than 50x a fresh
  10-item container to pass to `list()`.
* Changing 5,000 characters of a 100,000-character string by slicing, one new
  string per change, must cost more than 10x converting it to a list,
  assigning the characters and joining once.
* Every fenced Python block on the page runs in its own subprocess, and a
  mutated assertion in one of them is asserted to fail.

Not settled here:

* Treating taking one item from the argument as O(1) is a cost-model
  assumption; a generator or `map()` adds whatever producing its items costs.
* The timing tests use only int and str elements; the identity and
  allocation tests use `object()` instances and small lists. Element type was
  not varied in the timings, and tuple sources are checked for identity, not
  timed.
"""

from __future__ import annotations

import copy
import itertools
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

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "list_func.md"
EXPECTED_BLOCKS = 5


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


class CountingIterator:
    """An iterator over range(n) that records how many items were taken."""

    def __init__(self, n: int) -> None:
        self._items = iter(range(n))
        self.taken = 0

    def __iter__(self) -> CountingIterator:
        return self

    def __next__(self) -> int:
        item = next(self._items)
        self.taken += 1
        return item


class TestEveryCallBuildsANewShallowList:
    """`list(lst)` | O(n) | O(n) | A new list holding the same elements.

    Identity separates a copy from returning the argument, and element
    identity separates a shallow copy from a deep one.
    """

    def test_a_list_argument_is_copied(self) -> None:
        source = [object() for _ in range(100)]
        result = list(source)
        assert result is not source and result == source
        assert all(a is b for a, b in zip(result, source, strict=True))

    def test_a_tuple_argument_gives_a_list_of_the_same_elements(self) -> None:
        source = tuple(object() for _ in range(100))
        result = list(source)
        assert type(result) is list
        assert all(a is b for a, b in zip(result, source, strict=True))

    def test_the_other_copies_are_shallow_too(self) -> None:
        source = [[i] for i in range(100)]
        for result in (source.copy(), source[:], copy.copy(source)):
            assert result is not source
            assert all(a is b for a, b in zip(result, source, strict=True))

    def test_each_empty_list_is_new(self) -> None:
        first, second = list(), list()  # noqa: C408 - the call is the subject
        assert first == second == [] and first is not second


class TestEveryItemIsTakenOnce:
    """`list(iterable)` | O(n) | Takes every item; an iterator is left exhausted."""

    @pytest.mark.parametrize("n", [1_000, 100_000])
    def test_n_items_are_taken(self, n: int) -> None:
        source = CountingIterator(n)
        assert len(list(source)) == n
        assert source.taken == n

    def test_the_iterator_is_exhausted(self) -> None:
        source = CountingIterator(1_000)
        list(source)
        assert list(source) == []
        assert source.taken == 1_000


class TestSpaceIsOneReferencePerItem:
    """Space is the new list's references; the items are shared, not copied."""

    def test_the_peak_grows_with_n(self) -> None:
        item = object()
        small = peak_bytes(lambda: list(itertools.repeat(item, 10_000)))
        large = peak_bytes(lambda: list(itertools.repeat(item, 1_000_000)))
        assert large > small * 50, f"10,000 items: {small} bytes, 1,000,000: {large}"

    def test_the_items_are_not_copied(self) -> None:
        item = object()
        assert all(x is item for x in list(itertools.repeat(item, 1_000)))


@pytest.mark.timing
def test_copying_a_list_grows_linearly() -> None:
    times = []
    for n in (10_000, 100_000, 1_000_000):
        source = list(range(2_000, 2_000 + n))
        times.append(best_ns(lambda source=source: list(source)))
    for smaller, larger in itertools.pairwise(times):
        assert smaller * 4 < larger < smaller * 50, f"{times}"


class TestASparseHashTableCostsItsFormerSize:
    """`list(d)` where `d` is a dict, set or dict view walks the hash table:
    one that had most of its items removed costs its former size."""

    @staticmethod
    def _sparse_dict() -> dict[int, int]:
        d = dict.fromkeys(range(200_000), 0)
        for key in range(10, 200_000):
            del d[key]
        return d

    @staticmethod
    def _sparse_set() -> set[int]:
        s = set(range(200_000))
        for item in range(10, 200_000):
            s.discard(item)
        return s

    @pytest.mark.timing
    @pytest.mark.parametrize("kind", ["dict", "set", "keys", "values", "items"])
    def test_removed_items_still_cost(self, kind: str) -> None:
        builders: dict[str, tuple[Any, Any]] = {
            "dict": (self._sparse_dict(), dict.fromkeys(range(10), 0)),
            "set": (self._sparse_set(), set(range(10))),
            "keys": (self._sparse_dict().keys(), dict.fromkeys(range(10), 0).keys()),
            "values": (self._sparse_dict().values(), dict.fromkeys(range(10), 0).values()),
            "items": (self._sparse_dict().items(), dict.fromkeys(range(10), 0).items()),
        }
        sparse, fresh = builders[kind]
        assert list(sparse) == list(fresh)
        sparse_ns = best_ns(lambda: list(sparse))
        fresh_ns = best_ns(lambda: list(fresh), inner=100)
        assert sparse_ns > fresh_ns * 50, f"fresh {fresh_ns:.0f}ns, sparse {sparse_ns:.0f}ns"


@pytest.mark.timing
def test_changing_characters_through_a_list_beats_slicing() -> None:
    text = "a" * 100_000
    positions = range(0, 100_000, 20)
    assert len(positions) == 5_000

    def by_slicing() -> str:
        result = text
        for i in positions:
            result = result[:i] + "b" + result[i + 1 :]
        return result

    def through_a_list() -> str:
        chars = list(text)
        for i in positions:
            chars[i] = "b"
        return "".join(chars)

    assert by_slicing() == through_a_list()
    slicing_ns = best_ns(by_slicing, repeats=3)
    list_ns = best_ns(through_a_list)
    assert slicing_ns > list_ns * 10, f"slicing {slicing_ns:.0f}ns, list {list_ns:.0f}ns"


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
        line, source = next((n, s) for n, s in _blocks() if "assert list(gen) == []" in s)
        mutated = source.replace("assert list(gen) == []", "assert list(gen) == [0]", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
