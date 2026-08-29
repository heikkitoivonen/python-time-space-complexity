"""Tests to verify documented behaviour of Counter, per docs/stdlib/counter.md.

That page has its own complexity table, separate from the Counter section of
docs/stdlib/collections.md, and all ten of its code blocks run - the first
page checked where none were broken. Two table claims did not survive:

* `subtract()` was priced at O(1) space. Subtracting a key the counter does
  not have creates it with a negative count.
* "Not good for: simple counting loops (slightly slower)" is right for one
  usage and backwards for the other. `Counter(iterable)` counts in C through
  `_count_elements` and beats a `defaultdict(int)` loop; incrementing one key
  at a time does not use that path and is slower than the same loop.

tests/test_collections_complexity.py covers most_common() and the arithmetic
operators; this file covers what is specific to the standalone page.
"""

import importlib
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable
from typing import Any


def best_time(func: Callable[[], Any], repeats: int = 5) -> float:
    """Return the fastest of several runs, which is the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return min(times)


SAMPLE = [index % 1_000 for index in range(200_000)]


class TestSubtractAllocates:
    """The table said O(1) space; subtract() can add keys."""

    def test_subtracting_an_absent_key_creates_it(self) -> None:
        counter = Counter(a=1)
        counter.subtract(Counter(b=5))

        assert "b" in counter, "the key did not exist before the subtraction"
        assert counter["b"] == -5

    def test_space_grows_with_the_argument(self) -> None:
        counter = Counter(a=1)
        counter.subtract({f"k{index}": 1 for index in range(500)})

        assert len(counter) == 501, "one entry per key subtracted, not O(1)"

    def test_negative_counts_are_kept(self) -> None:
        """Unlike the arithmetic operators, which drop non-positive counts."""
        counter = Counter(a=1)
        counter.subtract(Counter(a=5))
        assert counter["a"] == -4

        assert (Counter(a=1) - Counter(a=5)) == Counter(), "the operator drops it"

    def test_a_missing_key_reads_as_zero_without_being_created(self) -> None:
        """Contrast: a plain lookup does not allocate."""
        counter = Counter(a=1)
        assert counter["absent"] == 0
        assert "absent" not in counter


class TestCountingSpeedDependsOnHowYouFeedIt:
    """The page's "slightly slower" claim, in both directions.

    Counter.update() dispatches to _count_elements, which has a C
    implementation, but only when handed an iterable. Incrementing a single
    key goes through Counter.__missing__, which is written in Python, where
    defaultdict.__missing__ is not.
    """

    def test_counting_a_whole_iterable_beats_a_python_loop(self) -> None:
        def manual() -> defaultdict[int, int]:
            counts: defaultdict[int, int] = defaultdict(int)
            for value in SAMPLE:
                counts[value] += 1
            return counts

        bulk_time = best_time(lambda: Counter(SAMPLE), repeats=3)
        loop_time = best_time(manual, repeats=3)

        assert bulk_time < loop_time, (
            f"Counter(iterable) counts in C: {bulk_time:.2e}s vs loop {loop_time:.2e}s"
        )

    def test_counting_one_key_at_a_time_loses_to_defaultdict(self) -> None:
        def with_counter() -> Counter:
            counts: Counter = Counter()
            for value in SAMPLE:
                counts[value] += 1
            return counts

        def with_defaultdict() -> defaultdict[int, int]:
            counts: defaultdict[int, int] = defaultdict(int)
            for value in SAMPLE:
                counts[value] += 1
            return counts

        counter_time = best_time(with_counter, repeats=3)
        default_time = best_time(with_defaultdict, repeats=3)

        assert counter_time > default_time, (
            f"per-key increments miss the C path: Counter {counter_time:.2e}s "
            f"defaultdict {default_time:.2e}s"
        )

    def test_update_uses_the_same_fast_path_as_the_constructor(self) -> None:
        construct_time = best_time(lambda: Counter(SAMPLE), repeats=3)

        def via_update() -> Counter:
            counts: Counter = Counter()
            counts.update(SAMPLE)
            return counts

        update_time = best_time(via_update, repeats=3)

        assert update_time < construct_time * 3, (
            f"update(iterable) should be about as fast as Counter(iterable): "
            f"{update_time:.2e}s vs {construct_time:.2e}s"
        )

    def test_the_c_helper_is_what_makes_the_difference(self) -> None:
        """Named in the page's explanation, so worth pinning."""
        # Imported dynamically: _collections is a built-in extension module
        # with no stub, so a plain import fails the type check.
        helpers = importlib.import_module("_collections")

        assert hasattr(helpers, "_count_elements")
        assert "_count_elements" in Counter.update.__code__.co_names


class TestCounterIsADictSubclass:
    """The page listed space-constrained environments under "not good for"."""

    def test_it_costs_about_what_the_dict_would(self) -> None:
        counter = Counter(SAMPLE)
        plain = dict(counter)

        assert abs(sys.getsizeof(counter) - sys.getsizeof(plain)) < 1_000, (
            f"Counter {sys.getsizeof(counter)} vs dict {sys.getsizeof(plain)}"
        )

    def test_lookup_is_constant_time(self) -> None:
        small = Counter(range(1_000))
        large = Counter(range(1_000_000))

        small_time = best_time(lambda: [small[500] for _ in range(10_000)])
        large_time = best_time(lambda: [large[500_000] for _ in range(10_000)])

        assert large_time < small_time * 3, (
            f"lookup is a dict lookup: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_construction_is_linear(self) -> None:
        small = list(range(100_000))
        large = list(range(1_000_000))

        small_time = best_time(lambda: Counter(small), repeats=3)
        large_time = best_time(lambda: Counter(large), repeats=3)

        assert large_time < small_time * 30, (
            f"Counter() should be linear: {small_time:.2e}s vs {large_time:.2e}s"
        )
