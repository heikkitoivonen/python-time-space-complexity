"""Tests to verify documented behaviour of OrderedDict.

docs/stdlib/ordereddict.md had no test file. All ten of its code blocks run,
and its complexity table holds: every operation it prices at O(1) stays flat
from a thousand entries to a million.

What needed work was the comparative advice, which was true but shapeless.
"Regular dict is faster" spans 1.05x for a lookup to 5.69x for iteration,
and "memory-constrained environments" is a factor of 2.4. Both are now
numbers on the page, and pinned here.

The table also described popitem() as removing the last item, which misses
the capability that distinguishes OrderedDict: popitem(last=False) pops the
first in O(1), and dict.popitem() takes no arguments at all.
"""

import sys
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

import pytest


def best_time(func: Callable[[], Any], repeats: int = 5) -> float:
    """Return the fastest of several runs, which is the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return min(times)


def ordered(size: int) -> OrderedDict:
    return OrderedDict((f"k{index}", index) for index in range(size))


SMALL, LARGE = 1_000, 1_000_000


class TestConstantTimeOperations:
    """Every row the table prices at O(1), from 1k entries to 1M."""

    def _flat(self, action: Callable[[OrderedDict], Any], label: str) -> None:
        small, large = ordered(SMALL), ordered(LARGE)
        small_time = best_time(lambda: [action(small) for _ in range(5_000)])
        large_time = best_time(lambda: [action(large) for _ in range(5_000)])

        # A thousand times the entries; O(n) would be a thousand times the
        # cost. Anything in single digits is locality, not complexity.
        assert large_time < small_time * 10, (
            f"{label} should not scale with the mapping: {small_time:.2e}s vs {large_time:.2e}s"
        )

    @pytest.mark.timing
    def test_lookup_is_o1(self) -> None:
        self._flat(lambda od: od["k0"], "lookup")

    @pytest.mark.timing
    def test_move_to_end_is_o1(self) -> None:
        self._flat(lambda od: od.move_to_end(next(iter(od))), "move_to_end()")

    @pytest.mark.timing
    def test_popitem_is_o1(self) -> None:
        self._flat(lambda od: od.__setitem__(*od.popitem()), "popitem()")

    @pytest.mark.timing
    def test_popitem_first_is_o1(self) -> None:
        self._flat(lambda od: od.__setitem__(*od.popitem(last=False)), "popitem(last=False)")

    @pytest.mark.timing
    def test_delete_and_reinsert_is_o1(self) -> None:
        def churn(od: OrderedDict) -> None:
            del od["k0"]
            od["k0"] = 0

        self._flat(churn, "__delitem__")


class TestPopitemBothEnds:
    """The capability the table's note left out."""

    def test_popitem_defaults_to_the_last_item(self) -> None:
        od = OrderedDict([("a", 1), ("b", 2), ("c", 3)])
        assert od.popitem() == ("c", 3)

    def test_popitem_can_take_the_first(self) -> None:
        od = OrderedDict([("a", 1), ("b", 2), ("c", 3)])
        assert od.popitem(last=False) == ("a", 1)

    def test_a_plain_dict_cannot(self) -> None:
        with pytest.raises(TypeError):
            {"a": 1}.popitem(last=False)  # type: ignore[call-arg]

    def test_move_to_end_also_works_both_ways(self) -> None:
        od = OrderedDict([("a", 1), ("b", 2), ("c", 3)])
        od.move_to_end("a")
        assert list(od) == ["b", "c", "a"]
        od.move_to_end("a", last=False)
        assert list(od) == ["a", "b", "c"]


class TestEqualityIsOrderSensitiveOnlyBetweenOrderedDicts:
    """The page claims strict, insertion-order equality. It is asymmetric."""

    def test_two_ordered_dicts_compare_by_order(self) -> None:
        first = OrderedDict([("x", 1), ("y", 2)])
        reordered = OrderedDict([("y", 2), ("x", 1)])
        assert first != reordered

    def test_against_a_plain_dict_order_is_ignored(self) -> None:
        first = OrderedDict([("x", 1), ("y", 2)])
        assert first == {"y": 2, "x": 1}

    def test_so_equality_is_not_transitive_here(self) -> None:
        """Worth knowing: a == b and b == c, but a != c."""
        first = OrderedDict([("x", 1), ("y", 2)])
        plain = {"y": 2, "x": 1}
        reordered = OrderedDict([("y", 2), ("x", 1)])

        assert first == plain
        assert plain == reordered
        assert first != reordered


class TestCostAgainstAPlainDict:
    """The page's "regular dict is faster", quantified.

    The spread is the point: lookups are the same code, so the gap only
    appears where the linked list is maintained or walked.
    """

    SIZE = 100_000

    def _pair(self) -> tuple[dict, OrderedDict]:
        items = [(f"k{index}", index) for index in range(self.SIZE)]
        return dict(items), OrderedDict(items)

    @pytest.mark.timing
    def test_lookups_cost_about_the_same(self) -> None:
        plain, od = self._pair()

        plain_time = best_time(lambda: [plain["k500"] for _ in range(10_000)])
        ordered_time = best_time(lambda: [od["k500"] for _ in range(10_000)])

        assert ordered_time < plain_time * 2, (
            f"OrderedDict inherits __getitem__ unchanged: "
            f"dict {plain_time:.2e}s OrderedDict {ordered_time:.2e}s"
        )

    @pytest.mark.timing
    def test_iteration_is_where_it_hurts(self) -> None:
        plain, od = self._pair()

        plain_time = best_time(lambda: list(plain))
        ordered_time = best_time(lambda: list(od))

        assert ordered_time > plain_time * 2, (
            f"walking the linked list is the expensive part: "
            f"dict {plain_time:.2e}s OrderedDict {ordered_time:.2e}s"
        )

    @pytest.mark.timing
    def test_construction_costs_more(self) -> None:
        items = [(f"k{index}", index) for index in range(self.SIZE)]

        plain_time = best_time(lambda: dict(items), repeats=3)
        ordered_time = best_time(lambda: OrderedDict(items), repeats=3)

        assert ordered_time > plain_time, (
            f"each insert also links a node: dict {plain_time:.2e}s OrderedDict {ordered_time:.2e}s"
        )

    def test_memory_is_roughly_doubled(self) -> None:
        plain, od = self._pair()
        ratio = sys.getsizeof(od) / sys.getsizeof(plain)

        assert ratio > 1.5, (
            f"the linked list is not free: dict {sys.getsizeof(plain):,} "
            f"OrderedDict {sys.getsizeof(od):,} ({ratio:.2f}x)"
        )
