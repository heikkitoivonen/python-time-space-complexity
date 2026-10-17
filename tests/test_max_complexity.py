"""Tests for docs/builtins/max.md.

max() is min_max in Python/bltinmodule.c, shared with min(): it takes items
one at a time from the iterable or the positional arguments, calls the key
once per item, compares the new key with the best so far by
PyObject_RichCompareBool(val, maxval, Py_GT), and replaces the best only on
a strictly greater result. It keeps one item and its key. The loop is the
same in the v3.11.14, v3.12.12, v3.13.11, v3.14.2 and v3.15.0rc3 tags,
except that from 3.13 positional arguments are read from the vectorcall
array rather than a tuple; the comparison and key logic is unchanged. The
empty-iterable ValueError message reads "arg is an empty sequence" on 3.11
and "iterable argument is empty" from 3.12, so the tests match only "empty".
The official time-complexity page prices `max(l)`, `max(t)` and `max(r)`
at O(n) for list, tuple and range, which the page agrees with.

Most rows are settled by observation: counting comparisons and key calls,
counting live items, identity among equal items. The range row needs a
stopwatch, and the cost of unpacking a traced allocation.

Measurement scope:

* 1,000 items whose `__gt__` counts calls: exactly 999 comparisons, all of
  them `>`, both from an iterable and as positional arguments; `__lt__`
  raises if called.
* key: a counting key over 1,000 items is called 1,000 times, each item
  once, in order; the items themselves are never compared, and the keys
  take exactly 999 comparisons.
* laziness: a generator of 100,000 items that tracks how many are alive
  never has more than three alive at once while max() consumes it.
* range: max(range(1,000,000)) costs more than x20 max(range(10,000)),
  where O(n) predicts x100 and an endpoint shortcut x1.
* unpacking: max(*items) over a 100,000-item list peaks over 500 KB of
  traced allocation, max(items) under 10 KB, and max(*items) over a tuple
  of the same items under 10 KB, since an exact tuple is passed as it is.
  Run serially, since xdist's
  I/O thread allocates while tracemalloc is tracing.
* ties: among equal maxima the first object is returned, with and without
  a key, asserted by identity.
* edges: an empty iterable raises ValueError mentioning "empty" without
  calling the key; `default` is returned for an empty iterable and ignored
  otherwise; `default` with two positional arguments and a single
  non-iterable argument raise TypeError.
* every fenced block runs in its own subprocess and asserts its own results,
  and a mutated assertion in one is asserted to fail.

Not settled here:

* The cost of a key call or of comparing two long strings or tuples is the
  caller's; the page names it once and the tests hold each at O(1).
* sorted() and heapq.nlargest() are priced on their own pages; the sorting
  section here only runs them.
* Not varied: element types beyond ints, strings and counting objects, and
  input order beyond ascending and one pseudo-random permutation.
"""

from __future__ import annotations

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

# The edge-case tests make calls the builtin's stubs reject.
untyped_max: Any = max

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "max.md"
EXPECTED_BLOCKS = 11


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


class Counted:
    """An item that counts `>` comparisons and refuses `<`."""

    comparisons = 0

    def __init__(self, value: int) -> None:
        self.value = value

    def __gt__(self, other: Counted) -> bool:
        if not isinstance(other, Counted):
            raise AssertionError(f"compared with {other!r}")
        Counted.comparisons += 1
        return self.value > other.value

    def __lt__(self, other: Counted) -> bool:
        raise AssertionError("max() should compare with >")


class TestOnePass:
    """`max(iterable)` and `max(arg1, arg2, *args)` are O(n): n - 1
    comparisons, all with `>`."""

    @pytest.mark.parametrize("form", ["iterable", "arguments"])
    def test_n_items_take_n_minus_one_comparisons(self, form: str) -> None:
        items = [Counted((i * 7919) % 1_009) for i in range(1_000)]
        Counted.comparisons = 0

        best = max(items) if form == "iterable" else max(*items)

        assert best.value == 1_008
        assert Counted.comparisons == 999


