"""Tests for docs/stdlib/deque.md.

`collections.deque` is the C type in Modules/_collectionsmodule.c on every
supported interpreter: a doubly linked chain of 64-pointer blocks
(`BLOCKLEN`), the left and right ends each holding a block and an index. That
layout is what the page's bounds follow from, and the block size is read from
source rather than measured. The same file also settles by source that
`insert()`, `del d[i]` and `remove()` are built on `_deque_rotate()`, that a
deque compares only with another deque (`deque_richcompare` returns
NotImplemented otherwise), that `+` copies the left operand and extends it
with the right, which must be a deque, that `+=` is `extend()`, and that
`*` and `*=` reduce their repeat count to what `maxlen` can hold. None of
that has moved between the v3.10.0 tag and the 3.14 branch.

The O(1) rows for the ends and for `len()` are timed in
tests/test_collections_complexity.py; this file settles the rest.

Counted with a `__eq__` that records its calls, on distinct objects that are
equal by value so `PyObject_RichCompareBool`'s identity shortcut does not
skip the comparison: `count()` compares every item, `in` and `remove()` stop
at the first match, `index(x, start, stop)` compares from `start` to the
match or to `stop`, and `==` compares to the first difference (that pair
twice, once for equality and once with the operator) and not at all when the
lengths differ or the other side is a list. A bounded deque built from a
generator is watched from inside it: no more than `maxlen` earlier items are
alive at any step, which is the O(k)-consumed, `maxlen`-held space row.

Observed directly: a bounded deque built or extended from an iterator
exhausts it and keeps the last `maxlen` items; `append()` on a full bounded
deque drops the opposite end while `insert()` raises `IndexError` and leaves
it unchanged; `extendleft()` reverses; `+=` returns the same object and `+`
a new one carrying the left operand's `maxlen`; `copy()`, `copy.copy()`,
`copy.deepcopy()` and a pickle round trip keep `maxlen`, the first two
sharing the items; `clear()` lets every item be collected; `d * k` matches
`deque(list(d) * k, maxlen)` across shapes, and only `*=` empties the
deque at a count of 0 or below, `*` handing back a fresh empty one; an `insert()` position past either end is
clamped to that end; a negative `stop` to `index()` is normalised before the
scan; an iterator, forward or reversed, raises `RuntimeError` after an
append, a pop or a rotate (the operations that bump `deque->state`) and
survives item assignment and `reverse()`, which do not; slicing and hashing
raise `TypeError`; `maxlen` cannot be assigned.

Timed on the pinned interpreter (aarch64, CPython 3.14) at n = 1,000,000:

* `d[i]` costs 30ns at i = 1 and at i = n - 2, and 48us at the middle, a
  x1,600 gap that a position-independent O(1) or O(n) would not show;
  `d[i] = x` follows the same shape;
* `insert()` costs 75ns at 1 and at n - 1 and 231us at the middle (x3,000);
  `del d[i]` 60ns, 66ns and 239us (x3,600);
* `iter()` and `reversed()` cost 50ns to create over ten items and over a
  million alike;
* `rotate()` costs 34ns for 1, 43ns for n - 1 and for n + 1, and 128us for
  n // 2 (x3,000), which is the modular k in the row;
* `deque(range(100)) * 100_000` costs 55ms and the same with `maxlen=100`
  0.7us (x80,000), the cap in the `*` row;
* the page's sliding window over 50,000 items costs 3.4ms for a width of 2
  and 60ms for 256 (x17), the O(n * window_size) it is annotated with;
* `list.pop(0)` on a million items costs 365us against 40ns for
  `deque.popleft()`, the comparison the page's benchmark block makes.

Thresholds sit at x50 for the position and cap gaps, which the measured
values clear by two to three orders of magnitude, and at x4 for the window
against its measured x17.

Not varied: the element type in the timing tests is int, the block size is
fixed by the interpreter, and `rotate()` is timed on one length only. The
`d < e` row is counted only on deques whose common prefix is equal. The
per-item cost of `copy.deepcopy()` and pickling is the items' own and is not
measured.
"""

