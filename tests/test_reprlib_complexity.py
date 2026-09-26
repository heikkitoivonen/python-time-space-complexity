"""Tests for docs/stdlib/reprlib.md.

The page separates what the limits bound from what is read. Sequences and
strings are read only as far as the limit; dicts and sets are sorted in full;
an int is converted in full; and any type `Repr` has no method for is rendered
by its own `repr()` before it is trimmed. Most of that is settled by
observation - a counting `__repr__`, a counting `__lt__`, an exact output -
and the space bounds by traced peak allocation, which separates an input-sized
copy from a limit-sized one by orders of magnitude.

Measurement scope:

* Sequences: a list, tuple and deque of 10,000 counting elements call
  `__repr__` exactly `k` times. Traced peaks for a list, tuple, deque and
  array of 1,000 and 100,000 ints differ by under 3x, and one timing test
  has a list of 200,000 cost under 10x a list of 200 at `maxlist=3`. A
  string's peak at 1,000 and 1,000,000 characters differs by under 3x.
* Dicts and sets: 1,000 keys with `maxdict=4` take at least 999
  comparisons. Traced peaks for a dict, a set and a set of unorderable
  elements grow more than 20x from 1,000 to 100,000 elements. Ascending
  input takes exactly n-1 comparisons at 1,000 and 10,000; 10,000 shuffled
  elements take more than 5x that and fewer than n log2 n. A comparison that
  fails on its last call has paid every comparison of the full sort, and
  the output is then in iteration order. A set at the depth where
  `maxlevel` shows `{...}` is compared at least n-1 times; a dict there
  is compared zero times.
* `maxlevel`: counting elements nested below the depth limit are never
  rendered, and the output is the documented `[...]` form.
* Ints: at a fixed `maxlong`, 4,000 digits take more than 20x the time of
  500 (linear predicts 8x, quadratic 64x), and the traced peak grows more
  than 4x. The placeholder beyond `sys.get_int_max_str_digits()` is
  asserted on 3.13.6+ and the `ValueError` before it, each guarded on
  `sys.version_info`.
* `repr_instance`: `bytes` and a `list` subclass have traced peaks that
  grow more than 20x from 1,000 to 100,000 elements although the output
  stays at `maxother` characters; a `__repr__` that raises gives
  `<Type instance at 0x...>`.
* Dispatch: a `list` subclass reaches `repr_instance`, a `Repr` subclass's
  `repr_bytes` is found by name, and `repr1(x, 0)` shows only `fillvalue`.
  `reprlib.repr` is bound to `reprlib.aRepr`, and changing `aRepr` changes
  it.
* `recursive_repr`: a cycle short-circuits to `fillvalue`, the in-progress
  set holds one entry during a call and none after it, and a 50-node
  acyclic chain renders all 50 nodes.
* `Repr()` defaults are asserted; keyword construction and `indent` are
  guarded on 3.12, `fillvalue` on 3.11.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The O(n log n) worst case for dicts and sets is Timsort's bound. The tests
  bound one shuffled input under n log2 n comparisons; they do not search for
  a worst input.
* The quadratic int conversion is measured only within the default digit
  limit of 4,300; above it, with the limit raised, CPython 3.12+ switches to
  a subquadratic algorithm, which O(d²) still bounds.
* Element hashing and comparison costs, and the cost of a user `__repr__`
  beyond the characters it returns, are outside the bounds by definition.
* `reprlib.aRepr.<attribute>` names reported by the API audit are the same
  attributes as `Repr.<attribute>`, documented once.
"""

from __future__ import annotations

import collections
import gc
import math
import pathlib
import random
import re
import reprlib
import subprocess
import sys
import textwrap
import time
import tracemalloc
from array import array
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "reprlib.md"
EXPECTED_BLOCKS = 8


def best_ns(func: Callable[[], Any], repeats: int = 7) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        elapsed = time.perf_counter_ns() - start
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs, above what was live before."""
    gc.collect()
    tracemalloc.start()
    try:
        base = tracemalloc.get_traced_memory()[0]
        func()
        return tracemalloc.get_traced_memory()[1] - base
    finally:
        tracemalloc.stop()


class CountingRepr:
    """An element that counts how often it is rendered."""

    calls = 0

    def __repr__(self) -> str:
        CountingRepr.calls += 1
        return "c"


def counting_comparables(
    size: int, *, ordered: bool, fail_after: float = math.inf
) -> tuple[list[Any], dict[str, int]]:
    """Hashable elements that count `__lt__` calls and raise past a threshold.

    Each hashes to its value, so a set of them iterates in ascending order
    whichever way they were drawn; a dict keeps the drawn order, which is
    one ascending run when `ordered` and shuffled otherwise.
    """
    comparisons = {"n": 0}

    class Counted:
        def __init__(self, value: int) -> None:
            self.value = value

        def __hash__(self) -> int:
            return hash(self.value)

        def __repr__(self) -> str:
            return f"c{self.value}"

        def __lt__(self, other: Counted) -> bool:
            comparisons["n"] += 1
            if comparisons["n"] > fail_after:
                raise TypeError("not orderable")
            return self.value < other.value

    values = list(range(size)) if ordered else random.Random(12345).sample(range(size), size)
    return [Counted(value) for value in values], comparisons


class TestModuleFunctions:
    """`reprlib.repr(obj)` is the bound `repr` of `reprlib.aRepr`, so
    changing `aRepr` changes it for every caller."""

    def test_repr_is_bound_to_the_shared_instance(self) -> None:
        assert reprlib.repr.__self__ is reprlib.aRepr  # type: ignore[attr-defined]

    def test_changing_arepr_changes_reprlib_repr(self) -> None:
        previous = reprlib.aRepr.maxlist
        try:
            reprlib.aRepr.maxlist = 2
            assert reprlib.repr(list(range(10))) == "[0, 1, ...]"
        finally:
            reprlib.aRepr.maxlist = previous
        assert reprlib.repr(list(range(10))) == "[0, 1, 2, 3, 4, 5, ...]"


class TestRecursiveRepr:
    """`recursive_repr(fillvalue)` | O(1) per call plus the wrapped call, one
    entry per call in progress; it bounds cycles, not depth."""

    @staticmethod
    def _node_class(*fill: str) -> type:
        class Node:
            def __init__(self) -> None:
                self.child: Any = None

            @reprlib.recursive_repr(*fill)
            def __repr__(self) -> str:
                return f"Node({self.child!r})"

        return Node

    def test_a_cycle_returns_the_fillvalue(self) -> None:
        node = self._node_class("<...>")()
        node.child = node

        assert repr(node) == "Node(<...>)"

    def test_the_fillvalue_defaults_to_an_ellipsis(self) -> None:
        node = self._node_class()()
        node.child = node

        assert repr(node) == "Node(...)"

    def test_one_entry_is_held_per_call_in_progress(self) -> None:
        seen: list[int] = []

        class Probe:
            @reprlib.recursive_repr()
            def __repr__(self) -> str:
                seen.append(len(running))
                return "Probe()"

        cells = Probe.__repr__.__closure__ or ()
        running = next(cell.cell_contents for cell in cells if isinstance(cell.cell_contents, set))

        assert repr(Probe()) == "Probe()"
        assert seen == [1]
        assert running == set()

    def test_an_acyclic_chain_still_renders_to_the_end(self) -> None:
        node_class = self._node_class()
        head = node = node_class()
        for _ in range(49):
            node.child = node_class()
            node = node.child

        assert repr(head).count("Node(") == 50


class TestRepr:
    """The `Repr` rows: construction stores the limits, and `repr1()`
    dispatches on the type's name."""

    def test_defaults(self) -> None:
        printer = reprlib.Repr()

        assert (
            printer.maxlevel,
            printer.maxtuple,
            printer.maxlist,
            printer.maxarray,
            printer.maxdict,
            printer.maxset,
            printer.maxfrozenset,
            printer.maxdeque,
            printer.maxstring,
            printer.maxlong,
            printer.maxother,
        ) == (6, 6, 6, 5, 4, 6, 6, 6, 30, 40, 30)

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="fillvalue is 3.11+")
    def test_fillvalue(self) -> None:
        printer = reprlib.Repr()
        assert printer.fillvalue == "..."  # type: ignore[attr-defined]
        printer.fillvalue = "~"  # type: ignore[attr-defined]
        printer.maxlist = 2
        assert printer.repr([1, 2, 3]) == "[1, 2, ~]"

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="keyword limits are 3.12+")
    def test_limits_are_keyword_arguments(self) -> None:
        printer = reprlib.Repr(maxlist=2, maxstring=10)  # type: ignore[call-arg]

        assert (printer.maxlist, printer.maxstring) == (2, 10)

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="keyword limits are 3.12+")
    def test_limits_are_not_keyword_arguments_before_312(self) -> None:
        with pytest.raises(TypeError):
            reprlib.Repr(maxlist=2)  # type: ignore[call-arg]

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="indent is 3.12+")
    def test_indent_puts_each_element_on_its_own_line(self) -> None:
        printer = reprlib.Repr()
        assert printer.indent is None  # type: ignore[attr-defined]
        printer.indent = 2  # type: ignore[attr-defined]

        assert printer.repr([1, [2]]) == "[\n  1,\n  [\n    2,\n  ],\n]"

    def test_repr_is_repr1_at_maxlevel(self) -> None:
        printer = reprlib.Repr()
        value = [[1, 2], "x" * 100]

        assert printer.repr(value) == printer.repr1(value, printer.maxlevel)

    def test_repr1_at_level_zero_shows_only_the_fillvalue(self) -> None:
        assert reprlib.Repr().repr1(list(range(100)), 0) == "[...]"

    def test_a_builtin_subclass_falls_back_to_repr_instance(self) -> None:
        class Rows(list):
            pass

        reached: list[str] = []

        class Recording(reprlib.Repr):
            def repr_instance(self, x: Any, level: int) -> str:
                reached.append(type(x).__name__)
                return super().repr_instance(x, level)

        Recording().repr(Rows([1, 2]))
        assert reached == ["Rows"]

        reached.clear()
        Recording().repr([1.5])
        assert reached == ["float"], "a plain list dispatches to repr_list"

    def test_a_subclass_method_is_found_by_type_name(self) -> None:
        class ShortBytes(reprlib.Repr):
            def repr_bytes(self, obj: bytes, level: int) -> str:
                return "bytes!"

        assert ShortBytes().repr([b"abc"]) == "[bytes!]"


class TestSequencesStopAtTheLimit:
    """`repr_tuple`, `repr_list`, `repr_deque`, `repr_array` | O(min(n, k)).

    Counting elements show exactly k are rendered; traced peaks show nothing
    input-sized is copied, which is the half a counter cannot see.
    """

    @pytest.mark.parametrize("build", [list, tuple, collections.deque])
    def test_only_k_elements_are_rendered(self, build: Callable[[Any], Any]) -> None:
        printer = reprlib.Repr()
        printer.maxlist = printer.maxtuple = printer.maxdeque = 4
        source = build(CountingRepr() for _ in range(10_000))

        CountingRepr.calls = 0
        printer.repr(source)

        assert CountingRepr.calls == 4

    @pytest.mark.parametrize(
        "build",
        [list, tuple, collections.deque, lambda values: array("i", values)],
        ids=["list", "tuple", "deque", "array"],
    )
    def test_peak_does_not_grow_with_n(self, build: Callable[[Any], Any]) -> None:
        printer = reprlib.Repr()
        small = build(range(1_000))
        large = build(range(100_000))

        small_peak = peak_bytes(lambda: printer.repr(small))
        large_peak = peak_bytes(lambda: printer.repr(large))

        assert large_peak < small_peak * 3, (
            f"100x the input should hold nothing more: {small_peak:,}B vs {large_peak:,}B"
        )

    @pytest.mark.timing
    def test_list_time_does_not_grow_with_n(self) -> None:
        printer = reprlib.Repr()
        printer.maxlist = 3
        small = list(range(200))
        large = list(range(200_000))

        small_time = best_ns(lambda: printer.repr(small))
        large_time = best_ns(lambda: printer.repr(large))

        assert large_time < small_time * 10, (
            f"1,000x the list should cost about the same at a fixed maxlist: "
            f"n=200 {small_time:,.0f}ns vs n=200,000 {large_time:,.0f}ns"
        )


class TestStringsSliceFirst:
    """`repr_str` | O(min(n, k)): sliced to `maxstring` before quoting."""

    def test_output(self) -> None:
        printer = reprlib.Repr()
        printer.maxstring = 20

        assert printer.repr("x" * 1000) == "'xxxxxxx...xxxxxxxx'"
        assert printer.repr("abc") == "'abc'"

    def test_peak_does_not_grow_with_n(self) -> None:
        printer = reprlib.Repr()
        small = "x" * 1_000
        large = "x" * 1_000_000

        small_peak = peak_bytes(lambda: printer.repr(small))
        large_peak = peak_bytes(lambda: printer.repr(large))

        assert large_peak < small_peak * 3, f"{small_peak:,}B vs {large_peak:,}B"


class TestDictsAndSetsSortEverything:
    """`repr_dict`, `repr_set`, `repr_frozenset` | O(n log n), O(n) when
    already ascending | O(n): every element is sorted before k are shown."""

    SMALL = 1_000
    LARGE = 100_000

    def test_every_key_is_compared(self) -> None:
        elements, comparisons = counting_comparables(self.SMALL, ordered=False)
        printer = reprlib.Repr()
        printer.maxdict = 4

        printer.repr(dict.fromkeys(elements, 0))

        assert comparisons["n"] >= self.SMALL - 1

    @pytest.mark.parametrize(
        "build",
        [
            lambda n: dict.fromkeys(range(n), 0),
            lambda n: set(range(n)),
            lambda n: frozenset(range(n)),
        ],
        ids=["dict", "set", "frozenset"],
    )
    def test_peak_grows_with_n(self, build: Callable[[int], Any]) -> None:
        printer = reprlib.Repr()
        small = build(self.SMALL)
        large = build(self.LARGE)

        small_peak = peak_bytes(lambda: printer.repr(small))
        large_peak = peak_bytes(lambda: printer.repr(large))

        assert large_peak > small_peak * 20, f"{small_peak:,}B vs {large_peak:,}B"

    def test_unorderable_elements_hold_everything_too(self) -> None:
        class Unorderable:
            def __init__(self, value: int) -> None:
                self.value = value

            def __hash__(self) -> int:
                return hash(self.value)

        printer = reprlib.Repr()
        small = {Unorderable(value) for value in range(self.SMALL)}
        large = {Unorderable(value) for value in range(self.LARGE)}

        small_peak = peak_bytes(lambda: printer.repr(small))
        large_peak = peak_bytes(lambda: printer.repr(large))

        assert large_peak > small_peak * 20, f"{small_peak:,}B vs {large_peak:,}B"

    def test_ascending_input_takes_n_minus_one_comparisons(self) -> None:
        counts = []
        for size in (1_000, 10_000):
            elements, comparisons = counting_comparables(size, ordered=True)
            reprlib.repr(set(elements))
            counts.append(comparisons["n"])

        assert counts == [999, 9_999]

    def test_shuffled_input_costs_over_5x_ascending_and_under_n_log_n(self) -> None:
        size = 10_000
        ordered, ordered_count = counting_comparables(size, ordered=True)
        shuffled, shuffled_count = counting_comparables(size, ordered=False)
        reprlib.repr(dict.fromkeys(ordered, 0))
        reprlib.repr(dict.fromkeys(shuffled, 0))

        assert shuffled_count["n"] > ordered_count["n"] * 5
        assert shuffled_count["n"] < size * math.log2(size)

    def test_a_late_failure_pays_the_whole_sort_then_uses_iteration_order(self) -> None:
        """A dict keeps insertion order, so the shuffled keys reach sorted()
        unsorted and the successful sort is superlinear."""
        size = 2_000
        elements, comparisons = counting_comparables(size, ordered=False)
        reprlib.repr(dict.fromkeys(elements, 0))
        full = comparisons["n"]

        elements, comparisons = counting_comparables(size, ordered=False, fail_after=full - 1)
        rendered = reprlib.repr(dict.fromkeys(elements, 0))

        assert full > size * 2
        assert comparisons["n"] == full
        expected = ", ".join(f"{item!r}: 0" for item in elements[:4])
        assert rendered == "{" + expected + ", ...}"

    def test_a_set_at_the_depth_limit_is_still_sorted(self) -> None:
        elements, comparisons = counting_comparables(self.SMALL, ordered=True)
        printer = reprlib.Repr()
        printer.maxlevel = 1

        assert printer.repr([set(elements)]) == "[{...}]"
        assert comparisons["n"] >= self.SMALL - 1

    def test_a_dict_at_the_depth_limit_is_not(self) -> None:
        elements, comparisons = counting_comparables(self.SMALL, ordered=True)
        printer = reprlib.Repr()
        printer.maxlevel = 1

        assert printer.repr([dict.fromkeys(elements, 0)]) == "[{...}]"
        assert comparisons["n"] == 0


