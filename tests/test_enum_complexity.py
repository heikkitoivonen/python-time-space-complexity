"""Tests for docs/stdlib/enum.md.

The page prices an enum as one expensive build followed by cheap reads: the
class body checks every value against the ones before it, and lookups by name
and by hashable value are dictionary reads. Nearly every row is settled by
counting: member values are an `int` or `list` subclass whose `__eq__` counts
calls, so a dictionary probe shows up as at most one comparison and a scan as
one per member, with no tolerance. Views and caches are settled by identity.

Measurement scope:

* Building: an `Enum` of 100 and of 400 counting-`int` values makes exactly
  n(n - 1)/2 comparisons on 3.10 and from 3.13.1, and none on 3.11 to 3.13.0.
  The same sizes with counting-`list` values make exactly n(n - 1)/2 on every
  version. A class built through `__prepare__` with 50 `auto()` members hands
  `_generate_next_value_` 50 distinct lists of 0 to 49 values, 1,225 in all;
  the functional API with a list of 50 names does the same. An `_order_` of
  100 and of 400 counting-`str` names makes at least n(n + 1)/2 comparisons
  from 3.11 and at most 2n on 3.10.
* `C(value)` makes at most one comparison for a hashable value at 10 and
  1,000 members, first member or last. An unhashable value at 10 and 100
  members makes index + 1 comparisons to find a member and between n and 2n
  to miss. `C['NAME']` with a counting `str` key makes at most one comparison
  at 10 and 1,000 members.
* `value in C` with a raw counting `int`: before 3.12 it raises `TypeError`
  under a `DeprecationWarning`; on 3.12.x it makes at most one comparison;
  from 3.13.4 it makes exactly n comparisons at 10 and 100 members, hit or
  miss. `C(value)` stays at one comparison at the same sizes on every version.
  An unhashable raw value raises `TypeError` on 3.12.0 to 3.12.9 and is
  answered from 3.12.10. In an enum of 10 counting-`int` and 30
  counting-`list` values, a plain `int` miss makes 30 comparisons on 3.12, none
  on 3.13.0 to 3.13.2, and 40 from 3.13.4.
* `C.__members__` is a `MappingProxyType` that sees a key added to the
  backing map after it was taken, so it is a view, not a copy. `len(C)` and
  name lookup are timed at 10 and 1,000 members (under 3x); iteration yields
  the canonical members only, `reversed()` yields them backwards, and
  `dir()` is sorted and lists a canonical name but not its alias.
* Flags: `a | b` returns the same object twice, and the class's value map
  grows by one for a new combination and not for a repeat; 1,000 distinct
  `IntFlag` values grow it by at least 1,000. On 3.11+ `~flag` is stored on
  the operand, `len(flag)` answers with the class's member iterator replaced
  by one that raises, and iteration yields the b members set, in definition
  order for a class defined out of value order. `~flag` of a value holding
  every member, at 20 and 60 single-bit members with a counting `__eq__`,
  makes exactly n(n - 1)/2 comparisons on each of two calls on 3.10, and
  none from 3.11.
* `verify(CONTINUOUS)` on a two-member `Enum` valued 0 and r: the traced peak
  grows more than 5x from r = 100,000 to r = 1,000,000. It runs serially, so
  xdist's I/O thread cannot add to the peak.
* `EnumDict.member_names` is a fresh list on each access, including aliases;
  a counting backing dictionary is visited once per name at 0, 10 and 1,000
  names. `EnumDict.update()` resolves `auto()` and aliases as the class body
  does. `_add_value_alias_()` makes at most one comparison for a hashable
  value and n for an unhashable one, at 10 and 100 members.
* `show_flag_values()`, `global_flag_repr()`, `enum.bin()` and `unique()` are
  asserted by what they return or raise: b powers of two, a combination's
  2 and 16 names each module-qualified and a named combination kept whole,
  `max_bits` digits after the sign, every alias named.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The O(n) cost of making a new flag combination for the first time is read
  from Lib/enum.py: `_decompose()` walks the canonical members on 3.10, and
  from 3.11 `Flag._missing_()` walks the bits set plus, when the value covers
  a multi-bit alias, every member. Only the caching is observed.
* `~flag`'s first call is priced from the same source; its cache is observed.
* The default `_generate_next_value_()` sorts the values it is handed from
  3.11 and walks back from the last one on 3.10; that the sort is linear
  when they ascend is Timsort's, not measured here.
* On 3.10 a first-time combination sorts the members it contains
  (`_decompose()`), and from 3.11 iterating a flag defined out of value order
  sorts the members set (`_iter_member_by_def_()`); both log factors are read
  from Lib/enum.py, and only the iteration order is observed.
* `dir(C)` is O(n log n) because `dir()` sorts; only that every member name is
  in it is asserted.
* `verify(UNIQUE)` and `verify(NAMED_FLAGS)` being O(n) is read from
  Lib/enum.py; `NAMED_FLAGS` scans the canonical members, which machine-word
  flag values bound. Neither is varied in n.
* The cost model takes flag values to be machine-word integers; wide
  `IntFlag` values make each bitwise operation O(w) and are not varied.
* Custom `_missing_()`, `__new__`, `__init__`, `__hash__` and `__eq__` costs
  are outside the bounds and are not varied beyond the counting values above.
* `value in C` on 3.13.3, which scans only for a value with no member, is
  read from that release's Lib/enum.py; no 3.13.3 interpreter is run.
* The audit lists `EnumDict.update`, the `global_*` helpers and the
  `pickle_by_*` helpers under needs-classification, as names found in
  `__all__` or at run time but not in the official inventory; each has a row.
  `enum.property.member` is listed there too and has none: it is an
  undocumented attribute the module sets on its own descriptors.
"""

from __future__ import annotations

import enum
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import types
from collections.abc import Callable
from enum import Enum, Flag, IntFlag, auto, unique
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "enum.md"
EXPECTED_BLOCKS = 8

# The module as Any, so 3.11+ names type-check against pyright's 3.10 floor.
ENUM: Any = enum


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


class Counter:
    """How many times a counting value's `__eq__` has run."""

    calls = 0


class CountingInt(int):
    __hash__ = int.__hash__

    def __eq__(self, other: object) -> bool:
        Counter.calls += 1
        return int.__eq__(self, other)


class CountingList(list[int]):
    def __eq__(self, other: object) -> bool:
        Counter.calls += 1
        return list.__eq__(self, other)


class CountingStr(str):
    __hash__ = str.__hash__

    def __eq__(self, other: object) -> bool:
        Counter.calls += 1
        return str.__eq__(self, other)


def counted(func: Callable[[], Any]) -> int:
    """Comparisons the counting values make while func runs."""
    Counter.calls = 0
    func()
    return Counter.calls


def numbered(size: int, label: str = "E") -> Any:
    """An Enum of `size` members, valued 0 through size - 1."""
    return Enum(f"{label}{size}", {f"M{index}": index for index in range(size)})


def counting_ints(size: int) -> Any:
    return Enum(f"I{size}", {f"M{index}": CountingInt(index) for index in range(size)})


def counting_lists(size: int) -> Any:
    return Enum(f"L{size}", {f"M{index}": CountingList([index]) for index in range(size)})


QUADRATIC_BUILD = sys.version_info < (3, 11) or sys.version_info >= (3, 13, 1)


class TestBuildingChecksEachValueAgainstTheEarlierOnes:
    """`class C(enum.Enum)` and the functional API | O(n²) | O(n).

    Each value is checked against the ones before it: by a list scan on 3.10
    and from 3.13.1, by the value dictionary on 3.11 to 3.13.0, and by a scan
    on every version when the value is unhashable. Counting comparisons
    separates n²/2 from n with no tolerance.
    """

    @pytest.mark.parametrize("size", [100, 400])
    def test_hashable_values(self, size: int) -> None:
        comparisons = counted(lambda: counting_ints(size))

        if QUADRATIC_BUILD:
            assert comparisons == size * (size - 1) // 2
        else:
            assert comparisons == 0

    @pytest.mark.parametrize("size", [100, 400])
    def test_unhashable_values_on_every_version(self, size: int) -> None:
        assert counted(lambda: counting_lists(size)) == size * (size - 1) // 2

    def test_each_auto_is_handed_a_fresh_copy_of_the_values_before_it(self) -> None:
        handed: list[list[Any]] = []

        class Recording(Enum):
            @staticmethod
            def _generate_next_value_(
                name: str, start: int, count: int, last_values: list[Any]
            ) -> Any:
                handed.append(last_values)
                return count

        meta: Any = type(Recording)
        namespace = meta.__prepare__("Auto", (Recording,))
        for index in range(50):
            namespace[f"M{index}"] = auto()
        built = meta("Auto", (Recording,), namespace)

        assert [len(values) for values in handed] == list(range(50))
        assert len({id(values) for values in handed}) == 50
        assert [member.value for member in built] == list(range(50))

    def test_the_functional_api_numbers_names_the_same_way(self) -> None:
        handed: list[list[Any]] = []

        class Recording(Enum):
            @staticmethod
            def _generate_next_value_(
                name: str, start: int, count: int, last_values: list[Any]
            ) -> Any:
                handed.append(last_values)
                return count

        built: Any = Recording("Names", [f"M{index}" for index in range(50)])

        assert [len(values) for values in handed] == list(range(50))
        assert len({id(values) for values in handed}) == 50
        assert len(built) == 50

    def test_the_default_counts_up_from_one(self) -> None:
        assert [member.value for member in Enum("Color", "RED GREEN BLUE")] == [1, 2, 3]

    @pytest.mark.parametrize("size", [100, 400])
    def test_order_looks_each_name_up_in_the_member_list(self, size: int) -> None:
        meta: Any = type(Enum)
        namespace = meta.__prepare__("Ordered", (Enum,))
        namespace["_order_"] = [CountingStr(f"M{index}") for index in range(size)]
        for index in range(size):
            namespace[f"M{index}"] = index

        comparisons = counted(lambda: meta("Ordered", (Enum,), namespace))

        if sys.version_info >= (3, 11):
            assert comparisons >= size * (size + 1) // 2
        else:
            assert comparisons <= 2 * size

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="EnumType is the 3.11+ name")
    def test_enum_meta_is_the_same_metaclass(self) -> None:
        assert ENUM.EnumType is enum.EnumMeta is type(Enum)


class TestLookingMembersUp:
    """`C.NAME`, `C['NAME']` | O(1); `C(value)` | O(1) expected, O(n) unhashable."""

    @pytest.mark.parametrize("size", [10, 1_000])
    def test_a_hashable_value_is_one_probe_first_or_last(self, size: int) -> None:
        cls = counting_ints(size)

        for index in (0, size - 1):
            found: list[Any] = []
            assert counted(lambda i=index, f=found: f.append(cls(CountingInt(i)))) <= 1
            assert found[0] is cls[f"M{index}"]

    @pytest.mark.parametrize("size", [10, 1_000])
    def test_a_name_is_one_probe(self, size: int) -> None:
        cls = counting_ints(size)

        assert counted(lambda: cls[CountingStr(f"M{size - 1}")]) <= 1
        assert cls[f"M{size - 1}"] is getattr(cls, f"M{size - 1}")

    @pytest.mark.parametrize("kind", [list, dict])
    @pytest.mark.parametrize("size", [10, 100])
    def test_an_unhashable_value_is_compared_with_each_member(self, kind: type, size: int) -> None:
        class Value(kind):
            def __eq__(self, other: object) -> bool:
                Counter.calls += 1
                return super().__eq__(other)

        def value(index: int) -> Any:
            return Value([index] if kind is list else {"v": index})

        cls: Any = Enum("Values", {f"M{i}": value(i) for i in range(size)})
        for index in (0, size - 1):
            found: list[Any] = []
            assert counted(lambda i=index, f=found: f.append(cls(value(i)))) == index + 1
            assert found[0] is cls[f"M{index}"]

        def miss() -> None:
            with pytest.raises(ValueError, match="is not a valid"):
                cls(value(-1))

        assert size <= counted(miss) <= 2 * size

    def test_a_value_with_no_member_calls_missing_then_raises(self) -> None:
        asked: list[Any] = []

        class Color(Enum):
            RED = 1

            @classmethod
            def _missing_(cls, value: object) -> Any:
                asked.append(value)
                return None

        with pytest.raises(ValueError, match="is not a valid"):
            Color(2)
        assert asked == [2]
        assert Enum._missing_(2) is None

    @pytest.mark.timing
    def test_a_hundred_times_the_members_costs_the_same_by_name(self) -> None:
        small, large = numbered(10, "SN"), numbered(1_000, "LN")

        small_ns = best_ns(lambda: small["M5"], inner=200)
        large_ns = best_ns(lambda: large["M5"], inner=200)

        ratio = large_ns / small_ns
        assert ratio < 3, f"100x the members cost x{ratio:.2f} ({small_ns:.0f}ns, {large_ns:.0f}ns)"


class TestIterationAndLength:
    """`iter(C)`, `reversed(C)` | O(n); `len(C)` | O(1); aliases are skipped."""

    class Color(Enum):
        RED = 1
        CRIMSON = 1
        GREEN = 2

    def test_iteration_skips_aliases(self) -> None:
        assert [member.name for member in self.Color] == ["RED", "GREEN"]
        assert [member.name for member in reversed(self.Color)] == ["GREEN", "RED"]
        assert len(self.Color) == 2

    def test_an_alias_resolves_to_its_canonical_member(self) -> None:
        assert self.Color.CRIMSON is self.Color.RED
        assert self.Color["CRIMSON"] is self.Color.RED

    def test_dir_lists_the_canonical_names_sorted(self) -> None:
        cls = numbered(100, "D")

        listing = dir(cls)
        assert {f"M{index}" for index in range(100)} <= set(listing)
        assert listing == sorted(listing)
        assert "RED" in dir(self.Color) and "CRIMSON" not in dir(self.Color)

    @pytest.mark.timing
    def test_len_does_not_move_with_the_member_count(self) -> None:
        small, large = numbered(10, "SL"), numbered(1_000, "LL")

        small_ns = best_ns(lambda: len(small), inner=200)
        large_ns = best_ns(lambda: len(large), inner=200)

        ratio = large_ns / small_ns
        assert ratio < 3, f"100x the members cost x{ratio:.2f} ({small_ns:.0f}ns, {large_ns:.0f}ns)"


class TestMembersIsALiveView:
    """`C.__members__` | O(1) | O(1): a read-only view, aliases included."""

    def test_it_sees_a_key_added_after_it_was_taken(self) -> None:
        cls = numbered(10, "V")
        proxy = cls.__members__

        assert isinstance(proxy, types.MappingProxyType)
        with pytest.raises(TypeError):
            proxy["EXTRA"] = cls.M0  # type: ignore[index]
        cls._member_map_["EXTRA"] = cls.M0
        assert proxy["EXTRA"] is cls.M0

    def test_it_includes_aliases(self) -> None:
        cls: Any = Enum("Aliased", [("RED", 1), ("CRIMSON", 1), ("GREEN", 2)])

        assert list(cls.__members__) == ["RED", "CRIMSON", "GREEN"]


