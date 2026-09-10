"""Tests to verify documented behaviour of the enum module.

docs/stdlib/enum.md said lookup by value was "O(n), linear search through
members". It is a dict lookup. `_value2member_map_` is built when the class body
runs, and the measurement is flat in both directions:

* Ten members against a thousand: 252ns and 247ns on 3.10, 140ns and 195ns on
  3.14. A scan over a thousand members would be a hundred times the ten-member
  case, not the same.
* Within one enum, the last member declared costs what the first does - 247ns
  against 220ns at a thousand members on 3.10, 195ns against 180ns on 3.14.
  A scan would find the first immediately and the last after n steps.

Lookup by name is flat the same way, and iteration is the operation that is
genuinely O(n): 1.1us for ten members against 67.6us for a thousand on 3.10.

Two version boundaries:

* `value in EnumClass` raises `TypeError` on 3.10 and 3.11 (with a
  `DeprecationWarning` announcing the change) and answers `True`/`False` from
  3.12.
* A combined `Flag` became sized and iterable in 3.11; before that `len()` on
  one raises.

The module also grew from 7 exported names on 3.10 to 30 on 3.14 - 22 of them
arriving at once in 3.11 - and the page's `verify()` row named something 3.10
does not have.

Not settled here:

* What `_missing_()` costs. It is caller-supplied by definition, and the page
  names it rather than pricing it.
* `global_enum` and the `pickle_by_*` helpers beyond their existence; both act
  on module namespaces and pickling, neither of which is a bound.
* `FlagBoundary` behaviour for out-of-range bits, which changes the result
  rather than the cost.

Axes not varied: enums with unhashable values (which fall back to a scan),
`__init_subclass__` hooks, and members whose values are other enums.
"""

import enum
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import warnings
from collections.abc import Callable
from enum import Enum, Flag, IntEnum, auto, unique
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "enum.md"

EXPECTED_BLOCKS = 10

# Documented, but absent from the older interpreters. Each row must say so.
ADDED_AFTER_310 = dict.fromkeys(
    [
        "CONFORM",
        "CONTINUOUS",
        "EJECT",
        "EnumCheck",
        "EnumType",
        "FlagBoundary",
        "KEEP",
        "NAMED_FLAGS",
        "ReprEnum",
        "STRICT",
        "StrEnum",
        "UNIQUE",
        "global_enum",
        "global_enum_repr",
        "global_flag_repr",
        "global_str",
        "member",
        "nonmember",
        "pickle_by_enum_name",
        "pickle_by_global_name",
        "property",
        "verify",
    ],
    "3.11",
) | {"EnumDict": "3.13"}


def best_ns(func: Callable[[], Any], repeats: int = 9, inner: int = 1) -> float:
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


def numbered(size: int, label: str = "E") -> Any:
    """An Enum of `size` members, valued 0 through size - 1."""
    return Enum(f"{label}{size}", {f"M{index}": index for index in range(size)})


def _documented_names() -> set[str]:
    """Every `enum.<name>` the Complexity Reference tables mention."""
    text = PAGE.read_text(encoding="utf-8")
    start = text.index("## Complexity Reference")
    end = text.index("\n## Enum Basics", start)
    return set(re.findall(r"enum\.([A-Za-z_][A-Za-z0-9_]*)", text[start:end]))


class TestEveryPublicNameIsDocumented:
    """The tables have to name every entry in `enum.__all__`.

    enum went from 7 names to 30 across the supported range, so most of the
    table is version-gated and the interpreter decides how much is live.
    """

    def test_no_exported_name_is_missing_from_the_tables(self) -> None:
        missing = sorted(set(enum.__all__) - _documented_names())

        assert not missing, f"{len(missing)} exported names absent from the tables: {missing}"

    def test_the_tables_name_nothing_that_does_not_exist(self) -> None:
        """The other direction, so a typo cannot pass as coverage."""
        unknown = sorted(_documented_names() - set(enum.__all__) - set(ADDED_AFTER_310))

        assert not unknown, f"the tables name attributes enum does not have: {unknown}"

    def test_every_later_addition_carries_its_version(self) -> None:
        rows = [
            line for line in PAGE.read_text(encoding="utf-8").splitlines() if line.startswith("|")
        ]

        for name, version in sorted(ADDED_AFTER_310.items()):
            owning = [row for row in rows if f"enum.{name}" in row]
            assert len(owning) >= 1, f"no row names {name}"
            assert any(version in row for row in owning), (
                f"the {name} row should say {version}+: {owning[0]}"
            )

    def test_the_additions_list_matches_this_interpreter(self) -> None:
        current = sys.version_info[:2]
        for name, version in ADDED_AFTER_310.items():
            introduced = tuple(int(part) for part in version.split("."))
            if current >= introduced:
                assert hasattr(enum, name), f"{name} should exist on {current}"
            else:
                assert not hasattr(enum, name), f"{name} should not exist on {current}"

    def test_the_module_has_not_grown_names_this_suite_has_not_seen(self) -> None:
        assert 7 <= len(enum.__all__) <= 33, (
            f"enum exports {len(enum.__all__)} names; re-run the coverage audit"
        )

    def test_the_coverage_check_would_notice_a_gap(self) -> None:
        """A coverage test that cannot fail proves nothing about coverage."""
        documented = _documented_names()

        assert {"Enum", "Flag", "IntEnum", "auto", "unique"} <= documented
        thinned = documented - {"IntFlag"}
        assert set(enum.__all__) - thinned == {"IntFlag"}, (
            "dropping one row from the extracted set should surface it as missing"
        )


class TestLookupByValueIsADict:
    """`C(value)` | O(1) | O(1).

    Two directions are measured: across enum sizes, and within one enum between
    the first member declared and the last. A linear search would fail both.
    """

    def test_the_map_is_what_answers(self) -> None:
        colors = numbered(10)

        assert hasattr(colors, "_value2member_map_")
        assert colors(5) is colors["M5"]
        assert colors(5).value == 5

    def test_a_value_with_no_member_raises(self) -> None:
        colors = numbered(10)

        with pytest.raises(ValueError, match="is not a valid"):
            colors(999)

    @pytest.mark.timing
    def test_a_hundred_times_the_members_costs_the_same(self) -> None:
        small, large = numbered(10, "S"), numbered(1_000, "L")

        small_ns = best_ns(lambda: small(5), inner=50)
        large_ns = best_ns(lambda: large(5), inner=50)

        ratio = large_ns / small_ns
        assert ratio < 3, (
            f"100x the members cost x{ratio:.2f} ({small_ns:.0f}ns to {large_ns:.0f}ns); "
            "a linear search would give about x100"
        )

    @pytest.mark.timing
    def test_the_last_member_costs_what_the_first_does(self) -> None:
        large = numbered(1_000, "P")

        first_ns = best_ns(lambda: large(0), inner=50)
        last_ns = best_ns(lambda: large(999), inner=50)

        ratio = last_ns / first_ns
        assert ratio < 3, (
            f"the last member cost x{ratio:.2f} the first "
            f"({first_ns:.0f}ns to {last_ns:.0f}ns); a scan would find the first at once"
        )


class TestLookupByNameIsADictToo:
    """`C['NAME']` and `C.NAME` | O(1) | O(1)."""

    def test_both_forms_reach_the_same_member(self) -> None:
        colors = numbered(10)

        assert colors["M3"] is colors.M3

    def test_an_unknown_name_raises_keyerror(self) -> None:
        colors = numbered(10)

        with pytest.raises(KeyError):
            colors["NOPE"]

    @pytest.mark.timing
    def test_a_hundred_times_the_members_costs_the_same(self) -> None:
        small, large = numbered(10, "SN"), numbered(1_000, "LN")

        small_ns = best_ns(lambda: small["M5"], inner=50)
        large_ns = best_ns(lambda: large["M5"], inner=50)

        ratio = large_ns / small_ns
        assert ratio < 3, (
            f"100x the members cost x{ratio:.2f} ({small_ns:.0f}ns to {large_ns:.0f}ns)"
        )


class TestIterationIsTheLinearOne:
    """`iter(C)` | O(n) | O(1), while `len(C)` stays O(1)."""

    def test_len_is_the_member_count(self) -> None:
        assert len(numbered(10)) == 10
        assert len(numbered(1_000, "Z")) == 1_000

    @pytest.mark.timing
    def test_len_does_not_move_with_the_member_count(self) -> None:
        small, large = numbered(10, "SL"), numbered(1_000, "LL")

        small_ns = best_ns(lambda: len(small), inner=100)
        large_ns = best_ns(lambda: len(large), inner=100)

        assert large_ns / small_ns < 3, f"{small_ns:.0f}ns to {large_ns:.0f}ns"

    @pytest.mark.timing
    def test_iteration_does(self) -> None:
        small, large = numbered(10, "SI"), numbered(1_000, "LI")

        small_ns = best_ns(lambda: list(small), inner=3)
        large_ns = best_ns(lambda: list(large), inner=3)

        ratio = large_ns / small_ns
        assert ratio > 10, (
            f"100x the members cost x{ratio:.2f} to iterate ({small_ns:.0f}ns to {large_ns:.0f}ns)"
        )


class TestMembersAreSingletons:
    """One object per member, so `is` is the right comparison."""

    class Color(Enum):
        RED = 1
        GREEN = 2

    def test_every_route_reaches_the_same_object(self) -> None:
        assert self.Color(1) is self.Color.RED
        assert self.Color["RED"] is self.Color.RED

    def test_a_member_is_not_its_value(self) -> None:
        assert self.Color.RED != 1
        assert self.Color.RED.value == 1

    def test_an_int_enum_member_is(self) -> None:
        class Priority(IntEnum):
            LOW = 1
            HIGH = 3

        assert Priority.HIGH == 3
        assert Priority.HIGH > Priority.LOW
        assert Priority.HIGH + 1 == 4
        assert sorted(Priority) == [Priority.LOW, Priority.HIGH]


class TestAliases:
    """A second name for one value is an alias: reachable, but not iterated."""

    class Color(Enum):
        RED = 1
        CRIMSON = 1
        GREEN = 2

    def test_the_alias_resolves_to_the_canonical_member(self) -> None:
        assert self.Color.CRIMSON is self.Color.RED

    def test_iteration_and_len_skip_it(self) -> None:
        assert [member.name for member in self.Color] == ["RED", "GREEN"]
        assert len(self.Color) == 2

    def test_members_includes_it(self) -> None:
        assert list(self.Color.__members__) == ["RED", "CRIMSON", "GREEN"]

    def test_unique_refuses_one(self) -> None:
        with pytest.raises(ValueError, match="duplicate values"):

            @unique
            class Duplicated(Enum):
                A = 1
                B = 1


class TestMembership:
    """`x in C`: a member always works; a bare value changed in 3.12."""

    class Color(Enum):
        RED = 1

    def test_a_member_is_in_its_own_enum(self) -> None:
        assert self.Color.RED in self.Color

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="answers from 3.12")
    def test_a_bare_value_raises_before_312(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with pytest.raises(TypeError):
                # The membership test itself is what raises here.
                assert 1 in self.Color

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="raises before 3.12")
    def test_a_bare_value_answers_from_312(self) -> None:
        assert (1 in self.Color) is True
        assert (99 in self.Color) is False

    def test_the_value_map_answers_on_every_version(self) -> None:
        """The workaround the page gives for 3.10 and 3.11."""
        assert 1 in self.Color._value2member_map_  # noqa: SLF001
        assert 99 not in self.Color._value2member_map_  # noqa: SLF001


class TestFlags:
    """`Flag` members are powers of two, so combining is one int operation."""

    class Permission(Flag):
        READ = auto()
        WRITE = auto()
        EXECUTE = auto()

    def test_the_values_are_powers_of_two(self) -> None:
        assert [member.value for member in self.Permission] == [1, 2, 4]

    def test_combining_and_testing(self) -> None:
        combined = self.Permission.READ | self.Permission.WRITE

        assert self.Permission.READ in combined
        assert self.Permission.EXECUTE not in combined
        assert combined & self.Permission.READ == self.Permission.READ

    def test_a_combination_is_looked_up_by_value_like_any_member(self) -> None:
        combined = self.Permission.READ | self.Permission.WRITE

        assert self.Permission(combined.value) is combined

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="sized and iterable from 3.11")
    def test_a_combination_is_sized_and_iterable_from_311(self) -> None:
        combined = self.Permission.READ | self.Permission.WRITE

        assert len(combined) == 2
        assert {member.name for member in combined} == {"READ", "WRITE"}

    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="the change lands in 3.11")
    def test_a_combination_has_no_length_before_311(self) -> None:
        combined = self.Permission.READ | self.Permission.WRITE

        with pytest.raises(TypeError):
            len(combined)


class TestBuildingCostsItsMembers:
    """The class body is the O(n) part; the functional API is the same work."""

    def test_the_functional_api_builds_the_same_thing(self) -> None:
        colors = Enum("Color", ["RED", "GREEN", "BLUE"])

        assert colors.RED.value == 1
        assert len(colors) == 3
        assert colors(1) is colors.RED

    def test_a_mapping_gives_explicit_values(self) -> None:
        status = Enum("Status", {"OK": 200, "MISSING": 404})

        assert status(404) is status.MISSING

    def test_methods_and_properties_are_not_members(self) -> None:
        class Planet(Enum):
            MERCURY = (3.303e23, 2.4397e6)
            EARTH = (5.976e24, 6.37814e6)

            def __init__(self, mass: float, radius: float) -> None:
                self.mass = mass
                self.radius = radius

            @property
            def surface_gravity(self) -> float:
                return 6.67300e-11 * self.mass / (self.radius * self.radius)

        assert len(Planet) == 2
        assert round(Planet.EARTH.surface_gravity, 2) == 9.80

    @pytest.mark.timing
    def test_building_grows_with_the_member_count(self) -> None:
        small = {f"M{index}": index for index in range(10)}
        large = {f"M{index}": index for index in range(1_000)}

        small_ns = best_ns(lambda: Enum("S", small), inner=1, repeats=5)
        large_ns = best_ns(lambda: Enum("L", large), inner=1, repeats=5)

        ratio = large_ns / small_ns
        assert ratio > 10, (
            f"100x the members cost x{ratio:.2f} to build ({small_ns:.0f}ns to {large_ns:.0f}ns)"
        )


@pytest.mark.skipif(not hasattr(enum, "verify"), reason="verify is 3.11+")
class TestVerify:
    """`verify()` | O(n) | O(n): the constraints applied once, at class build."""

    def test_continuous_refuses_a_gap(self) -> None:
        with pytest.raises(ValueError):

            @enum.verify(enum.CONTINUOUS)  # type: ignore[attr-defined]
            class Gapped(Enum):
                A = 1
                C = 3

    def test_unique_refuses_an_alias(self) -> None:
        with pytest.raises(ValueError):

            @enum.verify(enum.UNIQUE)  # type: ignore[attr-defined]
            class Duplicated(Enum):
                A = 1
                B = 1

    def test_a_well_formed_enum_passes(self) -> None:
        @enum.verify(enum.CONTINUOUS, enum.UNIQUE)  # type: ignore[attr-defined]
        class Fine(Enum):
            A = 1
            B = 2

        assert len(Fine) == 2


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
    """Every block runs, on every supported version - which is the point, since
    three of them branch on the interpreter."""

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
        broken = original.replace("from enum import", "from enum import Missing,", 1)
        assert broken != original, "the mutation did not reach an import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "ImportError" in result.stderr
