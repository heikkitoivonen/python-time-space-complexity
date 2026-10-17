"""Tests for docs/builtins/len.md.

The page prices `len()` as a read of a stored count on every built-in and
standard-library container except `ChainMap`, and as the cost of `__len__`
everywhere else. The stored counts are settled by timing one size against
another a hundred thousand times larger; `ChainMap`, the lookup of `__len__`
on the class, truth testing and `operator.length_hint()` are settled by
counting calls and items, which needs no tolerance.

Measurement scope:

* `len()` on a `bytearray`, `memoryview`, `frozenset`, `deque`, the three
  `dict` views, `defaultdict`, `OrderedDict`, `Counter` and (3.15+)
  `frozendict` is timed as the fastest of seven runs of 2,000 calls, at 10
  and at 1,000,000 items: the large container must cost under 3x the small
  one, where a count would cost about 100,000x. `list`, `tuple`, `str`,
  `set`, `dict` and `range` are timed the same way in
  tests/test_builtin_complexity.py.
* `ChainMap.__len__` is run over two maps that count the keys their
  `__iter__` yields: one call takes every key of both maps, overlapping keys
  included, and a second call takes them all again. A key in both maps is
  counted once in the result. The m term is timed on chains of empty dicts:
  100,000 maps must cost more than 100x 10 maps.
* `len(obj)` ignores an instance attribute named `__len__` and calls the
  class's method. It accepts a result with `__index__`, and raises
  `ValueError` for a negative result, `TypeError` for a `float`, and
  `OverflowError` for 2**70; `len(range(10**20))` raises
  `OverflowError` while indexing and `in` on that range still answer.
* Truth testing calls `__len__` once per test on a class without `__bool__`,
  and never on a class that defines `__bool__`.
* `len()` on a generator raises `TypeError`. `operator.length_hint()` gives
  the exact remaining count of a list iterator after one `next()` and the
  default for a generator, and neither iterator loses an item to it. It
  prefers `__len__` to `__length_hint__`, and gives the default when
  `__length_hint__` returns `NotImplemented`.
* `len()` on a two-dimensional `memoryview` of 12 bytes shaped 3 by 4 is 3,
  and on `"café"` is 4 against 5 for its UTF-8 bytes.
* Every fenced Python block on the page runs in its own interpreter, and a
  flipped assertion in one of them is asserted to fail.

Not settled here:

* That a range computes its length when it is built, rather than on each
  `len()` call, is read from Objects/rangeobject.c (`make_range_object`
  stores the result of `compute_range_length`) in every supported release;
  timing cannot separate one O(1) arithmetic step from one O(1) read.
* Element type was not varied in the timing tests: each container holds
  ints, or bytes for the byte types.
"""

from __future__ import annotations

import builtins
import collections
import operator
import pathlib
import time
from collections.abc import Callable, Iterator, Mapping, Sized
from typing import Any

import pytest

from tests.page_examples import DOCS, failing_blocks, python_blocks, run_block

PAGE = DOCS / "builtins" / "len.md"
EXPECTED_BLOCKS = 6
FROZENDICT: Any = getattr(builtins, "frozendict", None)


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 2_000) -> float:
    best = float("inf")
    for _ in range(repeats):
        start = time.perf_counter_ns()
        for _ in range(inner):
            func()
        best = min(best, (time.perf_counter_ns() - start) / inner)
    return best


def _containers(size: int) -> dict[str, Sized]:
    keys = range(2_000, 2_000 + size)
    d = dict.fromkeys(keys, 0)
    built: dict[str, Sized] = {
        "bytearray": bytearray(size),
        "memoryview": memoryview(bytes(size)),
        "frozenset": frozenset(keys),
        "deque": collections.deque(keys),
        "keys": d.keys(),
        "values": d.values(),
        "items": d.items(),
        "defaultdict": collections.defaultdict(int, d),
        "OrderedDict": collections.OrderedDict(d),
        "Counter": collections.Counter(d),
    }
    if FROZENDICT is not None:
        built["frozendict"] = FROZENDICT(d)
    return built


class TestStoredLengths:
    """Built-in and standard-library containers return a stored count in O(1)."""

    @pytest.mark.timing
    @pytest.mark.parametrize("kind", list(_containers(1)))
    def test_a_large_container_costs_what_a_small_one_does(self, kind: str) -> None:
        small = _containers(10)[kind]
        large = _containers(1_000_000)[kind]
        assert len(small) == 10 and len(large) == 1_000_000
        small_ns = best_ns(lambda: len(small))
        large_ns = best_ns(lambda: len(large))
        assert large_ns < small_ns * 3, f"{kind}: {small_ns:.0f}ns vs {large_ns:.0f}ns"


class CountingMap(Mapping[str, int]):
    """A mapping that counts the keys its iterator yields."""

    def __init__(self, data: dict[str, int]) -> None:
        self.data = data
        self.yielded = 0

    def __getitem__(self, key: str) -> int:
        return self.data[key]

    def __len__(self) -> int:
        return len(self.data)

    def __iter__(self) -> Iterator[str]:
        for key in self.data:
            self.yielded += 1
            yield key


