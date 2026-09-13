"""Tests for docs/builtins/sum.md.

sum() is builtin_sum_impl in Python/bltinmodule.c: one PyIter_Next and one
PyNumber_Add per item, with three fast paths that keep the running total in C
instead of allocating an object per step. The exact-`int` path (bools included)
accumulates in a Py_ssize_t until an item or the total overflows a machine
word; the exact-`float` path accumulates in a double, with Neumaier
compensation from the v3.12.0 tag; the exact-`complex` path exists on 3.14
only. Every other type, and every fast path once it drops out, goes through
PyNumber_Add and rebinds the result, so the previous total is freed as the
next replaces it. A `str`, `bytes` or `bytearray` start is rejected before the
loop, and the message names ''.join(). The release branches from v3.10.0 to
3.14 differ only in which fast paths exist, never in the bound.

Observation settles most rows:

* a machine-word int, bool, float or complex sum holds the same few bytes at
  100,000 items as at 10,000, and a wide sum allocates the result's own width;
* a `str`, `bytes` or `bytearray` start raises before the first item is
  consumed, and a str item without a start fails as `0 + "a"`;
* a custom type's `__add__` runs exactly once per item, and without a start
  the first call is `int.__add__`, which hands off to the item's `__radd__`;
* `sum(nested, [])` leaves the start list untouched, because each step binds
  a fresh list rather than extending the old one;
* `sum(1 for _ in data)` iterates `data` a second time, where `len()` does
  not;
* on 3.12 and later `sum([0.1] * 10)` is exactly 1.0, and on 3.10 and 3.11 it
  is 0.9999999999999999; `[1e16, 1.0] + [1e-16] * 10000 + [-1e16]` sums to
  1.0 from 3.12 and to 0.0 before, where `math.fsum` gives 1.000000000001 on
  every version, which is the page's claim that fsum keeps exact partial sums
  and one compensation term does not;
* a custom type's intermediate results are freed as sum() goes: when
  `__add__` runs, the only earlier result still alive is the running total.

The rest need elapsed time or traced allocation, each framed at the widest
gap measured on the pinned interpreter (aarch64, CPython 3.14):

* a machine-word int, float or complex sum is linear in the item count: x10
  in items costs x10.0 for ints, x9.8 for floats and x10.3 for complex;
* a wide-int sum is linear in the item width: x10.7 for x10 in bits at a
  fixed 200 items, where the machine-word row's O(1) per item predicts x1;
* and linear in the item count: x4.0 for x4 at a fixed 100,000 bits;
* `sum(nested, [])` depends on the number of lists at a fixed total of
  40,000 elements: 8,000 lists of 5 cost x43 what 200 lists of 200 do, and
  tuples cost x41; at a fixed 1,000 lists, x10 in elements costs x11 for
  lists and x11 for tuples, where
  the O(N) `chain.from_iterable` and the comprehension each cost x1.7 across
  the same two shapes, and x9.6 and x9.9 for x10 in the total;
* its peak allocation is about twice the final list or tuple, at both 10,000
  and 40,000 elements: the running total plus the one it is about to replace;
* a wide-int sum's peak is under three times its result, and x10 in items at a
  fixed width leaves it unchanged.

One claim cannot be settled by running code here: the page dates the `start`
keyword to Python 3.8, and every supported interpreter already has it. The
tests use the keyword form and assert nothing about the release.

Not varied: the cost of a custom `__add__` beyond counting its calls (the
page's Vector adds in its own zip, which is that class's cost, not sum()'s),
mixed int and float inputs, which leave the fast paths but not the bound, and
the complex fast path's constant factor, which is a 3.14 change with no bound
behind it. `math.fsum`'s and `str.join`'s own costs belong to their pages.
"""

import math
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable, Iterator
from itertools import accumulate, chain
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "sum.md"


def best_time(func: Callable[[], Any], repeats: int = 5) -> float:
    """The fastest of several single runs, which is the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return min(times)


def traced_peak(func: Callable[[], Any]) -> int:
    """Peak bytes tracemalloc attributes to one call, after a warm-up call.

    Inputs must be built before the call, or their construction is counted."""
    func()
    tracemalloc.start()
    try:
        func()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak


def wide(bits: int) -> int:
    """An int of exactly `bits` bits, with a low digit set so it is not a power of two."""
    return (1 << (bits - 1)) | 7


class TestMachineWordInts:
    """Row: O(n) time, O(1) space, accumulated in a C integer."""

    @pytest.mark.parametrize("one", [1, 1.0, 1 + 1j], ids=["int", "float", "complex"])
    def test_allocation_does_not_grow_with_n(self, one: complex) -> None:
        small = [one] * 10_000
        large = [one] * 100_000

        small_peak = traced_peak(lambda: sum(small))
        large_peak = traced_peak(lambda: sum(large))

        # The result, one replaced total at most, and on some versions one
        # list iterator: never more, and never more at 100,000 than at 10,000.
        assert small_peak == large_peak, (small_peak, large_peak)
        assert large_peak < 256, large_peak

    def test_bools_are_summed_on_the_int_path(self) -> None:
        result = sum([True, False, True])
        assert result == 2
        assert type(result) is int
        flags = [True] * 100_000
        assert traced_peak(lambda: sum(flags)) < 256

    def test_a_total_past_a_machine_word_is_still_correct(self) -> None:
        items = [sys.maxsize] * 3
        assert sum(items) == 3 * sys.maxsize

    @pytest.mark.timing
    @pytest.mark.parametrize("one", [1, 1.0, 1 + 1j], ids=["int", "float", "complex"])
    def test_time_is_linear_in_the_item_count(self, one: complex) -> None:
        few = [one] * 100_000
        many = [one] * 1_000_000

        growth = best_time(lambda: sum(many)) / best_time(lambda: sum(few))

        assert 4 < growth < 25, f"x10 in items cost x{growth:.1f}"

    def test_start_is_added_once(self) -> None:
        assert sum([1, 2, 3], start=100) == 106
        assert sum([], start=100) == 100
        assert sum([]) == 0


class TestWideInts:
    """Row: O(n*w) time, O(w + log n) space, each + copies the running total."""

    def test_allocation_follows_the_item_width(self) -> None:
        peaks = {}
        for bits in (100_000, 1_000_000):
            items = [wide(bits)] * 100
            peaks[bits] = traced_peak(lambda items=items: sum(items))
            result_size = sys.getsizeof(sum(items))
            assert result_size <= peaks[bits] < 3 * result_size, (bits, peaks[bits], result_size)
        growth = peaks[1_000_000] / peaks[100_000]
        assert 5 < growth < 20, f"x10 in bits allocated x{growth:.1f}"

    def test_allocation_does_not_follow_the_item_count(self) -> None:
        peaks = {}
        for count in (100, 1_000):
            items = [wide(100_000)] * count
            peaks[count] = traced_peak(lambda items=items: sum(items))
        growth = peaks[1_000] / peaks[100]
        assert growth < 1.5, f"x10 in items allocated x{growth:.2f}; retaining totals predicts x10"

    def test_the_result_is_at_most_log_n_bits_wider(self) -> None:
        bits = 10_000
        items = [wide(bits)] * 1_000
        result = sum(items)
        assert result == 1_000 * wide(bits)
        assert bits < result.bit_length() <= bits + 10

    @pytest.mark.timing
    def test_time_is_linear_in_the_item_width(self) -> None:
        narrow = [wide(100_000)] * 200
        broad = [wide(1_000_000)] * 200

        growth = best_time(lambda: sum(broad)) / best_time(lambda: sum(narrow))

        assert 3 < growth < 40, f"x10 in bits cost x{growth:.1f}; O(1) per item predicts x1"

    @pytest.mark.timing
    def test_time_is_linear_in_the_item_count(self) -> None:
        few = [wide(100_000)] * 1_000
        many = [wide(100_000)] * 4_000

        growth = best_time(lambda: sum(many)) / best_time(lambda: sum(few))

        assert 2 < growth < 8, f"x4 in items cost x{growth:.1f}; quadratic predicts x16"


class TestFloats:
    """Row: O(n) time, O(1) space, accumulated in a C double."""

    def test_complex_items_are_summed(self) -> None:
        assert sum([1 + 1j] * 1_000) == 1_000 + 1_000j
        assert sum([1 + 1j, 2.0, 3]) == 6 + 1j

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="compensated from 3.12")
    def test_tenths_sum_to_one_from_312(self) -> None:
        assert sum([0.1] * 10) == 1.0

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="uncompensated before 3.12")
    def test_tenths_fall_short_of_one_before_312(self) -> None:
        assert sum([0.1] * 10) == 0.9999999999999999

    def test_fsum_is_exact_where_sum_is_not(self) -> None:
        values = [1e16, 1.0] + [1e-16] * 10_000 + [-1e16]

        assert math.fsum(values) == 1.000000000001
        assert sum(values) != math.fsum(values)
        assert math.fsum([0.1] * 10) == 1.0


class TestNestedLists:
    """Row: O(n*N) time and O(N) space, each + copying the running total."""

    def test_stated_result_and_the_start_is_untouched(self) -> None:
        nested = [[1, 2], [3, 4], [5, 6]]
        start: list[int] = []

        flat = sum(nested, start)

        assert flat == [1, 2, 3, 4, 5, 6]
        assert start == []
        assert flat is not start

    def test_the_alternatives_agree(self) -> None:
        nested = [[1, 2], [3, 4], [5, 6]]
        assert list(chain.from_iterable(nested)) == [1, 2, 3, 4, 5, 6]
        assert [item for sublist in nested for item in sublist] == [1, 2, 3, 4, 5, 6]

    @pytest.mark.parametrize("kind", [list, tuple])
    def test_peak_allocation_is_a_small_multiple_of_the_result(self, kind: type) -> None:
        for total in (10_000, 40_000):
            nested = [kind([0] * 10) for _ in range(total // 10)]
            start = kind()
            final = sys.getsizeof(kind([0] * total))
            peak = traced_peak(lambda nested=nested, start=start: sum(nested, start))
            assert final <= peak < 3 * final, (kind, total, peak, final)

    @pytest.mark.timing
    @pytest.mark.parametrize("kind", [list, tuple])
    def test_cost_depends_on_the_number_of_lists_at_a_fixed_total(self, kind: type) -> None:
        bushy = [kind([0] * 200) for _ in range(200)]
        flat = [kind([0] * 5) for _ in range(8_000)]
        start = kind()

        shape_gap = best_time(lambda: sum(flat, start)) / best_time(lambda: sum(bushy, start))

        assert 8 < shape_gap < 200, (
            f"x40 lists at a fixed total cost x{shape_gap:.1f}; O(N) predicts x1, O(n*N) x40"
        )

    @pytest.mark.timing
    @pytest.mark.parametrize("kind", [list, tuple])
    def test_cost_is_linear_in_the_total_at_a_fixed_number_of_lists(self, kind: type) -> None:
        short = [kind([0] * 10) for _ in range(1_000)]
        long = [kind([0] * 100) for _ in range(1_000)]
        start = kind()

        growth = best_time(lambda: sum(long, start)) / best_time(lambda: sum(short, start))

        assert 3 < growth < 30, f"x10 in elements at 1,000 lists cost x{growth:.1f}"

    @pytest.mark.timing
    def test_chain_and_the_comprehension_do_not_depend_on_shape(self) -> None:
        bushy = [[0] * 200 for _ in range(200)]
        flat = [[0] * 5 for _ in range(8_000)]

        chain_gap = best_time(lambda: list(chain.from_iterable(flat))) / best_time(
            lambda: list(chain.from_iterable(bushy))
        )
        comprehension_gap = best_time(
            lambda: [item for sublist in flat for item in sublist]
        ) / best_time(lambda: [item for sublist in bushy for item in sublist])

        assert chain_gap < 4, f"chain cost x{chain_gap:.1f} across shapes"
        assert comprehension_gap < 4, f"the comprehension cost x{comprehension_gap:.1f}"

    @pytest.mark.timing
    def test_chain_and_the_comprehension_are_linear_in_the_total(self) -> None:
        small = [[0] * 10 for _ in range(4_000)]
        large = [[0] * 10 for _ in range(40_000)]

        chain_growth = best_time(lambda: list(chain.from_iterable(large))) / best_time(
            lambda: list(chain.from_iterable(small))
        )
        comprehension_growth = best_time(
            lambda: [item for sublist in large for item in sublist]
        ) / best_time(lambda: [item for sublist in small for item in sublist])

        assert 3 < chain_growth < 30, f"x10 in elements cost chain x{chain_growth:.1f}"
        assert 3 < comprehension_growth < 30, (
            f"x10 in elements cost the comprehension x{comprehension_growth:.1f}"
        )


class TestStrings:
    """Row: a str, bytes or bytearray start raises TypeError; join is the tool."""

    @pytest.mark.parametrize(
        ("start", "message"),
        [
            ("", r"sum\(\) can't sum strings \[use ''\.join\(seq\) instead\]"),
            (b"", r"sum\(\) can't sum bytes \[use b''\.join\(seq\) instead\]"),
            (bytearray(), r"sum\(\) can't sum bytearray \[use b''\.join\(seq\) instead\]"),
        ],
        ids=["str", "bytes", "bytearray"],
    )
    def test_such_a_start_is_rejected(self, start: Any, message: str) -> None:
        with pytest.raises(TypeError, match=message):
            sum(["a", "b", "c"], start)

    def test_the_start_is_rejected_before_any_item_is_read(self) -> None:
        consumed = 0

        def items() -> Iterator[str]:
            nonlocal consumed
            for text in "abc":
                consumed += 1
                yield text

        with pytest.raises(TypeError):
            sum(items(), "")
        assert consumed == 0

    def test_without_a_start_the_first_add_is_int_plus_str(self) -> None:
        with pytest.raises(
            TypeError, match=r"unsupported operand type\(s\) for \+: 'int' and 'str'"
        ):
            sum(["a", "b", "c"])  # pyright: ignore[reportCallIssue, reportArgumentType]

    def test_join_gives_the_stated_result(self) -> None:
        assert "".join(["a", "b", "c", "d", "e"]) == "abcde"
        assert b"".join([b"a", b"b"]) == b"ab"


class Vector:
    """The page's class, with a call counter on __add__."""

    calls = 0

    def __init__(self, *components: int) -> None:
        self.components = components

    def __add__(self, other: "Vector") -> "Vector":
        Vector.calls += 1
        return Vector(*(a + b for a, b in zip(self.components, other.components, strict=True)))

    def __radd__(self, other: object) -> "Vector":
        if other == 0:
            return self
        return NotImplemented  # pyright: ignore[reportReturnType]

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Vector) and self.components == other.components

    __hash__ = None  # pyright: ignore[reportAssignmentType]

    def __repr__(self) -> str:
        return f"Vector{self.components}"


class TestCustomObjects:
    """Row: O(n*a), exactly one __add__ per item, the first one on start."""

    def test_dunder_add_runs_exactly_once_per_item(self) -> None:
        Vector.calls = 0
        vectors = [Vector(1, 2), Vector(3, 4), Vector(5, 6)]

        result = sum(vectors, Vector(0, 0))

        assert result == Vector(9, 12)
        assert repr(result) == "Vector(9, 12)"
        assert Vector.calls == 3

    def test_without_a_start_the_first_item_is_added_to_zero(self) -> None:
        Vector.calls = 0
        seen: list[object] = []

        class Recording(Vector):
            def __radd__(self, other: object) -> Vector:
                seen.append(other)
                return super().__radd__(other)

        result = sum([Recording(1, 2), Vector(3, 4)])

        assert result == Vector(4, 6)
        assert seen == [0]
        assert Vector.calls == 1

    def test_a_type_without_radd_needs_a_start(self) -> None:
        class Plain:
            def __add__(self, other: "Plain") -> "Plain":
                return self

        with pytest.raises(TypeError, match=r"unsupported operand type\(s\) for \+"):
            sum([Plain(), Plain()])  # pyright: ignore[reportCallIssue, reportArgumentType]
        assert isinstance(sum([Plain(), Plain()], Plain()), Plain)

    def test_each_intermediate_result_is_freed_as_the_next_replaces_it(self) -> None:
        import weakref

        made: list[weakref.ref[Vector]] = []
        alive_at_each_add: list[list[bool]] = []

        class Tracked(Vector):
            def __add__(self, other: Vector) -> Vector:
                alive_at_each_add.append([ref() is not None for ref in made])
                result = Tracked(
                    *(a + b for a, b in zip(self.components, other.components, strict=True))
                )
                made.append(weakref.ref(result))
                return result

        result = sum([Tracked(1, 1)] * 5, Tracked(0, 0))

        assert result == Vector(5, 5)
        assert alive_at_each_add == [
            [],
            [True],
            [False, True],
            [False, False, True],
            [False, False, False, True],
        ]
        assert [ref() is not None for ref in made] == [False, False, False, False, True]