import contextlib
import copy
import functools
import io
import itertools
import pathlib
import pickle
import queue
import re
import subprocess
import sys
import textwrap
import time
import typing
import weakref
from collections import deque
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "deque.md"

LARGE = 1_000_000
POSITION_FLOOR = 50.0
"""An end against the middle of a million items: measured x1,600 to x5,000."""
CAP_FLOOR = 50.0
"""A capped repeat against an uncapped one: measured x80,000."""
WINDOW_FLOOR = 4.0
"""Width 256 against width 2: measured x17; a flat helper would show x1."""
FLAT_CEILING = 3.0
"""Creating an iterator over ten items against a million: measured x1.0."""


def best_time(func: Callable[[], Any], repeats: int = 5, loops: int = 1) -> float:
    """The fastest of several runs of `loops` calls."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        for _ in range(loops):
            func()
        times.append(time.perf_counter() - start)
    return min(times)


class Equal:
    """Equal by value; every __eq__ call is counted on the class."""

    calls = 0

    def __init__(self, value: int) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        Equal.calls += 1
        return isinstance(other, Equal) and self.value == other.value


def comparisons(func: Callable[[], Any]) -> int:
    Equal.calls = 0
    func()
    return Equal.calls


def equal_items(count: int) -> deque[Equal]:
    return deque(Equal(value) for value in range(count))


@pytest.fixture(scope="module")
def million() -> deque[int]:
    return deque(range(LARGE))


class TestConstruction:
    """Row: deque(iterable, maxlen) is O(k) time, O(min(k, maxlen)) space."""

    def test_a_bounded_deque_consumes_the_whole_iterable(self) -> None:
        source = iter(range(10_000))

        d = deque(source, maxlen=3)

        assert list(d) == [9997, 9998, 9999]
        assert next(source, None) is None, "every item was consumed"

    def test_a_bounded_deque_never_holds_more_than_maxlen(self) -> None:
        """Observed from inside the iterable: at each step, how many earlier
        items are still alive."""

        class Item:
            pass

        refs: list[weakref.ref[Item]] = []
        peaks: list[int] = []

        def items() -> Iterator[Item]:
            for _ in range(1000):
                peaks.append(sum(ref() is not None for ref in refs))
                item = Item()
                refs.append(weakref.ref(item))
                yield item

        d = deque(items(), maxlen=3)

        assert len(d) == 3
        assert max(peaks) == 3, f"most earlier items alive at once: {max(peaks)}"

    def test_the_bound_is_kept(self) -> None:
        assert deque(range(10), maxlen=3).maxlen == 3
        assert deque(range(10)).maxlen is None


class TestEnds:
    """Rows: append/appendleft and pop/popleft, and what a bound does to them."""

    def test_append_on_a_full_bounded_deque_drops_the_opposite_end(self) -> None:
        d = deque([1, 2, 3], maxlen=3)

        d.append(4)
        assert list(d) == [2, 3, 4]

        d.appendleft(0)
        assert list(d) == [0, 2, 3]

    def test_pop_on_an_empty_deque_raises(self) -> None:
        d: deque[int] = deque()

        with pytest.raises(IndexError):
            d.pop()
        with pytest.raises(IndexError):
            d.popleft()


class TestIndexing:
    """Row: d[i] and d[i] = x are O(min(i, n - i)); no slicing."""

    @pytest.mark.timing
    def test_the_middle_costs_far_more_than_either_end(self, million: deque[int]) -> None:
        d = million
        middle = LARGE // 2

        near_left = best_time(lambda: d[1], loops=1000)
        near_right = best_time(lambda: d[-2], loops=1000)
        centre = best_time(lambda: d[middle], loops=1000)

        assert centre / near_left > POSITION_FLOOR, (
            f"d[1] {near_left:.2e}s vs d[n//2] {centre:.2e}s ({centre / near_left:.0f}x)"
        )
        assert centre / near_right > POSITION_FLOOR, (
            f"d[-2] {near_right:.2e}s vs d[n//2] {centre:.2e}s ({centre / near_right:.0f}x)"
        )

    @pytest.mark.timing
    def test_assignment_follows_the_same_shape(self, million: deque[int]) -> None:
        d = million
        middle = LARGE // 2

        def set_near() -> None:
            d[1] = 1

        def set_middle() -> None:
            d[middle] = middle

        near = best_time(set_near, loops=1000)
        centre = best_time(set_middle, loops=1000)

        assert centre / near > POSITION_FLOOR, (
            f"d[1] = x {near:.2e}s vs d[n//2] = x {centre:.2e}s ({centre / near:.0f}x)"
        )

    def test_a_slice_raises(self) -> None:
        d: Any = deque(range(5))

        with pytest.raises(TypeError):
            _ = d[1:3]

    def test_islice_iterates_from_the_left(self) -> None:
        """The page's replacement for a slice: O(max(start, stop)), never O(stop - start)."""
        d = deque(range(100))
        steps = 0

        def counted() -> Iterator[int]:
            nonlocal steps
            for item in d:
                steps += 1
                yield item

        assert list(itertools.islice(counted(), 40, 43)) == [40, 41, 42]
        assert steps == 43

        steps = 0
        assert list(itertools.islice(counted(), 90, 3)) == []
        assert steps == 90, "a start past stop is still walked to"


class TestPositionalEdits:
    """Rows: del d[i] and insert(i, x) are O(min(i, n - i)); remove(x) is O(n)."""

    @staticmethod
    def _gaps(edit: Callable[[int], None]) -> tuple[float, float, float]:
        """Time `edit` at 1, at n - 1 and at the middle of a million items."""
        middle = LARGE // 2
        near_left = best_time(lambda: edit(1), loops=100)
        near_right = best_time(lambda: edit(LARGE - 1), loops=100)
        centre = best_time(lambda: edit(middle), loops=100)
        return near_left, near_right, centre

    @pytest.mark.timing
    def test_insert_costs_the_distance_to_the_nearer_end(self, million: deque[int]) -> None:
        d = million

        def insert(position: int) -> None:
            d.insert(position, 0)
            d.pop()

        near_left, near_right, centre = self._gaps(insert)

        assert centre / near_left > POSITION_FLOOR, (
            f"insert(1) {near_left:.2e}s vs insert(n//2) {centre:.2e}s ({centre / near_left:.0f}x)"
        )
        assert centre / near_right > POSITION_FLOOR, (
            f"insert(n-1) {near_right:.2e}s vs insert(n//2) {centre:.2e}s "
            f"({centre / near_right:.0f}x)"
        )

    @pytest.mark.timing
    def test_delete_costs_the_distance_to_the_nearer_end(self, million: deque[int]) -> None:
        d = million

        def delete(position: int) -> None:
            del d[position]
            d.append(0)

        near_left, near_right, centre = self._gaps(delete)

        assert centre / near_left > POSITION_FLOOR, (
            f"del d[1] {near_left:.2e}s vs del d[n//2] {centre:.2e}s ({centre / near_left:.0f}x)"
        )
        assert centre / near_right > POSITION_FLOOR, (
            f"del d[n-1] {near_right:.2e}s vs del d[n//2] {centre:.2e}s "
            f"({centre / near_right:.0f}x)"
        )

    def test_an_out_of_range_position_is_clamped_to_an_end(self) -> None:
        d = deque([1, 2, 3])

        d.insert(10**6, 4)
        d.insert(-(10**6), 0)

        assert list(d) == [0, 1, 2, 3, 4]

    def test_insert_on_a_full_bounded_deque_raises_and_changes_nothing(self) -> None:
        d = deque([1, 2, 3], maxlen=3)

        with pytest.raises(IndexError):
            d.insert(1, 0)

        assert list(d) == [1, 2, 3]

    def test_remove_compares_up_to_the_first_match(self) -> None:
        d = equal_items(100)

        assert comparisons(lambda: d.remove(Equal(30))) == 31
        assert [item.value for item in d][:31] == [*range(30), 31]

    def test_a_missing_value_costs_every_comparison(self) -> None:
        d = equal_items(100)

        with pytest.raises(ValueError):
            comparisons(lambda: d.remove(Equal(-1)))

        assert Equal.calls == 100


class TestExtend:
    """Rows: extend/extendleft, += and + are O(k); + is a new deque."""

    def test_extend_consumes_every_item_even_when_bounded(self) -> None:
        d: deque[int] = deque(maxlen=3)
        source = iter(range(10_000))

        d.extend(source)

        assert list(d) == [9997, 9998, 9999]
        assert next(source, None) is None

    def test_extendleft_reverses(self) -> None:
        d = deque([1, 2, 3])

        d.extendleft([0, -1])

        assert list(d) == [-1, 0, 1, 2, 3]

    def test_extending_with_itself_doubles(self) -> None:
        d = deque([1, 2])

        d.extend(d)

        assert list(d) == [1, 2, 1, 2]

    def test_inplace_concat_is_extend(self) -> None:
        d = deque([1, 2])
        before = d

        d += [3, 4]

        assert d is before
        assert list(d) == [1, 2, 3, 4]

    def test_concat_builds_a_new_deque_with_the_left_bound(self) -> None:
        d = deque([1, 2], maxlen=2)

        joined = d + deque([3])

        assert joined is not d
        assert list(joined) == [2, 3]
        assert joined.maxlen == 2
        assert list(d) == [1, 2]

    def test_concat_needs_a_deque_on_the_right(self) -> None:
        d: Any = deque([1])

        with pytest.raises(TypeError):
            _ = d + [2]


class TestRotate:
    """Row: rotate(n) is O(min(n mod len, len - n mod len))."""

    @pytest.mark.timing
    def test_one_step_either_way_or_a_full_turn_less_one_is_cheap(
        self, million: deque[int]
    ) -> None:
        d = million

        one = best_time(lambda: d.rotate(1), loops=100)
        nearly_all = best_time(lambda: d.rotate(LARGE - 1), loops=100)
        over = best_time(lambda: d.rotate(LARGE + 1), loops=100)
        half = best_time(lambda: d.rotate(LARGE // 2), loops=100)

        for label, cheap in (("1", one), ("n-1", nearly_all), ("n+1", over)):
            assert half / cheap > POSITION_FLOOR, (
                f"rotate({label}) {cheap:.2e}s vs rotate(n//2) {half:.2e}s ({half / cheap:.0f}x)"
            )

    def test_the_documented_rotations(self) -> None:
        d = deque([1, 2, 3, 4, 5])

        d.rotate(2)
        assert list(d) == [4, 5, 1, 2, 3]

        d.rotate(-1)
        assert list(d) == [5, 1, 2, 3, 4]

        d.rotate(5)
        assert list(d) == [5, 1, 2, 3, 4], "a full turn is the identity"


class TestScans:
    """Rows: count(x), x in d and index(x, start, stop)."""

    def test_count_compares_every_item(self) -> None:
        d = equal_items(100)

        assert comparisons(lambda: d.count(Equal(5))) == 100

    def test_membership_stops_at_the_first_match(self) -> None:
        d = equal_items(100)

        assert comparisons(lambda: Equal(30) in d) == 31
        assert comparisons(lambda: Equal(-1) in d) == 100

    def test_index_compares_from_start_to_the_match(self) -> None:
        d = equal_items(100)

        assert comparisons(lambda: d.index(Equal(30), 10)) == 21

    def test_index_compares_from_start_to_stop_when_missing(self) -> None:
        d = equal_items(100)

        with pytest.raises(ValueError):
            comparisons(lambda: d.index(Equal(-1), 10, 40))

        assert Equal.calls == 30

    def test_a_negative_stop_is_normalised_first(self) -> None:
        d = equal_items(100)

        with pytest.raises(ValueError):
            comparisons(lambda: d.index(Equal(-1), 0, -60))

        assert Equal.calls == 40

    def test_the_identity_shortcut_skips_eq(self) -> None:
        """Which is why the counted tests use distinct, equal objects."""
        d = equal_items(100)
        present = d[0]

        assert comparisons(lambda: d.count(present)) == 99


class TestCopies:
    """Rows: copy(), copy.copy(), copy.deepcopy() and pickle are O(n) and keep maxlen."""

    def test_copy_shares_the_items_and_keeps_the_bound(self) -> None:
        d = deque([[1], [2]], maxlen=5)

        for duplicate in (d.copy(), copy.copy(d)):
            assert duplicate is not d
            assert all(a is b for a, b in zip(duplicate, d, strict=True))
            assert duplicate.maxlen == 5

    def test_copy_keeps_a_subclass(self) -> None:
        class Sub(deque[int]):
            pass

        assert type(Sub([1]).copy()) is Sub

    def test_deepcopy_and_pickle_rebuild_the_items_and_keep_the_bound(self) -> None:
        d = deque([[1], [2]], maxlen=5)

        for duplicate in (copy.deepcopy(d), pickle.loads(pickle.dumps(d))):
            assert duplicate == d
            assert not any(a is b for a, b in zip(duplicate, d, strict=True))
            assert duplicate.maxlen == 5


class TestClear:
    """Row: clear() is O(n) and releases every item."""

    def test_every_item_is_released(self) -> None:
        class Item:
            pass

        d = deque(Item() for _ in range(100))
        refs = [weakref.ref(item) for item in d]

        d.clear()

        assert len(d) == 0
        assert all(ref() is None for ref in refs)


class TestRepeat:
    """Row: d * k and d *= k are O(n * k), capped by maxlen."""

    @pytest.mark.parametrize(
        ("items", "maxlen", "k"),
        [
            ([1, 2], None, 3),
            ([1, 2], 3, 5),
            ([7], 3, 100),
            ([1, 2, 3], 1, 4),
            ([1, 2], 3, 0),
            ([], 3, 4),
        ],
    )
    def test_matches_the_capped_list_repeat(
        self, items: list[int], maxlen: int | None, k: int
    ) -> None:
        assert deque(items, maxlen=maxlen) * k == deque(items * k, maxlen=maxlen)

    def test_only_the_inplace_form_empties_the_deque(self) -> None:
        d = deque([1, 2])

        empty = d * 0

        assert list(empty) == []
        assert empty is not d
        assert list(d) == [1, 2]

        d *= 0

        assert list(d) == []

        d = deque([1, 2])
        d *= -1

        assert list(d) == []

    def test_inplace_repeat_keeps_the_object(self) -> None:
        d = deque([1, 2])
        before = d

        d *= 3

        assert d is before
        assert list(d) == [1, 2, 1, 2, 1, 2]

    @pytest.mark.timing
    def test_a_bound_caps_the_work(self) -> None:
        unbounded = deque(range(100))
        bounded = deque(range(100), maxlen=100)

        uncapped = best_time(lambda: unbounded * 100_000, repeats=3)
        capped = best_time(lambda: bounded * 100_000, repeats=3, loops=100) / 100

        assert uncapped / capped > CAP_FLOOR, (
            f"unbounded {uncapped:.2e}s vs maxlen=100 {capped:.2e}s ({uncapped / capped:.0f}x)"
        )


class TestComparison:
    """Row: == and < compare to the first difference, only against a deque."""

    def test_equal_deques_compare_every_item(self) -> None:
        d, e = equal_items(50), equal_items(50)

        assert comparisons(lambda: d == e) == 50

    def test_a_difference_stops_the_comparison(self) -> None:
        """The differing pair is compared twice: for equality, then with the operator."""
        d, e = equal_items(50), equal_items(50)
        e[3] = Equal(-1)

        assert comparisons(lambda: d == e) == 3 + 2

    def test_unequal_lengths_compare_nothing(self) -> None:
        d, e = equal_items(50), equal_items(51)

        assert comparisons(lambda: d == e) == 0
        assert comparisons(lambda: d != e) == 0

    def test_ordering_walks_the_common_prefix(self) -> None:
        d, e = equal_items(50), equal_items(51)

        assert comparisons(lambda: d < e) == 50

    def test_a_list_is_never_equal_and_never_compared(self) -> None:
        d = equal_items(3)

        assert comparisons(lambda: d == list(d)) == 0
        assert d != list(d)
        assert deque([1]) != [1]

    def test_unhashable(self) -> None:
        with pytest.raises(TypeError):
            hash(deque())


class TestIteration:
    """Row: iter(d) and reversed(d) are O(n) and fail on mutation."""

    def test_forward_iteration_fails_once_the_deque_changes(self) -> None:
        d = deque(range(3))
        it = iter(d)
        next(it)

        d.append(9)

        with pytest.raises(RuntimeError):
            next(it)

    def test_reversed_iteration_fails_once_the_deque_changes(self) -> None:
        d = deque(range(3))
        it = reversed(d)
        next(it)

        d.popleft()

        with pytest.raises(RuntimeError):
            next(it)

    def test_assignment_and_reverse_leave_the_iterator_valid(self) -> None:
        d = deque(range(5))
        it = iter(d)
        next(it)

        d[2] = 9
        d.reverse()

        assert list(it) == [3, 9, 1, 0], "the rest of the walk, over the changed slots"

    def test_rotate_invalidates_the_iterator(self) -> None:
        d = deque(range(5))
        it = iter(d)
        next(it)

        d.rotate(1)

        with pytest.raises(RuntimeError):
            next(it)

    @pytest.mark.timing
    def test_creating_an_iterator_does_not_scale(self, million: deque[int]) -> None:
        small = deque(range(10))

        for label, make in (("iter", iter), ("reversed", reversed)):
            tiny = best_time(functools.partial(make, small), loops=10_000)
            huge = best_time(functools.partial(make, million), loops=10_000)

            assert huge / tiny < FLAT_CEILING, (
                f"{label}() over 10 {tiny:.2e}s vs over a million {huge:.2e}s ({huge / tiny:.1f}x)"
            )

    def test_both_directions_visit_every_item(self) -> None:
        d = deque(range(200))

        assert list(d) == list(range(200))
        assert list(reversed(d)) == list(range(199, -1, -1))


class TestMaxlen:
    """Row: maxlen is read-only."""

    def test_cannot_be_assigned(self) -> None:
        d: deque[int] = deque(maxlen=3)

        with pytest.raises(AttributeError):
            d.__setattr__("maxlen", 5)

        assert d.maxlen == 3


class TestVersionNotesAndRelated:
    """The Version Notes name methods that exist; queue.Queue holds a deque."""

    def test_the_named_methods_exist(self) -> None:
        for name in ("count", "reverse", "copy", "index", "insert"):
            assert callable(getattr(deque, name)), name

    def test_the_generic_alias(self) -> None:
        assert typing.get_origin(deque[int]) is deque

    def test_queue_is_built_on_a_deque(self) -> None:
        assert isinstance(queue.Queue().queue, deque)


class TestPublicNamesAreDocumented:
    """The Complexity Reference against dir(deque)."""

    @staticmethod
    def documented_names() -> set[str]:
        text = PAGE.read_text(encoding="utf-8")
        start = text.index("## Complexity Reference")
        end = text.index("## Basic Usage")
        names: set[str] = set()
        for line in text[start:end].splitlines():
            if not line.startswith("| `"):
                continue
            names.update(re.findall(r"\bd\.(\w+)", line.split("|")[1]))
        return names

    def test_the_extractor_sees_the_table(self) -> None:
        assert {"rotate", "maxlen", "extendleft"} <= self.documented_names()

    def test_every_public_name_has_a_row(self) -> None:
        public = {name for name in dir(deque) if not name.startswith("_")}

        missing = public - self.documented_names()

        assert not missing, f"public names without a row: {sorted(missing)}"

    def test_every_row_names_something_that_exists(self) -> None:
        public = {name for name in dir(deque) if not name.startswith("_")}

        invented = self.documented_names() - public

        assert not invented, f"rows naming nothing that exists: {sorted(invented)}"


EXPECTED_BLOCKS = 10


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


def _page_function(name: str, **bindings: Any) -> Callable[..., Any]:
    """The function `name` as the page defines it, with the block's usage run silently."""
    source = next(source for _, source in _blocks() if f"def {name}(" in source)
    namespace: dict[str, Any] = dict(bindings)
    with contextlib.redirect_stdout(io.StringIO()):
        exec(source, namespace)
    return namespace[name]


class TestDocumentedExamples:
    """Every block runs, and the results the comments state are the results."""

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
        source = next(source for _, source in _blocks() if "def bfs(" in source)
        broken = source.replace("visited = set()", "visited_ = set()", 1)
        assert broken != source, "the mutation did not rename the set"
        broken += "\nbfs({1: [2], 2: []}, 1)\n"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr

    def test_the_extend_block_ends_as_its_comment_says(self) -> None:
        d = deque([1, 2, 3])
        d.extend([4, 5, 6])
        d.extendleft([0, -1])

        assert list(d) == [-1, 0, 1, 2, 3, 4, 5, 6]

    def test_the_maxlen_block_drops_the_oldest(self) -> None:
        d: deque[int] = deque(maxlen=3)
        seen: list[list[int]] = []
        for value in (1, 2, 3, 4):
            d.append(value)
            seen.append(list(d))

        assert seen == [[1], [1, 2], [1, 2, 3], [2, 3, 4]]

    @pytest.mark.timing
    def test_the_benchmark_block_favours_the_deque(self) -> None:
        lst = list(range(LARGE))
        dq = deque(range(LARGE))

        list_time = best_time(lambda: lst.pop(0), repeats=3, loops=100)
        deque_time = best_time(lambda: dq.popleft(), repeats=3, loops=100)

        assert list_time / deque_time > POSITION_FLOOR, (
            f"list.pop(0) {list_time:.2e}s vs popleft() {deque_time:.2e}s "
            f"({list_time / deque_time:.0f}x)"
        )


class TestSlidingWindowExample:
    """The page's sliding_window: n - w + 1 tuples, and O(n * w) because of them."""

    def test_yields_every_window(self) -> None:
        sliding_window = _page_function("sliding_window")

        windows = list(sliding_window(range(10), 3))

        assert windows == [(i, i + 1, i + 2) for i in range(8)]
        assert len(windows) == 10 - 3 + 1

    def test_a_short_input_yields_nothing(self) -> None:
        sliding_window = _page_function("sliding_window")

        assert list(sliding_window(range(2), 3)) == []

    @pytest.mark.timing
    def test_the_width_is_paid_on_every_step(self) -> None:
        sliding_window = _page_function("sliding_window")

        def drain(width: int) -> Callable[[], None]:
            def run() -> None:
                deque(sliding_window(range(50_000), width), maxlen=0)

            return run

        narrow = best_time(drain(2), repeats=3)
        wide = best_time(drain(256), repeats=3)

        assert wide / narrow > WINDOW_FLOOR, (
            f"w=2 {narrow:.2e}s vs w=256 {wide:.2e}s ({wide / narrow:.1f}x)"
        )


class TestBreadthFirstSearchExample:
    """The page's bfs: every reachable vertex, nothing else."""

    def test_finds_the_reachable_set(self) -> None:
        bfs = _page_function("bfs")
        graph = {1: [2, 3], 2: [4], 3: [4], 4: [1], 5: [1]}

        assert bfs(graph, 1) == {1, 2, 3, 4}
        assert bfs(graph, 5) == {1, 2, 3, 4, 5}

    def test_visits_in_breadth_order(self) -> None:
        order: list[int] = []

        class Recording(set[int]):
            def add(self, element: int) -> None:
                order.append(element)
                super().add(element)

        bfs = _page_function("bfs", set=Recording)
        graph = {1: [2, 3], 2: [4], 3: [5], 4: [], 5: []}

        bfs(graph, 1)

        assert order == [1, 2, 3, 4, 5]
