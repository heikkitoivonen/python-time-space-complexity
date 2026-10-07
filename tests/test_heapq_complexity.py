"""Tests for docs/stdlib/heapq.md.

The page prices every operation in comparisons between items, so almost
every claim is settled by counting them: heap items are an `int` subclass
whose `__lt__` and `__gt__` increment one counter, which needs no tolerance
and does not flake. The heap functions only use `<`; `__gt__` is what
`max()` calls when `nlargest()` is asked for one item. Space is settled by traced allocation, and laziness by iterators that
record how far they have been advanced. Nothing here times anything.

Measurement scope:

* `heapify()` and `heapify_max()` are held under 2n comparisons on random,
  ascending and descending lists of 1,000, 10,000 and 100,000 items, which
  excludes n log n (about 1.7 million at the largest). `heapify()` returns
  `None`, leaves the same list object in place, and peaks under 1 KB of
  traced allocation on 100,000 items; `heapify_max()` is not measured for
  allocation.
* `heappush()`, `heappop()`, `heapreplace()` and `heappushpop()` with an item
  that enters, and their `_max` twins on 3.14+, are held under
  2 * log2(n + 1) + 2 comparisons on heaps of 2**10 - 1 to 2**18 - 1 items,
  and a 256x heap costs under 3x the comparisons. That push and pop are
  amortized is observed through `sys.getsizeof`: across 100,000 pushes, and
  then 100,000 pops, the list's allocation changes fewer than 100 times.
  `heapreplace()` and `heappushpop()` peak under 1 KB of traced allocation on
  both a 1,000- and a 100,000-item heap.
* `heappushpop()` with an item smaller than or equal to the root, or onto an
  empty heap, makes one comparison or none and leaves the heap equal to what
  it was; `heappushpop_max()` likewise for an item larger than or equal to
  the root or an empty heap. `heapreplace()` is asserted to return the old root when it is
  larger than the new item, and to make fewer comparisons than a pop followed
  by a push. `heappop()`, `heapreplace()` and their `_max` twins raise
  `IndexError` on an empty heap.
* `nlargest()` on 100,000 random items with k = 10 makes under 1.1
  comparisons per item; on ascending input it makes more than 3 per item, and
  raising k from 10 to 1,000 on that input raises comparisons less than 5x
  (100x would be linear in k). `nsmallest()` is the same with descending
  input as the worst case. With k = 1 both make exactly m - 1 comparisons.
  A counting `key` is called exactly once per item.
  Results are asserted equal to `sorted(...)[:k]` on duplicate-heavy input
  with and without a key. The traced peak of `nlargest(10, ...)` over a
  200,000-item generator stays under 20 KB, against more than 500 KB for
  k = 20,000 over the same generator.
* `merge()` is a generator that reads nothing when it is built and, after
  yielding j items, has advanced its r inputs at most j + r times in total,
  and after the first item exactly once each. The first item costs under 2r
  comparisons at r = 256; over 65,536 items the whole merge makes under
  2 * log2(r) + 2 comparisons per item at r = 2, 16 and 256, which excludes a
  scan of all r inputs per item. The traced peak of merging four
  100,000-item generators stays under 10 KB. A counting `key` is called once
  per item on interleaved inputs and not at all on the tail of the last input
  left, ties come out in input order, `reverse=True` merges descending inputs,
  and an unsorted input yields unsorted output without an error.
* Tuple entries with equal priorities compare their payloads: two payloads
  without `<` raise `TypeError`, and a counter in the middle field keeps a
  counting payload's `__lt__` at zero calls and returns equal priorities in
  insertion order.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail. The block using the 3.14
  max-heap functions is skipped below 3.14.

Not settled here:

* Treating one comparison and one `key` call as O(1) is a cost-model
  assumption; items whose `__lt__` or key does real work multiply every bound
  by that cost.
* "random input with a small k costs close to O(m)" for `nlargest` and
  `nsmallest` is measured at k = 10 on uniformly shuffled input only. Larger
  k, and partially sorted orders between the two measured extremes, are not
  varied; nor is the cost of one rejected item isolated from the aggregate.
* `merge()`'s O(r) space is measured at r = 4 only, and the O(k) space of
  `nlargest()` at one input length.
* The amortized push and pop bounds rest on `list`'s over-allocation; the
  O(n) copy a single resize can cost is not timed.
* Heaps of items with expensive or inconsistent comparisons, and heaps
  mutated by a comparison while a sift is running, are outside the page.
"""

from __future__ import annotations

import heapq
import itertools
import math
import pathlib
import random
import re
import subprocess
import sys
import textwrap
import tracemalloc
from collections.abc import Callable, Iterable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "heapq.md"
EXPECTED_BLOCKS = 10

HAS_MAX_HEAP = sys.version_info >= (3, 14)
MAX_HEAP = pytest.mark.skipif(not HAS_MAX_HEAP, reason="the max-heap functions are new in 3.14")

# typeshed for the 3.10 floor has no max-heap functions; every use is behind MAX_HEAP.
heapify_max: Any = getattr(heapq, "heapify_max", None)
heappush_max: Any = getattr(heapq, "heappush_max", None)
heappop_max: Any = getattr(heapq, "heappop_max", None)
heappushpop_max: Any = getattr(heapq, "heappushpop_max", None)
heapreplace_max: Any = getattr(heapq, "heapreplace_max", None)


class Counted(int):
    """A heap item that counts every `<` and `>` made with it on the left."""

    comparisons = 0

    def __lt__(self, other: object) -> bool:
        Counted.comparisons += 1
        return int.__lt__(self, other)  # type: ignore[operator]

    def __gt__(self, other: object) -> bool:
        Counted.comparisons += 1
        return int.__gt__(self, other)  # type: ignore[operator]


def comparisons(func: Callable[[], Any]) -> int:
    """Comparisons between Counted items made while func runs."""
    Counted.comparisons = 0
    func()
    return Counted.comparisons


def counted(values: Iterable[int]) -> list[Counted]:
    return [Counted(value) for value in values]


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def log_bound(n: int) -> float:
    """Two comparisons per level of an n-item heap, plus slack for the ends."""
    return 2 * math.log2(n + 1) + 2


