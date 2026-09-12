"""Tests for docs/builtins/sorted.md.

sorted() copies its input into a new list and sorts that in place, so every
bound on the page is list.sort()'s plus an O(n) copy. Comparisons are counted
through a `__lt__` that increments a counter, and key calls through a counting
key function, so the growth tests need no timing tolerance.

Measured on the pinned interpreter at n = 100,000 unless stated:

* random input costs about 15.3 comparisons per element, against 12.0 at
  n = 10,000 - the n log n growth the table claims;
* ascending input costs exactly n - 1 comparisons, and so does strictly
  descending input, which is why reverse-sorted input shares the O(n) row;
* descending input with equal neighbours costs 1.5 comparisons per element
  from 3.13, where a descending run may contain equal keys (GH-116554), and
  about 5.1 before, where each equal pair ends the run. The pre-3.13 figure
  moves from 4.85 to 5.29 per element across a hundredfold size increase, so
  the shape stays far below random's 15 on every supported version and the
  page gives it no row of its own;
* the key function is called exactly n times, and the items themselves are
  never compared when a key is given;
* `reverse=True` costs the same comparisons as sorting the reversed input,
  which is how it is implemented, and keeps equal keys in input order;
* `functools.cmp_to_key` calls its Python function exactly once per `<` the
  sort asks for, about 12 n calls at n = 10,000, where a key function is
  called n times;
* peak traced allocation for sorting shuffled ints grows fourfold when n does,
  with or without a key, which is the O(n) space row (quadratic would be
  sixteenfold).

One claim needs a stopwatch: heapq.nsmallest(10) against sorted() on a
million shuffled ints, x18 measured on one aarch64 machine and asserted at x3.
Both sides are O(n) on already-sorted input, so the test shuffles; k and the
input shape are not varied, and the page's recommendation rests on the
O(n log k) against O(n log n) bounds rather than on this one measurement.

One claim cannot be settled by running code: the page dates the switch from
Timsort's merge policy to Powersort at 3.11. The sorted result and the bound
are the same under both, so released source settles it - Objects/listobject.c
names powersort in v3.11.0 and not in v3.10.0.

The case-insensitive example prices `str.lower()` at the word's length; that
is str's own bound and is covered on its page, not here.

Not varied: element type. Every test that counts comparisons sorts a Python
class with a `__lt__`, which takes the general comparison path; the type-specialised
comparisons for homogeneous int, float and str lists change the cost of one
comparison, not how many the algorithm asks for.
"""

import heapq
import math
import pathlib
import random
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from functools import cmp_to_key
from operator import attrgetter, itemgetter
from types import SimpleNamespace
from typing import Any

import pytest

SIZE = 100_000


def best_time(func: Callable[[], Any], repeats: int = 5) -> float:
    """Return the fastest of several runs, which is the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return min(times)


class Counted:
    """An element whose `<` comparisons are counted on the class."""

    comparisons = 0

    __slots__ = ("value",)

    def __init__(self, value: int) -> None:
        self.value = value

    def __lt__(self, other: "Counted") -> bool:
        Counted.comparisons += 1
        return self.value < other.value


def comparisons_to_sort(values: list[int], **kwargs: Any) -> int:
    """How many `<` calls sorted() makes on a list of these values."""
    items = [Counted(value) for value in values]
    Counted.comparisons = 0
    sorted(items, **kwargs)
    return Counted.comparisons


def shuffled(size: int, seed: int = 42) -> list[int]:
    return random.Random(seed).sample(range(size * 10), size)


class TestComparisonCounts:
    """The table's time column, counted rather than timed."""

    def test_random_input_tracks_n_log_n(self) -> None:
        small = comparisons_to_sort(shuffled(SIZE // 10))
        large = comparisons_to_sort(shuffled(SIZE))
        ratio = large / small
        expected = 10 * math.log2(SIZE) / math.log2(SIZE // 10)  # 12.5; linear would be 10

        assert 11.5 < ratio < 14, (
            f"{small:,} vs {large:,} comparisons ({ratio:.2f}x, expected about {expected:.1f}x)"
        )

    def test_ascending_input_costs_n_minus_one_comparisons(self) -> None:
        assert comparisons_to_sort(list(range(SIZE))) == SIZE - 1
        assert comparisons_to_sort([i // 2 for i in range(SIZE)]) == SIZE - 1

    def test_descending_input_costs_n_minus_one_comparisons(self) -> None:
        assert comparisons_to_sort(list(range(SIZE, 0, -1))) == SIZE - 1

    def test_descending_input_with_equal_neighbours_stays_far_below_random(self) -> None:
        """Every supported version keeps this shape near the one-run cost; the
        random n log n shape at the same size costs about 15 per element."""
        pairs = comparisons_to_sort([(SIZE - i) // 2 for i in range(SIZE)])
        cap = 2 * SIZE if sys.version_info >= (3, 13) else 6 * SIZE

        assert pairs <= cap, f"{pairs / SIZE:.2f} comparisons per element"

    def test_empty_and_single_element_inputs_make_no_comparisons(self) -> None:
        assert comparisons_to_sort([]) == 0
        assert comparisons_to_sort([1]) == 0


class TestReverse:
    """The Reverse sorting row: reversed before and after, and still stable."""

    def test_reverse_costs_the_same_comparisons_as_sorting_the_reversed_input(self) -> None:
        values = shuffled(SIZE)

        assert comparisons_to_sort(values, reverse=True) == comparisons_to_sort(values[::-1])

    def test_reverse_keeps_equal_keys_in_input_order(self) -> None:
        data = [(key, index) for index, key in enumerate([2, 1, 2, 1, 2])]

        result = sorted(data, key=itemgetter(0), reverse=True)

        assert result == [(2, 0), (2, 2), (2, 4), (1, 1), (1, 3)]


class TestKeyFunction:
    """The key row and the two sections built on it."""

    def test_key_is_called_once_per_element(self) -> None:
        calls = 0

        def key(value: int) -> int:
            nonlocal calls
            calls += 1
            return value

        sorted(shuffled(SIZE), key=key)

        assert calls == SIZE

    def test_items_are_never_compared_when_a_key_is_given(self) -> None:
        assert comparisons_to_sort(shuffled(SIZE), key=lambda item: item.value) == 0

    def test_hand_built_decoration_compares_items_on_tied_keys(self) -> None:
        items = [Counted(index) for index in range(1_000)]
        Counted.comparisons = 0

        sorted((item.value % 10, item) for item in items)

        assert Counted.comparisons > 0

    def test_hand_built_decoration_raises_where_key_does_not(self) -> None:
        items = [{"name": "b", "rank": 1}, {"name": "a", "rank": 1}]

        assert sorted(items, key=lambda d: d["rank"]) == items
        with pytest.raises(TypeError):
            sorted((d["rank"], d) for d in items)

    def test_stored_keys_are_not_recomputed_by_later_sorts(self) -> None:
        calls = 0

        def expensive_key(value: int) -> int:
            nonlocal calls
            calls += 1
            return -value

        values = shuffled(1_000)
        keyed = [(value, expensive_key(value)) for value in values]
        assert calls == len(values)

        ascending = sorted(keyed, key=itemgetter(1))
        descending = sorted(keyed, key=itemgetter(1), reverse=True)

        assert calls == len(values)
        assert [value for value, _ in ascending] == sorted(values, reverse=True)
        assert descending == ascending[::-1]

    def test_cmp_to_key_calls_python_once_per_comparison(self) -> None:
        size = 10_000
        values = shuffled(size)
        key_calls = 0
        cmp_calls = 0

        def key(value: int) -> int:
            nonlocal key_calls
            key_calls += 1
            return value

        def compare(left: int, right: int) -> int:
            nonlocal cmp_calls
            cmp_calls += 1
            return (left > right) - (left < right)

        assert sorted(values, key=key) == sorted(values, key=cmp_to_key(compare))
        assert key_calls == size
        assert cmp_calls == comparisons_to_sort(values), (
            f"{cmp_calls / size:.1f} compare calls per element"
        )


class TestNewList:
    """The Basic sorting row's note: the input is copied, never sorted in place."""

    def test_sorted_returns_a_new_list_and_leaves_the_input_alone(self) -> None:
        original = [3, 1, 2]

        result = sorted(original)

        assert result is not original
        assert original == [3, 1, 2]
        assert result == [1, 2, 3]

    def test_any_iterable_becomes_a_list(self) -> None:
        assert sorted((3, 1, 2)) == [1, 2, 3]
        assert sorted(value for value in (3, 1, 2)) == [1, 2, 3]


class TestSpace:
    """The O(n) space column: the new list, the merge buffer and the stored
    keys all grow with n, so peak allocation does too - and no faster."""

    @staticmethod
    def peak_bytes(size: int, **kwargs: Any) -> int:
        values = shuffled(size)
        tracemalloc.start()
        try:
            sorted(values, **kwargs)
            return tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()

    @pytest.mark.parametrize("kwargs", [{}, {"key": lambda value: -value}], ids=["plain", "key"])
    def test_peak_allocation_grows_linearly(self, kwargs: dict[str, Any]) -> None:
        small = self.peak_bytes(50_000, **kwargs)
        large = self.peak_bytes(200_000, **kwargs)
        ratio = large / small

        assert 3 < ratio < 6, f"{small:,} vs {large:,} bytes ({ratio:.1f}x for 4x the items)"


class TestNsmallest:
    """docs/builtins/sorted.md: heapq.nsmallest() wins when k << n."""

    @pytest.mark.timing
    def test_nsmallest_beats_sorting_everything(self) -> None:
        numbers = shuffled(1_000_000)

        full_sort = best_time(lambda: sorted(numbers), repeats=3)
        ten_smallest = best_time(lambda: heapq.nsmallest(10, numbers), repeats=3)

        assert full_sort > 3 * ten_smallest, (
            f"sorted {full_sort:.3f}s vs nsmallest(10) {ten_smallest:.3f}s "
            f"({full_sort / ten_smallest:.1f}x)"
        )


class TestDocumentedOutputs:
    """The results the page prints in comments."""

    def test_simple_sorting(self) -> None:
        assert sorted([3, 1, 4, 1, 5, 9, 2, 6]) == [1, 1, 2, 3, 4, 5, 6, 9]
        assert sorted((3, 1, 4)) == [1, 3, 4]
        assert sorted({3, 1, 4}) == [1, 3, 4]
        assert sorted("cadb") == ["a", "b", "c", "d"]

    def test_reverse_sorting(self) -> None:
        assert sorted([3, 1, 4, 1, 5, 9, 2, 6], reverse=True) == [9, 6, 5, 4, 3, 2, 1, 1]
        assert sorted(["apple", "pie", "cat"], reverse=True) == ["pie", "cat", "apple"]

    def test_custom_comparisons(self) -> None:
        words = ["apple", "pie", "cat", "banana"]

        assert sorted(words, key=len) == ["pie", "cat", "apple", "banana"]
        assert sorted(words, key=lambda x: x[-1]) == ["banana", "apple", "pie", "cat"]

    def test_sorting_objects(self) -> None:
        people = [
            SimpleNamespace(name=n, age=a) for n, a in [("Alice", 30), ("Bob", 25), ("Charlie", 35)]
        ]

        by_lambda = sorted(people, key=lambda p: p.age)
        by_attrgetter = sorted(people, key=attrgetter("age"))

        assert [p.name for p in by_lambda] == ["Bob", "Alice", "Charlie"]
        assert by_attrgetter == by_lambda

    def test_tuple_sorting(self) -> None:
        coords = [(1, 5), (3, 2), (2, 8)]

        assert sorted(coords) == [(1, 5), (2, 8), (3, 2)]
        assert sorted(coords, key=lambda c: c[1]) == [(3, 2), (1, 5), (2, 8)]

    def test_stability(self) -> None:
        data = [(1, "a"), (2, "b"), (1, "c"), (2, "d")]

        assert sorted(data, key=lambda x: x[0]) == [(1, "a"), (1, "c"), (2, "b"), (2, "d")]

    def test_multiple_criteria(self) -> None:
        students = [("Alice", 85), ("Bob", 85), ("Charlie", 90)]

        assert sorted(students, key=lambda s: (-s[1], s[0])) == [
            ("Charlie", 90),
            ("Alice", 85),
            ("Bob", 85),
        ]
        # The name breaks the tie, not input order
        bob_first = [("Bob", 85), ("Alice", 85), ("Charlie", 90)]
        assert sorted(bob_first, key=lambda s: (-s[1], s[0])) == [
            ("Charlie", 90),
            ("Alice", 85),
            ("Bob", 85),
        ]

    def test_case_insensitive(self) -> None:
        words = ["Apple", "banana", "Cherry", "date"]

        assert sorted(words, key=str.lower) == ["Apple", "banana", "Cherry", "date"]

    def test_custom_order(self) -> None:
        priority = {"high": 0, "medium": 1, "low": 2}
        tasks = [
            {"name": "A", "priority": "low"},
            {"name": "B", "priority": "high"},
            {"name": "C", "priority": "medium"},
        ]

        result = sorted(tasks, key=lambda t: priority[t["priority"]])

        assert [t["name"] for t in result] == ["B", "C", "A"]


PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "sorted.md"

EXPECTED_BLOCKS = 19


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
    """Every python block runs, under the interpreter running the tests. The
    one unlabelled block is the algorithm outline, which is prose."""

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

    def test_every_block_binds_the_names_it_uses(self, tmp_path: pathlib.Path) -> None:
        """A block that leans on a name from its prose rather than binding it
        compiles and then dies at run time, so NameError gets its own check."""
        failures: list[str] = []

        for line, source in _blocks():
            result = _run(source, tmp_path)
            if "NameError" in result.stderr:
                failures.append(f"{PAGE.name}:{line}: {result.stderr.strip()}")

        assert not failures, "\n".join(failures)

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = _blocks()[0][1]
        broken = original.replace("sorted(numbers)", "sorted(undefined_numbers)", 1)
        assert broken != original, "the mutation did not rewrite the call"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr
