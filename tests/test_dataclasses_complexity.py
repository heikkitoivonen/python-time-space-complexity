"""Tests for docs/stdlib/dataclasses.md.

The page prices a dataclass in two sizes: n, the fields of one class with
inherited fields included, and N, the values `asdict()` and `astuple()` visit.
Space bounds are settled by traced allocation at two widths an order of
magnitude apart, which separates O(1) from O(n) without a tolerance; the
behavioural rows are settled by observation - identity, call counts and the
exception raised. A stopwatch is used only for the decorator and for
`asdict()`, where nothing else shows the growth.

Measurement scope:

* The decorator, through `make_dataclass()`, at 25 and 400 int fields: 16x
  the fields cost between x11 and x18 on 3.10 to 3.14, where a quadratic
  would cost x256; the test asserts x4 to x80. At thousands of fields the
  compile step grows faster than linear on 3.10 to 3.13 (6,400 fields cost
  x7.7 to x10 the time of 1,600) and stays linear on 3.14 (x3.8); that width
  is outside what the page prices. `default_factory` is asserted uncalled by
  the decorator, called once per instance that omits the field, and skipped
  when a value is supplied, with a counting factory.
* Generated `__init__` retains traced memory that grows more than 5x from 100
  to 1,000 fields on an instance allocated before tracing. Construction with
  and without `slots=True` is compared by traced peak at 10 and 1,000 fields,
  arguments built inside the measurement: both grow more than 5x, and the
  slotted peak at 1,000 fields is the smaller (52,704 against 75,944 bytes on
  3.14, 44,884 against 47,820 on 3.10). With `slots=True` the field is a member descriptor on the class and
  the instance has no `__dict__`; without it, the value is in `vars(obj)`.
* Generated `__eq__`, `__lt__`, `__hash__` and `__repr__` peaks at 200 and
  2,000 fields on 3.10 to 3.14: `__lt__` about 4.9 KB and 48 KB, `__hash__`
  3.2 KB and 32 KB, `__repr__` 14 to 16 KB and 144 to 160 KB; `__eq__` the
  same as `__lt__` on 3.10 to 3.12 and zero at both widths on 3.13 and 3.14. The
  zero is measured on a second call, after warming, because from 3.12 a
  code object's first run after any tracer was installed allocates
  monitoring data. At 10 fields 3.11 and 3.12 take the tuples from a
  freelist, so widths start at 200. `__eq__` time over 200 and 2,000 equal
  fields is asserted between x4 and x40, where linear predicts x10 and
  quadratic x100. `field(repr=False)` is asserted absent from the repr.
* Hashing is asserted by `__hash__` identity and set membership for the
  default, `frozen=True`, `unsafe_hash=True` and `eq=False` cases, and an
  explicit `__hash__` is asserted kept under `eq=True`.
* `KW_ONLY` is asserted to make later fields keyword-only and to yield to a
  later `field(kw_only=False)`.
* `asdict()` time at 100 and 400 nodes, as a chain of two-field instances
  (a value and the next node) and as one flat class: 4x the nodes costs between x2.5 and x6 in both shapes.
  A list holding one instance 200 times converts to 200 distinct
  dictionaries, so a shared value is counted once per reference; a list in a
  field comes back as a different list.
* `replace()` is asserted to run `__post_init__` again and to reject an
  `init=False` field with `ValueError` on 3.10 to 3.12 and `TypeError` from
  3.13, each version asserting the other type is not raised. `copy.replace()`
  is asserted to work from 3.13.
* `fields()` is asserted to return equal, distinct tuples on two calls of a
  class with fields (an empty result is the shared empty tuple) and to
  leave out `InitVar` and `ClassVar` pseudo-fields. `Field.metadata` is
  asserted to show a later change to the mapping passed in, and `Field.doc`
  to exist from 3.14.
* A default whose class sets `__hash__ = None` is rejected with `ValueError`
  from 3.11 and accepted on 3.10; a `list` default is rejected on every
  version.
* Every fenced Python block runs in its own subprocess and working
  directory, and an import mutated in one of them is asserted to fail.

Not settled here:

* The bound for a hierarchy of many dataclass levels, which the page scopes
  out. The decorator merges
  the field table of every dataclass base in the MRO (Lib/dataclasses.py,
  `_process_class`), and those tables already include their own bases'
  fields, so a d-level chain repeats work across levels; only one base is
  tested.
* `is_dataclass()` as O(1) is read from source: one `hasattr()` on the class.
  Deep MROs are not varied.
* Field `==`, `<`, `hash()` and `repr()` costs, `default_factory` and
  `__post_init__` are held at O(1) in every measurement; the per-field
  values are small ints.
"""

from __future__ import annotations

import copy
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from dataclasses import (
    KW_ONLY,
    MISSING,
    Field,
    FrozenInstanceError,
    InitVar,
    asdict,
    astuple,
    dataclass,
    field,
    fields,
    is_dataclass,
    make_dataclass,
    replace,
)
from typing import Any, ClassVar

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "dataclasses.md"
EXPECTED_BLOCKS = 12


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


def wide(width: int, **options: Any) -> type:
    """A dataclass of `width` int fields."""
    return make_dataclass(f"Wide{width}", [(f"f{index}", int) for index in range(width)], **options)


class TestDecoratorIsLinearInFields:
    """`@dataclass` and `make_dataclass()` | O(n) | O(n), once per class."""

    @pytest.mark.timing
    def test_sixteen_times_the_fields_is_not_quadratic(self) -> None:
        narrow = [(f"f{index}", int) for index in range(25)]
        broad = [(f"f{index}", int) for index in range(400)]

        narrow_ns = best_ns(lambda: make_dataclass("N", narrow))
        broad_ns = best_ns(lambda: make_dataclass("B", broad))

        ratio = broad_ns / narrow_ns
        assert 4 < ratio < 80, (
            f"16x the fields cost x{ratio:.2f} ({narrow_ns:.0f}ns to {broad_ns:.0f}ns); "
            "linear predicts x16, quadratic x256"
        )

    def test_each_make_dataclass_call_builds_a_new_class(self) -> None:
        first = make_dataclass("P", [("x", int)])
        second = make_dataclass("P", [("x", int)])

        assert first is not second
        assert first(1) != second(1)

    def test_a_plain_default_lives_on_the_class(self) -> None:
        @dataclass
        class Config:
            retries: int = 3

        assert Config.__dict__["retries"] == 3
        assert Config().retries == 3

    def test_default_factory_runs_per_instance_and_not_at_decoration(self) -> None:
        calls: list[int] = []

        def factory() -> list[int]:
            calls.append(1)
            return []

        @dataclass
        class Config:
            tags: list[int] = field(default_factory=factory)

        assert calls == []
        first, second = Config(), Config()
        assert len(calls) == 2
        assert first.tags is not second.tags
        assert Config(tags=[1]).tags == [1]
        assert len(calls) == 2, "a supplied value should bypass the factory"

    def test_a_list_default_is_rejected_on_every_version(self) -> None:
        with pytest.raises(ValueError, match="mutable default"):

            @dataclass
            class Broken:
                tags: list = []  # noqa: RUF012

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="3.10 checks list, dict, set only")
    def test_any_unhashable_default_is_rejected_from_311(self) -> None:
        class Unhashable:
            __hash__ = None  # type: ignore[assignment]

        with pytest.raises(ValueError, match="mutable default"):

            @dataclass
            class Broken:
                value: Unhashable = Unhashable()  # noqa: RUF009

    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="3.11 rejects any unhashable default")
    def test_310_accepts_an_unhashable_default_of_another_type(self) -> None:
        class Unhashable:
            __hash__ = None  # type: ignore[assignment]

        @dataclass
        class Accepted:
            value: Unhashable = Unhashable()  # noqa: RUF009

        assert Accepted().value is Accepted().value


class TestInitStoresOneValuePerField:
    """Generated `__init__` | O(n) | O(n); `slots=True` is smaller at the same
    bound, and attribute access is a dict lookup or a slot descriptor."""

    def test_initialization_retains_storage_for_each_field(self) -> None:
        retained = []
        for count in (100, 1_000):
            cls = wide(count)
            value = object()
            args = (value,) * count
            obj = object.__new__(cls)
            tracemalloc.start()
            try:
                cls.__init__(obj, *args)
                retained.append(tracemalloc.get_traced_memory()[0])
            finally:
                tracemalloc.stop()
            assert len(vars(obj)) == count
            assert all(item is value for item in vars(obj).values())
        assert retained[0] > 0
        assert retained[1] > retained[0] * 5, retained

    def test_slots_keep_the_storage_linear_at_a_smaller_constant(self) -> None:
        peaks: dict[bool, list[int]] = {False: [], True: []}
        for slotted in (False, True):
            for count in (10, 1_000):
                built = wide(count, slots=slotted)
                built(*range(count))  # warm the class before tracing
                peaks[slotted].append(peak_bytes(lambda b=built, c=count: b(*range(c))))

        for series in peaks.values():
            assert series[1] > series[0] * 5, f"storage should follow the fields: {series}"
        assert peaks[True][1] < peaks[False][1], (
            f"slots should hold the same fields more cheaply: {peaks}"
        )

    def test_a_slotted_field_is_a_descriptor_and_a_plain_one_a_dict_entry(self) -> None:
        plain = wide(2)(0, 1)
        slotted_type = wide(2, slots=True)
        slotted = slotted_type(0, 1)

        assert vars(plain)["f0"] == 0
        assert type(slotted_type.__dict__["f0"]).__name__ == "member_descriptor"
        assert not hasattr(slotted, "__dict__")
        assert slotted.f0 == 0

    def test_frozen_construction_bypasses_the_raising_setattr(self) -> None:
        @dataclass(frozen=True)
        class Point:
            x: float
            y: float

        point = Point(1.0, 2.0)

        assert (point.x, point.y) == (1.0, 2.0)
        with pytest.raises(FrozenInstanceError, match="cannot assign"):
            point.x = 5.0  # type: ignore[misc]
        with pytest.raises(FrozenInstanceError):
            del point.x  # type: ignore[misc]
        assert issubclass(FrozenInstanceError, AttributeError)


class TestComparisonsVisitEveryField:
    """`__eq__` | O(n) | O(n), O(1) from 3.13; ordering, `__hash__` and
    `__repr__` | O(n) | O(n) on every version.

    Widths start at 200: at 10 fields 3.11 and 3.12 take the tuples from a
    freelist and the peak reads zero for a reason unrelated to the bound.
    """

    @staticmethod
    def _pairs(width: int) -> tuple[Any, Any]:
        built = wide(width, order=True, frozen=True)
        return built(*range(width)), built(*range(width))

    @pytest.mark.parametrize(
        "operation",
        [
            pytest.param(lambda a, b: a < b, id="lt"),
            pytest.param(lambda a, b: hash(a), id="hash"),
            pytest.param(lambda a, b: repr(a), id="repr"),
        ],
    )
    def test_the_peak_follows_the_fields_on_every_version(
        self, operation: Callable[[Any, Any], Any]
    ) -> None:
        peaks = []
        for width in (200, 2_000):
            left, right = self._pairs(width)
            operation(left, right)  # warm the generated method
            peaks.append(peak_bytes(lambda a=left, b=right: operation(a, b)))

        assert peaks[0] > 0
        assert peaks[1] > peaks[0] * 5, f"10x the fields moved the peak {peaks}"

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="3.13 compares field by field")
    def test_eq_builds_tuples_before_313(self) -> None:
        peaks = []
        for width in (200, 2_000):
            left, right = self._pairs(width)
            assert left == right  # warm the generated method
            peaks.append(peak_bytes(lambda a=left, b=right: a == b))

        assert peaks[0] > 0
        assert peaks[1] > peaks[0] * 5, f"10x the fields moved the peak {peaks}"

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="the tuples are built before 3.13")
    @pytest.mark.serial
    def test_eq_allocates_nothing_from_313(self) -> None:
        """Measured on a second call of `compare`, so monitoring data the
        interpreter attaches to a code object on its first run is not counted.
        """
        left, right = self._pairs(2_000)

        def compare() -> bool:
            return left == right

        assert compare()  # warm the code paths

        assert peak_bytes(compare) == 0

    def test_a_repr_false_field_is_left_out(self) -> None:
        @dataclass
        class Secret:
            name: str
            token: str = field(repr=False)

        assert repr(Secret("a", "b")).endswith("Secret(name='a')")

    def test_eq_compares_every_field(self) -> None:
        built = wide(50)

        assert built(*range(50)) == built(*range(50))
        assert built(*range(50)) != built(*range(49), 999)

    @pytest.mark.timing
    def test_eq_time_is_linear_in_the_fields_on_every_version(self) -> None:
        narrow = self._pairs(200)
        broad = self._pairs(2_000)

        narrow_ns = best_ns(lambda: narrow[0] == narrow[1], inner=20)
        broad_ns = best_ns(lambda: broad[0] == broad[1], inner=5)

        ratio = broad_ns / narrow_ns
        assert 4 < ratio < 40, (
            f"10x the fields cost x{ratio:.2f} ({narrow_ns:.0f}ns to {broad_ns:.0f}ns); "
            "linear predicts x10, quadratic x100"
        )

    def test_order_generates_the_four_comparisons(self) -> None:
        @dataclass(order=True)
        class Version:
            major: int
            minor: int

        assert Version(1, 2) < Version(1, 10)
        assert Version(1, 10) >= Version(1, 2)
        assert sorted([Version(2, 0), Version(1, 5)])[0] == Version(1, 5)
        for name in ("__lt__", "__le__", "__gt__", "__ge__"):
            assert name in Version.__dict__


class TestHashabilityFollowsEqFrozenAndUnsafeHash:
    """`eq=True` alone sets `__hash__` to None; `frozen=True` or
    `unsafe_hash=True` generates one; `eq=False` keeps `object.__hash__`."""

    def test_the_default_decorator_makes_an_unhashable_class(self) -> None:
        @dataclass
        class Mutable:
            a: int

        assert Mutable.__hash__ is None
        with pytest.raises(TypeError, match="unhashable"):
            hash(Mutable(1))

    def test_frozen_with_eq_gets_a_generated_hash(self) -> None:
        @dataclass(frozen=True)
        class Frozen:
            a: int

        assert "__hash__" in Frozen.__dict__
        assert len({Frozen(1), Frozen(1)}) == 1

    def test_unsafe_hash_generates_one_without_frozen(self) -> None:
        @dataclass(unsafe_hash=True)
        class Forced:
            a: int

        assert Forced.__hash__ is not None
        assert hash(Forced(1)) == hash(Forced(1))
        assert len({Forced(1), Forced(1)}) == 1

    def test_an_explicit_hash_is_kept_under_eq(self) -> None:
        @dataclass
        class Explicit:
            a: int

            def __hash__(self) -> int:
                return 7

        assert hash(Explicit(1)) == 7

    def test_eq_false_keeps_the_inherited_hash(self) -> None:
        @dataclass(eq=False)
        class Identity:
            a: int

        assert Identity.__hash__ is object.__hash__
        assert Identity(1) != Identity(1)
        assert len({Identity(1), Identity(1)}) == 2


class TestAsdictWalksEveryValueReached:
    """`asdict`/`astuple` | O(N) | O(N), N = values visited, a value reached
    by two paths counted twice."""

    @staticmethod
    def _chain(length: int) -> Any:
        node_type = make_dataclass("Node", [("v", int), ("child", object)])
        node = None
        for index in range(length):
            node = node_type(index, node)
        return node

    @pytest.mark.timing
    def test_it_is_linear_in_depth(self) -> None:
        short = self._chain(100)
        long = self._chain(400)

        short_ns = best_ns(lambda: asdict(short), inner=3)
        long_ns = best_ns(lambda: asdict(long), inner=3)

        ratio = long_ns / short_ns
        assert 2.5 < ratio < 6, (
            f"4x the depth cost x{ratio:.2f} ({short_ns:.0f}ns to {long_ns:.0f}ns)"
        )

    @pytest.mark.timing
    def test_it_is_linear_in_width_the_same_way(self) -> None:
        narrow = wide(100)(*range(100))
        broad = wide(400)(*range(400))

        narrow_ns = best_ns(lambda: asdict(narrow), inner=3)
        broad_ns = best_ns(lambda: asdict(broad), inner=3)

        ratio = broad_ns / narrow_ns
        assert 2.5 < ratio < 6, (
            f"4x the fields cost x{ratio:.2f} ({narrow_ns:.0f}ns to {broad_ns:.0f}ns)"
        )

    def test_a_shared_instance_is_converted_once_per_reference(self) -> None:
        @dataclass
        class Holder:
            values: list

        shared = wide(10)(*range(10))

        converted = asdict(Holder([shared] * 200))["values"]

        assert len(converted) == 200
        assert len({id(item) for item in converted}) == 200
        assert converted[0] == converted[1] == asdict(shared)

    def test_it_copies_the_containers_it_finds(self) -> None:
        @dataclass
        class Holder:
            values: list

        holder = Holder([1, 2, 3])

        converted = asdict(holder)

        assert converted == {"values": [1, 2, 3]}
        assert converted["values"] is not holder.values

    def test_astuple_makes_the_same_walk(self) -> None:
        @dataclass
        class Inner:
            values: list

        @dataclass
        class Outer:
            inner: Inner
            label: str

        outer = Outer(Inner([1, 2]), "x")

        assert astuple(outer) == (([1, 2],), "x")
        assert astuple(outer)[0][0] is not outer.inner.values

    @pytest.mark.parametrize("access", [vars, lambda obj: obj.__dict__], ids=["vars", "__dict__"])
    def test_vars_reuses_the_dictionary_while_copying_allocates(
        self, access: Callable[[Any], dict]
    ) -> None:
        """The page's alternative: `vars(obj)` is O(1), its `.copy()` O(n)."""
        access_peaks = []
        copies = []
        for count in (100, 1_000):
            value: list[int] = []
            obj = wide(count)(*((value,) * count))
            existing = obj.__dict__
            assert access(obj) is existing  # warm the access callable before tracing
            tracemalloc.start()
            try:
                attributes = access(obj)
                access_peaks.append(tracemalloc.get_traced_memory()[1])
            finally:
                tracemalloc.stop()
            assert attributes is existing
            tracemalloc.start()
            try:
                shallow = attributes.copy()
                copies.append(tracemalloc.get_traced_memory()[0])
            finally:
                tracemalloc.stop()
            assert shallow == existing and shallow is not existing
            assert all(item is value for item in shallow.values())
        assert copies[0] > 0
        assert copies[1] > copies[0] * 5, copies
        assert max(access_peaks) < copies[0] // 4, (access_peaks, copies)


class TestReplaceRebuildsThroughInit:
    """`replace()` | O(n) | O(n): it calls `__init__`, so `__post_init__` runs
    again and an `init=False` field cannot be passed."""

    @dataclass
    class Measurement:
        value: int
        scale: InitVar[int] = 2
        scaled: int = field(init=False, default=0)

        def __post_init__(self, scale: int) -> None:
            self.scaled = self.value * scale

    def test_replace_recomputes_rather_than_copies(self) -> None:
        first = self.Measurement(3)

        assert (first.value, first.scaled) == (3, 6)
        assert replace(first, value=4).scaled == 8

    def test_an_init_false_field_is_refused(self) -> None:
        first = self.Measurement(3)
        expected = TypeError if sys.version_info >= (3, 13) else ValueError

        with pytest.raises(expected, match="init=False"):
            replace(first, scaled=99)

    def test_the_other_exception_type_is_not_raised(self) -> None:
        """So the version split above is asserted in both directions."""
        first = self.Measurement(3)
        unexpected = ValueError if sys.version_info >= (3, 13) else TypeError

        with pytest.raises(Exception) as caught:  # noqa: B017, PT011
            replace(first, scaled=99)

        assert not isinstance(caught.value, unexpected)

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="copy.replace is new in 3.13")
    def test_copy_replace_accepts_a_dataclass_from_313(self) -> None:
        first = self.Measurement(3)

        assert copy.replace(first, value=5).scaled == 10  # type: ignore[attr-defined]

    def test_initvar_is_not_stored(self) -> None:
        first = self.Measurement(3)

        assert "scale" not in vars(first)
        assert [f.name for f in fields(first)] == ["value", "scaled"]


class TestKeywordOnlyMarker:
    """`KW_ONLY` is a position in the field order, not a field."""

    @dataclass
    class Request:
        url: str
        _: KW_ONLY
        timeout: int = 30

    def test_the_later_field_must_be_named(self) -> None:
        assert self.Request("http://x", timeout=5).timeout == 5

        with pytest.raises(TypeError, match="positional"):
            self.Request("http://x", 5)  # type: ignore[misc]

    def test_a_later_field_can_opt_back_into_positional(self) -> None:
        @dataclass
        class Mixed:
            _: KW_ONLY
            a: int = field(kw_only=False)
            b: int = 0

        assert Mixed(1).a == 1
        with pytest.raises(TypeError, match="positional"):
            Mixed(1, 2)  # type: ignore[misc]

    def test_the_marker_leaves_no_field_behind(self) -> None:
        assert [f.name for f in fields(self.Request)] == ["url", "timeout"]


class TestIntrospection:
    """`fields()` | O(n) | O(n) rebuilt per call, the `Field` attribute rows,
    and `is_dataclass()` | O(1)."""

    @dataclass
    class Point:
        tag: ClassVar[str] = "p"
        x: float
        y: float = 0.0
        scale: InitVar[int] = 1

    def test_fields_rebuilds_its_tuple_each_call(self) -> None:
        assert fields(self.Point) == fields(self.Point)
        assert fields(self.Point) is not fields(self.Point)

    def test_fields_leaves_out_the_pseudo_fields(self) -> None:
        assert [f.name for f in fields(self.Point)] == ["x", "y"]

    def test_a_field_carries_the_sentinel_when_it_has_no_default(self) -> None:
        first, second = fields(self.Point)

        assert isinstance(first, Field)
        assert first.default is MISSING
        assert MISSING is not None
        assert second.default == 0.0

    def test_metadata_is_a_view_not_a_copy(self) -> None:
        source = {"unit": "m"}

        @dataclass
        class Length:
            value: float = field(metadata=source)

        (only,) = fields(Length)
        source["unit"] = "km"

        assert only.metadata["unit"] == "km"
        with pytest.raises(TypeError):
            only.metadata["unit"] = "mm"  # type: ignore[index]

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="field(doc=) is new in 3.14")
    def test_field_doc_exists_from_314(self) -> None:
        @dataclass
        class Documented:
            value: int = field(default=0, doc="the value")  # type: ignore[call-overload]

        assert fields(Documented)[0].doc == "the value"  # type: ignore[attr-defined]

    def test_initvar_type_is_the_parameter(self) -> None:
        assert InitVar[int].type is int  # type: ignore[attr-defined]

    def test_is_dataclass_answers_for_class_and_instance(self) -> None:
        assert is_dataclass(self.Point)
        assert is_dataclass(self.Point(1.0))
        assert not is_dataclass(object())


class TestInheritance:
    """A subclass's methods cover inherited fields, so n is the total."""

    def test_the_base_fields_come_first_and_are_compared(self) -> None:
        @dataclass
        class Base:
            a: int

        @dataclass
        class Derived(Base):
            b: int

        assert [f.name for f in fields(Derived)] == ["a", "b"]
        assert Derived(1, 2) != Derived(9, 2)
        assert repr(Derived(1, 2)).endswith("Derived(a=1, b=2)")

    def test_a_default_cannot_be_followed_by_a_bare_field(self) -> None:
        with pytest.raises(TypeError, match="non-default argument"):

            @dataclass
            class Broken:
                c: int = 0
                d: int  # type: ignore[reportGeneralTypeIssues]


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
    """Every block runs in its own subprocess, and each pins its result with
    an assert, or an `else` that raises where it expects an exception."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0

        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()[-400:]}")

        assert not failures, "\n".join(failures)
        assert ran == EXPECTED_BLOCKS

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = _blocks()[0][1]
        broken = original.replace("from dataclasses import", "from dataclasses import missing,", 1)
        assert broken != original, "the mutation did not reach an import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "ImportError" in result.stderr