class TestMembership:
    """`value in C` | O(1) for a member; O(n) for a raw value.

    A raw value raises `TypeError` before 3.12. From 3.13.4 it is compared
    with each member value; `C(value)` remains one probe on every version.
    """

    class Color(Enum):
        RED = 1

    def test_a_member_is_in_its_own_enum(self) -> None:
        cls = counting_ints(100)

        assert counted(lambda: cls.M99 in cls) == 0
        assert self.Color.RED in self.Color

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="answers from 3.12")
    def test_a_raw_value_raises_before_312(self) -> None:
        with pytest.warns(DeprecationWarning), pytest.raises(TypeError):
            _ = 1 in self.Color

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="raises before 3.12")
    @pytest.mark.parametrize("size", [10, 100])
    def test_a_raw_value_is_answered_from_312(self, size: int) -> None:
        cls = counting_ints(size)
        answers: list[bool] = []

        hit = counted(lambda: answers.append(CountingInt(size - 1) in cls))
        miss = counted(lambda: answers.append(CountingInt(-5) in cls))

        assert answers == [True, False]
        if sys.version_info >= (3, 13, 4):
            assert hit == miss == size
        elif sys.version_info < (3, 13):
            assert hit <= 1 and miss <= 1

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="raises before 3.12")
    def test_a_hashable_miss_in_a_mixed_enum(self) -> None:
        cls: Any = Enum(
            "Mixed",
            [(f"H{i}", CountingInt(i)) for i in range(10)]
            + [(f"U{i}", CountingList([i])) for i in range(30)],
        )

        answers: list[bool] = []
        comparisons = counted(lambda: answers.append(-5 in cls))

        assert answers == [False]

        if sys.version_info < (3, 13):
            assert comparisons == 30
        elif sys.version_info < (3, 13, 3):
            assert comparisons == 0
        elif sys.version_info >= (3, 13, 4):
            assert comparisons == 40

    @pytest.mark.parametrize("size", [10, 100])
    def test_calling_the_class_stays_one_probe(self, size: int) -> None:
        cls = counting_ints(size)

        assert counted(lambda: cls(CountingInt(size - 1))) <= 1

        def miss() -> None:
            with pytest.raises(ValueError):
                cls(CountingInt(-5))

        assert counted(miss) == 0

    @pytest.mark.skipif(
        not (3, 12) <= sys.version_info < (3, 12, 10), reason="3.12.0 to 3.12.9 only"
    )
    def test_an_unhashable_raw_value_raises_before_31210(self) -> None:
        cls: Any = Enum("Lists", {"A": [1]})

        with pytest.raises(TypeError, match="unhashable"):
            _ = [1] in cls

    @pytest.mark.skipif(sys.version_info < (3, 12, 10), reason="answers from 3.12.10")
    def test_an_unhashable_raw_value_is_answered_from_31210(self) -> None:
        cls: Any = Enum("Lists", {"A": [1], "B": [2]})

        assert [2] in cls
        assert [3] not in cls


class TestFlags:
    """Flag operators are O(1) once a value has been made; each value is cached."""

    class Permission(Flag):
        READ = auto()
        WRITE = auto()
        EXECUTE = auto()

    def test_the_values_are_single_bits(self) -> None:
        assert [member.value for member in self.Permission] == [1, 2, 4]

    def test_a_combination_is_made_once_and_cached(self) -> None:
        cls: Any = Flag("Cached", "A B C")
        before = len(cls._value2member_map_)

        first = cls.A | cls.B
        after_first = len(cls._value2member_map_)
        assert (cls.A | cls.B) is first
        assert cls(3) is first
        assert after_first == before + 1
        assert len(cls._value2member_map_) == after_first

    def test_every_distinct_value_made_stays_cached(self) -> None:
        class Wide(IntFlag):
            A = 1
            B = 2

        cached: Any = Wide
        before = len(cached._value2member_map_)
        for index in range(1_000):
            Wide((1 << 20) | index)

        assert len(cached._value2member_map_) - before >= 1_000

    def test_membership_and_masking(self) -> None:
        combined = self.Permission.READ | self.Permission.WRITE

        assert self.Permission.READ in combined
        assert self.Permission.EXECUTE not in combined
        assert (combined & self.Permission.READ) is self.Permission.READ
        assert bool(combined) and not bool(self.Permission(0))

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="sized and iterable from 3.11")
    def test_iteration_yields_the_bits_set(self) -> None:
        combined: Any = self.Permission.READ | self.Permission.EXECUTE

        assert [member.name for member in combined] == ["READ", "EXECUTE"]

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="sized and iterable from 3.11")
    def test_len_counts_bits_without_iterating(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cls: Any = Flag("Sized", "A B C D")
        combined = cls.A | cls.C | cls.D

        def refuse(value: int) -> Any:
            raise AssertionError("len() iterated the members")

        monkeypatch.setattr(cls, "_iter_member_", refuse)
        assert len(combined) == 3

    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="sized and iterable from 3.11")
    def test_a_combination_has_no_length_before_311(self) -> None:
        combined: Any = self.Permission.READ | self.Permission.WRITE

        with pytest.raises(TypeError):
            len(combined)

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="sized and iterable from 3.11")
    def test_members_defined_out_of_order_iterate_in_definition_order(self) -> None:
        class Backwards(Flag):
            B = 2
            A = 1

        combined: Any = Backwards.A | Backwards.B
        assert [member.name for member in combined] == ["B", "A"]

    @pytest.mark.parametrize("size", [20, 60])
    def test_inversion_compares_members_pairwise_on_every_call_on_310(self, size: int) -> None:
        class Base(Flag):
            def __eq__(self, other: object) -> bool:
                Counter.calls += 1
                return self is other

            __hash__ = Flag.__hash__

        cls: Any = Base(f"Wide{size}", [(f"M{i}", 1 << i) for i in range(size)])
        full = cls((1 << size) - 1)

        first, second = counted(lambda: ~full), counted(lambda: ~full)

        if sys.version_info >= (3, 11):
            assert first == second == 0
        else:
            assert first == second == size * (size - 1) // 2

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="added in 3.11")
    def test_numeric_repr_formats_unnamed_bits(self) -> None:
        class Kept(IntFlag):
            A = 1

        assert ENUM.Flag._numeric_repr_ is repr
        assert Kept._numeric_repr_ is not None
        assert repr(Kept(9)).endswith("A|8: 9>")

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="cached from 3.11")
    def test_inversion_is_stored_on_the_operand(self) -> None:
        cls: Any = Flag("Inverted", "A B C")

        inverted = ~cls.A
        assert inverted is cls.B | cls.C
        assert cls.A._inverted_ is inverted
        assert ~cls.A is inverted


class TestEnumDict:
    """`EnumDict` (3.13+): the class-body namespace."""

    pytestmark = pytest.mark.skipif(sys.version_info < (3, 13), reason="public from 3.13")

    def test_member_names_is_a_fresh_snapshot_including_aliases(self) -> None:
        namespace: Any = Enum.__prepare__("Colors", (Enum,))
        namespace["RED"] = 1
        namespace["CRIMSON"] = 1
        namespace["__doc__"] = "Color names"

        names = namespace.member_names
        other = namespace.member_names
        assert names == other == ["RED", "CRIMSON"]
        assert names is not other
        names.clear()
        assert namespace.member_names == ["RED", "CRIMSON"]

    @pytest.mark.parametrize("count", [0, 10, 1_000])
    def test_member_names_visits_each_name_once(self, count: int) -> None:
        visits = 0

        class CountingNames(dict[str, None]):
            def __iter__(self):
                nonlocal visits
                for name in super().__iter__():
                    visits += 1
                    yield name

        namespace: Any = Enum.__prepare__("Names", (Enum,))
        expected = [f"M{i}" for i in range(count)]
        backing = CountingNames.fromkeys(expected)
        namespace._member_names = backing
        assert namespace._member_names is backing

        assert namespace.member_names == expected
        assert visits == count

    def test_update_assigns_as_the_class_body_does(self) -> None:
        namespace: Any = Enum.__prepare__("Updated", (Enum,))
        namespace.update({"A": auto(), "B": auto()}, C=1)

        assert namespace.member_names == ["A", "B", "C"]
        built: Any = type(Enum)("Updated", (Enum,), namespace)
        assert [member.value for member in built] == [1, 2]
        assert built.C is built.A
        assert isinstance(namespace, ENUM.EnumDict)


@pytest.mark.skipif(sys.version_info < (3, 13), reason="added in 3.13")
class TestAddingAliases:
    """`_add_alias_()`, `_add_value_alias_()` | O(1) expected; O(n) unhashable."""

    def test_add_alias_makes_a_name_lead_to_the_member(self) -> None:
        cls: Any = numbered(10, "A")

        cls.M3._add_alias_("THREE")
        assert cls.THREE is cls.M3
        assert cls["THREE"] is cls.M3

    @pytest.mark.parametrize("size", [10, 100])
    def test_a_hashable_value_alias_is_one_probe(self, size: int) -> None:
        cls = counting_ints(size)

        assert counted(lambda: cls.M0._add_value_alias_(CountingInt(-1))) <= 1
        assert cls(-1) is cls.M0

    @pytest.mark.parametrize("size", [10, 100])
    def test_an_unhashable_value_alias_scans_the_members(self, size: int) -> None:
        cls = counting_lists(size)

        assert counted(lambda: cls.M0._add_value_alias_(CountingList([-1]))) == size
        assert cls(CountingList([-1])) is cls.M0


@pytest.mark.skipif(sys.version_info < (3, 11), reason="added in 3.11")
class TestClassBodyHelpers:
    """`member()`, `nonmember()`, `enum.property`, `_ignore_` and `_order_`."""

    def test_member_and_nonmember(self) -> None:
        class Marked(Enum):
            A = 1
            HELPER = ENUM.nonmember(2)
            FUNC = ENUM.member(len)

        assert [member.name for member in Marked] == ["A", "FUNC"]
        assert Marked.HELPER == 2

    def test_enum_property_lets_a_member_be_called_value(self) -> None:
        cls: Any = Enum("Odd", [("name", 1), ("value", 2)])
        assert cls.value.value == 2 and cls.value.name == "value"
        assert isinstance(vars(Enum)["value"], ENUM.property)

    def test_ignore_and_order(self) -> None:
        class Ordered(Enum):
            _ignore_ = ["TEMP"]
            _order_ = "A B"
            TEMP = 0
            A = 1
            B = 2

        assert [member.name for member in Ordered] == ["A", "B"]

        with pytest.raises(TypeError, match="member order does not match"):

            class Misordered(Enum):
                _order_ = "B A"
                A = 1
                B = 2


@pytest.mark.skipif(sys.version_info < (3, 11), reason="added in 3.11")
class TestVerify:
    """`verify(*checks)` | O(n + r) | O(n + r); `CONTINUOUS` walks the span."""

    def test_continuous_refuses_a_gap(self) -> None:
        with pytest.raises(ValueError, match="missing values 2"):

            @ENUM.verify(ENUM.CONTINUOUS)
            class Gapped(Enum):
                A = 1
                C = 3

    def test_unique_and_named_flags(self) -> None:
        with pytest.raises(ValueError, match="aliases found"):

            @ENUM.verify(ENUM.UNIQUE)
            class Duplicated(Enum):
                A = 1
                B = 1

        with pytest.raises(ValueError, match="is missing"):

            @ENUM.verify(ENUM.NAMED_FLAGS)
            class Unnamed(Flag):
                A = 1
                AB = 3

    def test_a_well_formed_enum_passes(self) -> None:
        @ENUM.verify(ENUM.CONTINUOUS, ENUM.UNIQUE)
        class Fine(Enum):
            A = 1
            B = 2

        assert len(Fine) == 2

    @pytest.mark.serial
    def test_continuous_space_follows_the_span_not_the_members(self) -> None:
        peaks = []
        for span in (100_000, 1_000_000):
            cls: Any = Enum(f"Span{span}", {"LOW": 0, "HIGH": span})
            check = ENUM.verify(ENUM.CONTINUOUS)

            def run(cls: Any = cls, check: Any = check) -> None:
                with pytest.raises(ValueError, match="missing values"):
                    check(cls)

            peaks.append(peak_bytes(run))

        assert peaks[1] > peaks[0] * 5, peaks


class TestUnique:
    """`unique(cls)` | O(n) | O(a): every alias is named in the error."""

    def test_each_alias_is_named(self) -> None:
        cls: Any = Enum("Twice", [("A", 1), ("B", 1), ("C", 2), ("D", 2), ("E", 3)])

        with pytest.raises(ValueError, match="duplicate values") as raised:
            unique(cls)
        assert "B -> A" in str(raised.value) and "D -> C" in str(raised.value)
        assert unique(numbered(10, "U")) is not None


@pytest.mark.skipif(sys.version_info < (3, 11), reason="added in 3.11")
class TestGlobalHelpers:
    @pytest.mark.parametrize("count", [10, 100])
    def test_global_enum_exports_every_member(
        self, count: int, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        module = types.ModuleType("_enum_helper_test")
        monkeypatch.setitem(sys.modules, module.__name__, module)
        cls: Any = Enum("Exported", {f"M{i}": i for i in range(count)}, module=module.__name__)

        assert ENUM.global_enum(cls) is cls
        assert all(vars(module)[name] is member for name, member in cls.__members__.items())
        assert str(cls.M0) == "M0"
        assert repr(cls.M0) == "_enum_helper_test.M0"

    def test_global_str_returns_the_stored_name(self) -> None:
        member = numbered(10, "G").M9

        assert ENUM.global_str(member) is member.name
        assert ENUM.global_enum_repr(member).endswith(".M9")

    @pytest.mark.parametrize("bits", [2, 16])
    def test_global_flag_repr_qualifies_each_name(self, bits: int) -> None:
        cls: Any = Flag("Bits", [f"B{i}" for i in range(bits)])
        module = cls.__module__.split(".")[-1]

        expected = "|".join(f"{module}.B{i}" for i in range(bits))
        assert ENUM.global_flag_repr(cls(2**bits - 1)) == expected

    def test_global_flag_repr_keeps_a_named_combination_whole(self) -> None:
        cls: Any = Flag("Named", [("A", 1), ("B", 2), ("AB", 3)])
        module = cls.__module__.split(".")[-1]

        assert ENUM.global_flag_repr(cls.AB) == f"{module}.AB"

    def test_pickle_helpers_reduce_to_a_name(self) -> None:
        member = numbered(10, "Pk").M2

        assert ENUM.pickle_by_enum_name(member, 2)[1] == (type(member), "M2")
        assert ENUM.pickle_by_global_name(member, 2) == "M2"


@pytest.mark.skipif(sys.version_info < (3, 11), reason="added in 3.11")
class TestBitHelpers:
    @pytest.mark.parametrize("bits", [1, 8, 32])
    def test_show_flag_values_returns_the_bits_set(self, bits: int) -> None:
        value = sum(1 << (2 * index) for index in range(bits))

        assert ENUM.show_flag_values(value) == [1 << (2 * index) for index in range(bits)]
        assert ENUM.show_flag_values(0) == []

    @pytest.mark.parametrize("width", [8, 100, 1_000])
    def test_bin_pads_to_max_bits(self, width: int) -> None:
        result = ENUM.bin(10, width)

        assert result.startswith("0b0 ")
        assert len(result) == width + 4
        assert int(result[4:], 2) == 10
        assert ENUM.bin(-11) == "0b1 0101"


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
    """Each block runs in its own subprocess and asserts its own result; four
    of them branch on the interpreter version."""

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
        target = "assert len(Color) == 2"
        line, source = next((n, s) for n, s in _blocks() if target in s)
        mutated = source.replace(target, "assert len(Color) == 3", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