def is_min_heap(items: list[Any]) -> bool:
    return all(items[(i - 1) // 2] <= items[i] for i in range(1, len(items)))


def is_max_heap(items: list[Any]) -> bool:
    return all(items[(i - 1) // 2] >= items[i] for i in range(1, len(items)))


HEAP_SIZES = (2**10 - 1, 2**14 - 1, 2**18 - 1)


class TestHeapifyIsLinear:
    """`heapify(x)` and `heapify_max(x)`: O(n) time, O(1) space, in place.

    Fewer than 2n comparisons at every size and input order separates the
    bottom-up build from n pushes, which would cost n log n.
    """

    SIZES = (1_000, 10_000, 100_000)

    @staticmethod
    def _shapes(size: int) -> dict[str, list[Counted]]:
        shuffled = list(range(size))
        random.Random(size).shuffle(shuffled)
        return {
            "random": counted(shuffled),
            "ascending": counted(range(size)),
            "descending": counted(range(size, 0, -1)),
        }

    @pytest.mark.parametrize("size", SIZES)
    def test_heapify_makes_fewer_than_two_comparisons_per_item(self, size: int) -> None:
        for shape, items in self._shapes(size).items():
            made = comparisons(lambda: heapq.heapify(items))  # noqa: B023
            assert is_min_heap(items)
            assert made < 2 * size, f"heapify on {size} {shape} items made {made} comparisons"

    @MAX_HEAP
    @pytest.mark.parametrize("size", SIZES)
    def test_heapify_max_makes_fewer_than_two_comparisons_per_item(self, size: int) -> None:
        for shape, items in self._shapes(size).items():
            made = comparisons(lambda: heapify_max(items))  # noqa: B023
            assert is_max_heap(items)
            assert made < 2 * size, f"heapify_max on {size} {shape} items made {made} comparisons"

    def test_heapify_works_in_place(self) -> None:
        items = list(range(100_000, 0, -1))
        before = id(items)

        result: list[None] = []
        peak = peak_bytes(lambda: result.append(heapq.heapify(items)))

        assert result == [None] and id(items) == before
        assert peak < 1_024, f"heapify of 100,000 items allocated {peak} bytes"

    def test_a_heap_is_not_a_sorted_list(self) -> None:
        data = [5, 3, 7, 1, 9, 4]

        heapq.heapify(data)

        assert data[0] == 1 and data != sorted(data)


class TestPushAndPopWalkOnePath:
    """The push, pop, replace and push-pop rows: O(log n).

    Each operation is held under two comparisons per level of the heap at
    three sizes spanning 256x; a linear scan would cost thousands.
    """

    @pytest.mark.parametrize("size", HEAP_SIZES)
    def test_min_heap_operations_stay_under_two_comparisons_per_level(self, size: int) -> None:
        heap = counted(range(size))  # ascending is already a min-heap
        bound = log_bound(size)
        operations: dict[str, Callable[[], Any]] = {
            "heappush": lambda: heapq.heappush(heap, Counted(-1)),
            "heappop": lambda: heapq.heappop(heap),
            "heapreplace": lambda: heapq.heapreplace(heap, Counted(size * 2)),
            "heappushpop": lambda: heapq.heappushpop(heap, Counted(size * 2)),
        }
        for name, operation in operations.items():
            made = comparisons(operation)
            assert 0 < made < bound, f"{name} on {size} items made {made}, bound {bound:.0f}"
        assert is_min_heap(heap)

    @MAX_HEAP
    @pytest.mark.parametrize("size", HEAP_SIZES)
    def test_max_heap_operations_stay_under_two_comparisons_per_level(self, size: int) -> None:
        heap = counted(range(size, 0, -1))  # descending is already a max-heap
        bound = log_bound(size)
        operations: dict[str, Callable[[], Any]] = {
            "heappush_max": lambda: heappush_max(heap, Counted(size * 2)),
            "heappop_max": lambda: heappop_max(heap),
            "heapreplace_max": lambda: heapreplace_max(heap, Counted(-1)),
            "heappushpop_max": lambda: heappushpop_max(heap, Counted(-1)),
        }
        for name, operation in operations.items():
            made = comparisons(operation)
            assert 0 < made < bound, f"{name} on {size} items made {made}, bound {bound:.0f}"
        assert is_max_heap(heap)

    def test_a_256x_heap_costs_under_three_times_the_comparisons(self) -> None:
        def pop_cost(size: int) -> int:
            heap = counted(range(size))
            return comparisons(lambda: heapq.heappop(heap))

        small, large = pop_cost(HEAP_SIZES[0]), pop_cost(HEAP_SIZES[-1])

        assert large < 3 * small, f"pop cost {small} then {large} for 256x the heap"

    def test_push_and_pop_resize_the_list_rarely(self) -> None:
        """The amortized part: most pushes and pops reuse the allocation."""
        heap: list[int] = []
        resizes = 0
        size = sys.getsizeof(heap)
        for value in range(100_000):
            heapq.heappush(heap, value)
            if sys.getsizeof(heap) != size:
                resizes, size = resizes + 1, sys.getsizeof(heap)
        pushes_resized = resizes

        resizes = 0
        while heap:
            heapq.heappop(heap)
            if sys.getsizeof(heap) != size:
                resizes, size = resizes + 1, sys.getsizeof(heap)

        assert 0 < pushes_resized < 100, f"100,000 pushes resized {pushes_resized} times"
        assert 0 < resizes < 100, f"100,000 pops resized {resizes} times"

    @pytest.mark.parametrize("size", [1_000, 100_000])
    def test_replace_and_pushpop_allocate_nothing(self, size: int) -> None:
        heap = list(range(size))
        high, higher = size * 2, size * 2 + 1

        peak = peak_bytes(lambda: (heapq.heapreplace(heap, high), heapq.heappushpop(heap, higher)))

        assert peak < 1_024, f"replace and push-pop on {size} items allocated {peak} bytes"
        assert len(heap) == size and is_min_heap(heap)

    def test_the_root_is_the_minimum(self) -> None:
        data = list(range(500))
        random.Random(3).shuffle(data)

        heapq.heapify(data)

        assert data[0] == min(data)

    def test_empty_heaps_raise_index_error(self) -> None:
        with pytest.raises(IndexError, match="index out of range"):
            heapq.heappop([])
        with pytest.raises(IndexError, match="index out of range"):
            heapq.heapreplace([], 1)

    @MAX_HEAP
    def test_empty_max_heaps_raise_index_error(self) -> None:
        with pytest.raises(IndexError, match="index out of range"):
            heappop_max([])
        with pytest.raises(IndexError, match="index out of range"):
            heapreplace_max([], 1)


class TestCombinedPushAndPop:
    """`heappushpop` returns an item that cannot enter after one comparison;
    `heapreplace` pops first and so can return something larger than its item."""

    SIZE = 2**14 - 1

    @pytest.mark.parametrize("offset", [-1, 0])
    def test_heappushpop_returns_an_item_not_larger_than_the_root(self, offset: int) -> None:
        heap = counted(range(self.SIZE))
        before = list(heap)
        item = Counted(heap[0] + offset)

        returned: list[Counted] = []
        made = comparisons(lambda: returned.append(heapq.heappushpop(heap, item)))

        assert returned == [item] and returned[0] is item
        assert made == 1, f"an item that cannot enter cost {made} comparisons"
        assert heap == before

    def test_heappushpop_on_an_empty_heap_returns_the_item(self) -> None:
        heap: list[Counted] = []
        item = Counted(7)

        made = comparisons(lambda: heapq.heappushpop(heap, item))

        assert made == 0 and heap == []
        assert heapq.heappushpop([], 7) == 7

    @MAX_HEAP
    def test_heappushpop_max_on_an_empty_heap_returns_the_item(self) -> None:
        heap: list[int] = []

        assert heappushpop_max(heap, 7) == 7 and heap == []

    def test_heapreplace_returns_the_old_root_even_when_larger(self) -> None:
        heap = [2, 4, 6]

        assert heapq.heapreplace(heap, 1) == 2
        assert sorted(heap) == [1, 4, 6] and len(heap) == 3

    def test_heapreplace_costs_less_than_a_pop_then_a_push(self) -> None:
        combined = counted(range(self.SIZE))
        separate = counted(range(self.SIZE))
        item = self.SIZE // 2

        one = comparisons(lambda: heapq.heapreplace(combined, Counted(item)))
        two = comparisons(
            lambda: (heapq.heappop(separate), heapq.heappush(separate, Counted(item)))
        )

        assert one < two, f"heapreplace made {one} comparisons, pop and push {two}"
        assert sorted(combined) == sorted(separate)

    @MAX_HEAP
    @pytest.mark.parametrize("offset", [1, 0])
    def test_heappushpop_max_returns_an_item_not_smaller_than_the_root(self, offset: int) -> None:
        heap = counted(range(self.SIZE, 0, -1))
        before = list(heap)
        item = Counted(heap[0] + offset)

        returned: list[Counted] = []
        made = comparisons(lambda: returned.append(heappushpop_max(heap, item)))

        assert returned[0] is item
        assert made == 1, f"an item that cannot enter cost {made} comparisons"
        assert heap == before


class TestSelectionComparesEachRejectedItemOnce:
    """`nlargest` and `nsmallest`: O(m log k) time, O(k) space.

    Random input stays near one comparison per item; input already in the
    adverse order reaches the log k term on every item, and raising k 100x
    raises that cost by about log k, not k.
    """

    M = 100_000

    @staticmethod
    def _cost(select: Callable[..., Any], k: int, values: Iterable[int]) -> float:
        items = counted(values)
        return comparisons(lambda: select(k, iter(items))) / len(items)

    def _random(self) -> list[int]:
        values = list(range(self.M))
        random.Random(2).shuffle(values)
        return values

    @pytest.mark.parametrize(
        ("select", "adverse"),
        [(heapq.nlargest, range(M)), (heapq.nsmallest, range(M, 0, -1))],
        ids=["nlargest", "nsmallest"],
    )
    def test_random_input_costs_about_one_comparison_per_item(
        self, select: Callable[..., Any], adverse: range
    ) -> None:
        typical = self._cost(select, 10, self._random())
        worst = self._cost(select, 10, adverse)

        assert typical < 1.1, f"random input cost {typical:.2f} comparisons per item"
        assert worst > 3, f"adverse input cost {worst:.2f} comparisons per item"

    @pytest.mark.parametrize(
        ("select", "adverse"),
        [(heapq.nlargest, range(M)), (heapq.nsmallest, range(M, 0, -1))],
        ids=["nlargest", "nsmallest"],
    )
    def test_the_worst_case_grows_with_log_k(
        self, select: Callable[..., Any], adverse: range
    ) -> None:
        few = self._cost(select, 10, adverse)
        many = self._cost(select, 1_000, adverse)

        assert few < many < 5 * few, f"k=10 cost {few:.2f} per item, k=1,000 {many:.2f}"

    @pytest.mark.parametrize("select", [heapq.nlargest, heapq.nsmallest])
    def test_one_item_is_a_single_pass(self, select: Callable[..., Any]) -> None:
        items = counted(self._random())

        made = comparisons(lambda: select(1, iter(items)))

        assert made == self.M - 1

    @pytest.mark.parametrize("select", [heapq.nlargest, heapq.nsmallest])
    def test_key_is_called_once_per_item(self, select: Callable[..., Any]) -> None:
        calls = 0

        def key(value: int) -> int:
            nonlocal calls
            calls += 1
            return -value

        select(10, self._random(), key=key)

        assert calls == self.M

    def test_results_match_sorting(self) -> None:
        rng = random.Random(9)
        data = [rng.randrange(50) for _ in range(2_000)]
        words = [str(value) * (value % 4) for value in data]

        for k in (2, 10, 500, 5_000):
            assert heapq.nlargest(k, data) == sorted(data, reverse=True)[:k]
            assert heapq.nsmallest(k, data) == sorted(data)[:k]
            assert heapq.nlargest(k, words, key=len) == sorted(words, key=len, reverse=True)[:k]
            assert heapq.nsmallest(k, words, key=len) == sorted(words, key=len)[:k]

    def test_memory_follows_k_not_the_input(self) -> None:
        few = peak_bytes(lambda: heapq.nlargest(10, (x for x in range(200_000))))
        many = peak_bytes(lambda: heapq.nlargest(20_000, (x for x in range(200_000))))

        assert few < 20_000, f"k=10 over 200,000 items peaked at {few} bytes"
        assert many > 500_000, f"k=20,000 peaked at only {many} bytes"


class Recording:
    """An iterator that counts how many items have been taken from it."""

    def __init__(self, values: Iterable[Any]) -> None:
        self._it = iter(values)
        self.taken = 0

    def __iter__(self) -> Iterator[Any]:
        return self

    def __next__(self) -> Any:
        value = next(self._it)
        self.taken += 1
        return value


class TestMergeIsLazy:
    """`merge(*iterables)`: O(m log r) time, O(r) space, a lazy generator."""

    def test_nothing_is_read_ahead(self) -> None:
        inputs = [Recording(range(i, 1_000, 10)) for i in range(10)]
        merged = heapq.merge(*inputs)
        assert sum(source.taken for source in inputs) == 0

        assert next(merged) == 0
        assert [source.taken for source in inputs] == [1] * 10

        for yielded in range(2, 500):
            next(merged)
            taken = sum(source.taken for source in inputs)
            assert taken <= yielded + len(inputs), f"{taken} taken after {yielded} items"

    @pytest.mark.parametrize("r", [2, 16, 256])
    def test_each_item_costs_log_r_comparisons(self, r: int) -> None:
        total = 2**16
        rng = random.Random(r)
        inputs = [sorted(counted(rng.sample(range(10**6), total // r))) for _ in range(r)]

        made = comparisons(lambda: list(heapq.merge(*inputs)))

        bound = 2 * math.log2(r) + 2
        assert made / total < bound, f"r={r}: {made / total:.2f} per item, bound {bound:.0f}"

    def test_memory_follows_the_number_of_inputs(self) -> None:
        def drain() -> None:
            for _ in heapq.merge(*((x for x in range(i, 400_000, 4)) for i in range(4))):
                pass

        peak = peak_bytes(drain)

        assert peak < 10_000, f"merging four 100,000-item generators peaked at {peak} bytes"

    @pytest.mark.parametrize("r", [16, 256])
    def test_the_first_item_heapifies_one_item_per_input(self, r: int) -> None:
        inputs = [counted(range(i, i + 3 * r, r)) for i in range(r - 1, -1, -1)]
        merged = heapq.merge(*inputs)

        made = comparisons(lambda: next(merged))

        assert made < 2 * r, f"the first of r={r} inputs cost {made} comparisons"

    def test_key_is_called_at_most_once_per_item(self) -> None:
        calls = 0

        def key(word: str) -> int:
            nonlocal calls
            calls += 1
            return len(word)

        inputs = [["a" * n for n in range(i, 300, 3)] for i in range(3)]
        merged = list(heapq.merge(*inputs, key=key))
        assert calls == 300 and merged == sorted(merged, key=len)

        calls = 0
        assert list(heapq.merge(["a"], ["bb", "ccc", "dddd"], key=key)) == [
            "a",
            "bb",
            "ccc",
            "dddd",
        ]
        assert calls == 2, "the last input's tail is yielded without its key"

    def test_ties_come_out_in_input_order(self) -> None:
        merged = heapq.merge(["fig", "pear"], ["kiwi", "banana"], key=len)

        assert list(merged) == ["fig", "pear", "kiwi", "banana"]

    def test_reverse_merges_descending_inputs(self) -> None:
        assert list(heapq.merge([9, 5, 1], [8, 2], reverse=True)) == [9, 8, 5, 2, 1]

    def test_unsorted_input_is_not_detected(self) -> None:
        assert list(heapq.merge([3, 1], [2])) == [2, 3, 1]


class Payload:
    """A tuple payload that counts the `<` comparisons made on it."""

    comparisons = 0

    def __init__(self, name: str) -> None:
        self.name = name

    def __lt__(self, other: Payload) -> bool:
        Payload.comparisons += 1
        return self.name < other.name


class TestTiesReachThePayload:
    """Equal priorities compare the next tuple field; a counter stops them there."""

    def test_uncomparable_payloads_raise_on_a_tie(self) -> None:
        heap: list[tuple[int, object]] = []
        heapq.heappush(heap, (1, object()))

        with pytest.raises(TypeError, match="'<' not supported"):
            heapq.heappush(heap, (1, object()))

    def test_a_counter_keeps_payloads_out_of_the_comparison(self) -> None:
        Payload.comparisons = 0
        counter = itertools.count()
        heap: list[tuple[int, int, Payload]] = []
        for name in "edcba":
            heapq.heappush(heap, (1, next(counter), Payload(name)))

        drained = [heapq.heappop(heap)[2].name for _ in range(5)]

        assert drained == list("edcba"), "equal priorities should leave in insertion order"
        assert Payload.comparisons == 0

    def test_without_a_counter_ties_compare_payloads(self) -> None:
        Payload.comparisons = 0
        heap = [(1, Payload("b")), (1, Payload("a")), (2, Payload("c"))]

        heapq.heapify(heap)

        assert Payload.comparisons > 0


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


def _needs_max_heap(source: str) -> bool:
    return "_max(" in source


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
    """Each block runs in its own subprocess and asserts its own result; the
    one block that uses the max-heap functions needs Python 3.14."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS
        assert sum(_needs_max_heap(source) for _, source in blocks) == 1

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            if _needs_max_heap(source) and not HAS_MAX_HEAP:
                continue
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == (EXPECTED_BLOCKS if HAS_MAX_HEAP else EXPECTED_BLOCKS - 1)
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "drained == [1, 2, 3, 4, 5]" in s)
        mutated = source.replace("drained == [1, 2, 3, 4, 5]", "drained == [5, 4, 3, 2, 1]", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
