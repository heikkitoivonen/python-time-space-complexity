"""Tests for docs/stdlib/ordereddict.md.

The page prices `collections.OrderedDict` as a `dict` plus a doubly-linked
list: lookups are inherited, the list makes reordering and popping either end
O(1), and every insertion, deletion and iteration maintains or walks it. What
the subclass inherits is settled by identity with the `dict` slot; constant
rows by timing the same operation on mappings of very different size; linear
rows by a tenfold size step; and iteration's lookups by a counting `__hash__`.

Measurement scope:

* `__getitem__`, `get`, `__contains__` and `__len__` are asserted to be the
  `dict` methods themselves, and `__setitem__`, `__delitem__`, `__iter__`
  and `__eq__` to be overridden.
* Every row priced O(1) or O(1) amortized - lookup, inserting a new key,
  deleting and reinserting, `move_to_end()` both ways, `popitem()` from
  both ends, `pop()`, `setdefault()` on a present key, and creating a view -
  is timed over 5,000 calls on mappings of 1,000 and 300,000 string keys;
  the larger must cost under 10x the smaller, against the 300x a linear
  operation would show. `od |= other` with a two-entry `other` is held to
  the same bound, which shows it does not depend on n.
* Every row priced O(n), O(m) or O(n + m) - construction, `fromkeys()`,
  `update()`, `copy()`, `clear()`, iteration, `reversed()`, each view's
  iteration, `==` against an `OrderedDict` and against a `dict`, and `|` -
  is timed at 2,000 and 20,000 string keys. The larger must cost between 3x
  and 40x the smaller: a constant operation predicts 1x, a linear one 10x
  and a quadratic one 100x. `update()` starts from an empty
  `OrderedDict`, so only m grows; for `|`, n and m grow together. `clear()`
  is timed on copies made before the clock starts.
* Iteration calls `__hash__` at least once on every step for `iter()`,
  `reversed()` and each of the three views, counted per `next()` on 1,000 keys with a
  counting `__hash__`; iterating a `dict` with the same keys calls it zero
  times. Iterating 100,000 string keys is asserted to cost over 1.5x a
  `dict`'s, with lookups of one key under 2x.
* Draining from the front: deleting `next(iter(d))` from a `dict` grows
  more than 24x from 5,000 to 40,000 entries, where quadratic predicts 64x
  and linear 8x; `popitem(last=False)` on an `OrderedDict` grows under 24x.
* Starting `iter()` or `reversed()` on 100,000 entries and taking one step
  peaks under 1 KB of traced allocation.
* `sys.getsizeof()` of an `OrderedDict` with 100,000 entries exceeds a
  `dict`'s with the same entries by over 1.5x.
* Behaviour is asserted directly: `popitem()` in both directions and its
  `KeyError` when empty, `dict.popitem(last=False)` raising `TypeError`,
  `move_to_end()` in both directions and its `KeyError`, updating an
  existing key keeping its position, `fromkeys()` sharing one value
  object, `copy()` being shallow, views being live and reversible,
  equality being order-sensitive only between two `OrderedDict` objects,
  `|` placing new keys after `od`'s, and adding, removing or moving a key
  during iteration raising `RuntimeError` while assigning to one does not.
* Every fenced Python block on the page runs in its own subprocess and a
  mutated assertion in one of them is asserted to fail.

Not settled here:

* The amortized bounds on insertion, deletion, `move_to_end()`, `popitem()`
  and `pop()` follow from Objects/odictobject.c: the table that maps a key's
  slot to its node is rebuilt, in O(n), on the first node lookup after the
  underlying `dict` resizes or rebuilds its keys, which insertions pay for.
  The churning constant-time tests insert repeatedly and so include those
  rebuilds in their average; they do not isolate a single one.
* `update()` into a populated `OrderedDict`, with or without overlapping
  keys, is not timed; its O(m) bound is read from source.
* Space for `clear()` and the views is read from source, not measured.
* Keys are strings, ints or a counting wrapper around an int throughout;
  expensive `__hash__` or `__eq__` implementations are not varied.

Coverage: the official API inventory names `OrderedDict`, `move_to_end()`
and `popitem()`. The audit reports the nine `dict` methods the class
overrides - `clear`, `copy`, `fromkeys`, `items`, `keys`, `pop`,
`setdefault`, `update`, `values` - as needing classification; each has a row.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "ordereddict.md"
EXPECTED_BLOCKS = 6


def best_ns(func: Callable[[], Any], repeats: int = 5) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        elapsed = time.perf_counter_ns() - start
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def ordered(size: int) -> OrderedDict[str, int]:
    return OrderedDict((f"k{index}", index) for index in range(size))


class CountingKey:
    """An int key that counts calls to its `__hash__`."""

    hashes = 0

    def __init__(self, value: int) -> None:
        self.value = value

    def __hash__(self) -> int:
        CountingKey.hashes += 1
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, CountingKey) and other.value == self.value


class TestLookupsAreInherited:
    """`od[key]`, `od.get(key)`, `key in od`, `len(od)` | inherited from `dict`."""

    @pytest.mark.parametrize("name", ["__getitem__", "get", "__contains__", "__len__"])
    def test_lookup_is_the_dict_method(self, name: str) -> None:
        assert getattr(OrderedDict, name) is getattr(dict, name)

    @pytest.mark.parametrize("name", ["__setitem__", "__delitem__", "__iter__", "__eq__"])
    def test_list_maintaining_methods_are_overridden(self, name: str) -> None:
        assert getattr(OrderedDict, name) is not getattr(dict, name)


SMALL, LARGE = 1_000, 300_000


def _churn_delete(od: OrderedDict[str, int]) -> None:
    del od["k0"]
    od["k0"] = 0


def _churn_new_key(od: OrderedDict[str, int]) -> None:
    od["new"] = 0
    del od["new"]


def _churn_pop(od: OrderedDict[str, int]) -> None:
    od["k0"] = od.pop("k0")


CONSTANT_ROWS: dict[str, Callable[[OrderedDict[str, int]], Any]] = {
    "lookup": lambda od: od["k0"],
    "new key": _churn_new_key,
    "delete and reinsert": _churn_delete,
    "move_to_end()": lambda od: od.move_to_end(next(iter(od))),
    "move_to_end(last=False)": lambda od: od.move_to_end(next(reversed(od)), last=False),
    "popitem()": lambda od: od.__setitem__(*od.popitem()),
    "popitem(last=False)": lambda od: od.__setitem__(*od.popitem(last=False)),
    "pop()": _churn_pop,
    "setdefault()": lambda od: od.setdefault("k0", 1),
    "keys()": lambda od: od.keys(),
    "values()": lambda od: od.values(),
    "items()": lambda od: od.items(),
    "|= two entries": lambda od: od.__ior__({"k0": 0, "k1": 1}),
}


class TestConstantTimeRows:
    """Every row the table prices O(1) or O(1) amortized, at 1k and 300k entries."""

    @pytest.mark.timing
    @pytest.mark.parametrize("label", list(CONSTANT_ROWS))
    def test_cost_does_not_follow_the_mapping_size(self, label: str) -> None:
        action = CONSTANT_ROWS[label]
        small, large = ordered(SMALL), ordered(LARGE)
        small_ns = best_ns(lambda: [action(small) for _ in range(5_000)])
        large_ns = best_ns(lambda: [action(large) for _ in range(5_000)])

        # 300x the entries; a linear operation would cost 300x as much.
        assert large_ns < small_ns * 10, (
            f"{label} should not scale with the mapping: {small_ns:.0f}ns vs {large_ns:.0f}ns"
        )


def _linear_rows(size: int) -> dict[str, Callable[[], Any]]:
    pairs = [(f"k{index}", index) for index in range(size)]
    other = [(f"o{index}", index) for index in range(size)]
    od = OrderedDict(pairs)
    twin = OrderedDict(pairs)
    plain = dict(pairs)
    keys = [key for key, _ in pairs]
    plain_other = dict(other)

    pool = [od.copy() for _ in range(7)]  # one per timed repeat below

    def clear() -> None:
        pool.pop().clear()

    return {
        "construction": lambda: OrderedDict(pairs),
        "fromkeys()": lambda: OrderedDict.fromkeys(keys),
        "update()": lambda: OrderedDict().update(other),
        "copy()": od.copy,
        "clear()": clear,
        "iteration": lambda: list(od),
        "reversed()": lambda: list(reversed(od)),
        "keys()": lambda: list(od.keys()),
        "values()": lambda: list(od.values()),
        "items()": lambda: list(od.items()),
        "== OrderedDict": lambda: od == twin,
        "== dict": lambda: od == plain,
        "|": lambda: od | plain_other,
    }


class TestLinearRows:
    """Every row the table prices O(n), O(m) or O(n + m), at 2k and 20k entries."""

    @pytest.mark.timing
    @pytest.mark.parametrize("label", list(_linear_rows(1)))
    def test_tenfold_entries_cost_about_tenfold(self, label: str) -> None:
        small_ns = best_ns(_linear_rows(2_000)[label], repeats=7)
        large_ns = best_ns(_linear_rows(20_000)[label], repeats=7)
        ratio = large_ns / small_ns

        # Constant predicts 1x, linear 10x, quadratic 100x.
        assert 3 < ratio < 40, f"{label}: 10x the entries cost {ratio:.1f}x"


class TestIterationLooksEachKeyUp:
    """Iteration "looks each key up again", so `__hash__` runs on every step."""

    SIZE = 1_000

    @pytest.mark.parametrize(
        "walk",
        [
            pytest.param(lambda od: od, id="iter"),
            pytest.param(lambda od: reversed(od), id="reversed"),
            pytest.param(lambda od: od.keys(), id="keys"),
            pytest.param(lambda od: od.values(), id="values"),
            pytest.param(lambda od: od.items(), id="items"),
        ],
    )
    def test_each_step_hashes_its_key(self, walk: Callable[[Any], Any]) -> None:
        od = OrderedDict.fromkeys(CountingKey(index) for index in range(self.SIZE))
        steps = iter(walk(od))
        for _ in range(self.SIZE):
            CountingKey.hashes = 0
            next(steps)
            assert CountingKey.hashes >= 1

    def test_iterating_a_dict_hashes_nothing(self) -> None:
        plain = dict.fromkeys(CountingKey(index) for index in range(self.SIZE))
        CountingKey.hashes = 0

        list(plain)
        list(plain.items())

        assert CountingKey.hashes == 0

    @pytest.mark.timing
    def test_iteration_is_slower_than_a_dict(self) -> None:
        pairs = [(f"k{index}", index) for index in range(100_000)]
        plain, od = dict(pairs), OrderedDict(pairs)

        plain_ns = best_ns(lambda: list(plain))
        ordered_ns = best_ns(lambda: list(od))

        assert ordered_ns > plain_ns * 1.5, f"dict {plain_ns:.0f}ns OrderedDict {ordered_ns:.0f}ns"

    @pytest.mark.timing
    def test_lookups_cost_about_the_same_as_a_dict(self) -> None:
        pairs = [(f"k{index}", index) for index in range(100_000)]
        plain, od = dict(pairs), OrderedDict(pairs)

        plain_ns = best_ns(lambda: [plain["k500"] for _ in range(10_000)])
        ordered_ns = best_ns(lambda: [od["k500"] for _ in range(10_000)])

        assert ordered_ns < plain_ns * 2, f"dict {plain_ns:.0f}ns OrderedDict {ordered_ns:.0f}ns"


class TestDrainingFromTheFront:
    """`dict` front pops drain in O(n²); `popitem(last=False)` in O(n).

    An 8x size step: quadratic predicts 64x, linear 8x. The threshold sits
    between them.
    """

    @staticmethod
    def _drain_dict(size: int) -> float:
        def setup_and_drain() -> None:
            plain = dict.fromkeys(range(size))
            for _ in range(size):
                del plain[next(iter(plain))]

        return best_ns(setup_and_drain, repeats=3)

    @staticmethod
    def _drain_ordered(size: int) -> float:
        def setup_and_drain() -> None:
            od = OrderedDict.fromkeys(range(size))
            for _ in range(size):
                od.popitem(last=False)

        return best_ns(setup_and_drain, repeats=3)

    @pytest.mark.timing
    def test_a_dict_drains_quadratically(self) -> None:
        ratio = self._drain_dict(40_000) / self._drain_dict(5_000)
        assert ratio > 24, f"8x the entries cost {ratio:.1f}x"

    @pytest.mark.timing
    def test_an_ordered_dict_drains_linearly(self) -> None:
        ratio = self._drain_ordered(40_000) / self._drain_ordered(5_000)
        assert ratio < 24, f"8x the entries cost {ratio:.1f}x"


class TestIterationCopiesNothing:
    """Iterating and `reversed(od)` | O(1) space: the list is walked in place."""

    @pytest.mark.parametrize("start", [iter, reversed], ids=["iter", "reversed"])
    def test_one_step_allocates_almost_nothing(self, start: Callable[[Any], Any]) -> None:
        od = ordered(100_000)

        def one_step() -> None:
            next(start(od))

        one_step()
        tracemalloc.start()
        try:
            one_step()
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()

        assert peak < 1_000, f"one step over 100,000 entries peaked at {peak} bytes"


class TestMemory:
    """An `OrderedDict` is larger than a `dict`: "every node costs memory"."""

    def test_an_ordered_dict_is_larger_than_the_same_dict(self) -> None:
        pairs = [(f"k{index}", index) for index in range(100_000)]
        plain, od = dict(pairs), OrderedDict(pairs)
        ratio = sys.getsizeof(od) / sys.getsizeof(plain)

        assert ratio > 1.5, f"dict {sys.getsizeof(plain):,} OrderedDict {sys.getsizeof(od):,}"


class TestReorderingAndPopping:
    """`move_to_end()` and `popitem()` in both directions, and their errors."""

    def test_popitem_takes_either_end(self) -> None:
        od = OrderedDict([("a", 1), ("b", 2), ("c", 3)])
        assert od.popitem() == ("c", 3)
        assert od.popitem(last=False) == ("a", 1)

    def test_popitem_on_an_empty_mapping_raises_key_error(self) -> None:
        with pytest.raises(KeyError):
            OrderedDict().popitem()

    def test_a_plain_dict_cannot_pop_the_first(self) -> None:
        with pytest.raises(TypeError):
            {"a": 1}.popitem(last=False)  # type: ignore[call-arg]

    def test_move_to_end_works_both_ways(self) -> None:
        od = OrderedDict([("a", 1), ("b", 2), ("c", 3)])
        od.move_to_end("a")
        assert list(od) == ["b", "c", "a"]
        od.move_to_end("a", last=False)
        assert list(od) == ["a", "b", "c"]

    def test_move_to_end_raises_for_a_missing_key(self) -> None:
        with pytest.raises(KeyError):
            OrderedDict(a=1).move_to_end("missing")

    def test_pop_and_delete_raise_for_a_missing_key(self) -> None:
        od = OrderedDict(a=1)
        with pytest.raises(KeyError):
            od.pop("missing")
        with pytest.raises(KeyError):
            del od["missing"]
        assert od.pop("missing", None) is None


class TestInsertionOrder:
    """Where new keys go, and that updating a present key does not move it."""

    def test_updating_a_present_key_keeps_its_position(self) -> None:
        od = OrderedDict(a=1, b=2)
        od["a"] = 9
        od.update([("c", 3), ("b", 8)])
        assert list(od.items()) == [("a", 9), ("b", 8), ("c", 3)]

    def test_setdefault_appends_only_a_missing_key(self) -> None:
        od = OrderedDict(a=1, b=2)
        assert od.setdefault("a", 7) == 1
        assert od.setdefault("c", 3) == 3
        assert list(od) == ["a", "b", "c"]

    def test_union_puts_new_keys_after_its_own(self) -> None:
        od = OrderedDict(a=1, b=2)
        merged = od | {"c": 3, "a": 9}
        assert type(merged) is OrderedDict
        assert list(merged.items()) == [("a", 9), ("b", 2), ("c", 3)]
        assert list(od.items()) == [("a", 1), ("b", 2)]

    def test_in_place_union_is_update(self) -> None:
        first, second = OrderedDict(a=1, b=2), OrderedDict(a=1, b=2)
        first |= {"c": 3, "a": 9}
        second.update({"c": 3, "a": 9})
        assert list(first.items()) == list(second.items())

    def test_fromkeys_shares_one_value_object(self) -> None:
        shared: list[int] = []
        od = OrderedDict.fromkeys("xyz", shared)
        assert all(value is shared for value in od.values())

    def test_copy_is_shallow_and_keeps_order(self) -> None:
        od = OrderedDict([("b", [1]), ("a", [2])])
        copied = od.copy()
        assert copied is not od and list(copied) == ["b", "a"]
        assert copied["b"] is od["b"]

    def test_views_are_live_and_reversible(self) -> None:
        od = OrderedDict(a=1)
        keys, items = od.keys(), od.items()
        od["b"] = 2
        assert list(keys) == ["a", "b"]
        assert list(reversed(items)) == [("b", 2), ("a", 1)]
        assert list(reversed(od.values())) == [2, 1]


class TestMutationDuringIteration:
    """Adding, removing or moving a key raises; assigning to one does not."""

    @pytest.mark.parametrize(
        "mutate",
        [
            pytest.param(lambda od: od.__setitem__("new", 0), id="add"),
            pytest.param(lambda od: od.__delitem__("c"), id="remove"),
            pytest.param(lambda od: od.move_to_end("a"), id="move"),
        ],
    )
    def test_structural_changes_raise(self, mutate: Callable[[Any], Any]) -> None:
        od = OrderedDict(a=1, b=2, c=3)
        with pytest.raises(RuntimeError):
            for _ in od:
                mutate(od)

    def test_assigning_to_a_present_key_does_not(self) -> None:
        od = OrderedDict(a=1, b=2, c=3)
        for key in od:
            od[key] *= 10
        assert list(od.values()) == [10, 20, 30]


class TestEqualityIsOrderSensitiveOnlyBetweenOrderedDicts:
    """`od == other` | order-sensitive against an `OrderedDict`, not a `dict`."""

    def test_two_ordered_dicts_compare_by_order(self) -> None:
        assert OrderedDict([("x", 1), ("y", 2)]) != OrderedDict([("y", 2), ("x", 1)])

    def test_against_a_plain_dict_order_is_ignored(self) -> None:
        assert OrderedDict([("x", 1), ("y", 2)]) == {"y": 2, "x": 1}

    def test_so_equality_is_not_transitive(self) -> None:
        first = OrderedDict([("x", 1), ("y", 2)])
        plain = {"y": 2, "x": 1}
        reordered = OrderedDict([("y", 2), ("x", 1)])

        assert first == plain
        assert plain == reordered
        assert first != reordered


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
        target = "assert list(cache.entries) == ['a', 'c']"
        line, source = next((n, s) for n, s in _blocks() if target in s)
        mutated = source.replace(target, "assert list(cache.entries) == ['b', 'c']", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