class TestChainMapCountsEveryKey:
    """`len(cm)` is O(t): every call walks every key of every map."""

    def test_each_call_walks_every_map(self) -> None:
        first = CountingMap({f"a{i}": i for i in range(1_000)})
        second = CountingMap({f"a{i}": i for i in range(500, 1_500)})
        chain = collections.ChainMap[str, int](first, second)  # pyright: ignore[reportArgumentType]

        assert len(chain) == 1_500
        assert (first.yielded, second.yielded) == (1_000, 1_000)
        assert len(chain) == 1_500
        assert (first.yielded, second.yielded) == (2_000, 2_000)

    @pytest.mark.timing
    def test_each_map_costs_even_when_empty(self) -> None:
        few = collections.ChainMap[int, int](*[{} for _ in range(10)])
        many = collections.ChainMap[int, int](*[{} for _ in range(100_000)])
        few_ns = best_ns(lambda: len(few), inner=10)
        many_ns = best_ns(lambda: len(many), inner=10)
        assert many_ns > few_ns * 100, f"{few_ns:.0f}ns vs {many_ns:.0f}ns"


class TestLenCallsTheClassMethod:
    """`len(obj)` calls `type(obj).__len__` and checks what it returns."""

    def test_an_instance_attribute_is_ignored(self) -> None:
        class Sized:
            def __len__(self) -> int:
                return 3

        class Unsized:
            pass

        sized, unsized = Sized(), Unsized()
        sized.__len__ = lambda: 99  # type: ignore[method-assign]
        unsized.__len__ = lambda: 99  # type: ignore[attr-defined]

        assert len(sized) == 3
        with pytest.raises(TypeError, match="has no len"):
            len(unsized)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        ("value", "error"),
        [(-1, ValueError), (1.5, TypeError), (2**70, OverflowError)],
    )
    def test_the_result_must_be_an_index_sized_int(
        self, value: object, error: type[Exception]
    ) -> None:
        class Returns:
            def __len__(self) -> Any:
                return value

        with pytest.raises(error):
            len(Returns())

    def test_an_index_result_is_accepted(self) -> None:
        class Four:
            def __index__(self) -> int:
                return 4

        class Returns:
            def __len__(self) -> Any:
                return Four()

        assert len(Returns()) == 4

    def test_a_range_longer_than_maxsize_has_no_len(self) -> None:
        huge = range(10**20)
        with pytest.raises(OverflowError):
            len(huge)
        assert huge[-1] == 10**20 - 1
        assert 10**19 in huge


class TestTruthTestingUsesLen:
    """`if obj:` calls `__len__` when the class has no `__bool__`."""

    def test_len_is_called_without_bool(self) -> None:
        calls = []

        class Box:
            def __len__(self) -> int:
                calls.append(1)
                return 0

        assert not Box()
        assert not bool(Box())
        assert len(calls) == 2

    def test_bool_is_preferred(self) -> None:
        calls = []

        class Box:
            def __bool__(self) -> bool:
                return True

            def __len__(self) -> int:
                calls.append(1)
                return 0

        assert Box()
        assert calls == []


class TestIteratorsHaveNoLength:
    """Iterators raise `TypeError`; `length_hint()` answers without consuming."""

    def test_a_generator_has_no_len(self) -> None:
        gen = (x for x in range(3))
        with pytest.raises(TypeError, match="has no len"):
            len(gen)  # type: ignore[arg-type]
        assert list(gen) == [0, 1, 2]

    def test_length_hint_does_not_consume(self) -> None:
        it = iter([10, 20, 30])
        next(it)
        assert operator.length_hint(it) == 2
        assert list(it) == [20, 30]

        gen = (x for x in range(3))
        assert operator.length_hint(gen, -1) == -1
        assert list(gen) == [0, 1, 2]

    def test_length_hint_prefers_len_then_falls_back_to_default(self) -> None:
        class Both:
            def __len__(self) -> int:
                return 1

            def __length_hint__(self) -> int:
                return 9

        class Declines:
            def __length_hint__(self) -> Any:
                return NotImplemented

        assert operator.length_hint(Both()) == 1
        assert operator.length_hint(Declines(), 5) == 5


class TestWhatIsCounted:
    """`str` counts characters, `bytes` bytes, a `memoryview` its first dimension."""

    def test_characters_and_bytes(self) -> None:
        assert len("café") == 4
        assert len("café".encode()) == 5

    def test_a_memoryview_counts_its_first_dimension(self) -> None:
        grid = memoryview(bytes(12)).cast("B", shape=[3, 4])
        assert len(grid) == 3
        assert grid.nbytes == 12


class TestDocumentedExamples:
    """Each block runs in its own interpreter and asserts its own results."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(python_blocks(PAGE)) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures = failing_blocks(PAGE, tmp_path)

        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_wrong_assertion(self, tmp_path: pathlib.Path) -> None:
        source = next(s for _, s in python_blocks(PAGE) if "ChainMap(" in s)
        mutated = source.replace("assert len(settings) == 2", "assert len(settings) == 3", 1)

        assert mutated != source
        assert run_block(mutated, tmp_path).returncode != 0