class TestMaxlevel:
    """`Repr.maxlevel`: a container at that depth shows only `fillvalue`,
    and its contents are not rendered."""

    def test_contents_below_the_limit_are_not_rendered(self) -> None:
        printer = reprlib.Repr()
        printer.maxlevel = 2
        CountingRepr.calls = 0

        assert printer.repr([[[CountingRepr()] * 1_000]]) == "[[[...]]]"
        assert CountingRepr.calls == 0


class TestIntsConvertEveryDigit:
    """`repr_int` | O(d²) | O(d): the whole decimal string is built before
    `maxlong` trims it."""

    def test_output_is_trimmed_to_maxlong(self) -> None:
        big = 7**1000
        shown = reprlib.repr(big)

        assert len(shown) == 40
        assert shown.startswith(str(big)[:18]) and shown.endswith(str(big)[-19:])

    @pytest.mark.timing
    def test_time_is_quadratic_in_digits(self) -> None:
        small = 10**500 - 1
        large = 10**4000 - 1

        small_time = best_ns(lambda: reprlib.repr(small), repeats=21)
        large_time = best_ns(lambda: reprlib.repr(large), repeats=21)

        assert large_time > small_time * 20, (
            f"8x the digits should cost far more than 8x at a fixed maxlong: "
            f"d=500 {small_time:,.0f}ns vs d=4,000 {large_time:,.0f}ns"
        )

    def test_peak_grows_with_digits(self) -> None:
        small = 10**500 - 1
        large = 10**4000 - 1

        small_peak = peak_bytes(lambda: reprlib.repr(small))
        large_peak = peak_bytes(lambda: reprlib.repr(large))

        assert large_peak > small_peak * 4, f"{small_peak:,}B vs {large_peak:,}B"

    @pytest.mark.skipif(sys.version_info < (3, 13, 6), reason="placeholder is 3.13.6+")
    def test_beyond_the_digit_limit_is_a_placeholder(self) -> None:
        huge = 10 ** (sys.get_int_max_str_digits() + 1)

        assert reprlib.repr(huge).startswith("<int instance with roughly")

    @pytest.mark.skipif(sys.version_info >= (3, 13, 6), reason="placeholder is 3.13.6+")
    def test_beyond_the_digit_limit_raises_before_3136(self) -> None:
        huge = 10 ** (sys.get_int_max_str_digits() + 1)

        with pytest.raises(ValueError, match="integer string conversion"):
            reprlib.repr(huge)


class TestReprInstanceBuildsTheWholeRepr:
    """`repr_instance` | O(r) | O(r): every type without a method, `bytes`
    and subclasses of built-in types included."""

    @pytest.mark.parametrize(
        "build",
        [bytes, lambda n: type("Rows", (list,), {})(range(n))],
        ids=["bytes", "list-subclass"],
    )
    def test_peak_grows_with_the_full_repr(self, build: Callable[[int], Any]) -> None:
        small = build(1_000)
        large = build(100_000)

        assert len(reprlib.repr(large)) == reprlib.aRepr.maxother
        small_peak = peak_bytes(lambda: reprlib.repr(small))
        large_peak = peak_bytes(lambda: reprlib.repr(large))

        assert large_peak > small_peak * 20, f"{small_peak:,}B vs {large_peak:,}B"

    def test_a_raising_repr_gives_a_placeholder(self) -> None:
        class Broken:
            def __repr__(self) -> str:
                raise RuntimeError("no")

        assert re.fullmatch(r"<Broken instance at 0x[0-9a-f]+>", reprlib.repr(Broken()))


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
    """Each block runs in its own subprocess and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "'[0, 1, 2, ...]'" in s)
        mutated = source.replace("'[0, 1, 2, ...]'", "'[0, 1, ...]'", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
