"""Tests for docs/builtins/tuple_func.md.

The page prices `tuple()` by the items its argument yields, except for an
exact tuple, which is returned itself. Identity settles that exception and the
shallowness of every copy without tolerance; a counting iterator settles that
each item is taken once; the growth of a copy and the cost of a sparse hash
table are timed.

Measurement scope:

* `tuple(t)` is asserted to return `t` itself for exact tuples of 0, 1 and
  100,000 elements. For a tuple subclass instance and for a list it is
  asserted to return a new exact `tuple` whose elements are the same objects
  as the source's.
* A counting iterator over 1,000 and 100,000 items is asserted to have
  exactly n items taken by `tuple()`, and to be exhausted afterwards.
* `tuple(itertools.repeat(obj, n))` holds n references to the one object: the
  traced construction peak at n = 1,000,000 is asserted between 50x and
  200x the peak at n = 10,000 (linear predicts 100x), and every element is
  asserted to be `obj`.
* `tuple(lst)` and `tuple(sub)` for a tuple subclass instance are timed at
  10,000, 100,000 and 1,000,000 int elements; each 10x step must cost more
  than 4x and less than 50x (linear predicts 10x, a constant-time return 1x,
  a quadratic copy 100x). `tuple(t)` for an exact tuple at 1,000,000
  elements is held under 3x the cost at 10 elements.
* A dict and a set of 200,000 ints with all but 10 removed, and that dict's
  `keys()`, `values()` and `items()` views, must cost more than 50x a fresh
  10-item container to pass to `tuple()`.
* Adding a fresh tuple of 1,000 elements with a counting `__hash__` to a set
  calls it exactly once per element. Whether a second hash of the same tuple
  repeats that work is version-dependent (3.14 added a cached tuple hash) and
  is not what the page prices.
* A function returning the literal `(1, 2, 3)` is asserted to return the same
  object on every call, and one returning `tuple([1, 2, 3])` a new one.
* Every fenced Python block on the page runs in its own subprocess, and a
  mutated assertion in one of them is asserted to fail.

Not settled here:

* Treating taking one item from the argument as O(1) is a cost-model
  assumption; a generator or `map()` adds whatever producing its items costs.
  On 3.11-3.13 `tuple()` preallocates from `__length_hint__`, so an
  iterable reporting a hint far above the items it yields costs its hint;
  that pathological protocol is not priced or tested.
* Element hashes cost what each element's `__hash__` costs; the test counts
  calls, with O(1) int hashes.
* The timing tests use only int elements; the identity and allocation tests
  use `object()` instances and small lists. Element type was not varied.
"""

from __future__ import annotations

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

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "tuple_func.md"
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


class SubTuple(tuple[Any, ...]):
    pass


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


class CountingHash:
    """An element that counts its `__hash__` calls."""

    hashes = 0

    def __init__(self, value: int) -> None:
        self.value = value

    def __hash__(self) -> int:
        type(self).hashes += 1
        return self.value


class TestAnExactTupleIsReturnedItself:
    """`tuple(t)` where `t` is an exact tuple | O(1) | O(1) | Returns `t` itself.

    Identity separates returning the argument from copying it; a subclass
    instance and a list are the controls that do copy.
    """

    @pytest.mark.parametrize("n", [0, 1, 100_000])
    def test_the_same_object_comes_back(self, n: int) -> None:
        source = tuple(range(n))
        assert tuple(source) is source

    def test_a_subclass_instance_is_copied(self) -> None:
        source = SubTuple(object() for _ in range(100))
        result = tuple(source)
        assert result is not source and type(result) is tuple
        assert all(a is b for a, b in zip(result, source, strict=True))

    def test_a_list_is_copied_shallowly(self) -> None:
        source = [[i] for i in range(100)]
        result = tuple(source)
        assert type(result) is tuple
        assert all(a is b for a, b in zip(result, source, strict=True))

    @pytest.mark.timing
    def test_returning_it_does_not_grow_with_n(self) -> None:
        small, large = tuple(range(10)), tuple(range(2_000, 1_002_000))
        small_ns = best_ns(lambda: tuple(small), inner=1_000)
        large_ns = best_ns(lambda: tuple(large), inner=1_000)
        assert large_ns < small_ns * 3, f"10 items {small_ns:.0f}ns, 1,000,000 {large_ns:.0f}ns"


class TestEveryItemIsTakenOnce:
    """`tuple(iterable)` | O(n) | Takes every item; an iterator is left exhausted."""

    @pytest.mark.parametrize("n", [1_000, 100_000])
    def test_n_items_are_taken(self, n: int) -> None:
        source = CountingIterator(n)
        assert len(tuple(source)) == n
        assert source.taken == n

    def test_the_iterator_is_exhausted(self) -> None:
        source = CountingIterator(1_000)
        tuple(source)
        assert tuple(source) == ()
        assert source.taken == 1_000


class TestSpaceIsOneReferencePerItem:
    """Space is the new tuple's references; the items are shared, not copied."""

    def test_the_peak_grows_with_n(self) -> None:
        item = object()
        small = peak_bytes(lambda: tuple(itertools.repeat(item, 10_000)))
        large = peak_bytes(lambda: tuple(itertools.repeat(item, 1_000_000)))
        assert small * 50 < large < small * 200, f"10,000 items: {small} bytes, 1,000,000: {large}"

    def test_the_items_are_not_copied(self) -> None:
        item = object()
        assert all(x is item for x in tuple(itertools.repeat(item, 1_000)))


@pytest.mark.timing
@pytest.mark.parametrize("kind", [list, SubTuple])
def test_copying_grows_linearly(kind: Callable[[range], Any]) -> None:
    times = []
    for n in (10_000, 100_000, 1_000_000):
        source = kind(range(2_000, 2_000 + n))
        times.append(best_ns(lambda source=source: tuple(source)))
    for smaller, larger in itertools.pairwise(times):
        assert smaller * 4 < larger < smaller * 50, f"{times}"


class TestASparseHashTableCostsItsFormerSize:
    """`tuple(d)` where `d` is a dict, set or dict view walks the hash table:
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
        assert tuple(sparse) == tuple(fresh)
        sparse_ns = best_ns(lambda: tuple(sparse))
        fresh_ns = best_ns(lambda: tuple(fresh), inner=100)
        assert sparse_ns > fresh_ns * 50, f"fresh {fresh_ns:.0f}ns, sparse {sparse_ns:.0f}ns"


class TestHashingTheResult:
    """Building the key costs O(n) once, and hashing it costs O(n) on top."""

    def test_each_element_is_hashed(self) -> None:
        key = tuple(CountingHash(i) for i in range(1_000))
        seen: set[tuple[CountingHash, ...]] = set()
        CountingHash.hashes = 0
        seen.add(key)
        assert CountingHash.hashes == 1_000


class TestALiteralOfConstantsIsBuiltOnce:
    """A literal of constants is one compiled constant; `tuple([...])` is not."""

    def test_the_literal_is_the_same_object(self) -> None:
        def literal() -> tuple[int, ...]:
            return (1, 2, 3)

        def converted() -> tuple[int, ...]:
            return tuple([1, 2, 3])  # noqa: C409 - the call is the subject

        assert literal() is literal()
        first, second = converted(), converted()
        assert first == second == literal() and first is not second


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
        line, source = next((n, s) for n, s in _blocks() if "assert tuple(t) is t" in s)
        mutated = source.replace("assert tuple(t) is t", "assert tuple(t) is not t", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