class TestStatistics:
    """Prose: len() is O(1); counting with a second sum() iterates again."""

    def test_len_does_not_iterate_but_a_counting_sum_does(self) -> None:
        passes = 0

        class Data(list[int]):
            def __iter__(self) -> Iterator[int]:
                nonlocal passes
                passes += 1
                return super().__iter__()

        numbers = Data([1, 2, 3, 4, 5])

        assert sum(numbers) / len(numbers) == 3.0
        assert passes == 1
        assert sum(numbers) / sum(1 for _ in numbers) == 3.0
        assert passes == 3


class TestGeneratorSpace:
    """Prose: a generator argument is O(1) space, a list comprehension O(n)."""

    def test_the_generator_allocates_nothing_that_scales(self) -> None:
        peaks = {n: traced_peak(lambda n=n: sum(x for x in range(n))) for n in (10_000, 100_000)}
        assert peaks[100_000] < 4 * peaks[10_000], peaks
        assert peaks[100_000] < 10_000, peaks

    def test_the_list_allocates_every_item(self) -> None:
        peaks = {n: traced_peak(lambda n=n: sum(list(range(n)))) for n in (10_000, 100_000)}
        assert peaks[100_000] > 5 * peaks[10_000], peaks
        assert peaks[100_000] >= sys.getsizeof([0] * 100_000)

    def test_a_bool_generator_allocates_nothing_that_scales(self) -> None:
        peak = traced_peak(lambda: sum(x % 2 == 0 for x in range(100_000)))
        assert peak < 10_000, peak


class TestStatedExampleValues:
    """The values the page's comments give, checked rather than trusted."""

    def test_summing_numbers(self) -> None:
        assert sum([1, 2, 3, 4, 5]) == 15
        assert sum([1.5, 2.5, 3.0]) == 7.0
        assert sum(range(100)) == 4950
        assert sum((10, 20, 30)) == 60
        assert sum([1, 2, 3], start=100) == 106

    def test_generators(self) -> None:
        assert sum(x for x in range(10)) == 45
        assert sum(x**2 for x in range(5)) == 30

    def test_counting(self) -> None:
        assert sum([1 for x in range(100) if x % 2 == 0]) == 50
        assert sum(x % 2 == 0 for x in range(100)) == 50

    def test_wide_integers(self) -> None:
        assert sum(range(1000)) == 499500
        assert sum([10**300] * 1000) == 1000 * 10**300

    def test_start_values(self) -> None:
        assert sum([1, 2, 3]) == 6
        assert sum([1, 2, 3], start=10) == 16

    def test_loop_agrees_with_sum(self) -> None:
        numbers = list(range(10000))
        total = 0
        for num in numbers:
            total += num
        assert total == sum(numbers)

    def test_accumulate(self) -> None:
        assert list(accumulate([1, 2, 3, 4, 5])) == [1, 3, 6, 10, 15]


EXPECTED_BLOCKS = 12


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
        strings = next(source for _, source in _blocks() if "can't sum strings" in source)
        broken = strings.replace(
            "except TypeError:\n    pass  # sum()", "except ValueError:\n    pass  # sum()", 1
        )
        assert broken != strings, "the mutation did not change the handler"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "TypeError" in result.stderr
