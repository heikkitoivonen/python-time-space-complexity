"""Tests for docs/builtins/bool_func.md.

bool(x) is bool_vectorcall in Objects/boolobject.c, which calls
PyObject_IsTrue (Objects/object.c) once and returns one of the two singletons.
PyObject_IsTrue answers True, False and None directly, then calls the type's
nb_bool slot, then mp_length, then sq_length, and returns 1 when the type has
none of them. A class written in Python gets slot_nb_bool (Objects/typeobject.c),
which calls `__bool__` if the class defines it and `__len__` otherwise. So the
page's rows are a count of method calls, settled by counting `__bool__` and
`__len__` calls, plus two timing tests for the built-in rows, whose O(1) is
about value size and has no call to count.

Measurement scope:

* numbers: bool() on 10**100_000 against 10**20 (both multi-digit ints),
  fastest of 7 runs of 2,000 calls each, the ratio asserted under 3 where a
  scan of the digits would cost over 1,000x; float and complex zero checks are
  asserted by value only, as their size is fixed;
* built-in containers: bool() on str, bytes, bytearray, list, tuple, dict,
  set, frozenset, range, a dict keys view and memoryview of 10 items against
  1,000,000; the ratio is asserted under 3 where counting items would cost
  about 100,000x. range(10**100) is asserted truthy, a length len() cannot
  return;
* a class defining `__bool__` (and an expensive `__len__`): bool() makes one
  `__bool__` call and no `__len__` call;
* a class defining only `__len__`: bool(), `if obj:`, `if bool(obj):` and
  `len(obj) > 0` each make one `__len__` call;
* a class defining neither: bool() is True, with a `__getattr__` asserted
  never consulted;
* the result is the `True` or `False` singleton, by identity;
* the `Expensive` example: `__bool__` takes all three items of [0, 0, 0] from
  the iterator and `Efficient` takes none;
* `bool(NotImplemented)`: TypeError on 3.14+, True with a DeprecationWarning
  on 3.10 to 3.13, each guarded on `sys.version_info`;
* every stated example value, and every fenced block runs in a subprocess.

Not settled here:

* The O(k) rows are the cost of the caller's method plus O(1); the tests show
  one call is made, not what the method costs.
* Which built-in types count as containers is the page's list; deque, array
  and other stdlib containers also store their length but are not timed.
* "Using `bool()` unnecessarily in conditions" and "Idiomatic" are style
  advice; the tests show only that `if bool(obj):` and `if obj:` each make one
  `__len__` call, not which is faster.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap
import time
import warnings
from collections.abc import Callable, Iterable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "bool_func.md"
EXPECTED_BLOCKS = 20


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 2_000) -> float:
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


class Calls:
    """Counts of the truth-protocol calls made since the last reset."""

    bool_calls = 0
    len_calls = 0

    @classmethod
    def reset(cls) -> None:
        cls.bool_calls = 0
        cls.len_calls = 0


class BoolAndLen:
    """Defines both; `__len__` stands in for an expensive count."""

    def __init__(self, truthy: bool) -> None:
        self.truthy = truthy

    def __bool__(self) -> bool:
        Calls.bool_calls += 1
        return self.truthy

    def __len__(self) -> int:
        Calls.len_calls += 1
        return sum(1 for _ in range(10_000))


class LenOnly:
    """Defines only `__len__`."""

    def __init__(self, size: int) -> None:
        self.size = size

    def __len__(self) -> int:
        Calls.len_calls += 1
        return self.size


class Neither:
    """Defines neither, and fails loudly if a lookup reaches `__getattr__`."""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"looked up {name}")


class TestNumbersDoNotGrowWithSize:
    """Row: convert number - O(1), a zero check whatever the value's size."""

    @pytest.mark.timing
    def test_a_huge_int_costs_what_a_small_one_does(self) -> None:
        small = 10**20
        huge = 10**100_000
        base = best_ns(lambda: bool(small))
        big = best_ns(lambda: bool(huge))
        assert big / base < 3, f"{base=:.1f}ns {big=:.1f}ns"

    def test_values(self) -> None:
        assert bool(0) is False
        assert bool(10**100_000) is True
        assert bool(-(10**100_000)) is True
        assert bool(0.0) is False
        assert bool(-0.0) is False
        assert bool(float("nan")) is True
        assert bool(0j) is False
        assert bool(1e-300j) is True


class TestBuiltinContainersReadTheirLength:
    """Row: convert built-in container - O(1), the stored length is read and
    the items are not counted."""

    @pytest.mark.timing
    @pytest.mark.parametrize(
        "make",
        [
            lambda n: "a" * n,
            lambda n: b"a" * n,
            lambda n: bytearray(n),
            lambda n: list(range(n)),
            lambda n: tuple(range(n)),
            lambda n: dict.fromkeys(range(n)),
            lambda n: set(range(n)),
            lambda n: frozenset(range(n)),
            lambda n: range(n),
            lambda n: dict.fromkeys(range(n)).keys(),
            lambda n: memoryview(bytes(n)),
        ],
        ids=[
            "str",
            "bytes",
            "bytearray",
            "list",
            "tuple",
            "dict",
            "set",
            "frozenset",
            "range",
            "keys",
            "memoryview",
        ],
    )
    def test_a_million_items_cost_what_ten_do(self, make: Callable[[int], object]) -> None:
        small = make(10)
        large = make(1_000_000)
        base = best_ns(lambda: bool(small))
        big = best_ns(lambda: bool(large))
        assert big / base < 3, f"{base=:.1f}ns {big=:.1f}ns"

    def test_range_longer_than_len_allows_is_truthy(self) -> None:
        huge = range(10**100)
        with pytest.raises(OverflowError):
            len(huge)
        assert bool(huge) is True
        assert bool(range(0)) is False


