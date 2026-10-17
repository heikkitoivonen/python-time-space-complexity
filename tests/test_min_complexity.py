"""Tests for docs/builtins/min.md.

min() is min_max in Python/bltinmodule.c, shared with max(). It takes the
items one at a time, from the positional arguments or from one iterator,
calls the key once per item when one is given, and compares each value with
the best so far using `<`, replacing it only when the comparison is true. It
keeps one item and one value. min_max does the same work in the v3.11.14,
v3.12.12, v3.13.11, v3.14.2 and v3.15.0rc3 tags; 3.13 moved it to
vectorcall argument parsing, which changes no bound. The empty-iterable
ValueError message differs between 3.11 and 3.12, so the page asserts only
its type.

Every row is settled by observation: counting `__lt__`, a counting key, a
counting iterator and traced allocation. No row needs a stopwatch.

Measurement scope:

* `min(iterable)` over a shuffled list of n items makes exactly n - 1 `<`
  comparisons, for n of 1, 10 and 1,000; at 1,000, `sorted()` on the same
  items makes more than twice as many. Four positional arguments take three
  comparisons. A three-item counting iterator is stepped four times, the
  last step ending it, and is left exhausted.
* ties: items that compare equal under the key, and items whose `<` is false
  both ways, return the first.
* `key=`: called exactly once per item, in input order, and the item rather
  than its key is returned.
* `default=`: an empty iterable returns it and an empty one without it raises
  ValueError; with items present it is ignored; with two positional
  arguments min() raises TypeError before any comparison.
* incomparable items: the TypeError is raised at the first item that cannot
  be compared, leaving the items after it unread in the iterator.
* space: tracemalloc's peak while min() consumes a generator of 1,000,000
  ints is under 10 KB, while min() over a list comprehension of the same
  values peaks over 1 MB. It runs serially, since xdist's I/O thread
  allocates while tracemalloc is tracing.
* every fenced block runs in its own subprocess and asserts its own results,
  and a mutated assertion in one is asserted to fail.

Not settled here:

* The O(n log n) of `sorted(x)[0]` and the O(n log k) of
  `heapq.nsmallest()` are the sorted and heapq pages' rows; the page's
  example runs, and those pages' tests settle the bounds.
* The O(n²) total of calling min() once per item follows from the O(n) row
  and is not measured.
* The cost of comparing long strings or tuples, of a key function, and of a
  lazy iterable is the caller's; the tests hold each at O(1).
* Not varied: space with a `key`, which is measured only without one, and
  item types other than ints and small wrappers of them.
"""

from __future__ import annotations

import pathlib
import random
import re
import subprocess
import sys
import textwrap
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "min.md"
EXPECTED_BLOCKS = 7


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class Counted:
    """An int wrapper that counts `<` comparisons across all instances."""

    comparisons = 0

    def __init__(self, value: int) -> None:
        self.value = value

    def __lt__(self, other: Counted) -> bool:
        Counted.comparisons += 1
        return self.value < other.value


class CountingIterator:
    """Yields the given items and counts the steps taken from it."""

    def __init__(self, items: list[Any]) -> None:
        self._items = iter(items)
        self.steps = 0

    def __iter__(self) -> CountingIterator:
        return self

    def __next__(self) -> Any:
        self.steps += 1
        return next(self._items)


