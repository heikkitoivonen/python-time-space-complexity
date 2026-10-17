"""Tests for docs/builtins/reversed.md.

reversed() is reversed_new_impl in Objects/enumobject.c. It looks up
`__reversed__` on the type: None raises TypeError, a method is called and its
result returned as it is. Otherwise the argument must pass PySequence_Check,
and PySequence_Size is called once to set the start index to len - 1; each
reversed_next then calls PySequence_GetItem for one index and stops at -1, at
IndexError or at StopIteration. reversed_new_impl and reversed_next do the
same work in the v3.11.14, v3.12.12, v3.13.11, v3.14.2 and v3.15.0rc3 tags;
the differences between them are free-threading atomics and reference
helpers, so no version is treated apart. A dict's reverse iterator,
dictreviter_iternext in Objects/dictobject.c, starts at the last used entry and
skips deleted ones.

Most rows are settled by observation: a counting `__len__` and `__getitem__`,
an identity check on what `__reversed__` returns, and the TypeErrors. The
per-call O(1), the linear full pass and the sparse dict need a stopwatch, and
the no-copy claim a traced peak.

Measurement scope:

* creating a reverse iterator and taking one item: `next(reversed(x))` costs
  under x5 from 1,000 items to 1,000,000 for a list, tuple, str, bytes,
  range, dict, deque and OrderedDict, where a copy predicts x1,000.
* a full pass over a list: 10,000 to 1,000,000 items costs between x20 and
  x400; linear predicts x100 and quadratic x10,000.
* space: tracemalloc's peak while creating `reversed()` over a 1,000,000-item
  list and taking one item is under 1 KB, while `[::-1]` peaks over 7 MB.
* the sequence protocol: `reversed()` calls `__len__` once and `__getitem__`
  never; draining four items tries indexes 3, 2, 1, 0 and no other; a loop
  that breaks after three items fetches three. A class with `__getitem__` and
  no `__len__`, a set, a frozenset, an iterator, a generator and a class with
  `__reversed__ = None` raise TypeError.
* a user `__reversed__` is called once, and `reversed()` returns its result
  by identity, even a plain object() that is not an iterator.
* list, range, dict, the three dict views, OrderedDict and deque define
  `__reversed__`; tuple, str, bytes, bytearray, memoryview and array.array do
  not and get the generic `reversed` iterator.
* the start index is fixed when reversed() is called: an item appended to a
  list afterwards is not yielded, a list cleared after one item yields
  nothing more, and a sequence shrunk below the start index stops at the
  first IndexError. A deque's reverse iterator raises on mutation instead and
  is not covered by that row.
* a dict of 1,000,000 keys with all but the first deleted: one next() on a
  fresh reverse iterator costs more than x20 what it costs on the same dict
  built from 10,000 keys, linear in the former size predicting x100, while a
  forward next() on that dict costs under a tenth of the reverse one. After
  `dict(d)` the reverse next() costs under a tenth of the sparse one.
* every fenced block runs in its own subprocess and asserts its own results,
  and a mutated assertion in one is asserted to fail.

Not settled here:

* The cost of a user `__reversed__`, `__len__` or `__getitem__` is the
  caller's; the page names it once and the tests hold each at O(1).
* OrderedDict and deque reverse iterators are timed for one next() only; a
  full pass over them is not timed.
* Not varied: element types (ints and one-character strings only), deletion
  by anything but `del d[key]`, and dict views beyond their types, which share
  the dict reverse iterators.
"""

from __future__ import annotations

import array
import collections
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

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "reversed.md"
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


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def drain(iterator: Iterator[Any]) -> None:
    for _ in iterator:
        pass


class Counting:
    """A sequence with `__len__` and `__getitem__` that records its calls."""

    def __init__(self, count: int) -> None:
        self.count = count
        self.lengths = 0
        self.attempted: list[int] = []
        self.fetched: list[int] = []

    def __len__(self) -> int:
        self.lengths += 1
        return self.count

    def __getitem__(self, index: int) -> int:
        self.attempted.append(index)
        if not 0 <= index < self.count:
            raise IndexError(index)
        self.fetched.append(index)
        return index


class TestReversedDoesNotCopy:
    """`reversed(seq)` is O(1) time and space, and so is each `next()`:
    neither grows with the sequence."""

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
        if kind == "range":
            return range(size)
        if kind == "dict":
            return dict.fromkeys(range(size))
        if kind == "deque":
            return collections.deque(range(size))
        return collections.OrderedDict.fromkeys(range(size))

    @pytest.mark.timing
    @pytest.mark.parametrize(
        "kind", ["list", "tuple", "str", "bytes", "range", "dict", "deque", "OrderedDict"]
    )
    def test_one_item_does_not_grow_with_the_sequence(self, kind: str) -> None:
        small = self._make(kind, 1_000)
        large = self._make(kind, 1_000_000)

        small_ns = best_ns(lambda: next(reversed(small)), inner=1_000)
        large_ns = best_ns(lambda: next(reversed(large)), inner=1_000)

        ratio = large_ns / small_ns
        assert ratio < 5, (
            f"reversed() plus next() on a {kind} of 1,000,000 cost x{ratio:.2f} its cost at "
            f"1,000 ({small_ns:.0f}ns to {large_ns:.0f}ns); a copy predicts x1,000"
        )

    @pytest.mark.timing
    def test_a_full_pass_is_linear(self) -> None:
        small = list(range(10_000))
        large = list(range(1_000_000))

        small_ns = best_ns(lambda: drain(reversed(small)), inner=3)
        large_ns = best_ns(lambda: drain(reversed(large)), repeats=5)

        ratio = large_ns / small_ns
        assert 20 < ratio < 400, (
            f"100x the items cost x{ratio:.1f} ({small_ns:.0f}ns to {large_ns:.0f}ns); "
            "linear predicts x100 and quadratic x10,000"
        )

    @pytest.mark.serial
    def test_reversed_allocates_almost_nothing_where_slicing_copies(self) -> None:
        items = list(range(1_000_000))

        lazy = peak_bytes(lambda: next(reversed(items)))
        copied = peak_bytes(lambda: items[::-1])

        assert lazy < 1_000, f"reversed() and one next() peaked at {lazy} bytes"
        assert copied > 7_000_000, f"[::-1] peaked at {copied} bytes"


class TestSequenceProtocol:
    """Without `__reversed__`, `reversed()` calls `len()` once and each
    `next()` fetches one index, from len - 1 down to 0."""

    def test_creating_it_calls_len_once_and_fetches_nothing(self) -> None:
        seq = Counting(1_000)
        reversed(seq)

        assert seq.lengths == 1
        assert seq.attempted == []

    def test_draining_fetches_each_index_once_from_the_end(self) -> None:
        seq = Counting(4)

        seen = []
        for value in reversed(seq):  # list() would call __len__ again for a size hint
            seen.append(value)
        assert seen == [3, 2, 1, 0]
        assert seq.attempted == [3, 2, 1, 0], "no index is tried after 0"
        assert seq.lengths == 1

    def test_breaking_early_fetches_only_what_was_read(self) -> None:
        seq = Counting(100_000)
        taken = []
        for value in reversed(seq):
            taken.append(value)
            if len(taken) == 3:
                break

        assert taken == [99_999, 99_998, 99_997]
        assert seq.attempted == [99_999, 99_998, 99_997]

    @pytest.mark.parametrize(
        "make",
        [
            lambda: (1, 2),
            lambda: "ab",
            lambda: b"ab",
            lambda: bytearray(b"ab"),
            lambda: memoryview(b"ab"),
            lambda: array.array("i", [1, 2]),
        ],
        ids=["tuple", "str", "bytes", "bytearray", "memoryview", "array"],
    )
    def test_builtin_sequences_without_reversed_use_the_generic_iterator(
        self, make: Callable[[], Any]
    ) -> None:
        seq = make()
        assert not hasattr(type(seq), "__reversed__")
        assert type(reversed(seq)) is reversed

    @pytest.mark.parametrize(
        "make",
        [
            lambda: [1, 2],
            lambda: range(2),
            lambda: {1: 1},
            lambda: {1: 1}.keys(),
            lambda: {1: 1}.values(),
            lambda: {1: 1}.items(),
            lambda: collections.OrderedDict(a=1),
            lambda: collections.deque([1, 2]),
        ],
        ids=["list", "range", "dict", "keys", "values", "items", "OrderedDict", "deque"],
    )
    def test_types_with_reversed_return_their_own_iterator(self, make: Callable[[], Any]) -> None:
        seq = make()
        assert hasattr(type(seq), "__reversed__")
        assert type(reversed(seq)) is not reversed


class TestCustomReversed:
    """`reversed(obj)` with a user `__reversed__` calls it once and returns
    its result."""

    def test_the_result_is_returned_as_it_is(self) -> None:
        calls = 0
        result = object()

        class Custom:
            def __reversed__(self) -> object:
                nonlocal calls
                calls += 1
                return result

        custom: Any = Custom()
        assert reversed(custom) is result
        assert calls == 1


