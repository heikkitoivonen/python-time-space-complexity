"""Tests for docs/builtins/any.md.

any() is builtin_any in Python/bltinmodule.c: it takes one iterator, calls its
`tp_iternext` once per item and PyObject_IsTrue on each item, and returns True
at the first truthy one. The function is the same in the v3.10.0, v3.11.0,
v3.12.0, v3.13.0 and v3.14.0 tags, so no version is treated apart. From 3.14
the compiler also inlines `any(<generator expression>)` into a loop when the
name `any` resolves to the builtin at run time (maybe_optimize_function_call
in Python/codegen.c); the item and truth-test counts below are asserted both
through that path and through an aliased call that cannot take it.

Every claim on the page is settled by counting, not timing:

* a counting iterator records how many items any() pulls - 1 when the first
  item is truthy, k when the k-th is, n when none is, and 0 items (one
  exhausted next()) on an empty iterable;
* a counting `__bool__` records one truth test per item looked at;
* the rest of a shared iterator is still there after any() returns;
* the page's short-circuit examples are checked by call counts: the generator
  stops at the first truthy item, a list comprehension makes every call;
* the examples' stated positions - 102 items of range(10**9), 10**5 + 2 of
  range(10**6) - are read back off the iterator.

Measurement scope: traced allocation of any() over a list of 1,000,000 falsy
items stays under 1,000 bytes, the O(1) Space column; the iterator any() makes
is the only allocation, and it does not grow with n.

Not settled here: the page states no relative speed for any() against `in`
or a manual loop, only that each is the same O(k) scan. The cost of producing
an item (a generator's expression) and of a truth test (`__bool__`, `__len__`)
is the caller's; the page prices both at O(1) and these tests do not vary it.
"""

import pathlib
import re
import subprocess
import sys
import textwrap
import tracemalloc
from collections.abc import Callable, Iterable, Iterator
from typing import Generic, TypeVar

import pytest

T = TypeVar("T")

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "any.md"


class Counting(Generic[T]):
    """An iterator over `items` that records how many items it has handed out."""

    def __init__(self, items: Iterable[T]) -> None:
        self._items = iter(items)
        self.pulled = 0

    def __iter__(self) -> Iterator[T]:
        return self

    def __next__(self) -> T:
        item = next(self._items)
        self.pulled += 1
        return item


class Truth:
    """An item whose truth test is counted."""

    tests = 0

    def __init__(self, value: bool) -> None:
        self.value = value

    def __bool__(self) -> bool:
        Truth.tests += 1
        return self.value


def any_direct(items: Iterable[object]) -> bool:
    """any() over a generator expression, the spelling 3.14 inlines."""
    return any(x for x in items)


def any_aliased(items: Iterable[object]) -> bool:
    """The same call through another name, which always reaches builtin_any."""
    call = any
    return call(x for x in items)


SPELLINGS = pytest.mark.parametrize("spelling", [any_direct, any_aliased, any])


class TestStopsAtTheFirstTruthyItem:
    """Rows: first item truthy O(1), early exit O(k), all falsy O(n), empty O(1)."""

    @SPELLINGS
    def test_a_truthy_first_item_pulls_one_item(self, spelling: Callable[..., bool]) -> None:
        items = Counting([1] + [0] * 1_000)
        assert spelling(items) is True
        assert items.pulled == 1

    @SPELLINGS
    @pytest.mark.parametrize("k", [2, 50, 999])
    def test_the_kth_item_truthy_pulls_k_items(self, spelling: Callable[..., bool], k: int) -> None:
        items = Counting([0] * (k - 1) + [1] + [0] * 1_000)
        assert spelling(items) is True
        assert items.pulled == k

    @SPELLINGS
    @pytest.mark.parametrize("n", [1, 100, 10_000])
    def test_all_falsy_pulls_every_item(self, spelling: Callable[..., bool], n: int) -> None:
        items = Counting([0] * n)
        assert spelling(items) is False
        assert items.pulled == n

    @SPELLINGS
    def test_an_empty_iterable_pulls_nothing(self, spelling: Callable[..., bool]) -> None:
        items = Counting([])
        assert spelling(items) is False
        assert items.pulled == 0

    @SPELLINGS
    def test_one_truth_test_per_item_looked_at(self, spelling: Callable[..., bool]) -> None:
        Truth.tests = 0
        assert spelling([Truth(False)] * 4 + [Truth(True)] + [Truth(False)] * 10) is True
        assert Truth.tests == 5

        Truth.tests = 0
        assert spelling([Truth(False)] * 20) is False
        assert Truth.tests == 20

    @SPELLINGS
    def test_the_result_is_a_bool_not_the_item(self, spelling: Callable[..., bool]) -> None:
        assert spelling([0, "yes", None]) is True
        assert spelling([0, "", None]) is False


class TestSpaceIsConstant:
    """Space column: O(1) in every row - any() holds one item at a time."""

    @pytest.mark.serial
    def test_scanning_a_million_items_allocates_a_constant(self) -> None:
        items = [0] * 1_000_000
        any(items)
        tracemalloc.start()
        try:
            assert any(items) is False
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        assert peak < 1_000, f"any() over 1,000,000 items traced a {peak}-byte peak"


class TestTheRestOfTheIteratorIsLeft:
    """Version Notes: any() leaves the rest of an iterator unconsumed."""

    @SPELLINGS
    def test_the_items_after_the_first_truthy_one_remain(
        self, spelling: Callable[..., bool]
    ) -> None:
        it = iter([0, 0, 7, 8, 9])
        assert spelling(it) is True
        assert list(it) == [8, 9]


