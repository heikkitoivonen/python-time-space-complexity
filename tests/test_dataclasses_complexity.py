"""Tests to verify documented behaviour of the dataclasses module.

docs/stdlib/dataclasses.md distinguishes two sizes: n, the fields on a class,
and N, the values a recursive walk reaches. Conflating them is what the page's
`asdict()` and `astuple()` rows did, and separating them is what these tests
mostly do.

* `asdict()` is O(N) in the values reached, with depth and width the same
  variable. A chain of 100, 200 and 400 one-field nodes costs 120, 253 and 503 us on 3.10
  and 57, 118 and 242 us on 3.14 - linear in nodes either way - and a flat class
  of 100, 200 and 400 fields costs 64, 127 and 257 us on 3.10. Depth and width
  are the same variable to it.
* `asdict()` also deep-copies: the list inside a converted instance is not the
  list the instance holds. That is why it is not a cheap projection, and why the
  page points at `vars()` for the shallow view.
* The generated `__eq__` compares two tuples, so its space is O(n).
  The peak tracks the field count exactly on 3.10 - 408, 4,880 and 48,208 bytes
  for 10, 200 and 2,000 fields - and 3.13 stops materializing them, reaching
  zero at every width on 3.13 and 3.14. (3.11 and 3.12 report zero at 10 fields
  only, where the tuples come off a freelist, so the tests use 200 and above.)
* `eq=True` sets `__hash__` to None, which is the single most surprising thing
  the module does: the default decorator produces an unhashable class.
* `replace()` refuses an `init=False` field with `ValueError` on 3.10 through
  3.12 and `TypeError` from 3.13. The page's example catches both, and the
  tests assert the split in both directions.

Generating the methods is linear enough at any width worth writing: x1.55 to
x1.69 per doubling up to 40 fields, drifting to x2.17 by 320 as the compiler
works on a wider generated function. The page says O(n) and stops there.

Not settled here:

* What `@dataclass` costs at import as an absolute number. It is a constant of
  the machine and the release, and the page carries no constants.
* `slots=True`, which changes attribute storage rather than any bound.
* Whether the 3.13 change to `__eq__` extends to the ordering methods; only
  `__eq__` was measured.

Axes not varied: `unsafe_hash`, dataclasses over non-dataclass containers
beyond one list, and inheritance deeper than one base.
"""

import dataclasses
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
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "dataclasses.md"

EXPECTED_BLOCKS = 11


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


def wide(width: int) -> type:
    """A dataclass of `width` int fields."""
    return make_dataclass(f"Wide{width}", [(f"f{index}", int) for index in range(width)])


def _documented_names() -> set[str]:
    """Every `dataclasses.<name>` the Complexity Reference table mentions."""
    text = PAGE.read_text(encoding="utf-8")
    start = text.index("| Operation | Time | Space | Notes |")
    end = text.index("\n## Basic Dataclass", start)
    return set(re.findall(r"dataclasses\.([A-Za-z_][A-Za-z0-9_]*)", text[start:end]))


class TestEveryPublicNameIsDocumented:
    """The table has to name every entry in `dataclasses.__all__`."""

    def test_no_exported_name_is_missing_from_the_table(self) -> None:
        missing = sorted(set(dataclasses.__all__) - _documented_names())

        assert not missing, f"{len(missing)} exported names absent from the table: {missing}"

    def test_the_table_names_nothing_that_does_not_exist(self) -> None:
        """The other direction, so a typo cannot pass as coverage."""
        unknown = sorted(_documented_names() - set(dataclasses.__all__))

        assert not unknown, f"the table names attributes dataclasses does not have: {unknown}"

    def test_the_module_has_not_grown_names_this_suite_has_not_seen(self) -> None:
        assert 12 <= len(dataclasses.__all__) <= 16, (
            f"dataclasses exports {len(dataclasses.__all__)} names; re-run the coverage audit"
        )

    def test_the_generated_methods_have_rows_too(self) -> None:
        """They are the module's real output and belong to no __all__."""
        text = PAGE.read_text(encoding="utf-8")

        for method in ("__init__", "__repr__", "__eq__", "__hash__"):
            assert f"Generated `{method}" in text, f"no row for the generated {method}"

    def test_the_coverage_check_would_notice_a_gap(self) -> None:
        """A coverage test that cannot fail proves nothing about coverage."""
        documented = _documented_names()

        assert {"dataclass", "asdict", "fields", "replace"} <= documented
        thinned = documented - {"astuple"}
        assert set(dataclasses.__all__) - thinned == {"astuple"}, (
            "dropping one row from the extracted set should surface it as missing"
        )


class TestAsdictWalksValuesNotFields:
    """`asdict`/`astuple` | O(N) | O(N) | N = values reached.

    Depth and width are the same variable here, so the two shapes below are
    both linear in their node count.
    """

    @staticmethod
    def _chain(length: int) -> Any:
        node_type = make_dataclass("Node", [("v", int), ("child", object)])
        node = None
        for index in range(length):
            node = node_type(index, node)
        return node

    def test_the_two_shapes_hold_comparable_node_counts(self) -> None:
        """So the timings below are not measuring different amounts of data."""
        flat = wide(100)(*range(100))
        chain = self._chain(100)

        assert len(asdict(flat)) == 100
        assert len(str(asdict(chain))) > 100

    @pytest.mark.timing
    def test_it_is_linear_in_depth(self) -> None:
        short = self._chain(100)
        long = self._chain(400)

        short_ns = best_ns(lambda: asdict(short), inner=3)
        long_ns = best_ns(lambda: asdict(long), inner=3)

        ratio = long_ns / short_ns
        assert 2.5 < ratio < 6, (
            f"4x the depth cost x{ratio:.2f} ({short_ns:.0f}ns to {long_ns:.0f}ns); "
            "the row claims linear in the values reached"
        )

    @pytest.mark.timing
    def test_it_is_linear_in_width_the_same_way(self) -> None:
        narrow = wide(100)(*range(100))
        broad = wide(400)(*range(400))

        narrow_ns = best_ns(lambda: asdict(narrow), inner=3)
        broad_ns = best_ns(lambda: asdict(broad), inner=3)

        ratio = broad_ns / narrow_ns
        assert 2.5 < ratio < 6, (
            f"4x the fields cost x{ratio:.2f} ({narrow_ns:.0f}ns to {broad_ns:.0f}ns); "
            "width and depth are the same variable to asdict"
        )

    def test_it_deep_copies_the_containers_it_finds(self) -> None:
        @dataclass
        class Holder:
            values: list

        holder = Holder([1, 2, 3])

        converted = asdict(holder)

        assert converted == {"values": [1, 2, 3]}
        assert converted["values"] is not holder.values

    def test_vars_is_the_shallow_alternative(self) -> None:
        @dataclass
        class Holder:
            values: list

        holder = Holder([1, 2, 3])

        assert vars(holder)["values"] is holder.values

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

    def test_dict_factory_replaces_the_container(self) -> None:
        @dataclass
        class Point:
            x: int

        assert asdict(Point(1), dict_factory=list) == [("x", 1)]


class TestGeneratedEqualityComparesTuples:
    """Generated `__eq__` | O(n) | O(n), with 3.13 dropping the space to O(1).

    Measured at 200 fields and above: at 10 fields the two tuples come off a
    freelist on 3.11 and 3.12 and the peak reads zero for a reason that has
    nothing to do with the bound.
    """

    def test_it_compares_every_field(self) -> None:
        point_type = wide(50)
        same = point_type(*range(50))
        other = point_type(*range(49), 999)

        assert point_type(*range(50)) == same
        assert same != other

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="3.13 stops materializing them")
    def test_the_peak_tracks_the_field_count_before_313(self) -> None:
        narrow_type, broad_type = wide(200), wide(2_000)
        narrow = (narrow_type(*range(200)), narrow_type(*range(200)))
        broad = (broad_type(*range(2_000)), broad_type(*range(2_000)))
        assert narrow[0] == narrow[1]  # warm the code paths
        assert broad[0] == broad[1]

        narrow_peak = peak_bytes(lambda: narrow[0] == narrow[1])
        broad_peak = peak_bytes(lambda: broad[0] == broad[1])

        assert narrow_peak > 0, "the tuples should be visible to tracemalloc here"
        assert broad_peak > narrow_peak * 5, (
            f"10x the fields moved the peak from {narrow_peak} to {broad_peak} bytes"
        )

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="the tuples are built before 3.13")
    def test_the_peak_is_flat_from_313(self) -> None:
        broad_type = wide(2_000)
        left, right = broad_type(*range(2_000)), broad_type(*range(2_000))
        assert left == right  # warm the code paths

        assert peak_bytes(lambda: left == right) == 0

    @pytest.mark.timing
    def test_the_time_is_linear_in_the_fields_on_every_version(self) -> None:
        narrow_type, broad_type = wide(200), wide(2_000)
        narrow = (narrow_type(*range(200)), narrow_type(*range(200)))
        broad = (broad_type(*range(2_000)), broad_type(*range(2_000)))

        narrow_ns = best_ns(lambda: narrow[0] == narrow[1], inner=20)
        broad_ns = best_ns(lambda: broad[0] == broad[1], inner=5)

        ratio = broad_ns / narrow_ns
        assert ratio > 4, (
            f"10x the fields cost x{ratio:.2f} ({narrow_ns:.0f}ns to {broad_ns:.0f}ns)"
        )


class TestHashabilityFollowsEqAndFrozen:
    """`eq=True` sets `__hash__` to None; only `frozen=True` with it gets one."""

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

        assert Frozen.__hash__ is not None
        assert len({Frozen(1), Frozen(1)}) == 1

    def test_eq_false_keeps_the_inherited_hash(self) -> None:
        @dataclass(eq=False)
        class Identity:
            a: int

        assert Identity.__hash__ is object.__hash__
        assert Identity(1) != Identity(1)
        assert len({Identity(1), Identity(1)}) == 2

    def test_order_generates_the_four_comparisons(self) -> None:
        @dataclass(order=True)
        class Version:
            major: int
            minor: int

        assert Version(1, 2) < Version(1, 10)
        assert sorted([Version(2, 0), Version(1, 5)])[0] == Version(1, 5)
        assert all(hasattr(Version, name) for name in ("__lt__", "__le__", "__gt__", "__ge__"))


class TestFrozenInstances:
    """`frozen=True` installs a raising `__setattr__` and routes `__init__`
    through `object.__setattr__`."""

    @dataclass(frozen=True)
    class Point:
        x: float
        y: float

    def test_assignment_raises(self) -> None:
        point = self.Point(1.0, 2.0)

        with pytest.raises(FrozenInstanceError, match="cannot assign"):
            point.x = 5.0  # type: ignore[misc]

    def test_deletion_raises_too(self) -> None:
        point = self.Point(1.0, 2.0)

        with pytest.raises(FrozenInstanceError):
            del point.x  # type: ignore[misc]

    def test_it_is_an_attribute_error(self) -> None:
        assert issubclass(FrozenInstanceError, AttributeError)

    def test_construction_still_sets_the_fields(self) -> None:
        assert self.Point(1.0, 2.0).x == 1.0


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

    def test_post_init_runs_on_construction(self) -> None:
        first = self.Measurement(3)

        assert (first.value, first.scaled) == (3, 6)

    def test_replace_recomputes_rather_than_copies(self) -> None:
        first = self.Measurement(3)

        assert replace(first, value=4).scaled == 8

    def test_an_init_false_field_is_refused(self) -> None:
        """ValueError before 3.13, TypeError from 3.13 - same refusal, new type."""
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

    def test_the_marker_leaves_no_field_behind(self) -> None:
        assert [f.name for f in fields(self.Request)] == ["url", "timeout"]


class TestIntrospection:
    """`fields()` | O(n) | O(n) rebuilt per call, `is_dataclass()` | O(1)."""

    @dataclass
    class Point:
        x: float
        y: float = 0.0

    def test_fields_rebuilds_its_tuple_each_call(self) -> None:
        assert fields(self.Point) == fields(self.Point)
        assert fields(self.Point) is not fields(self.Point)

    def test_a_field_carries_the_sentinel_when_it_has_no_default(self) -> None:
        first, second = fields(self.Point)

        assert isinstance(first, Field)
        assert first.default is MISSING
        assert second.default == 0.0

    def test_missing_is_not_none(self) -> None:
        assert MISSING is not None
        assert bool(MISSING) is True

    def test_is_dataclass_answers_for_class_and_instance(self) -> None:
        assert is_dataclass(self.Point)
        assert is_dataclass(self.Point(1.0))
        assert not is_dataclass(object())

    def test_default_factory_runs_per_instance(self) -> None:
        @dataclass
        class Config:
            tags: list = field(default_factory=list)

        first, second = Config(), Config()

        assert first.tags == [] and first.tags is not second.tags

    def test_a_mutable_default_is_rejected_outright(self) -> None:
        with pytest.raises(ValueError, match="mutable default"):

            @dataclass
            class Broken:
                tags: list = []  # noqa: RUF012


class TestMakeDataclass:
    """`make_dataclass()` | O(n) | O(n): the decorator at run time."""

    def test_it_builds_a_working_class(self) -> None:
        point_type = make_dataclass("Point", [("x", float), ("y", float)])

        assert [f.name for f in fields(point_type)] == ["x", "y"]
        assert point_type(1.0, 2.0) == point_type(1.0, 2.0)

    def test_each_call_builds_a_new_class(self) -> None:
        first = make_dataclass("P", [("x", int)])
        second = make_dataclass("P", [("x", int)])

        assert first is not second
        assert first(1) != second(1)

    @pytest.mark.timing
    def test_generation_grows_with_the_field_count(self) -> None:
        narrow = [("f0", int)]
        broad = [(f"f{index}", int) for index in range(100)]

        narrow_ns = best_ns(lambda: make_dataclass("N", narrow))
        broad_ns = best_ns(lambda: make_dataclass("B", broad))

        ratio = broad_ns / narrow_ns
        assert ratio > 2, (
            f"100 fields against one cost x{ratio:.2f} ({narrow_ns:.0f}ns to {broad_ns:.0f}ns)"
        )


class TestInheritance:
    """Fields are collected across the MRO, so a subclass costs the total."""

    def test_the_base_fields_come_first(self) -> None:
        @dataclass
        class Base:
            a: int

        @dataclass
        class Derived(Base):
            b: int

        assert [f.name for f in fields(Derived)] == ["a", "b"]
        assert Derived(1, 2).a == 1

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


def _run(source: str, cwd: Any) -> subprocess.CompletedProcess[str]:
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
    """Every block runs, several of them on the strength of an assert that
    would fail if the documented behaviour changed."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_every_block_runs(self, tmp_path: Any) -> None:
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

    def test_the_runner_catches_a_broken_block(self, tmp_path: Any) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = _blocks()[0][1]
        broken = original.replace("from dataclasses import", "from dataclasses import missing,", 1)
        assert broken != original, "the mutation did not reach an import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "ImportError" in result.stderr