class TestOnePass:
    """`min(iterable)` and `min(arg1, arg2, *args)` are O(n): n - 1
    comparisons and one step per item, where sorting a shuffled input makes
    O(n log n) comparisons."""

    @pytest.mark.parametrize("size", [1, 10, 1_000])
    def test_n_items_take_n_minus_one_comparisons(self, size: int) -> None:
        values = list(range(size))
        random.Random(size).shuffle(values)
        items = [Counted(v) for v in values]
        Counted.comparisons = 0

        assert min(items).value == 0
        assert Counted.comparisons == size - 1

    def test_sorting_the_same_items_compares_more(self) -> None:
        values = list(range(1_000))
        random.Random(1_000).shuffle(values)
        items = [Counted(v) for v in values]
        Counted.comparisons = 0

        assert sorted(items)[0].value == 0
        assert Counted.comparisons > 2 * 999, f"sorting made {Counted.comparisons} comparisons"

    def test_positional_arguments_take_the_same_pass(self) -> None:
        a, b, c, d = Counted(5), Counted(2), Counted(8), Counted(1)
        Counted.comparisons = 0

        assert min(a, b, c, d) is d
        assert Counted.comparisons == 3

    def test_the_iterable_is_consumed_once(self) -> None:
        source = CountingIterator([7, 3, 5])

        assert min(source) == 3
        assert source.steps == 4, "three items and the step that ends the iterator"
        assert list(source) == []


class TestTies:
    """On a tie the first smallest item is returned: only a strictly smaller
    value replaces the current one."""

    def test_equal_keys_return_the_first(self) -> None:
        assert min(["pear", "fig", "kiwi", "yam"], key=len) == "fig"
        assert min([(1, "b"), (1, "a")], key=lambda p: p[0]) == (1, "b")

    def test_unordered_items_return_the_first(self) -> None:
        first, second = {1}, {2}
        assert min(first, second) is first, "neither set is < the other"
        assert min(second, first) is second


class TestKeyFunction:
    """`min(iterable, key=func)` calls func once per item, compares the keys
    and returns the item."""

    def test_the_key_is_called_once_per_item_in_order(self) -> None:
        calls: list[int] = []

        def key(x: int) -> int:
            calls.append(x)
            return -x

        items = list(range(1_000))
        assert min(items, key=key) == 999
        assert calls == items

    def test_the_item_is_returned_not_its_key(self) -> None:
        assert min(["bb", "a", "ccc"], key=len) == "a"


class TestDefault:
    """`default` replaces the ValueError of an empty iterable and is not
    allowed with multiple positional arguments."""

    def test_an_empty_iterable_returns_the_default(self) -> None:
        sentinel = object()
        assert min([], default=sentinel) is sentinel
        assert min(iter(()), default=None) is None

    def test_an_empty_iterable_without_a_default_raises(self) -> None:
        with pytest.raises(ValueError, match="min"):
            min([])

    def test_the_default_is_ignored_when_there_are_items(self) -> None:
        assert min([4, 2], default=0) == 2

    def test_default_with_positional_arguments_raises_before_comparing(self) -> None:
        Counted.comparisons = 0
        with pytest.raises(TypeError, match="default"):
            min(Counted(1), Counted(2), default=0)  # type: ignore[call-overload]
        assert Counted.comparisons == 0


class TestIncomparableItems:
    """The TypeError comes from the first comparison that fails; the rest of
    the iterable is not read."""

    def test_the_pass_stops_at_the_first_incomparable_item(self) -> None:
        source = iter([1, "a", 3, 4])
        with pytest.raises(TypeError, match="'<' not supported"):
            min(source)
        assert list(source) == [3, 4]


class TestConstantSpace:
    """`min()` holds one item and its key: O(1) space over a generator,
    against O(n) when the argument is a list comprehension."""

    @pytest.mark.serial
    def test_a_generator_is_consumed_in_constant_space(self) -> None:
        def over_generator() -> int:
            return min(x * 3 + 2_000 for x in range(1_000_000))

        def over_list() -> int:
            return min([x * 3 + 2_000 for x in range(1_000_000)])

        over_generator()  # warm the code objects before tracing
        generator_peak = peak_bytes(over_generator)
        list_peak = peak_bytes(over_list)

        assert generator_peak < 10_000, f"min() over a generator peaked at {generator_peak} B"
        assert list_peak > 1_000_000, f"min() over a list peaked at only {list_peak} B"


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
    """Each block runs in its own subprocess and asserts its own results."""

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
        line, source = next((n, s) for n, s in _blocks() if "assert calls == points" in s)
        mutated = source.replace("assert calls == points", "assert calls == points * 2", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
