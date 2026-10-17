"""Tests for docs/builtins/property.md.

property is PyProperty_Type in Objects/descrobject.c. property_init_impl
stores fget, fset and fdel and, without a doc argument, reads fget.__doc__;
it calls none of them. property_descr_get returns the property itself for a
class access and otherwise calls fget once; property_descr_set calls fset or
fdel once, or raises AttributeError naming the missing function.
property_copy, behind getter(), setter() and deleter(), builds a new property
of the same type with one function replaced. These paths do the same work in
the v3.11.14, v3.12.12, v3.13.11, v3.14.2 and v3.15.0rc3 tags;
property_get__name__ exists from v3.13.11 on.

Most rows are settled by observation: call counters on the getter, setter and
deleter, identity, and the instance `__dict__`. Only the claim that an
inherited property's lookup does not grow with the MRO needs a stopwatch.

Measurement scope:

* building a property calls none of its functions, and reads the getter's
  docstring when `doc` is not given; `doc` wins when given.
* `getter()`, `setter()` and `deleter()` return a new object of the same type
  (property or a subclass) carrying the other two functions, and leave the
  original's functions unchanged. An explicit `doc` is carried over; a
  docstring taken from the getter is re-read from a replacement getter. `fget`, `fset` and
  `fdel` are the stored functions or `None`.
* each read calls the getter exactly once, 1,000 reads 1,000 times; each
  assignment and deletion calls the setter or deleter once. Without a setter
  or deleter the operation raises AttributeError with "has no setter" or
  "has no deleter" and the instance `__dict__` is left unchanged; without a
  getter, a read raises AttributeError with "has no getter".
* an instance `__dict__` entry named like the property is ignored by reads.
* `Class.attr` returns the property object and calls nothing.
* a `functools.cached_property` read three times calls its function once,
  where a property calls its getter three times.
* timing: reading a property defined on the root of a chain of 1,000 classes
  costs under x3 reading it from a chain of 10, where a walk of the MRO
  predicts x100. Assigning to the leaf class before every read, which drops
  the cached lookup, makes 10x the depth cost more than x4.
* `__name__` (Python 3.13+) is the name the property was bound to in a class
  body, falling back to the getter's `__name__` for a property never bound
  in one.
* every fenced block runs in its own subprocess and asserts its own results,
  and a mutated assertion in one is asserted to fail.

Not settled here:

* What the getter, setter and deleter cost is the caller's; the tests hold
  each at O(1).
* Not varied: properties on classes with multiple inheritance, and property
  subclasses beyond the type of the copy.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap
import time
from collections.abc import Callable
from functools import cached_property
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "property.md"
EXPECTED_BLOCKS = 7


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 10_000) -> float:
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


class Counted:
    """A class with a fully defined property that counts each call."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self._value = 0

    @property
    def value(self) -> int:
        """The value."""
        self.calls.append("get")
        return self._value

    @value.setter
    def value(self, new: int) -> None:
        self.calls.append("set")
        self._value = new

    @value.deleter
    def value(self) -> None:
        self.calls.append("del")
        self._value = 0


def chain(depth: int) -> type:
    """A single-inheritance chain whose MRO has `depth` classes, object
    included, with a property on the root."""

    class Root:
        @property
        def found(self) -> int:
            return 1

    leaf: type = Root
    for index in range(depth - 2):
        leaf = type(f"Level{index}", (leaf,), {})
    assert len(leaf.__mro__) == depth
    return leaf


class TestBuildingAProperty:
    """`property(fget, fset, fdel, doc)` is O(1): it stores the functions,
    calls none of them, and takes the getter's docstring without `doc`."""

    def test_building_calls_nothing(self) -> None:
        calls: list[str] = []

        def getter(self: Any) -> None:
            calls.append("get")

        def setter(self: Any, value: Any) -> None:
            calls.append("set")

        def deleter(self: Any) -> None:
            calls.append("del")

        prop = property(getter, setter, deleter)
        assert calls == []
        assert prop.fget is getter
        assert prop.fset is setter
        assert prop.fdel is deleter

    def test_the_getter_docstring_is_used_without_doc(self) -> None:
        def getter(self: Any) -> int:
            """From the getter."""
            return 1

        assert property(getter).__doc__ == "From the getter."
        assert property(getter, doc="Given.").__doc__ == "Given."

    def test_missing_functions_are_none(self) -> None:
        prop = property(lambda self: 1)
        assert prop.fset is None
        assert prop.fdel is None


class TestCopiesReplaceOneFunction:
    """`getter()`, `setter()` and `deleter()` are O(1): each returns a new
    property of the same type with one function replaced, leaving the
    original unchanged."""

    def test_setter_returns_a_new_property(self) -> None:
        def getter(self: Any) -> int:
            """Doc."""
            return 1

        def setter(self: Any, value: int) -> None:
            pass

        original = property(getter)
        copy = original.setter(setter)

        assert copy is not original
        assert original.fset is None
        assert copy.fget is getter
        assert copy.fset is setter
        assert copy.__doc__ == "Doc."

    def test_getter_and_deleter_keep_the_other_functions(self) -> None:
        prop = Counted.__dict__["value"]
        original = (prop.fget, prop.fset, prop.fdel)

        def other_getter(self: Any) -> int:
            return 2

        def other_deleter(self: Any) -> None:
            pass

        replaced = prop.getter(other_getter)
        assert replaced is not prop
        assert (replaced.fget, replaced.fset, replaced.fdel) == (other_getter, *original[1:])

        dropped = prop.deleter(other_deleter)
        assert dropped is not prop
        assert (dropped.fget, dropped.fset, dropped.fdel) == (*original[:2], other_deleter)

        assert (prop.fget, prop.fset, prop.fdel) == original

    def test_an_explicit_doc_is_kept_and_a_getter_doc_follows_the_getter(self) -> None:
        def getter(self: Any) -> int:
            """From the getter."""
            return 1

        def undocumented(self: Any) -> int:
            return 2

        assert property(getter, doc="Given.").getter(undocumented).__doc__ == "Given."
        assert property(getter).getter(undocumented).__doc__ is None

    def test_a_subclass_copies_to_the_subclass(self) -> None:
        class Tagged(property):
            pass

        prop = Tagged(lambda self: 1)
        copy = prop.setter(lambda self, value: None)
        assert type(copy) is Tagged


class TestEachAccessCallsOneFunction:
    """`obj.attr`, `obj.attr = value` and `del obj.attr` are O(1) plus one
    call of the getter, setter or deleter; nothing is cached."""

    def test_each_operation_calls_its_function_once(self) -> None:
        obj = Counted()
        assert obj.value == 0
        obj.value = 5
        assert obj.value == 5
        del obj.value
        assert obj.calls == ["get", "set", "get", "del"]

    def test_every_read_calls_the_getter(self) -> None:
        obj = Counted()
        for _ in range(1_000):
            assert obj.value == 0
        assert obj.calls.count("get") == 1_000

    def test_cached_property_calls_once_where_property_calls_every_time(self) -> None:
        calls: list[str] = []

        class Report:
            @property
            def total(self) -> int:
                calls.append("property")
                return 1

            @cached_property
            def cached_total(self) -> int:
                calls.append("cached")
                return 1

        report = Report()
        for _ in range(3):
            assert report.total == 1
            assert report.cached_total == 1
        assert calls.count("property") == 3
        assert calls.count("cached") == 1


class TestMissingFunctions:
    """Without a setter or deleter, assignment and deletion raise
    `AttributeError` and store nothing."""

    class ReadOnly:
        @property
        def x(self) -> int:
            return 1

    def test_assignment_without_a_setter_raises_and_stores_nothing(self) -> None:
        obj = self.ReadOnly()
        with pytest.raises(AttributeError, match="has no setter"):
            obj.x = 2  # type: ignore[misc]
        assert "x" not in vars(obj)
        assert obj.x == 1

    def test_deletion_without_a_deleter_raises(self) -> None:
        obj = self.ReadOnly()
        obj.other = 1  # type: ignore[attr-defined]
        before = dict(vars(obj))
        with pytest.raises(AttributeError, match="has no deleter"):
            del obj.x  # type: ignore[misc]
        assert vars(obj) == before

    def test_reading_without_a_getter_raises(self) -> None:
        class WriteOnly:
            x = property(None, lambda self, value: None)

        with pytest.raises(AttributeError, match="has no getter"):
            _ = WriteOnly().x


class TestDataDescriptorPrecedence:
    """A property wins over an instance `__dict__` entry of the same name,
    and a class access returns the property itself."""

    def test_an_instance_entry_does_not_shadow_the_property(self) -> None:
        obj = Counted()
        vars(obj)["value"] = 99
        assert obj.value == 0
        assert obj.calls == ["get"]

    def test_a_class_access_returns_the_property_and_calls_nothing(self) -> None:
        calls: list[str] = []

        class C:
            @property
            def x(self) -> int:
                calls.append("get")
                return 1

        assert isinstance(C.x, property)
        assert C.x is C.__dict__["x"]
        assert calls == []


class TestInheritedLookup:
    """An inherited property is found by the cached class-side lookup, so a
    read does not grow with the MRO; dropping the cache makes the next
    lookup walk it, O(d)."""

    @pytest.mark.timing
    def test_a_cached_lookup_does_not_grow_with_depth(self) -> None:
        timings: list[float] = []
        for depth in (10, 1_000):
            obj = chain(depth)()
            assert obj.found == 1
            timings.append(best_ns(lambda obj=obj: obj.found))

        ratio = timings[1] / timings[0]
        assert ratio < 3, (
            f"reading an inherited property through an MRO of 1,000 cost x{ratio:.2f} one "
            f"of 10 ({timings[0]:.0f}ns to {timings[1]:.0f}ns); a walk of the MRO predicts x100"
        )

    @pytest.mark.timing
    def test_an_uncached_lookup_walks_the_mro(self) -> None:
        timings: list[float] = []
        for depth in (100, 1_000):
            leaf = chain(depth)
            obj = leaf()

            def modify_then_read(leaf: type = leaf, obj: Any = obj) -> Any:
                leaf.bump = 0  # type: ignore[attr-defined]
                return obj.found

            timings.append(best_ns(modify_then_read, inner=500))

        ratio = timings[1] / timings[0]
        assert ratio > 4, (
            f"an MRO 10x deeper cost x{ratio:.1f} ({timings[0]:.0f}ns to "
            f"{timings[1]:.0f}ns); a walk of the MRO predicts about x10, a cached lookup x1"
        )


@pytest.mark.skipif(sys.version_info < (3, 13), reason="version: property.__name__ is 3.13+")
class TestName:
    """`prop.__name__` (Python 3.13+) is the assigned attribute name, else the
    getter's `__name__`."""

    def test_the_assigned_name_wins(self) -> None:
        def getter(self: Any) -> int:
            return 1

        class C:
            alias = property(getter)

        assert C.__dict__["alias"].__name__ == "alias"

    def test_an_unassigned_property_uses_the_getter_name(self) -> None:
        def getter(self: Any) -> int:
            return 1

        prop: Any = property(getter)
        assert prop.__name__ == "getter"


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
    """Each block runs in its own subprocess and asserts its own results."""

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
        line, source = next((n, s) for n, s in _blocks() if 'computed.count("cached") == 1' in s)
        mutated = source.replace(
            'computed.count("cached") == 1', 'computed.count("cached") == 3', 1
        )

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
