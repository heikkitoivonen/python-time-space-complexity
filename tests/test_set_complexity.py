"""Tests for docs/builtins/set.md and docs/builtins/set_func.md.

These cover the rows and paragraphs that pin the set page to the official
CPython time-complexity table: the in-place operations, the cost of a non-set
operand, the worst case under hash collisions, and the hash table that removal
does not shrink. Membership and `len()` are timed in
tests/test_builtin_complexity.py.

`intersection_update()` and `&=` are O(min(n, m)) amortized, as in the
official table (v3.15.0:Doc/builtins/time-complexity.rst, intersection update
row, footnotes 1 and 8). Both forms build the intersection, swap it into `s`
and free the old table, which releases each of its n entries
(Objects/setobject.c, `set_intersection_update` and `set_dealloc`). With a set
operand the build walks the smaller side, so a single call is O(min(n, m) + n);
a non-set operand is iterated to the end, or until the result holds n
elements, so a single call is O(m + n). At most min(n, m) of the old entries
are kept and the rest are dropped, so the release is paid for by the
insertions that put the dropped elements in `s`; on a sparse table, the slots
beyond its live entries were paid for by the insertions that filled them
(footnote 7). The timing tests below are finite-size scaling checks on that
argument, not a proof of it. Measured on 3.15.0 (aarch64 Linux) with a
3-element `other` and the elements kept alive elsewhere: one call costs 5% to
8% of building `s` by `add()` at 2,000 / 20,000 / 200,000 / 2,000,000
elements, for `&=` and for the method with a set or a list.

Measurement scope:

* Removal is observed through `sys.getsizeof()`: a set of 200,000 ints keeps
  its size after all but 10 are removed with `remove()`, `discard()` or
  `pop()`.
* The walking operations are timed on that sparse set against a fresh set of
  the same 10 ints: iteration, `copy()`, `set(s)`, `frozenset(s)`, `s | {-1}`,
  `s - {-1}`, `s ^ {-1}`, `s <= s` and `s == twin` must each cost more than
  50x (locally thousands). `len()` and `in` are held under 5x. `&=` and
  `intersection_update()` with a 1-element `other` must too, on a sparse set
  whose 10 survivors are its highest ints: freeing the old table stops at its
  last live entry, so survivors in the lowest slots cost far less (32x
  against 1,134x on 3.15.0 with a 3-element `other`). Spread hashes leave the
  last live entry near the end of the table.
* `-=`, `difference_update()`, `&=` and `intersection_update()` doing the
  same mass removal are asserted to leave a set under 1/100 of the full size,
  and so is `copy()` of the sparse set. So are `&=` and
  `intersection_update()` on the sparse set with an `other` holding all 10
  survivors, which removes nothing. Insertions, each removed again so the
  set keeps 10 elements, are asserted to rebuild the sparse table smaller
  before 400,000 of them.
* `intersection_update()` and `&=` are timed with a 3-element `other` on
  2,000 and 200,000 elements kept alive elsewhere: 100x the elements must
  cost more than 20x per call. `s & other` on the same sets must stay under
  5x. One call divided by the `add()` loop that built the same set must stay
  under 1/2 at 2,000, 20,000 and 200,000 elements, and grow under 3x across
  them, where a call quadratic in n would grow it 100x. The bound does not
  separate O(n) from O(n log n) per call; source settles that.
  With 100 elements, an `other` of 1,000 and of 1,000,000 elements that
  holds them all must cost under 5x apart, which is the min(n, m).
* `difference_update()` and `-=` are timed with `other` a set: 100 elements
  against 1,000 and 1,000,000, and 1,000 and 1,000,000 elements against 3
  absent ones, each under 5x, which is the O(min(n, m)).
* A non-set operand is a counting iterator: `intersection()`,
  `intersection_update()`, `difference()`, `difference_update()`,
  `issubset()` and `isdisjoint()` take all 1,000 of its items when none of
  them is in `s`. `difference()` is
  asserted to return a new set with `s` unchanged.
* The operators are asserted to raise `TypeError` for a list operand.
* The worst case is a counting `__eq__` on elements that share one hash:
  `a & b` over two disjoint sets of k such elements makes at least k squared
  comparisons for k = 40 and 80, and doubling k more than triples them.
* set_func.md: elements with a counting `__hash__` are hashed exactly once
  per item from a list of 1,000 holding 100 distinct values, and not at all
  from a set, a frozenset, a subclass instance of either, a dict or (3.15+)
  a frozendict of 1,000 distinct keys. A dict subclass and a `keys()` view
  are asserted to hash all 1,000.
* set_func.md: `set(s)` is asserted to return a new set holding the same
  element objects, for a set and for a frozenset. A set built from 1,000
  equal items is no larger than one built from a single item, and
  `set(itertools.repeat(x, 10**6))` is asserted to trace a peak under
  64 KiB, where a copied list would need about 8 MB. With every hash equal,
  40 and 80 elements must cost at least k(k-1)/2 `__eq__` calls, and
  doubling k must more than triple them.
* set_func.md: `set(d)` of a dict of 200,000 keys with all but 10 deleted
  must cost more than 50x `set()` of a fresh 10-key dict; `set(s)` of the
  sparse set is timed with the walking operations above. Both results are
  asserted under 1/100 of the sparse source's size. Only int and
  counted-object elements were used; element type and hash cost were not
  varied.
* Every fenced Python block on both pages runs in its own subprocess, and a
  mutated assertion in one of them is asserted to fail.

Not settled here:

* `symmetric_difference_update()` and `update()` with a non-set operand are
  not measured. The O(m) space of `symmetric_difference_update()` and of
  `issubset()` with a non-set operand, and the O(n) space of
  `difference_update()`, are read from Objects/setobject.c: the first builds
  a set from the operand, `issubset()` builds one on 3.11 and the
  intersection on 3.12+, and `difference_update()` builds the intersection
  when `other` is over 8x larger and may rebuild its own table.
* The point at which a sparse set is rebuilt depends on its fill; only that
  insertions eventually rebuild it is asserted.
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
from collections.abc import Callable, Iterator
from typing import Any

import pytest

DOCS = pathlib.Path(__file__).parent.parent / "docs" / "builtins"
PAGES = {"set.md": 6, "set_func.md": 5}

PEAK = 200_000
KEPT = 10


def best_ns(func: Callable[[], Any], repeats: int = 5, inner: int = 3) -> float:
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


def best_fresh_ns(
    func: Callable[[set[int]], Any], setup: Callable[[], set[int]], repeats: int = 7
) -> float:
    """Fastest of `repeats` calls, in nanoseconds, each on a fresh set that
    `setup` builds outside the timed region."""
    best: float | None = None
    for _ in range(repeats):
        argument = setup()
        start = time.perf_counter_ns()
        func(argument)
        elapsed = time.perf_counter_ns() - start
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def sparse_set(method: str = "discard") -> set[int]:
    """A set that held PEAK ints and now holds KEPT."""
    s = set(range(PEAK))
    if method == "pop":
        while len(s) > KEPT:
            s.pop()
        return s
    remove = getattr(s, method)
    for i in range(KEPT, PEAK):
        remove(i)
    return s


class TestRemovingDoesNotShrinkTheTable:
    @pytest.mark.parametrize("method", ["remove", "discard", "pop"])
    def test_the_table_keeps_its_size(self, method: str) -> None:
        full = sys.getsizeof(set(range(PEAK)))
        s = sparse_set(method)
        assert len(s) == KEPT
        assert sys.getsizeof(s) == full

    @pytest.mark.timing
    @pytest.mark.parametrize(
        "name", ["iterate", "copy", "set()", "frozenset()", "or", "sub", "xor", "le", "eq"]
    )
    def test_walking_costs_the_former_size(self, name: str) -> None:
        operations: dict[str, Callable[[set[int]], Any]] = {
            "iterate": list,
            "copy": lambda s: s.copy(),
            "set()": set,
            "frozenset()": frozenset,
            "or": lambda s: s | {-1},
            "sub": lambda s: s - {-1},
            "xor": lambda s: s ^ {-1},
            "le": lambda s: s <= s,
            "eq": lambda s: s == set(range(KEPT)),
        }
        op = operations[name]
        sparse, fresh = sparse_set(), set(range(KEPT))
        sparse_ns = best_ns(lambda: op(sparse))
        fresh_ns = best_ns(lambda: op(fresh))
        assert sparse_ns > fresh_ns * 50, f"{name}: {fresh_ns:.0f}ns vs {sparse_ns:.0f}ns"

    @pytest.mark.timing
    @pytest.mark.parametrize("form", ["method", "operator"])
    def test_in_place_intersection_costs_the_former_size(self, form: str) -> None:
        """Freeing the old table walks it up to its last live entry, so the
        survivors are the highest ints, which sit in the highest slots."""
        survivors = range(PEAK - KEPT, PEAK)
        other = {PEAK - 1}

        def sparse() -> set[int]:
            s = set(range(PEAK))
            for i in range(PEAK - KEPT):
                s.discard(i)
            return s

        def apply(s: set[int]) -> None:
            if form == "method":
                s.intersection_update(other)
            else:
                s &= other

        sparse_ns = best_fresh_ns(apply, sparse)
        fresh_ns = best_fresh_ns(apply, lambda: set(survivors))
        assert sparse_ns > fresh_ns * 50, f"{form}: {fresh_ns:.0f}ns vs {sparse_ns:.0f}ns"

    @pytest.mark.timing
    @pytest.mark.parametrize("name", ["len", "in"])
    def test_len_and_membership_are_unaffected(self, name: str) -> None:
        operations: dict[str, Callable[[set[int]], Any]] = {
            "len": len,
            "in": lambda s: (KEPT - 1) in s,
        }
        op = operations[name]
        sparse, fresh = sparse_set(), set(range(KEPT))
        sparse_ns = best_ns(lambda: op(sparse), inner=10_000)
        fresh_ns = best_ns(lambda: op(fresh), inner=10_000)
        assert sparse_ns < fresh_ns * 5, f"{name}: {fresh_ns:.0f}ns vs {sparse_ns:.0f}ns"

    @pytest.mark.parametrize("name", ["isub", "difference_update", "iand", "intersection_update"])
    def test_bulk_removal_leaves_a_compact_table(self, name: str) -> None:
        full = sys.getsizeof(set(range(PEAK)))
        s = set(range(PEAK))
        if name == "isub":
            s -= set(range(KEPT, PEAK))
        elif name == "difference_update":
            s.difference_update(range(KEPT, PEAK))
        elif name == "iand":
            s &= set(range(KEPT))
        else:
            s.intersection_update(range(KEPT))
        assert s == set(range(KEPT))
        assert sys.getsizeof(s) * 100 < full

    @pytest.mark.parametrize("form", ["method", "operator"])
    def test_intersection_update_compacts_without_removing(self, form: str) -> None:
        s = sparse_set()
        sparse_size = sys.getsizeof(s)
        if form == "method":
            s.intersection_update(set(range(KEPT)))
        else:
            s &= set(range(KEPT))
        assert s == set(range(KEPT))
        assert sys.getsizeof(s) * 100 < sparse_size

    def test_copy_is_compact(self) -> None:
        s = sparse_set()
        copied = s.copy()
        assert copied == s
        assert sys.getsizeof(copied) * 100 < sys.getsizeof(s)

    def test_insertions_eventually_rebuild_the_table(self) -> None:
        s = sparse_set()
        full = sys.getsizeof(s)
        for value in range(PEAK, 3 * PEAK):
            s.add(value)
            s.discard(value)
            if sys.getsizeof(s) != full:
                break
        assert len(s) == KEPT
        assert sys.getsizeof(s) * 100 < full, "an insertion must eventually rebuild the table"


class TestInPlaceIntersectionIsAmortizedMinOfTheTwo:
    """The row: O(min(n, m)) amortized, with one call freeing the old table in
    O(n). A single call grows with n even for a tiny `other`, but stays a
    fixed fraction of the insertions that built `s`, and does not grow with
    an `other` larger than `s`."""

    SMALL = 2_000
    LARGE = 200_000

    @pytest.mark.timing
    @pytest.mark.parametrize("form", ["method", "operator"])
    def test_a_small_other_does_not_make_it_cheap(self, form: str) -> None:
        def run(size: int) -> float:
            elements = list(range(size))
            other = {elements[0], elements[1], elements[2]}

            def apply(s: set[int]) -> None:
                if form == "method":
                    s.intersection_update(other)
                else:
                    s &= other

            return best_fresh_ns(apply, lambda: set(elements))

        small_ns, large_ns = run(self.SMALL), run(self.LARGE)
        assert large_ns > small_ns * 20, f"{form}: {small_ns:.0f}ns vs {large_ns:.0f}ns"

    @pytest.mark.timing
    def test_the_new_set_form_stays_flat(self) -> None:
        def run(size: int) -> float:
            s = set(range(size))
            other = {0, 1, 2}
            return best_ns(lambda: s & other, inner=1_000)

        small_ns, large_ns = run(self.SMALL), run(self.LARGE)
        assert large_ns < small_ns * 5, f"{small_ns:.0f}ns vs {large_ns:.0f}ns"

    @pytest.mark.timing
    @pytest.mark.parametrize("form", ["method", "operator"])
    def test_one_call_is_paid_for_by_building_the_set(self, form: str) -> None:
        def quotient(size: int) -> float:
            elements = list(range(self.SMALL, self.SMALL + size))
            other = {elements[0], elements[size // 2], elements[-1]}

            def apply(s: set[int]) -> None:
                if form == "method":
                    s.intersection_update(other)
                else:
                    s &= other

            def build(s: set[int]) -> None:
                for x in elements:
                    s.add(x)

            call_ns = best_fresh_ns(apply, lambda: set(elements))
            # The set to fill comes from setup, so freeing it falls outside the timing.
            build_ns = best_fresh_ns(build, set)
            return call_ns / build_ns

        quotients = [quotient(size) for size in (2_000, 20_000, 200_000)]
        shown = ", ".join(f"{q:.3f}" for q in quotients)
        assert max(quotients) < 0.5, f"{form}: {shown}"
        assert quotients[-1] < quotients[0] * 3, f"{form}: {shown}"

    @pytest.mark.timing
    def test_a_larger_other_costs_no_more(self) -> None:
        elements = list(range(self.SMALL, self.SMALL + 100))

        def run(size: int) -> float:
            other = set(range(self.SMALL, self.SMALL + size))
            return best_fresh_ns(lambda s: s.intersection_update(other), lambda: set(elements))

        small_ns, large_ns = run(1_000), run(1_000_000)
        assert large_ns < small_ns * 5, f"{small_ns:.0f}ns vs {large_ns:.0f}ns"


class TestDifferenceUpdateIsMinOfTheTwo:
    @pytest.mark.timing
    def test_flat_in_a_larger_other(self) -> None:
        def run(size: int) -> float:
            other = set(range(size))
            return best_fresh_ns(lambda s: s.difference_update(other), lambda: set(range(100)))

        small_ns, large_ns = run(1_000), run(1_000_000)
        assert large_ns < small_ns * 5, f"{small_ns:.0f}ns vs {large_ns:.0f}ns"

    @pytest.mark.timing
    @pytest.mark.parametrize("form", ["method", "operator"])
    def test_flat_in_a_larger_set(self, form: str) -> None:
        absent = {-1, -2, -3}

        def run(size: int) -> float:
            s = set(range(size))
            if form == "method":
                return best_ns(lambda: s.difference_update(absent), inner=1_000)

            def isub() -> None:
                target = s
                target -= absent

            return best_ns(isub, inner=1_000)

        small_ns, large_ns = run(1_000), run(1_000_000)
        assert large_ns < small_ns * 5, f"{form}: {small_ns:.0f}ns vs {large_ns:.0f}ns"


class CountingIterator:
    """An iterator over ints that counts how many were taken."""

    def __init__(self, count: int) -> None:
        self._items = iter(range(1_000_000, 1_000_000 + count))
        self.taken = 0

    def __iter__(self) -> Iterator[int]:
        return self

    def __next__(self) -> int:
        item = next(self._items)
        self.taken += 1
        return item


class TestNonSetOperands:
    @pytest.mark.parametrize(
        ("kind", "name"),
        [
            (set, "intersection"),
            (set, "intersection_update"),
            (set, "difference"),
            (set, "difference_update"),
            (set, "issubset"),
            (set, "isdisjoint"),
            (frozenset, "intersection"),
            (frozenset, "difference"),
        ],
    )
    def test_the_whole_iterable_is_taken(self, kind: type, name: str) -> None:
        s = kind(range(100))
        items = CountingIterator(1_000)
        getattr(s, name)(items)
        assert items.taken == 1_000

    def test_difference_returns_a_new_set(self) -> None:
        s = {1, 2, 3}
        result = s.difference([2])
        assert result == {1, 3} and result is not s and s == {1, 2, 3}

    @pytest.mark.parametrize(
        "operation",
        [
            lambda s: s | [1],
            lambda s: s & [1],
            lambda s: s - [1],
            lambda s: s ^ [1],
        ],
    )
    def test_operators_take_only_sets(self, operation: Callable[[set[int]], Any]) -> None:
        with pytest.raises(TypeError):
            operation({1, 2})

    @pytest.mark.parametrize("symbol", ["|=", "&=", "-=", "^="])
    def test_in_place_operators_take_only_sets(self, symbol: str) -> None:
        with pytest.raises(TypeError):
            exec(f"s {symbol} [1]", {"s": {1, 2}})


class Colliding:
    """An element whose hash collides with every other instance."""

    comparisons = 0

    def __init__(self, value: int) -> None:
        self.value = value

    def __hash__(self) -> int:
        return 7

    def __eq__(self, other: object) -> bool:
        type(self).comparisons += 1
        return isinstance(other, Colliding) and self.value == other.value


def test_collisions_make_a_whole_set_operation_quadratic() -> None:
    def comparisons(k: int) -> int:
        a = {Colliding(i) for i in range(k)}
        b = {Colliding(-1 - i) for i in range(k)}
        Colliding.comparisons = 0
        assert not a & b
        return Colliding.comparisons

    at_40, at_80 = comparisons(40), comparisons(80)
    assert at_40 >= 40 * 40 and at_80 >= 80 * 80
    assert at_80 > at_40 * 3, "doubling k must roughly quadruple the comparisons"


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
        target = "assert sys.getsizeof(s) == full"
        line, source = next((n, s) for n, s in _blocks("set.md") if target in s)
        mutated = source.replace(target, "assert sys.getsizeof(s) < full", 1)

        assert mutated != source, f"the mutation matched nothing in set.md:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0


# ---------------------------------------------------------------------------
# docs/builtins/set_func.md
# ---------------------------------------------------------------------------

FROZENDICT: Any = getattr(builtins, "frozendict", None)


class CountedKey:
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
        return isinstance(other, CountedKey) and self.value == other.value


class SubSet(set[Any]):
    pass


class SubFrozenset(frozenset[Any]):
    pass


class SubDict(dict[Any, Any]):
    pass


class TestSetFuncHashesEachItemOnce:
    """`set(iterable)` hashes each item once; a set, frozenset, subclass of
    either, dict or frozendict has its stored hashes reused, and a dict
    subclass or dict view is an ordinary iterable."""

    def test_an_iterable_is_hashed_once_per_item(self) -> None:
        distinct = [CountedKey(i) for i in range(100)]
        items = distinct * 10
        CountedKey.hashes = 0
        assert len(set(items)) == 100
        assert CountedKey.hashes == len(items)

    @pytest.mark.parametrize(
        "kind", ["set", "frozenset", "set subclass", "frozenset subclass", "dict", "frozendict"]
    )
    def test_stored_hashes_are_reused(self, kind: str) -> None:
        if kind == "frozendict" and FROZENDICT is None:
            pytest.skip("version: frozendict was added in 3.15")
        builders: dict[str, Callable[[list[CountedKey]], Any]] = {
            "set": set,
            "frozenset": frozenset,
            "set subclass": SubSet,
            "frozenset subclass": SubFrozenset,
            "dict": dict.fromkeys,
            "frozendict": lambda keys: FROZENDICT(dict.fromkeys(keys)),
        }
        source = builders[kind]([CountedKey(i) for i in range(1_000)])
        CountedKey.hashes = 0
        assert len(set(source)) == 1_000
        assert CountedKey.hashes == 0

    @pytest.mark.parametrize("kind", ["dict subclass", "keys view"])
    def test_other_iterables_are_hashed_again(self, kind: str) -> None:
        keys = [CountedKey(i) for i in range(1_000)]
        source = SubDict.fromkeys(keys) if kind == "dict subclass" else dict.fromkeys(keys).keys()
        CountedKey.hashes = 0
        assert len(set(source)) == 1_000
        assert CountedKey.hashes == 1_000

    def test_collisions_make_building_quadratic(self) -> None:
        def comparisons(k: int) -> int:
            keys = [CountedKey(i, hash_value=7) for i in range(k)]
            CountedKey.comparisons = 0
            assert len(set(keys)) == k
            return CountedKey.comparisons

        at_40, at_80 = comparisons(40), comparisons(80)
        assert at_40 >= 40 * 39 // 2 and at_80 >= 80 * 79 // 2
        assert at_80 > at_40 * 3, "doubling k must roughly quadruple the comparisons"


class TestSetFuncAlwaysCopies:
    """`set(s)` is a new, shallow copy, even of a set or a frozenset."""

    @pytest.mark.parametrize("kind", [set, frozenset])
    def test_the_result_is_a_new_set_of_the_same_elements(self, kind: type) -> None:
        elements = [(i, i) for i in range(100)]
        source = kind(elements)
        copied = set(source)
        assert copied == source and copied is not source and type(copied) is set
        by_value = {element: element for element in source}
        assert all(element is by_value[element] for element in copied)


class TestSetFuncSpace:
    """Space is O(u) in the distinct elements, and the iterable is consumed
    item by item rather than copied first."""

    def test_duplicates_take_no_space(self) -> None:
        assert sys.getsizeof(set([2_000] * 1_000)) <= sys.getsizeof({2_000})

    def test_the_iterable_is_not_copied(self) -> None:
        item = object()
        tracemalloc.start()
        try:
            result = set(itertools.repeat(item, 1_000_000))
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        assert result == {item}
        assert peak < 64 * 1024, f"traced peak {peak} bytes"


def sparse_dict() -> dict[int, None]:
    """A dict that held PEAK keys and now holds KEPT."""
    d = dict.fromkeys(range(PEAK))
    for i in range(KEPT, PEAK):
        del d[i]
    return d


class TestSetFuncFromASparseSource:
    """A source that had most of its elements removed costs its former size,
    and the set built from it is compact."""

    @pytest.mark.timing
    def test_a_sparse_dict_costs_its_former_size(self) -> None:
        sparse, fresh = sparse_dict(), dict.fromkeys(range(KEPT))
        sparse_ns = best_ns(lambda: set(sparse))
        fresh_ns = best_ns(lambda: set(fresh))
        assert sparse_ns > fresh_ns * 50, f"{fresh_ns:.0f}ns vs {sparse_ns:.0f}ns"

    @pytest.mark.parametrize("kind", ["set", "dict"])
    def test_the_result_is_compact(self, kind: str) -> None:
        source: Any = sparse_set() if kind == "set" else sparse_dict()
        result = set(source)
        assert result == set(range(KEPT))
        assert sys.getsizeof(result) * 100 < sys.getsizeof(source)
