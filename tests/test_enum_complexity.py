"""Evidence for docs/stdlib/enum.md.

Hashable integer lookup is measured across 10 and 1,000 members and between
first and last members. Unhashable list/dict values count comparisons at
10 and 100 members with constant-size values. Proxy allocations vary member
count, and a live backing-map mutation distinguishes a view from a copy.
Named global_str results use identity at both enum widths; global_enum exports
are checked in an isolated module. show_flag_values varies set-bit count and
integer width independently, checking output allocation in both dimensions.
The bit-work upper bound follows released CPython 3.14 Lib/enum.py's repeated
integer operations; no timing exponent is inferred from output allocation.
The bin helper checks padded output length, signs, and allocation growth. Its
integer exponentiation cost is left separate, as seen in released CPython
3.11 and 3.14 Lib/enum.py; output allocation alone does not bound that work.

Coverage includes enum.__all__ and the documented non-exported APIs listed at
https://docs.python.org/3/library/enum.html#module-contents.
All ten code blocks execute in subprocesses. Version gates cover membership,
flag iteration, and later APIs. Construction timings cover hashable integers.
Custom _missing_, hashing, equality and value formatting can execute arbitrary
code and are excluded from the simple lookup/helper bounds. Tests do not vary
custom class-building hooks, nested enum values or FlagBoundary policies.
"""

import enum
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import types
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
        "show_flag_values",
        "bin",
    ],
    "3.11",
) | {"EnumDict": "3.13"}


# Public in the official module reference, but absent from enum.__all__.
DOCUMENTED_NON_EXPORTS = {"show_flag_values", "bin"}


def _public_names() -> set[str]:
    return set(enum.__all__) | {name for name in DOCUMENTED_NON_EXPORTS if hasattr(enum, name)}


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
    """The tables cover exports plus documented public helpers outside __all__.

    enum went from 7 names to 30 across the supported range, so most of the
    table is version-gated and the interpreter decides how much is live.
    """

    def test_no_exported_name_is_missing_from_the_tables(self) -> None:
        missing = sorted(_public_names() - _documented_names())

        assert not missing, f"{len(missing)} exported names absent from the tables: {missing}"

    def test_the_tables_name_nothing_that_does_not_exist(self) -> None:
        """The other direction, so a typo cannot pass as coverage."""
        unknown = sorted(_documented_names() - _public_names() - set(ADDED_AFTER_310))

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
        assert _public_names() - thinned == {"IntFlag"}, (
            "dropping one row from the extracted set should surface it as missing"
        )


class TestLookupByValueIsADict:
    """Hashable integer `C(value)` | O(1) expected | O(1).

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


class TestUnhashableLookup:
    @pytest.mark.parametrize("kind", [list, dict])
    @pytest.mark.parametrize("count", [10, 100])
    def test_lookup_scans_values(self, kind: type, count: int) -> None:
        comparisons = 0

        class Value(kind):
            def __eq__(self, other: object) -> bool:
                nonlocal comparisons
                comparisons += 1
                return super().__eq__(other)

        def value(index: int) -> Any:
            return Value([index] if kind is list else {"v": index})

        cls: Any = Enum("Values", {f"M{i}": value(i) for i in range(count)})
        assert not cls._value2member_map_
        for index in (0, count - 1):
            comparisons = 0
            assert cls(value(index)) is cls[f"M{index}"]
            assert comparisons == index + 1
        comparisons = 0
        with pytest.raises(ValueError):
            cls(value(-1))
        assert count <= comparisons <= 2 * count
        if sys.version_info >= (3, 13):
            comparisons = 0
            assert value(count - 1) in cls
            assert count <= comparisons <= 2 * count
        else:
            # 3.10 and 3.11 refuse any raw value; 3.12 hashes before comparing,
            # so an unhashable one raises there too. 3.13 is the first to scan.
            with pytest.raises(TypeError):
                assert value(count - 1) in cls

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="value containment is 3.12+")
    @pytest.mark.parametrize("count", [10, 100])
    def test_raw_hashable_containment_can_scan(self, count: int) -> None:
        comparisons = 0

        class Value(int):
            __hash__ = int.__hash__

            def __eq__(self, other: object) -> bool:
                nonlocal comparisons
                comparisons += 1
                return int.__eq__(self, other)

        cls: Any = Enum("Values", {f"M{i}": Value(i) for i in range(count)})
        comparisons = 0
        assert Value(-1) not in cls
        assert comparisons <= 2 * count
        if sys.version_info >= (3, 14):
            assert comparisons == count


class TestMembersProxy:
    def test_proxy_is_live_and_read_only(self) -> None:
        cls = numbered(10)
        proxy = cls.__members__
        assert isinstance(proxy, types.MappingProxyType)
        with pytest.raises(TypeError):
            proxy["EXTRA"] = cls.M0  # type: ignore[index]
        cls._member_map_["EXTRA"] = cls.M0
        assert proxy["EXTRA"] is cls.M0

    def test_view_allocation_stays_small_while_copy_grows(self) -> None:
        peaks, copies = [], []
        for count in (100, 1_000):
            cls = numbered(count)
            tracemalloc.start()
            try:
                proxy = cls.__members__
                peaks.append(tracemalloc.get_traced_memory()[1])
            finally:
                tracemalloc.stop()
            tracemalloc.start()
            try:
                copied = dict(proxy)
                copies.append(tracemalloc.get_traced_memory()[0])
            finally:
                tracemalloc.stop()
            assert len(proxy) == count
            assert copied == proxy
        assert max(peaks) < copies[0] // 4, (peaks, copies)
        assert copies[1] > copies[0] * 5, copies


@pytest.mark.skipif(sys.version_info < (3, 11), reason="helpers are 3.11+")
class TestPublicHelpers:
    @pytest.mark.parametrize("count", [10, 1_000])
    def test_global_str_returns_the_stored_name(self, count: int) -> None:
        cls = numbered(count)
        member = cls[f"M{count - 1}"]
        assert enum.global_str(member) is member.name  # type: ignore[attr-defined]

    def test_global_str_formats_unnamed_values(self) -> None:
        flags = Flag("Bits", {"A": 1})
        assert flags(0).name is None
        assert enum.global_str(flags(0)) == "Bits(0)"  # type: ignore[attr-defined]

    @pytest.mark.parametrize("count", [10, 100])
    def test_global_enum_exports_members(self, count: int, monkeypatch: pytest.MonkeyPatch) -> None:
        module = types.ModuleType("_enum_helper_test")
        monkeypatch.setitem(sys.modules, module.__name__, module)
        cls: Any = Enum("Exported", {f"M{i}": i for i in range(count)}, module=module.__name__)
        assert enum.global_enum(cls) is cls  # type: ignore[attr-defined]
        assert all(vars(module)[name] is member for name, member in cls.__members__.items())
        assert str(cls.M0) == "M0"
        assert repr(cls.M0) == "_enum_helper_test.M0"

    def test_non_exported_helpers_are_in_the_coverage_inventory(self) -> None:
        assert DOCUMENTED_NON_EXPORTS <= _public_names()
        for name in DOCUMENTED_NON_EXPORTS:
            thinned = _documented_names() - {name}
            assert _public_names() - thinned == {name}

    @pytest.mark.parametrize("dimension", ["bits", "width"])
    def test_show_flag_values_output_scales_in_both_dimensions(self, dimension: str) -> None:
        retained = []
        sizes = ((8, 4096), (128, 4096)) if dimension == "bits" else ((16, 256), (16, 8192))
        for count, width in sizes:
            expected = [1 << index for index in range(width - count, width)]
            value = sum(expected)
            tracemalloc.start()
            try:
                result = enum.show_flag_values(value)  # type: ignore[attr-defined]
                retained.append(tracemalloc.get_traced_memory()[0])
            finally:
                tracemalloc.stop()
            assert result == expected
            assert len(result) == count
            assert value.bit_length() == width
        assert retained[1] > retained[0] * 5, retained

    def test_show_flag_values_accepts_flags_and_zero(self) -> None:
        flags = Flag("Bits", {"A": 1, "B": 4})
        assert enum.show_flag_values(flags.A | flags.B) == [1, 4]  # type: ignore[attr-defined]
        assert enum.show_flag_values(0) == []  # type: ignore[attr-defined]
        with pytest.raises(ValueError):
            enum.show_flag_values(-1)  # type: ignore[attr-defined]

    @pytest.mark.parametrize("padding", [False, True])
    def test_bin_output_scales_with_width(self, padding: bool) -> None:
        retained = []
        for width in (100, 10_000):
            value = 10 if padding else (1 << (width - 1))
            tracemalloc.start()
            try:
                result = enum.bin(value, width if padding else None)  # type: ignore[attr-defined]
                retained.append(tracemalloc.get_traced_memory()[0])
            finally:
                tracemalloc.stop()
            assert result.startswith("0b0 ")
            assert len(result) == width + 4
            assert int(result[4:], 2) == value
        assert retained[1] > retained[0] * 20, retained
        assert enum.bin(-11) == "0b1 0101"  # type: ignore[attr-defined]
