"""Tests to verify documented behaviour of the typing module.

docs/stdlib/typing.md had three rows and claimed type hints cost nothing at
runtime. Both parts needed work, and the measurements are what settled the
replacement.

Three facts drive the page, and all three move with the version:

* **Subscription is memoized.** `List[int] is List[int]` on every supported
  version, while `list[int] is not list[int]` - the builtin generics do not
  share that cache. Identity, so no tolerance is involved.
* **`isinstance()` against a runtime protocol is O(m) until 3.12.** One member
  against forty costs 2,480ns to 10,429ns on 3.10 and 2,121ns to 9,219ns on
  3.11. From 3.12 the answer is cached per class and the width stops mattering:
  207/209ns on 3.12, 163/163 on 3.13, 169/169 on 3.14.
* **Annotations are evaluated when the `def` runs, until 3.14.** Defining a
  function with three parameterized hints against a bare one costs x16.0 on
  3.10, x15.2 on 3.11, x22.5 on 3.12 and x16.7 on 3.13. PEP 649 makes 3.14
  lazy, and the gap falls to x1.7.

`Union` is the fourth version boundary: it flattens and deduplicates on every
version, but from 3.14 it produces a `types.UnionType` - the same object `X | Y`
gives - and is no longer memoized, so two identical unions stop being identical.

`get_type_hints()` is the one linear introspection, x7.4 to x8.3 per 10x the
annotations at the larger step.

Not settled here:

* What a `typing` import costs. The module builds every alias at import, but a
  suite that has already imported it cannot measure that without a subprocess
  per version, and the number would be a constant.
* Whether the protocol cache from 3.12 can be defeated. It is keyed per class,
  and only the documented shape was measured.
* The eight names the page marks 3.12+, 3.13+ or 3.14+ on interpreters that
  lack them; the coverage check allows those absences and asserts the marker.

Axes not varied: protocols with non-method members, generic classes with more
than two parameters, and `get_type_hints` over deep inheritance beyond one
merge.
"""

import pathlib
import re
import subprocess
import sys
import textwrap
import time
import typing
from collections.abc import Callable
from typing import (
    TYPE_CHECKING,
    NamedTuple,
    NewType,
    Optional,
    Protocol,
    TypedDict,
    Union,
    cast,
    get_args,
    get_origin,
    get_type_hints,
    is_typeddict,
    runtime_checkable,
)

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "typing.md"

EXPECTED_BLOCKS = 8

# Documented, but absent from the older interpreters. Each row must say so.
ADDED_AFTER_310 = {
    "LiteralString": "3.11",
    "Never": "3.11",
    "NotRequired": "3.11",
    "Required": "3.11",
    "Self": "3.11",
    "TypeVarTuple": "3.11",
    "Unpack": "3.11",
    "assert_never": "3.11",
    "assert_type": "3.11",
    "clear_overloads": "3.11",
    "dataclass_transform": "3.11",
    "get_overloads": "3.11",
    "reveal_type": "3.11",
    "TypeAliasType": "3.12",
    "override": "3.12",
    "NoDefault": "3.13",
    "ReadOnly": "3.13",
    "TypeIs": "3.13",
    "get_protocol_members": "3.13",
    "is_protocol": "3.13",
    "evaluate_forward_ref": "3.14",
}


def best_ns(func: Callable[[], object], repeats: int = 9, inner: int = 1) -> float:
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


def _documented_names() -> set[str]:
    """Every `typing.<name>` the Complexity Reference tables mention."""
    text = PAGE.read_text(encoding="utf-8")
    start = text.index("## Complexity Reference")
    end = text.index("\n## Subscription Is Memoized", start)
    return set(re.findall(r"typing\.([A-Za-z_][A-Za-z0-9_]*)", text[start:end]))


class TestEveryPublicNameIsDocumented:
    """The tables have to name every entry in `typing.__all__`.

    typing grew 21 names between 3.10 and 3.14 without losing any, so the
    interpreter running the suite decides how much of the table is live.
    """

    def test_no_exported_name_is_missing_from_the_tables(self) -> None:
        missing = sorted(set(typing.__all__) - _documented_names())

        assert not missing, f"{len(missing)} exported names absent from the tables: {missing}"

    def test_the_tables_name_nothing_that_does_not_exist(self) -> None:
        """The other direction, so a typo cannot pass as coverage."""
        unknown = sorted(_documented_names() - set(typing.__all__) - set(ADDED_AFTER_310))

        assert not unknown, f"the tables name attributes typing does not have: {unknown}"

    def test_every_later_addition_carries_its_version(self) -> None:
        rows = [
            line for line in PAGE.read_text(encoding="utf-8").splitlines() if line.startswith("|")
        ]

        for name, version in sorted(ADDED_AFTER_310.items()):
            owning = [row for row in rows if f"typing.{name}" in row]
            assert len(owning) == 1, f"expected one row naming {name}, found {len(owning)}"
            assert version in owning[0], f"the {name} row should say {version}+: {owning[0]}"

    def test_the_additions_list_matches_this_interpreter(self) -> None:
        """A name recorded as 3.13+ must actually be absent on 3.12."""
        current = sys.version_info[:2]
        for name, version in ADDED_AFTER_310.items():
            introduced = tuple(int(part) for part in version.split("."))
            if current >= introduced:
                assert hasattr(typing, name), f"{name} should exist on {current}"
            else:
                assert not hasattr(typing, name), f"{name} should not exist on {current}"

    def test_the_module_has_not_grown_names_this_suite_has_not_seen(self) -> None:
        assert 80 <= len(typing.__all__) <= 110, (
            f"typing exports {len(typing.__all__)} names; re-run the coverage audit"
        )

    def test_the_coverage_check_would_notice_a_gap(self) -> None:
        """A coverage test that cannot fail proves nothing about coverage."""
        documented = _documented_names()

        assert {"Any", "Union", "Protocol", "get_type_hints", "cast"} <= documented
        thinned = documented - {"NewType"}
        assert set(typing.__all__) - thinned == {"NewType"}, (
            "dropping one row from the extracted set should surface it as missing"
        )


class TestSubscriptionIsMemoized:
    """Parameterizing a `typing` generic returns the same object; the builtin
    generics do not share that cache.

    `typing.List` and `list` are the two sides of this comparison, so neither
    may be rewritten into the other - see the per-file ruff ignore.
    """

    def test_the_same_parameters_give_the_same_object(self) -> None:
        assert typing.List[int] is typing.List[int]
        assert typing.Dict[str, int] is typing.Dict[str, int]

    def test_different_parameters_do_not(self) -> None:
        assert typing.List[int] is not typing.List[str]

    def test_the_builtin_form_is_not_cached(self) -> None:
        assert list[int] is not list[int]
        assert list[int] == list[int]

    def test_the_two_forms_are_genuinely_different_objects(self) -> None:
        """So the contrast above is not comparing a thing with itself."""
        assert typing.List[int] is not list[int]

    def test_nested_parameters_are_cached_too(self) -> None:
        assert typing.Dict[str, typing.List[int]] is typing.Dict[str, typing.List[int]]


class TestUnionNormalises:
    """`Union` flattens and deduplicates, which is why its row is O(p²)."""

    def test_duplicates_are_dropped(self) -> None:
        assert Union[int, str, int] == Union[int, str]
        assert len(get_args(Union[int, str, int])) == 2

    def test_nested_unions_are_flattened(self) -> None:
        assert Union[int, str | float] == Union[int, str, float]
        assert len(get_args(Union[int, str | float])) == 3

    def test_optional_is_a_union_with_none(self) -> None:
        assert Optional[int] == Union[int, None]
        assert type(None) in get_args(Optional[int])

    def test_a_single_argument_collapses(self) -> None:
        assert Union[int] is int

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="3.14 drops the union cache")
    def test_unions_are_memoized_before_314(self) -> None:
        assert Union[int, str] is Union[int, str]

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="the change lands in 3.14")
    def test_from_314_a_union_is_the_pipe_form(self) -> None:
        assert Union[int, str] == int | str
        assert Union[int, str] is not Union[int, str]


class TestRuntimeProtocols:
    """`isinstance()` against a runtime-checkable protocol: O(m) before 3.12,
    a cached lookup from 3.12."""

    @staticmethod
    def _protocol(members: int) -> type:
        body: dict[str, object] = {"__annotations__": {}}
        for index in range(members):
            body[f"m{index}"] = lambda self: None
        bases: tuple[type, ...] = (Protocol,)  # type: ignore[assignment]
        return runtime_checkable(type("Wide", bases, body))

    @staticmethod
    def _implementation(members: int) -> object:
        body = {f"m{index}": (lambda self: None) for index in range(members)}
        return type("Impl", (), body)()

    def test_a_matching_object_passes(self) -> None:
        @runtime_checkable
        class Closeable(Protocol):
            def close(self) -> None: ...

        class Handle:
            def close(self) -> None: ...

        assert isinstance(Handle(), Closeable)
        assert not isinstance(object(), Closeable)

    def test_an_unmarked_protocol_refuses(self) -> None:
        class Unmarked(Protocol):
            def close(self) -> None: ...

        with pytest.raises(TypeError, match="runtime_checkable"):
            isinstance(object(), Unmarked)  # type: ignore[misc]

    def test_it_checks_names_and_not_signatures(self) -> None:
        """Which is the caveat the page carries next to the bound."""

        @runtime_checkable
        class Closeable(Protocol):
            def close(self) -> None: ...

        class WrongSignature:
            def close(self, how: str, when: int) -> None: ...

        assert isinstance(WrongSignature(), Closeable)

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="cached from 3.12")
    def test_the_width_costs_before_312(self) -> None:
        narrow, wide = self._protocol(1), self._protocol(40)
        obj = self._implementation(40)
        assert isinstance(obj, narrow) and isinstance(obj, wide)

        narrow_ns = best_ns(lambda: isinstance(obj, narrow), inner=20)
        wide_ns = best_ns(lambda: isinstance(obj, wide), inner=20)

        ratio = wide_ns / narrow_ns
        assert ratio > 2, (
            f"40x the members cost x{ratio:.2f} ({narrow_ns:.0f}ns to {wide_ns:.0f}ns); "
            "before 3.12 each member is checked in turn"
        )

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 12), reason="O(m) before 3.12")
    def test_the_width_stops_costing_from_312(self) -> None:
        narrow, wide = self._protocol(1), self._protocol(40)
        obj = self._implementation(40)
        assert isinstance(obj, narrow) and isinstance(obj, wide)

        narrow_ns = best_ns(lambda: isinstance(obj, narrow), inner=50)
        wide_ns = best_ns(lambda: isinstance(obj, wide), inner=50)

        ratio = wide_ns / narrow_ns
        assert ratio < 1.6, (
            f"40x the members cost x{ratio:.2f} ({narrow_ns:.0f}ns to {wide_ns:.0f}ns); "
            "from 3.12 the answer is cached per class"
        )

    @pytest.mark.skipif(
        not hasattr(typing, "get_protocol_members"), reason="get_protocol_members is 3.13+"
    )
    def test_the_members_can_be_read_back(self) -> None:
        wide = self._protocol(5)

        members = typing.get_protocol_members(wide)  # type: ignore[attr-defined]

        assert members == {f"m{index}" for index in range(5)}
        assert typing.is_protocol(wide) is True  # type: ignore[attr-defined]


class TestAnnotationsCostSomethingBefore314:
    """An annotation is an expression, evaluated when the `def` runs - until
    PEP 649 makes 3.14 lazy."""

    @staticmethod
    def _plain() -> object:
        def function(first, second):  # noqa: ANN001, ANN202
            return first

        return function

    @staticmethod
    def _hinted() -> object:
        def function(
            first: typing.Dict[str, typing.List[int]],
            second: typing.Optional[typing.Union[int, str]],
        ) -> typing.List[typing.Dict[str, int]]:
            return first  # type: ignore[return-value]

        return function

    def test_neither_form_checks_anything_when_called(self) -> None:
        hinted = self._hinted()
        assert callable(hinted)
        assert hinted("not a dict", "not an int") == "not a dict"  # type: ignore[operator]

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="lazy from 3.14")
    def test_defining_with_hints_costs_more_before_314(self) -> None:
        plain_ns = best_ns(self._plain, inner=200)
        hinted_ns = best_ns(self._hinted, inner=200)

        ratio = hinted_ns / plain_ns
        assert ratio > 5, (
            f"hints cost x{ratio:.2f} to define ({plain_ns:.0f}ns to {hinted_ns:.0f}ns); "
            "before 3.14 every annotation is evaluated at definition time"
        )

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 14), reason="eager before 3.14")
    def test_defining_with_hints_is_nearly_free_from_314(self) -> None:
        plain_ns = best_ns(self._plain, inner=200)
        hinted_ns = best_ns(self._hinted, inner=200)

        ratio = hinted_ns / plain_ns
        assert ratio < 5, (
            f"hints cost x{ratio:.2f} to define ({plain_ns:.0f}ns to {hinted_ns:.0f}ns); "
            "from 3.14 annotations are evaluated lazily"
        )

    def test_type_checking_is_false_at_runtime(self) -> None:
        assert TYPE_CHECKING is False


class TestReadingHintsBack:
    """`get_type_hints()` | O(k·s) | O(k), and taking an alias apart is O(1)."""

    @staticmethod
    def _function(annotations: int) -> Callable[..., int]:
        parameters = ", ".join(f"a{index}: int" for index in range(annotations))
        namespace: dict[str, object] = {}
        exec(  # noqa: S102 - building the shape under test is the point
            f"def f({parameters}) -> int: return 0", {"int": int}, namespace
        )
        return cast(Callable[..., int], namespace["f"])

    def test_it_resolves_every_annotation(self) -> None:
        def transform(rows: typing.Dict[str, typing.List[int]], limit: int) -> typing.List[int]:
            return []

        hints = get_type_hints(transform)

        assert hints["limit"] is int
        assert hints["return"] == typing.List[int]
        assert hints["rows"] == typing.Dict[str, typing.List[int]]

    def test_a_class_merges_its_whole_mro(self) -> None:
        class Base:
            base_field: int

        class Derived(Base):
            own_field: str

        hints = get_type_hints(Derived)

        assert hints == {"base_field": int, "own_field": str}

    def test_string_annotations_are_evaluated(self) -> None:
        def later(value: "typing.List[int]") -> "int":
            return 0

        assert get_type_hints(later) == {"value": typing.List[int], "return": int}

    def test_taking_an_alias_apart_reads_attributes(self) -> None:
        assert get_origin(dict[str, int]) is dict
        assert get_args(dict[str, int]) == (str, int)
        assert get_origin(int) is None
        assert get_args(int) == ()

    @pytest.mark.timing
    def test_ten_times_the_annotations_costs_far_more_than_a_constant(self) -> None:
        few = self._function(10)
        many = self._function(100)

        few_ns = best_ns(lambda: get_type_hints(few), inner=3)
        many_ns = best_ns(lambda: get_type_hints(many), inner=3)

        ratio = many_ns / few_ns
        assert ratio > 3, (
            f"10x the annotations cost x{ratio:.2f} ({few_ns:.0f}ns to {many_ns:.0f}ns); "
            "a constant-time lookup would give x1"
        )


class TestDeclaringTypes:
    """`NamedTuple`, `TypedDict` and `NewType`: one class or function per
    declaration, built at import."""

    class Point(NamedTuple):
        x: float
        y: float

    class Config(TypedDict):
        name: str
        retries: int

    def test_a_named_tuple_is_a_tuple(self) -> None:
        point = self.Point(1.0, 2.0)

        assert point.x == 1.0
        assert tuple(point) == (1.0, 2.0)
        assert isinstance(point, tuple)

    def test_a_typed_dict_is_a_dict(self) -> None:
        config: TestDeclaringTypes.Config = {"name": "svc", "retries": 3}

        assert isinstance(config, dict)
        assert is_typeddict(self.Config) is True
        assert is_typeddict(self.Point) is False

    def test_new_type_returns_its_argument(self) -> None:
        UserId = NewType("UserId", int)
        value = 7

        assert UserId(value) is value
        assert UserId.__supertype__ is int  # type: ignore[attr-defined]


class TestCastIsANoOp:
    """`cast(typ, val)` | O(1) | O(1): it returns `val`, unexamined."""

    def test_it_returns_the_same_object(self) -> None:
        values = [1, 2, 3]

        assert cast(typing.List[str], values) is values

    def test_the_type_is_never_looked_at(self) -> None:
        values = [1, 2, 3]

        assert cast("anything at all", values) is values  # type: ignore[misc]


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


def _run(source: str, cwd: object) -> subprocess.CompletedProcess[str]:
    script = cast(pathlib.Path, cwd) / "_block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, script.name],
        cwd=cast(pathlib.Path, cwd),
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Every block runs, including the one that starts with a `__future__`
    import and so has to be the first statement in its own file."""

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
        broken = original.replace("from typing import", "from typing import Missing,", 1)
        assert broken != original, "the mutation did not reach an import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "ImportError" in result.stderr