class TestRejectedInputs:
    """A set, an iterator, a generator, `__reversed__ = None`, and
    `__getitem__` without `__len__` raise TypeError."""

    class NoneReversed:
        __reversed__ = None

        def __len__(self) -> int:
            return 1

        def __getitem__(self, index: int) -> int:
            return index

    class GetitemOnly:
        def __getitem__(self, index: int) -> int:
            return index

    @pytest.mark.parametrize(
        "make",
        [
            lambda: {1, 2},
            lambda: frozenset({1, 2}),
            lambda: iter([1, 2]),
            lambda: (x for x in [1, 2]),
            lambda: TestRejectedInputs.NoneReversed(),
        ],
        ids=["set", "frozenset", "iterator", "generator", "reversed_none"],
    )
    def test_it_is_not_reversible(self, make: Callable[[], Any]) -> None:
        with pytest.raises(TypeError, match="is not reversible"):
            reversed(make())

    def test_getitem_without_len_raises(self) -> None:
        with pytest.raises(TypeError, match="has no len"):
            getitem_only: Any = self.GetitemOnly()
            reversed(getitem_only)


class TestStartIsFixedAtCreation:
    """The iterator starts at the length the sequence had when `reversed()`
    was called."""

    def test_an_appended_item_is_not_yielded(self) -> None:
        items = [1, 2, 3]
        backwards = reversed(items)
        items.append(4)
        assert list(backwards) == [3, 2, 1]

    def test_a_cleared_list_ends_the_iterator(self) -> None:
        items = [1, 2, 3, 4]
        backwards = reversed(items)
        assert next(backwards) == 4
        items.clear()
        assert list(backwards) == []

    def test_a_sequence_that_shrinks_stops_at_index_error(self) -> None:
        seq = Counting(4)
        backwards = reversed(seq)
        seq.count = 2

        assert list(backwards) == []
        assert seq.attempted == [3], "the first index raises IndexError and ends it"


class TestReverseDictIteration:
    """A dict iterates backwards in reverse insertion order; its reverse
    iterator starts at the newest entry, so deleting the newest keys one at a
    time leaves slots the first `next()` scans past, and a rebuild restores
    O(1)."""

    @staticmethod
    def _newest_deleted(size: int) -> dict[int, int]:
        table = {i: i for i in range(size)}
        for i in range(1, size):
            del table[i]
        return table

    def test_it_yields_reverse_insertion_order(self) -> None:
        prices = {"apple": 3, "pear": 5, "plum": 2}
        assert list(reversed(prices)) == ["plum", "pear", "apple"]
        assert list(reversed(prices.values())) == [2, 5, 3]
        assert list(reversed(prices.items())) == [("plum", 2), ("pear", 5), ("apple", 3)]

    @pytest.mark.timing
    def test_one_next_costs_the_deleted_newest_entries(self) -> None:
        small = self._newest_deleted(10_000)
        large = self._newest_deleted(1_000_000)
        assert list(small) == list(large) == [0]

        small_ns = best_ns(lambda: next(reversed(small)), inner=3)
        large_ns = best_ns(lambda: next(reversed(large)), inner=3)

        ratio = large_ns / small_ns
        assert ratio > 20, (
            f"one reverse next() on a one-key dict that held 1,000,000 cost x{ratio:.1f} "
            f"the one that held 10,000 ({small_ns:.0f}ns to {large_ns:.0f}ns); a cost "
            "linear in the deleted entries predicts x100, an O(1) one x1"
        )

    @pytest.mark.timing
    def test_forward_iteration_does_not_pay_for_the_newest_entries(self) -> None:
        sparse = self._newest_deleted(1_000_000)

        reverse_ns = best_ns(lambda: next(reversed(sparse)), inner=3)
        forward_ns = best_ns(lambda: next(iter(sparse)), inner=1_000)

        assert forward_ns * 10 < reverse_ns, (
            f"forward next() cost {forward_ns:.0f}ns against {reverse_ns:.0f}ns reversed"
        )

    @pytest.mark.timing
    def test_rebuilding_makes_reverse_next_cheap_again(self) -> None:
        sparse = self._newest_deleted(1_000_000)
        rebuilt = dict(sparse)
        assert rebuilt == sparse

        sparse_ns = best_ns(lambda: next(reversed(sparse)), inner=3)
        rebuilt_ns = best_ns(lambda: next(reversed(rebuilt)), inner=1_000)

        assert rebuilt_ns * 10 < sparse_ns, (
            f"reverse next() on the rebuilt dict cost {rebuilt_ns:.0f}ns against "
            f"{sparse_ns:.0f}ns on the sparse one"
        )


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
        line, source = next((n, s) for n, s in _blocks() if "assert squares.fetched == [999]" in s)
        mutated = source.replace("fetched == [999]", "fetched == [999, 998]", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