class TestBoolMethod:
    """Row: class defining `__bool__()` - one call to it, `__len__()` not called."""

    @pytest.mark.parametrize("truthy", [True, False])
    def test_one_bool_call_and_no_len_call(self, truthy: bool) -> None:
        obj = BoolAndLen(truthy)
        Calls.reset()
        assert bool(obj) is truthy
        assert (Calls.bool_calls, Calls.len_calls) == (1, 0)

    def test_if_statement_skips_len_too(self) -> None:
        """Best practice: `__bool__()` lets truth tests skip an expensive `__len__()`."""
        obj = BoolAndLen(True)
        Calls.reset()
        reached = False
        if obj:
            reached = True
        assert reached
        assert (Calls.bool_calls, Calls.len_calls) == (1, 0)


class TestLenOnly:
    """Row: class defining only `__len__()` - one call to it."""

    @pytest.mark.parametrize(("size", "truthy"), [(0, False), (5, True)])
    def test_one_len_call(self, size: int, truthy: bool) -> None:
        obj = LenOnly(size)
        Calls.reset()
        assert bool(obj) is truthy
        assert Calls.len_calls == 1

    def test_len_comparison_makes_the_same_call(self) -> None:
        """Prose: `len(obj) > 0` makes the `__len__()` call that `if obj:` makes."""
        obj = LenOnly(5)
        Calls.reset()
        assert obj
        implicit = Calls.len_calls
        Calls.reset()
        assert len(obj) > 0
        assert implicit == Calls.len_calls == 1

    def test_explicit_bool_makes_the_same_call(self) -> None:
        """Best practice: `if bool(obj):` makes the one truth test `if obj:` makes."""
        obj = LenOnly(5)
        Calls.reset()
        reached = False
        if bool(obj):
            reached = True
        assert reached
        assert Calls.len_calls == 1


class TestNeither:
    """Row: class defining neither - O(1), always True."""

    def test_always_true_without_a_lookup_through_getattr(self) -> None:
        assert bool(Neither()) is True
        assert bool(object()) is True


class TestResultIsASingleton:
    """Prose: the result is `True` or `False`, so nothing is allocated for it."""

    @pytest.mark.parametrize("value", [0, 1, "", "a", [], [0], None, object()])
    def test_identity(self, value: object) -> None:
        result = bool(value)
        assert result is True or result is False


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


class NoIteration(list[object]):
    """A list that fails if anything iterates over its items."""

    def __iter__(self) -> Iterator[object]:
        raise AssertionError("iterated over the items")


class TestCustomBoolExample:
    """Example: `Expensive.__bool__` is `any(self.data)`, O(n) worst case;
    `Efficient` answers from `__len__()` without looking at an item."""

    def test_any_scans_every_falsy_item(self) -> None:
        class Expensive:
            def __init__(self, data: Iterable[object]) -> None:
                self.data = data

            def __bool__(self) -> bool:
                return any(self.data)

        items = CountingIterator([0, 0, 0])
        assert bool(Expensive(items)) is False
        assert items.taken == 3

        items = CountingIterator([1, 0, 0])
        assert bool(Expensive(items)) is True
        assert items.taken == 1

    def test_len_answers_non_empty(self) -> None:
        class Efficient:
            def __init__(self, data: list[object]) -> None:
                self.data = data

            def __len__(self) -> int:
                return len(self.data)

        assert bool(Efficient(NoIteration([0, 0, 0]))) is True
        assert bool(Efficient(NoIteration())) is False


class TestNotImplemented:
    """Version Notes: `bool(NotImplemented)` raises from 3.14 and warns before."""

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="version: raises from 3.14")
    def test_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="boolean context"):
            bool(NotImplemented)

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="version: warns before 3.14")
    def test_warns_and_returns_true(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            assert bool(NotImplemented) is True
        assert [w.category for w in caught] == [DeprecationWarning]


class TestStatedExampleValues:
    """The values the page's comments give, checked rather than trusted."""

    def test_falsy(self) -> None:
        for value in [None, False, 0, 0.0, 0j, "", [], {}, set(), (), range(0)]:
            assert bool(value) is False, value

    def test_truthy(self) -> None:
        for value in [True, 1, -1, 0.1, 3.14, "a", "0", [0], [None], [False], (1, 2), {1, 2}]:
            assert bool(value) is True, value

    def test_filtering(self) -> None:
        items = [0, 1, "", "hello", [], [1], None, False, True]
        assert [x for x in items if x] == [1, "hello", [1], True]
        assert list(filter(bool, items)) == [1, "hello", [1], True]
        values = [0, 1, 2, 3, 0, 5]
        assert list(map(bool, values)) == [False, True, True, True, False, True]

    def test_default_parameter(self) -> None:
        default_value = 10

        def process(value: int | None = None) -> int:
            if value is None:
                value = default_value
            return value

        def process_with_not(value: int | None = None) -> int:
            if not value:
                value = default_value
            return value

        assert process(0) == 0
        assert process_with_not(0) == 10

    def test_custom_falsy(self) -> None:
        class AlwaysFalse:
            def __bool__(self) -> bool:
                return False

        obj = AlwaysFalse()
        assert bool(obj) is False
        assert obj is not None


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
        block = next(source for _, source in _blocks() if "divisor = 4" in source)
        broken = block.replace("divisor = 4\n", "", 1)
        assert broken != block, "the mutation did not remove the binding"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr
