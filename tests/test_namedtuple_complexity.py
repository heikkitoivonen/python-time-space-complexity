"""Tests for docs/stdlib/namedtuple.md.

The page prices `namedtuple()` as an O(f) class factory and its instances as
plain tuples of f items. Space and identity rows are settled by observation -
which object an attribute returns, how big an instance is, whether a call
builds something new - and need no tolerance. Timing is used only where the
growth class itself is the claim: class creation, keyword construction, field
access and `_replace()`.

Measurement scope:

* `namedtuple()` is observed to give the class one `_tuplegetter` per field
  and a distinct class per call. A timing test builds classes of 400, 4,000
  and 40,000 fields and asserts each 10x step costs under 30x, which excludes
  the 100x a quadratic factory would give.
* An instance of a two-field and a 10,000-field class has the `sys.getsizeof`
  of a plain tuple of the same items, no `__dict__`, and is smaller than the
  dict of the same fields. Equality and hashing match the plain tuple's.
* Keyword construction is timed with every field passed by name at 1,000 and
  8,000 fields: the 8x step costs over 25x (quadratic predicts 64x, linear
  8x), while positional construction over the same sizes costs under 25x. The
  dict's keys are the class's own interned names, the shape `_asdict()`
  produces.
* Field access reads the first field of a two-field instance and the last of
  a 10,000-field one through `operator.attrgetter`; the second is under 10x
  the first, where a scan over the fields would give thousands.
* `_replace()` of one field returns a new instance of all f fields; a timing
  test asserts one-field replacement at 10,000 fields costs over 50x what it
  does at 10. `_asdict()` returns a new dict of f entries on each call.
  `_fields`, `_field_defaults` and `__match_args__` are the same object on
  every access.
* `_make()` is observed to drain a generator of n items before raising
  `TypeError` for a length other than f. `copy.copy()` returns a new instance
  for a named tuple and the same object for a plain tuple. `copy.replace()`
  and the `_replace()` exception type are guarded on `sys.version_info` at
  3.13.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The O(f) upper bounds for `_asdict()`, `_replace()`, `repr()` and
  positional construction, and the O(n) of `_make()`, are read from
  Lib/collections/__init__.py, whose `namedtuple()` changes no bound across
  3.10-3.14; the tests show the f-sized result each successful call builds,
  which is the lower bound.
* Comparison, hashing and unpacking are the tuple's own operations, and
  `copy.copy()` rebuilds the instance through `__getnewargs__`; their O(f)
  bounds follow from that. The tests observe tuple semantics and identity on
  two-field instances, not growth.
* That a keyword is matched by scanning the parameter list is read from
  Python/ceval.c's keyword loop on each supported release. Only the all-
  keyword case is timed; k is not varied at a fixed f.
* Field-name length and the cost of each value's `repr`, `__eq__` and
  `__hash__` are held fixed; the page prices both at O(1).
"""

from __future__ import annotations

import copy
import pathlib
import re
import subprocess
import sys
import textwrap
import time
from collections import namedtuple
from collections.abc import Callable, Iterator
from operator import attrgetter
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "namedtuple.md"
EXPECTED_BLOCKS = 7


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


def names(fields: int) -> list[str]:
    return [f"f{index}" for index in range(fields)]


class TestTheFactoryBuildsAClass:
    """`namedtuple()` | O(f) | O(f): one accessor per field, a new class per call."""

    def test_the_class_holds_one_accessor_per_field(self) -> None:
        for fields in (2, 1_000):
            cls = namedtuple("Wide", names(fields))
            getters = [
                value for value in vars(cls).values() if type(value).__name__ == "_tuplegetter"
            ]

            assert len(getters) == fields
            assert cls._fields == tuple(names(fields))

    def test_every_call_returns_a_distinct_class(self) -> None:
        first = namedtuple("Point", "x y")
        second = namedtuple("Point", "x y")

        assert first is not second
        assert not isinstance(second(1, 2), first)

    def test_comma_and_space_separated_names_are_the_same(self) -> None:
        assert namedtuple("P", "x, y")._fields == namedtuple("P", ["x", "y"])._fields

    def test_defaults_fill_the_rightmost_fields(self) -> None:
        point = namedtuple("Point", "x y z", defaults=[0, 0])

        assert point(1) == (1, 0, 0)
        assert point._field_defaults == {"y": 0, "z": 0}

    def test_rename_replaces_bad_names_by_position(self) -> None:
        # Lists held in variables, so the type checker does not reject them statically.
        renamed: list[str] = ["id", "def", "id", "_x"]
        rejected: list[str] = ["id", "def"]
        row = namedtuple("Row", renamed, rename=True)

        assert row._fields == ("id", "_1", "_2", "_3")
        with pytest.raises(ValueError, match="keyword"):
            namedtuple("Row", rejected)

    @pytest.mark.timing
    def test_building_the_class_is_linear_in_fields(self) -> None:
        sizes = (400, 4_000, 40_000)
        lists = [names(size) for size in sizes]
        durations = [best_ns(lambda n=n: namedtuple("Wide", n), repeats=3) for n in lists]
        ratios = [later / earlier for earlier, later in zip(durations, durations[1:], strict=False)]

        assert all(ratio < 30 for ratio in ratios), (
            f"10x steps in fields cost {[f'x{r:.1f}' for r in ratios]} "
            f"({[f'{d / 1e6:.1f}ms' for d in durations]}); a quadratic factory gives x100"
        )


class TestInstancesAreTuples:
    """Instances | O(f) space: tuple slots and nothing else; comparison and
    hashing are the tuple's."""

    @pytest.mark.parametrize("fields", [2, 10_000])
    def test_an_instance_is_the_size_of_a_plain_tuple(self, fields: int) -> None:
        cls = namedtuple("Wide", names(fields))
        values = tuple(range(fields))
        instance = cls(*values)

        assert sys.getsizeof(instance) == sys.getsizeof(values)
        assert not hasattr(instance, "__dict__")
        assert sys.getsizeof(instance) < sys.getsizeof(
            dict(zip(names(fields), values, strict=True))
        )

    def test_it_compares_and_hashes_as_a_tuple(self) -> None:
        point = namedtuple("Point", "x y")(3, 4)
        other = namedtuple("Other", "a b")(3, 4)

        assert point == (3, 4) == other
        assert hash(point) == hash((3, 4))
        assert point < (3, 5)

    def test_repr_names_every_field(self) -> None:
        assert repr(namedtuple("Point", "x y")(1, 2)) == "Point(x=1, y=2)"

    @pytest.mark.timing
    def test_field_access_does_not_scan_the_fields(self) -> None:
        small = namedtuple("Small", "f0 f1")(0, 1)
        wide_names = names(10_000)
        wide = namedtuple("Wide", wide_names)(*range(10_000))
        first, last = attrgetter("f0"), attrgetter(wide_names[-1])
        assert last(wide) == 9_999

        small_ns = best_ns(lambda: first(small), inner=2_000)
        wide_ns = best_ns(lambda: last(wide), inner=2_000)

        assert wide_ns < small_ns * 10, (
            f"the last of 10,000 fields took {wide_ns:.0f}ns against {small_ns:.0f}ns "
            "for the first of two"
        )


class TestKeywordConstructionScansTheParameters:
    """`Point(**fields)` | O(f·k): each keyword is matched by a scan, so every
    field by name is O(f²); positional construction stays O(f)."""

    SIZES = (1_000, 8_000)

    @staticmethod
    def _ratio(build: Callable[[Any, list[int], dict[str, int]], Any]) -> tuple[float, list[float]]:
        durations = []
        for fields in TestKeywordConstructionScansTheParameters.SIZES:
            cls = namedtuple("Wide", names(fields))
            values = list(range(fields))
            by_name = cls(*values)._asdict()
            durations.append(best_ns(lambda c=cls, v=values, d=by_name: build(c, v, d)))
        return durations[1] / durations[0], durations

    def test_keywords_and_make_build_the_same_record(self) -> None:
        cls = namedtuple("Record", "id name score")
        data = {"id": 1, "name": "Ada", "score": 9.5}

        assert cls(**data) == cls._make(data[name] for name in cls._fields) == (1, "Ada", 9.5)

    @pytest.mark.timing
    def test_every_field_by_keyword_is_quadratic(self) -> None:
        ratio, durations = self._ratio(lambda cls, values, data: cls(**data))

        assert ratio > 25, (
            f"8x the fields by keyword cost x{ratio:.1f} ({durations} ns); "
            "quadratic predicts x64, linear x8"
        )

    @pytest.mark.timing
    def test_every_field_by_position_is_linear(self) -> None:
        ratio, durations = self._ratio(lambda cls, values, data: cls(*values))

        assert ratio < 25, f"8x the fields by position cost x{ratio:.1f} ({durations} ns)"


class TestMakeBuildsBeforeChecking:
    """`_make(iterable)` | O(n): the whole iterable is consumed, then the
    length is checked against f."""

    def test_it_accepts_any_iterable(self) -> None:
        point = namedtuple("Point", "x y")

        assert point._make(iter([1, 2])) == (1, 2)

    def test_a_wrong_length_raises_after_draining_the_iterable(self) -> None:
        point = namedtuple("Point", "x y")
        taken: list[int] = []

        def items() -> Iterator[int]:
            for index in range(1_000):
                taken.append(index)
                yield index

        with pytest.raises(TypeError, match="Expected 2 arguments, got 1000"):
            point._make(items())
        assert len(taken) == 1_000


class TestConversionsBuildNewObjects:
    """`_asdict()` and `_replace()` | O(f) | O(f) build new objects; `_fields`,
    `_field_defaults` and `__match_args__` | O(1) are the class's own."""

    WIDE = namedtuple("WIDE", names(10_000), defaults=[0])

    def test_asdict_is_a_new_dict_of_every_field(self) -> None:
        record = self.WIDE(*range(10_000))

        first = record._asdict()

        assert type(first) is dict
        assert len(first) == 10_000
        assert record._asdict() is not first

    def test_replace_builds_a_whole_new_instance(self) -> None:
        record = self.WIDE(*range(10_000))

        changed = record._replace(f0=-1)

        assert changed is not record
        assert len(changed) == 10_000
        assert changed[0] == -1 and record[0] == 0
        assert changed[1:] == record[1:]

    def test_class_attributes_are_not_copied(self) -> None:
        record = self.WIDE(*range(10_000))

        assert record._fields is self.WIDE._fields
        assert self.WIDE._field_defaults is self.WIDE._field_defaults
        assert self.WIDE.__match_args__ is self.WIDE._fields

    def test_match_args_allow_positional_patterns(self) -> None:
        point = namedtuple("Point", "x y")

        match point(2, 0):
            case point(x, 0):
                matched = x
            case _:
                matched = None

        assert matched == 2

    def test_copying_builds_a_new_instance_unlike_a_plain_tuple(self) -> None:
        record = namedtuple("Point", "x y")(1, 2)
        plain = (1, 2)

        assert copy.copy(record) is not record
        assert copy.copy(record) == record
        assert copy.copy(plain) is plain

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="version: TypeError from 3.13")
    def test_an_unknown_field_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="unexpected field names"):
            namedtuple("Point", "x y")(1, 2)._replace(z=1)

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="version: ValueError before 3.13")
    def test_an_unknown_field_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="unexpected field names"):
            namedtuple("Point", "x y")(1, 2)._replace(z=1)

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="version: copy.replace() is 3.13+")
    def test_copy_replace_calls_replace(self) -> None:
        replace: Callable[..., Any] = getattr(copy, "replace")  # noqa: B009
        point = namedtuple("Point", "x y")(1, 2)

        assert replace(point, x=5) == (5, 2)
        assert getattr(type(point), "__replace__") is type(point)._replace  # noqa: B009

    @pytest.mark.timing
    def test_replacing_one_field_costs_every_field(self) -> None:
        small = namedtuple("Small", names(10))(*range(10))
        wide = self.WIDE(*range(10_000))

        small_ns = best_ns(lambda: small._replace(f0=-1), inner=20)
        wide_ns = best_ns(lambda: wide._replace(f0=-1), inner=20)

        assert wide_ns > small_ns * 50, (
            f"one field replaced at 10,000 fields took {wide_ns:.0f}ns against "
            f"{small_ns:.0f}ns at 10; O(f) predicts about x1000"
        )


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
        line, source = next((n, s) for n, s in _blocks() if "assert Again is not Point" in s)
        mutated = source.replace("assert Again is not Point", "assert Again is Point", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