class TestKeyCalls:
    """`max(iterable, key=func)` is O(n·k): the key is called once per item and
    the best key is kept, so items are compared only through their keys."""

    def test_the_key_is_called_once_per_item(self) -> None:
        class Item:
            def __init__(self, value: int) -> None:
                self.value = value

            def __gt__(self, other: object) -> bool:
                raise AssertionError("an item was compared")

            def __lt__(self, other: object) -> bool:
                raise AssertionError("an item was compared")

        items = [Item(i) for i in range(1_000)]
        seen: list[Item] = []

        def key(item: Item) -> Counted:
            seen.append(item)
            return Counted(-item.value)

        Counted.comparisons = 0
        assert max(items, key=key) is items[0]
        assert seen == items
        assert Counted.comparisons == 999, "the 1,000 keys take n - 1 comparisons"


class TestLazyConsumption:
    """`max(iterable)` is O(1) space: items are taken one at a time and only
    the largest so far is kept."""

    def test_at_most_a_few_items_are_alive(self) -> None:
        alive = 0
        most_alive = 0

        class Tracked:
            def __init__(self, value: int) -> None:
                nonlocal alive, most_alive
                self.value = value
                alive += 1
                most_alive = max(most_alive, alive)

            def __del__(self) -> None:
                nonlocal alive
                alive -= 1

            def __gt__(self, other: Tracked) -> bool:
                return self.value > other.value

        def produce() -> Iterator[Tracked]:
            for i in range(100_000):
                yield Tracked((i * 7919) % 100_003)

        best = max(produce())
        assert best.value == max((i * 7919) % 100_003 for i in range(100_000))
        assert most_alive <= 3, f"{most_alive} items were alive at once"


class TestRangeIsScanned:
    """`max(range_object)` is O(n): the range is iterated, not read from its
    endpoints."""

    @pytest.mark.timing
    def test_a_hundredfold_range_costs_far_more(self) -> None:
        small = range(10_000)
        large = range(1_000_000)

        small_ns = best_ns(lambda: max(small), inner=10)
        large_ns = best_ns(lambda: max(large), repeats=5)

        ratio = large_ns / small_ns
        assert ratio > 20, (
            f"max() over a range 100x longer cost x{ratio:.1f} "
            f"({small_ns:.0f}ns to {large_ns:.0f}ns); O(n) predicts x100, a shortcut x1"
        )


@pytest.mark.serial
class TestUnpackingCopies:
    """`max(*items)` builds a tuple of all n items before max() starts, where
    `max(items)` iterates the list in place."""

    def test_unpacking_allocates_the_items_and_iterating_does_not(self) -> None:
        items = list(range(2_000, 102_000))
        as_tuple = tuple(items)
        max(items)
        max(*items)
        max(*as_tuple)

        iterated = peak_bytes(lambda: max(items))
        unpacked = peak_bytes(lambda: max(*items))
        unpacked_tuple = peak_bytes(lambda: max(*as_tuple))

        assert iterated < 10_000, f"max(items) peaked at {iterated} bytes"
        assert unpacked > 500_000, f"max(*items) peaked at {unpacked} bytes"
        assert unpacked_tuple < 10_000, f"max(*tuple) peaked at {unpacked_tuple} bytes"


class TestTiesAndEdges:
    """Among equal maxima the first is returned; an empty iterable raises
    ValueError unless `default` is given; `default` needs a single iterable."""

    def test_the_first_of_equal_items_wins(self) -> None:
        first = [1, 2]
        second = [1, 2]
        assert max([[0], first, second]) is first
        pear = "".join(["pe", "ar"])
        plum = "".join(["pl", "um"])
        assert max(["fig", pear, plum], key=len) is pear

    def test_an_empty_iterable_raises_without_calling_the_key(self) -> None:
        calls: list[object] = []
        with pytest.raises(ValueError, match="empty"):
            untyped_max([], key=calls.append)
        assert calls == []

    def test_the_default_is_returned_only_when_empty(self) -> None:
        sentinel = object()
        assert max([], default=sentinel) is sentinel
        assert max(iter(()), default=sentinel) is sentinel
        assert max([4, 7], default=sentinel) == 7

    def test_a_default_with_several_arguments_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="default"):
            untyped_max(1, 2, default=0)

    def test_a_single_value_must_be_iterable(self) -> None:
        with pytest.raises(TypeError, match="not iterable"):
            untyped_max(42)


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
        line, source = next((n, s) for n, s in _blocks() if "assert calls == words" in s)
        mutated = source.replace("calls == words", "calls == words * 2", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
