"""Tests for docs/builtins/frozenset.md and docs/builtins/frozenset_func.md.

The rows that differ from `set` are the ones that hand back an existing
object: `copy()` and `frozenset(fs)` return `fs` itself, so they are O(1).
Identity settles them without timing.

Measurement scope:

* `fs.copy()` and `frozenset(fs)` are asserted to return `fs` for an exact
  frozenset; for an instance of a subclass both are asserted to return a new,
  equal object, which is the O(n) copy. `set(fs)` is asserted to be a new set.
* A frozenset built from a set that had all but 10 of 200,000 elements
  discarded is asserted to be under 1/100 of that set's size, so the result
  is compact even though building it walks the old table; the walk itself is
  timed in tests/test_set_complexity.py.
* That `intersection()` and `difference()` take all of a non-set operand is
  asserted for frozensets in tests/test_set_complexity.py, beside the same
  test for sets; that two frozensets with colliding hashes still compare
  elements is in tests/test_complexity_caveats.py.
* frozenset.md: `hash()` of a fresh 200,000-element frozenset is asserted
  over 100x the cost of a second `hash()` on the same object, fastest of
  five fresh objects against fastest of five repeats; an equal frozenset
  built separately is asserted to pay the same first-call cost. Element
  `__hash__` is never called by `hash(fs)`: it reuses the hashes stored in
  the table, so the cache is only observable by time.
* frozenset.md: with elements whose `__eq__` counts calls and equal elements
  as distinct objects, a dict lookup by an equal but distinct frozenset of
  100 elements is asserted to compare all 100, and a lookup by the stored
  object to compare none. `==` between frozensets of different lengths
  compares none; `fs <= other` compares the n elements of `fs` against a
  1,000-element `other`, and `fs >= other` the m elements of `other`.
* frozenset.md: union, intersection, difference and symmetric difference,
  as operators and as methods, are asserted to return a new object, a
  frozenset when a frozenset is on the left and a set when a set is.
* frozenset.md: `frozenset(range(65_536)).difference(range(65_535))` keeps
  one element and is asserted over 1,000x the size of a one-element
  frozenset, the table the copy started with; the same difference with a
  set operand is asserted compact. Retention depends on where the removals
  leave the table against its resize threshold: from 65,535 elements the
  same removal compacts, which is why the page says "can keep". The cost of
  walking such a table is timed for sets in tests/test_set_complexity.py.
* frozenset_func.md: elements with a counting `__hash__` are
  hashed exactly once per item from a list of 1,000 holding 100 distinct
  values, and not at all from a set, a dict, a frozenset subclass instance
  or (3.15+) a frozendict of 1,000 distinct keys. A result built from 1,000
  equal items is asserted to be no larger than one built from a single
  item. `frozenset(itertools.repeat(x, 10**6))` is asserted to trace a peak under 64 KiB, where a copied list would need
  about 8 MB. With every hash equal, 40 and 80 elements must cost at least
  k(k-1)/2 `__eq__` calls, and doubling k must more than triple them.
* frozenset_func.md: building from a dict of 200,000 keys with all but 10
  deleted must cost more than 50x building from a fresh 10-key dict; the
  same for a sparse set is timed in tests/test_set_complexity.py. Only int
  elements were used; element type and hash cost were not varied.
* Every fenced Python block on both pages runs in its own subprocess, and a
  mutated assertion in one of them is asserted to fail.
"""

from __future__ import annotations

import builtins
import itertools
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any, ClassVar

import pytest

DOCS = pathlib.Path(__file__).parent.parent / "docs" / "builtins"
PAGES = {"frozenset.md": 8, "frozenset_func.md": 5}
FROZENDICT: Any = getattr(builtins, "frozendict", None)


class SubFrozenset(frozenset[int]):
    pass


class TestReturnsItself:
    def test_copy_returns_the_same_object(self) -> None:
        fs = frozenset(range(1_000))
        assert fs.copy() is fs

    def test_the_constructor_returns_the_same_object(self) -> None:
        fs = frozenset(range(1_000))
        assert frozenset(fs) is fs

    def test_a_subclass_instance_is_copied(self) -> None:
        sub = SubFrozenset(range(1_000))
        for copied in (sub.copy(), frozenset(sub)):
            assert copied is not sub and copied == sub and type(copied) is frozenset

    def test_set_of_it_is_a_new_set(self) -> None:
        fs = frozenset(range(10))
        assert set(fs) is not fs and set(fs) == fs


def test_building_from_a_sparse_set_is_compact() -> None:
    s = set(range(200_000))
    for i in range(10, 200_000):
        s.discard(i)
    frozen = frozenset(s)
    assert frozen == s
    assert sys.getsizeof(frozen) * 100 < sys.getsizeof(s)


# frozenset.md


def _fastest_ns(func: Callable[[], object], repeats: int = 5) -> int:
    best = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        elapsed = time.perf_counter_ns() - start
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


class _Counted:
    """An element whose equality checks are counted; equal values are distinct objects."""

    comparisons = 0

    def __init__(self, value: int) -> None:
        self.value = value

    def __hash__(self) -> int:
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        type(self).comparisons += 1
        return isinstance(other, _Counted) and self.value == other.value


def _counted(n: int, start: int = 0) -> frozenset[_Counted]:
    return frozenset(_Counted(i) for i in range(start, start + n))


class TestHashIsCachedPerObject:
    """`hash(fs)` is O(n) on the first call and O(1) after, per object."""

    SIZE = 200_000

    @pytest.mark.timing
    def test_a_second_hash_reads_the_cache(self) -> None:
        items = list(range(2_000, 2_000 + self.SIZE))
        fresh = iter([frozenset(items) for _ in range(5)])
        first_ns = _fastest_ns(lambda: hash(next(fresh)))
        hashed = frozenset(items)
        hash(hashed)
        cached_ns = _fastest_ns(lambda: hash(hashed))
        assert first_ns > cached_ns * 100, f"first {first_ns}ns, cached {cached_ns}ns"

    @pytest.mark.timing
    def test_an_equal_frozenset_computes_its_own(self) -> None:
        items = list(range(2_000, 2_000 + self.SIZE))
        hashed = frozenset(items)
        hash(hashed)
        twins = iter([frozenset(items) for _ in range(5)])
        twin_ns = _fastest_ns(lambda: hash(next(twins)))
        cached_ns = _fastest_ns(lambda: hash(hashed))
        assert twin_ns > cached_ns * 100, f"twin {twin_ns}ns, cached {cached_ns}ns"


class TestComparisonsCountElements:
    """Lookups and comparisons compare elements unless identity or length settles them."""

    def test_an_equal_key_compares_every_element(self) -> None:
        fs, twin = _counted(100), _counted(100)
        table = {fs: "found"}
        _Counted.comparisons = 0
        assert table[twin] == "found"
        assert _Counted.comparisons == 100

    def test_the_same_key_compares_nothing(self) -> None:
        fs = _counted(100)
        table = {fs: "found"}
        _Counted.comparisons = 0
        assert table[fs] == "found"
        assert _Counted.comparisons == 0

    def test_different_lengths_are_unequal_without_comparing(self) -> None:
        small, large = _counted(100), _counted(101)
        _Counted.comparisons = 0
        assert small != large and not small == large
        assert _Counted.comparisons == 0

    def test_subset_looks_up_the_left_operand(self) -> None:
        fs, other = _counted(10), _counted(1_000)
        _Counted.comparisons = 0
        assert fs <= other and fs < other
        assert _Counted.comparisons == 20

    def test_superset_looks_up_the_right_operand(self) -> None:
        fs, other = _counted(1_000), _counted(10)
        _Counted.comparisons = 0
        assert fs >= other and fs > other
        assert _Counted.comparisons == 20


class TestOperationsReturnNewObjects:
    """Each operation returns a new object, of the type of the set on its left."""

    OPERATIONS: ClassVar[list[Callable[[Any, Any], Any]]] = [
        lambda a, b: a | b,
        lambda a, b: a & b,
        lambda a, b: a - b,
        lambda a, b: a ^ b,
        lambda a, b: a.union(b),
        lambda a, b: a.intersection(b),
        lambda a, b: a.difference(b),
        lambda a, b: a.symmetric_difference(b),
    ]

    @pytest.mark.parametrize("operation", OPERATIONS)
    def test_a_frozenset_on_the_left_gives_a_new_frozenset(
        self, operation: Callable[[Any, Any], Any]
    ) -> None:
        fs = frozenset(range(10))
        for other in (frozenset(), fs, {1, 2}):
            result = operation(fs, other)
            assert type(result) is frozenset and result is not fs

    @pytest.mark.parametrize("operation", OPERATIONS)
    def test_a_set_on_the_left_gives_a_set(self, operation: Callable[[Any, Any], Any]) -> None:
        left = {1, 2}
        result = operation(left, frozenset(range(10)))
        assert type(result) is set and result is not left


class TestDifferenceCanLeaveASparseTable:
    """`difference()` with a non-set iterable copies the table and removes from the copy."""

    def test_removing_most_elements_keeps_the_table(self) -> None:
        sparse = frozenset(range(65_536)).difference(range(65_535))
        assert sparse == {65_535}
        assert sys.getsizeof(sparse) > sys.getsizeof(frozenset([65_535])) * 1_000

    def test_a_set_operand_gives_a_compact_result(self) -> None:
        compact = frozenset(range(65_536)).difference(set(range(65_535)))
        assert sys.getsizeof(compact) == sys.getsizeof(frozenset([65_535]))


# docs/builtins/frozenset_func.md


class CountingKey:
    """An element that counts its `__hash__` and `__eq__` calls."""

    hashes = 0
    comparisons = 0

    def __init__(self, value: int, hash_value: int | None = None) -> None:
        self.value = value
        self.hash_value = value if hash_value is None else hash_value

    def __hash__(self) -> int:
        type(self).hashes += 1
        return self.hash_value

    def __eq__(self, other: object) -> bool:
        type(self).comparisons += 1
        return isinstance(other, CountingKey) and self.value == other.value


class SubFrozensetOf(frozenset[Any]):
    pass


class TestBuildingHashesEachItemOnce:
    """`frozenset(iterable)` hashes each item once; a set, frozenset subclass
    or dict argument has its stored hashes reused, so nothing is rehashed."""

    def test_an_iterable_is_hashed_once_per_item(self) -> None:
        distinct = [CountingKey(i) for i in range(100)]
        items = distinct * 10
        CountingKey.hashes = 0
        assert len(frozenset(items)) == 100
        assert CountingKey.hashes == len(items)

    @pytest.mark.parametrize("kind", ["set", "subclass", "dict", "frozendict"])
    def test_stored_hashes_are_reused(self, kind: str) -> None:
        if kind == "frozendict" and FROZENDICT is None:
            pytest.skip("version: frozendict was added in 3.15")
        builders: dict[str, Callable[[list[CountingKey]], Any]] = {
            "set": set,
            "subclass": SubFrozensetOf,
            "dict": dict.fromkeys,
            "frozendict": lambda keys: FROZENDICT(dict.fromkeys(keys)),
        }
        keys = [CountingKey(i) for i in range(1_000)]
        source = builders[kind](keys)
        CountingKey.hashes = 0
        assert len(frozenset(source)) == 1_000
        assert CountingKey.hashes == 0

    def test_collisions_make_building_quadratic(self) -> None:
        def comparisons(k: int) -> int:
            keys = [CountingKey(i, hash_value=7) for i in range(k)]
            CountingKey.comparisons = 0
            assert len(frozenset(keys)) == k
            return CountingKey.comparisons

        at_40, at_80 = comparisons(40), comparisons(80)
        assert at_40 >= 40 * 39 // 2 and at_80 >= 80 * 79 // 2
        assert at_80 > at_40 * 3, "doubling k must roughly quadruple the comparisons"


class TestBuildingSpace:
    """Space is O(u) in the distinct elements, and the iterable is consumed
    item by item rather than copied first."""

    def test_duplicates_take_no_space(self) -> None:
        assert sys.getsizeof(frozenset([2_000] * 1_000)) <= sys.getsizeof(frozenset([2_000]))

    def test_the_iterable_is_not_copied(self) -> None:
        item = object()
        tracemalloc.start()
        try:
            result = frozenset(itertools.repeat(item, 1_000_000))
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        assert result == {item}
        assert peak < 64 * 1024, f"traced peak {peak} bytes"


def best_ns(func: Callable[[], Any], repeats: int = 5, inner: int = 3) -> float:
    best = float("inf")
    for _ in range(repeats):
        start = time.perf_counter_ns()
        for _ in range(inner):
            func()
        best = min(best, (time.perf_counter_ns() - start) / inner)
    return best


@pytest.mark.timing
def test_building_from_a_sparse_dict_costs_its_former_size() -> None:
    sparse = dict.fromkeys(range(200_000))
    for i in range(10, 200_000):
        del sparse[i]
    fresh = dict.fromkeys(range(10))
    sparse_ns = best_ns(lambda: frozenset(sparse))
    fresh_ns = best_ns(lambda: frozenset(fresh))
    assert sparse_ns > fresh_ns * 50, f"{fresh_ns:.0f}ns vs {sparse_ns:.0f}ns"


def _blocks(page: str) -> list[tuple[int, str]]:
    """Every fenced python block on the page, with its 1-based line number."""
    lines = (DOCS / page).read_text(encoding="utf-8").splitlines()
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
    @pytest.mark.parametrize(("page", "expected"), PAGES.items())
    def test_the_page_has_the_expected_blocks(self, page: str, expected: int) -> None:
        assert len(_blocks(page)) == expected

    @pytest.mark.parametrize("page", PAGES)
    def test_every_block_runs(self, page: str, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        for line, source in _blocks(page):
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{page}:{line}\n{result.stderr.strip()}")
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        target = "assert 'unhashable' in str(error)"
        line, source = next((n, s) for n, s in _blocks("frozenset.md") if target in s)
        mutated = source.replace(target, "assert 'hashable' not in str(error)", 1)

        assert mutated != source, f"the mutation matched nothing in frozenset.md:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
