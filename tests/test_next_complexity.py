"""Tests for docs/builtins/next.md.

next() is builtin_next in Python/bltinmodule.c: it checks that the argument
is an iterator, calls its tp_iternext once, and substitutes the default when
that ends with StopIteration. All the cost beyond that O(1) is the iterator's,
so the page prices the built-in iterators one row each. builtin_next does the
same work in the v3.11.14, v3.12.12, v3.13.11, v3.14.2 and v3.15.0rc3 tags,
so no version is treated apart.

Most rows are settled by observation: a counting predicate, function,
callable or generator body. The per-call O(1) of container iterators and the
sparse-table cost of dict and set iterators need a stopwatch.

Measurement scope:

* `next()` on a list, tuple, str, bytes and range iterator: one `iter()` plus
  `next()` costs under x5 from a 1,000-item container to a 1,000,000-item
  one, where a cost linear in the container predicts x1,000. Draining the
  same five kinds' iterators with `deque(it, maxlen=0)`, which calls the
  `__next__` that next() calls, from 10,000 to 1,000,000 items, a hundredfold
  step, costs between x20 and x400; linear predicts x100, and a per-call cost
  growing with the position reached predicts x10,000.
* a dict or a set of 1,000,000 keys with all but the last deleted: one next()
  on a fresh iterator costs more than x20 what it costs on the same container
  built from 10,000 keys with all but the last deleted, linear in the former
  size predicting x100. After `dict(d)` or `set(s)` it costs under a tenth of
  the sparse one.
* a generator: creating it runs no body code, and each next() runs the body
  up to one yield, observed by a counting body with a limit of 1,000,000.
* filter: a counting predicate is called on exactly the items one next()
  examines. map: a counting function is called once per next(), and a map
  over three counting iterators takes one item from each; m is not varied
  further.
* iter(callable, sentinel): each next() makes one call, and a sentinel of 1
  stops at a result of 1.0, so the comparison is `==`.
* `next(it, default)` returns the default once exhausted and leaves the
  iterator exhausted; `next()` on a list or a range raises TypeError naming
  "is not an iterator"; a for loop over an iterator resumes after the items
  next() took.
* every fenced block runs in its own subprocess and asserts its own results,
  and a mutated assertion in one is asserted to fail.

Not settled here:

* The cost of a user `__next__`, a generator body, a predicate, function or
  callable, taking an item from a filter's or a map's input, and the `==`
  comparison with a sentinel is the caller's; the page names it once and the
  tests hold each at O(1).
* next()'s own O(1) is read from builtin_next; it is not separated from the
  iterator's work by measurement.
* Only `del` and `discard` are timed; `d.pop(key)` and `s.remove(x)` reach the
  same single-key deletion in Objects/dictobject.c and Objects/setobject.c.
  `dict.popitem()` keeps the table but shortens the entries iteration scans,
  and `set.difference_update()` can resize the table; the row covers neither.
* Not varied: element types inside containers (ints and one-character
  strings only), the position at which deletions happen (all but the last
  key, deleted with `del` and `discard`), and the number of map inputs beyond
  three.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap
import time
from collections import deque
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "next.md"
EXPECTED_BLOCKS = 8


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


class TestContainerIteratorsAreConstantPerCall:
    """`next(iterator)` is O(1) on list, tuple, str, bytes and range
    iterators: the cost grows neither with the container nor with the
    position reached in it."""

    @staticmethod
    def _make(kind: str, size: int) -> Any:
        if kind == "list":
            return list(range(size))
        if kind == "tuple":
            return tuple(range(size))
        if kind == "str":
            return "x" * size
        if kind == "bytes":
            return b"x" * size
        return range(size)

    @pytest.mark.timing
    @pytest.mark.parametrize("kind", ["list", "tuple", "str", "bytes", "range"])
    def test_one_next_does_not_grow_with_the_container(self, kind: str) -> None:
        small = self._make(kind, 1_000)
        large = self._make(kind, 1_000_000)

        small_ns = best_ns(lambda: next(iter(small)), inner=1_000)
        large_ns = best_ns(lambda: next(iter(large)), inner=1_000)

        ratio = large_ns / small_ns
        assert ratio < 5, (
            f"iter() plus next() on a {kind} of 1,000,000 cost x{ratio:.2f} its cost at "
            f"1,000 ({small_ns:.0f}ns to {large_ns:.0f}ns); a linear cost predicts x1,000"
        )

    @pytest.mark.timing
    @pytest.mark.parametrize("kind", ["list", "tuple", "str", "bytes", "range"])
    def test_a_full_pass_is_linear(self, kind: str) -> None:
        small = self._make(kind, 10_000)
        large = self._make(kind, 1_000_000)

        small_ns = best_ns(lambda: deque(iter(small), maxlen=0), inner=3)
        large_ns = best_ns(lambda: deque(iter(large), maxlen=0), repeats=5)

        ratio = large_ns / small_ns
        assert 20 < ratio < 400, (
            f"draining a {kind} of 1,000,000 cost x{ratio:.1f} draining 10,000 "
            f"({small_ns:.0f}ns to {large_ns:.0f}ns); linear predicts x100, and a per-call "
            "cost growing with the position x10,000"
        )


class TestSparseHashTables:
    """`next()` on a dict or set iterator is O(1) amortized: deleting single
    keys does not shrink the table, so the first next() after deleting most
    of them walks the empty slots, and a rebuild restores O(1)."""

    @staticmethod
    def _sparse(kind: str, size: int) -> Any:
        if kind == "dict":
            table: Any = {i: i for i in range(size)}
            for i in range(size - 1):
                del table[i]
        else:
            table = set(range(size))
            for i in range(size - 1):
                table.discard(i)
        return table

    @pytest.mark.timing
    @pytest.mark.parametrize("kind", ["dict", "set"])
    def test_one_next_costs_the_former_size(self, kind: str) -> None:
        small = self._sparse(kind, 10_000)
        large = self._sparse(kind, 1_000_000)
        assert len(small) == len(large) == 1

        small_ns = best_ns(lambda: next(iter(small)), inner=3)
        large_ns = best_ns(lambda: next(iter(large)), inner=3)

        ratio = large_ns / small_ns
        assert ratio > 20, (
            f"one next() on a one-item {kind} that held 1,000,000 cost x{ratio:.1f} the "
            f"one that held 10,000 ({small_ns:.0f}ns to {large_ns:.0f}ns); a cost linear "
            "in the former size predicts x100, an O(1) one x1"
        )

    @pytest.mark.timing
    @pytest.mark.parametrize("kind", ["dict", "set"])
    def test_rebuilding_makes_next_cheap_again(self, kind: str) -> None:
        sparse = self._sparse(kind, 1_000_000)
        rebuilt = dict(sparse) if kind == "dict" else set(sparse)
        assert rebuilt == sparse

        sparse_ns = best_ns(lambda: next(iter(sparse)), inner=3)
        rebuilt_ns = best_ns(lambda: next(iter(rebuilt)), inner=1_000)

        assert rebuilt_ns * 10 < sparse_ns, (
            f"next() on the rebuilt {kind} cost {rebuilt_ns:.0f}ns against "
            f"{sparse_ns:.0f}ns on the sparse one"
        )


class TestGeneratorsRunToTheNextYield:
    """`next()` on a generator costs the body from where it last stopped to
    the next `yield`: nothing runs at creation, and two calls run two steps of
    a million-step body."""

    def test_each_next_runs_one_step(self) -> None:
        steps: list[int] = []

        def count_up(limit: int) -> Iterator[int]:
            i = 0
            while i < limit:
                steps.append(i)
                yield i
                i += 1

        gen = count_up(1_000_000)
        assert steps == []

        assert next(gen) == 0
        assert steps == [0]
        assert next(gen) == 1
        assert steps == [0, 1]

    def test_the_first_match_stops_the_scan(self) -> None:
        checked: list[int] = []

        def is_even(x: int) -> bool:
            checked.append(x)
            return x % 2 == 0

        assert next((x for x in [1, 3, 4, 5, 6, 8] if is_even(x)), None) == 4
        assert checked == [1, 3, 4]


class TestBuiltinIterators:
    """`filter` is O(k) per next() in the items examined; `map` is O(m) in
    its inputs with one function call; `iter(callable, sentinel)` makes one
    call per next() and compares with `==`."""

    def test_filter_examines_the_skipped_items_and_the_returned_one(self) -> None:
        examined: list[int] = []

        def is_big(x: int) -> bool:
            examined.append(x)
            return x > 10

        big = filter(is_big, [1, 2, 3, 50, 4, 60])
        assert examined == []
        assert next(big) == 50
        assert examined == [1, 2, 3, 50]
        assert next(big) == 60
        assert examined == [1, 2, 3, 50, 4, 60]

    def test_map_calls_the_function_once_per_next(self) -> None:
        calls: list[int] = []

        def double(x: int) -> int:
            calls.append(x)
            return 2 * x

        doubled = map(double, range(1_000))
        assert calls == []
        assert [next(doubled), next(doubled)] == [0, 2]
        assert calls == [0, 1]

    def test_map_takes_one_item_from_each_input(self) -> None:
        taken: list[str] = []

        def source(name: str) -> Iterator[int]:
            for i in range(1_000):
                taken.append(name)
                yield i

        sums = map(lambda a, b, c: a + b + c, source("a"), source("b"), source("c"))
        assert next(sums) == 0
        assert taken == ["a", "b", "c"]

    def test_a_callable_iterator_calls_once_per_next_and_compares_by_equality(self) -> None:
        results = iter([3, 2, 1.0, 0])
        calls = 0

        def produce() -> float:
            nonlocal calls
            calls += 1
            return next(results)

        it = iter(produce, 1)
        assert next(it) == 3
        assert calls == 1
        assert next(it) == 2
        assert calls == 2
        assert next(it, "END") == "END", "1.0 == 1 should end the iterator"
        assert calls == 3


class TestNextContract:
    """The default replaces StopIteration, a non-iterator raises TypeError,
    and a for loop resumes where next() stopped."""

    def test_the_default_replaces_stop_iteration(self) -> None:
        it = iter([1])
        assert next(it, "END") == 1
        assert next(it, "END") == "END"
        assert next(it, None) is None
        with pytest.raises(StopIteration):
            next(it)

    @pytest.mark.parametrize("iterable", [[1, 2, 3], range(3)], ids=["list", "range"])
    def test_next_rejects_an_iterable(self, iterable: Any) -> None:
        with pytest.raises(TypeError, match="is not an iterator"):
            next(iterable)

    def test_a_for_loop_resumes_after_next(self) -> None:
        it = iter(["header", "a", "b"])
        assert next(it) == "header"
        rest = []
        for item in it:
            rest.append(item)
        assert rest == ["a", "b"]


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
        line, source = next((n, s) for n, s in _blocks() if "assert checked == [1, 3, 4]" in s)
        mutated = source.replace("checked == [1, 3, 4]", "checked == [1, 3, 4, 5, 6, 8]", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