class TestShortCircuitExamples:
    """Performance Patterns: a generator stops at the first truthy item; a list
    comprehension makes every call before any() starts."""

    def test_the_generator_never_calls_the_expensive_checks(self) -> None:
        calls = 0

        def expensive_function() -> bool:
            nonlocal calls
            calls += 1
            return False

        checks = [lambda: True, expensive_function, expensive_function]
        assert any(check() for check in checks) is True
        assert calls == 0

    def test_the_list_makes_every_call(self) -> None:
        calls = 0

        def expensive_function() -> bool:
            nonlocal calls
            calls += 1
            return False

        assert any([True] + [expensive_function() for _ in range(1000)]) is True
        assert calls == 1000

    def test_range_of_a_billion_stops_after_102_items(self) -> None:
        numbers = Counting(range(10**9))
        assert any(x > 100 for x in numbers) is True
        assert numbers.pulled == 102

    def test_range_of_a_million_stops_after_10_to_the_5_plus_2(self) -> None:
        numbers = Counting(range(10**6))
        assert any(x > 10**5 for x in numbers) is True
        assert numbers.pulled == 10**5 + 2

    def test_the_list_comprehension_builds_every_result(self) -> None:
        numbers = Counting(range(10**6))
        assert any([x > 10**5 for x in numbers]) is True  # noqa: C419 - the eager list is the subject
        assert numbers.pulled == 10**6

    def test_the_or_chain_returns_an_operand_and_any_a_bool(self) -> None:
        condition1, condition2, condition3 = 0, "yes", None
        assert any([condition1, condition2, condition3]) is True
        assert (condition1 or condition2 or condition3) == "yes"

    def test_the_generator_of_callables_stops_at_the_first_true(self) -> None:
        called: list[str] = []

        def make(name: str, value: bool) -> Callable[[], bool]:
            def check() -> bool:
                called.append(name)
                return value

            return check

        checks = [make("expensive1", True), make("expensive2", False), make("expensive3", False)]
        assert any(f() for f in checks) is True
        assert called == ["expensive1"]

        called.clear()
        assert any([f() for f in checks]) is True  # noqa: C419 - the eager list is the subject
        assert called == ["expensive1", "expensive2", "expensive3"]


class TestStatedExampleValues:
    """The results and stopping points the page's comments give."""

    def test_checking_any_true(self) -> None:
        numbers = Counting([0, 0, 1, 2, 3])
        assert any(numbers) is True
        assert numbers.pulled == 3
        numbers = Counting([0, 0, 0, 0, 5])
        assert any(numbers) is True
        assert numbers.pulled == 5
        assert any([0, False, None, "", []]) is False

    def test_with_conditions(self) -> None:
        numbers = [1, 2, 3, 4, 5]
        stops = Counting(numbers)
        assert any(x > 3 for x in stops) is True
        assert stops.pulled == 4
        stops = Counting(numbers)
        assert any(x > 2 for x in stops) is True
        assert stops.pulled == 3

    def test_membership_gives_the_same_answer(self) -> None:
        items = [1, 2, 3, 4, 5]
        for value in (0, 1, 3, 5, 6):
            assert any(x == value for x in items) is (value in items)

    def test_membership_scans_as_far_as_any(self) -> None:
        compared: list[int] = []

        class Item:
            def __init__(self, value: int) -> None:
                self.value = value

            def __eq__(self, other: object) -> bool:
                compared.append(self.value)
                return self.value == other

            __hash__ = None  # pyright: ignore[reportAssignmentType]

        items = [Item(v) for v in (1, 2, 3, 4, 5)]
        assert any(x == 3 for x in items) is True
        by_any = compared.copy()
        compared.clear()
        assert 3 in items
        assert by_any == compared == [1, 2, 3]

    def test_checking_conditions(self) -> None:
        assert any(x % 2 == 1 for x in [2, 4, 6, 8, 10]) is False
        stops = Counting([2, 4, 5, 8, 10])
        assert any(x % 2 == 1 for x in stops) is True
        assert stops.pulled == 3

    def test_comparison_with_all(self) -> None:
        assert any([False, False, False]) is False
        assert any([False, True, False]) is True
        assert any([]) is False
        assert all([True, True, True]) is True
        assert all([True, False, True]) is False
        assert all([]) is True

    def test_edge_cases(self) -> None:
        assert any(()) is False
        assert any(set()) is False
        assert any(x for x in []) is False
        assert [any([True]), any([False]), any([1]), any([0])] == [True, False, True, False]
        assert any([0, "", None]) is False
        stops = Counting([False, [], {}, "hello"])
        assert any(stops) is True
        assert stops.pulled == 4

    def test_manual_loop_agrees(self) -> None:
        numbers = [5, 50, 500, 5000]
        result = False
        for x in numbers:
            if x > 100:
                result = True
                break
        assert result is any(x > 100 for x in numbers) is True

    def test_complex_check(self) -> None:
        items = [1, 2, 3, 4, 5]
        assert any(x > 3 for x in items) is True
        assert any(w.startswith("a") for w in ["kiwi", "apple", "plum"]) is True


EXPECTED_BLOCKS = 14


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
        short_circuit = next(source for _, source in _blocks() if "expensive_function" in source)
        broken = short_circuit.replace("def expensive_function():\n    return False\n", "", 1)
        assert broken != short_circuit, "the mutation did not remove the definition"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr
