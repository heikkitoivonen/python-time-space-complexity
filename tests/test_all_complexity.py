"""Tests for docs/builtins/all.md.

all() is builtin_all in Python/bltinmodule.c: one loop that takes the next item
from the iterator, calls PyObject_IsTrue on it once, and returns False at the
first falsy result. It holds one item at a time and keeps no state of its own,
so the page's bounds are a count of items taken and truth tests made. Those are
observed directly, with a counting iterator and a counting `__bool__`, so no
claim here needs a stopwatch.

From 3.14 the compiler inlines `all(<generator expression>)` into the same loop
when the name `all` is the builtin (maybe_optimize_function_call in
Python/codegen.c), so builtin_all is not called on that spelling. Both paths are
exercised: the counting-iterator tests pass an iterator to builtin_all, and the
short-circuit tests use generator expressions.

Measurement scope:

* all-truthy input: n items taken and n truth tests made, for n = 5 and 10,000;
* falsy item at position k: exactly k items taken and k truth tests made, and
  the rest of the iterator is left unconsumed;
* empty input: no item taken and no truth test made;
* space: tracemalloc's peak for all(repeat(True, n)) is under 1 KiB at n = 1,000
  and at n = 1,000,000;
* the page's short-circuit examples: a generator stops at the first falsy
  predicate and a list comprehension runs every predicate first, counted by
  calls; `all(x < 100 for x in range(...))` evaluates the predicate 101 times;
* every stated example value, and every fenced block runs in a subprocess.

Not settled here:

* "same complexity" for all() against the manual loop is a source-level
  equivalence: both make one truth test per item and stop at the first falsy
  one. The test checks they agree in result and in items taken, not their
  constant factors, which the page does not compare.
* The cost of producing an item (an iterator's own steps, including items a
  filter skips, or a predicate call) and of one truth test is the caller's;
  the page names it once as an added cost and the tests hold it at O(1).
"""

from __future__ import annotations

import itertools
import pathlib
import re
import subprocess
import sys
import textwrap
import tracemalloc
from collections.abc import Iterable, Iterator

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "all.md"
EXPECTED_BLOCKS = 13


class Counted:
    """An item whose truth test is counted."""

    tests = 0

    def __init__(self, truthy: bool) -> None:
        self.truthy = truthy

    def __bool__(self) -> bool:
        Counted.tests += 1
        return self.truthy


class CountingIterator:
    """Wraps an iterable and counts the items taken from it."""

    def __init__(self, items: Iterable[object]) -> None:
        self._items = iter(items)
        self.taken = 0

    def __iter__(self) -> Iterator[object]:
        return self

    def __next__(self) -> object:
        item = next(self._items)
        self.taken += 1
        return item


def scan(items: list[object]) -> tuple[bool, int, int, CountingIterator]:
    """Return all(items), the items taken, the truth tests made, and the iterator."""
    Counted.tests = 0
    source = CountingIterator(items)
    result = all(source)
    return result, source.taken, Counted.tests, source


class TestAllItemsTruthy:
    """Row: O(n) time, must check all items."""

    @pytest.mark.parametrize("n", [5, 10_000])
    def test_takes_and_tests_every_item(self, n: int) -> None:
        result, taken, tests, _ = scan([Counted(True) for _ in range(n)])
        assert result is True
        assert taken == n
        assert tests == n


class TestEarlyExit:
    """Row: O(k), k = position of the first falsy item."""

    @pytest.mark.parametrize("k", [1, 3, 5_000])
    def test_stops_at_the_first_falsy_item(self, k: int) -> None:
        items: list[object] = [Counted(True) for _ in range(k - 1)]
        items += [Counted(False)] + [Counted(True) for _ in range(10_000)]

        result, taken, tests, source = scan(items)

        assert result is False
        assert taken == k
        assert tests == k
        assert sum(1 for _ in source) == 10_000, "items past the falsy one were consumed"


class TestEmptyIterable:
    """Row: O(1), returns True immediately."""

    def test_returns_true_without_a_truth_test(self) -> None:
        result, taken, tests, _ = scan([])
        assert result is True
        assert taken == 0
        assert tests == 0

    def test_vacuous_truth(self) -> None:
        assert all([]) is True
        assert all(()) is True
        assert all(set()) is True
        assert all(x for x in []) is True


class TestConstantSpace:
    """Space column: O(1) - all() holds one item at a time, whatever n is."""

    @pytest.mark.serial
    def test_peak_does_not_grow_with_n(self) -> None:
        peaks: dict[int, int] = {}
        for n in (1_000, 1_000_000):
            all(itertools.repeat(True, 10))
            tracemalloc.start()
            try:
                assert all(itertools.repeat(True, n)) is True
                _, peaks[n] = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
        assert max(peaks.values()) < 1024, peaks


class TestShortCircuitExamples:
    """Prose: a generator stops at the first falsy predicate, a list
    comprehension evaluates every one before all() sees any."""

    def test_generator_never_calls_the_later_checks(self) -> None:
        calls = 0

        def expensive_function() -> bool:
            nonlocal calls
            calls += 1
            return True

        checks = [lambda: False, expensive_function, expensive_function]
        assert all(check() for check in checks) is False
        assert calls == 0

    def test_list_comprehension_calls_every_check(self) -> None:
        calls = 0

        def expensive_function() -> bool:
            nonlocal calls
            calls += 1
            return True

        assert all([False] + [expensive_function() for _ in range(1000)]) is False
        assert calls == 1000

    def test_range_predicate_runs_101_times(self) -> None:
        calls = 0

        def below_100(x: int) -> bool:
            nonlocal calls
            calls += 1
            return x < 100

        assert all(below_100(x) for x in range(10**7)) is False
        assert calls == 101

        calls = 0
        assert all([below_100(x) for x in range(10_000)]) is False  # noqa: C419
        assert calls == 10_000

    def test_validation_stops_at_the_first_non_int(self) -> None:
        checked = 0

        def is_int(item: object) -> bool:
            nonlocal checked
            checked += 1
            return isinstance(item, int)

        assert all(is_int(item) for item in [1, 2, "three", 4, 5]) is False
        assert checked == 3
        checked = 0
        assert all(is_int(item) for item in [1, 2, 3, 4, 5]) is True
        assert checked == 5


class TestManualLoop:
    """Prose: the manual loop has the same complexity - one test per item,
    stopping at the first failure."""

    @staticmethod
    def loop(numbers: Iterable[object]) -> bool:
        result = True
        for x in numbers:
            if not x:
                result = False
                break
        return result

    @pytest.mark.parametrize("k", [1, 50, None])
    def test_agrees_in_result_and_items_taken(self, k: int | None) -> None:
        values = [k is None or i != k - 1 for i in range(100)]
        builtin, manual = CountingIterator(values), CountingIterator(values)
        assert all(builtin) is self.loop(manual)
        assert builtin.taken == manual.taken == (100 if k is None else k)


class TestStatedExampleValues:
    """The values the page's comments give, checked rather than trusted."""

    def test_basic_usage(self) -> None:
        assert all([1, 2, 3, 4, 5]) is True
        assert all([1, 2, 0, 4, 5]) is False
        numbers = [1, 2, 3, 4, 5]
        assert all(x > 0 for x in numbers) is True
        assert all(x > 2 for x in numbers) is False

    def test_conditions(self) -> None:
        assert all(x % 2 == 0 for x in [2, 4, 6, 8, 10]) is True
        assert all(x % 2 == 0 for x in [2, 4, 5, 8, 10]) is False

    def test_comparison_with_any(self) -> None:
        assert all([True, True, True]) is True
        assert all([True, False, True]) is False
        assert any([False, False, False]) is False
        assert any([False, True, False]) is True
        assert any([]) is False

    def test_single_item_and_types(self) -> None:
        assert all([True]) is True
        assert all([False]) is False
        assert all([1]) is True
        assert all([0]) is False
        assert all([1, "hello", [1, 2], {"key": "value"}]) is True
        assert all([1, "", [1, 2], {"key": "value"}]) is False

    def test_any_spellings(self) -> None:
        numbers = [1, 2, 3, 4, 5]
        assert all(x > 0 for x in numbers) is True
        assert any(not (x > 0) for x in numbers) is False
        assert (not any(x > 0 for x in numbers)) is False


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
    """Every block runs, under the interpreter running the tests."""

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

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        loop = next(source for _, source in _blocks() if "for x in numbers:" in source)
        broken = loop.replace("numbers = [1, 2, 3, 4, 5]\n", "", 1)
        assert broken != loop, "the mutation did not remove the binding"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr
