"""Tests for docs/builtins/classmethod.md.

classmethod is PyClassMethod_Type in Objects/funcobject.c. cm_init stores the
function and copies `__module__`, `__name__`, `__qualname__` and `__doc__` onto
the new object; cm_descr_get returns PyMethod_New(function, type) on every
access. Finding the descriptor is _PyType_Lookup in Objects/typeobject.c: a
hit in the type attribute cache, keyed by the class's version tag, or else
find_name_in_mro, which walks the MRO. Assigning a class attribute calls
PyType_Modified, which clears the version tag of the class and its subclasses.
From v3.13.0 assign_version_tag refuses a class that has used
MAX_VERSIONS_PER_CLASS (1,000) tags, and its lookups are never cached again;
v3.10.19, v3.11.14 and v3.12.12 have no such limit. Up to v3.12.12
cm_descr_get delegates to the wrapped object's `__get__` when it has one;
v3.13.11 and v3.14.2 always bind.

Measurement scope:

* binding: `Cls.method is not Cls.method`, `__self__` is the class when read
  through the class and through an instance, an instance attribute of the same
  name shadows the classmethod, and a staticmethod reads back as the same
  function each time;
* inheritance: a classmethod defined on a base and called on a subclass
  receives the subclass, and a staticmethod factory naming its class does not;
* cached lookup: reading a classmethod defined at the root of a 1,000-class
  chain against a 2-class chain measured x1.0 on the pinned interpreter
  (aarch64, CPython 3.14). The test accepts under x3; an O(d) lookup predicts
  x500;
* cache miss: assigning a class attribute and then reading the classmethod,
  at chain depths 10 and 1,000, measured about x90 on the pinned interpreter.
  The test asserts more than x10; a cached O(1) lookup predicts x1;
* losing the cache: after 2,000 rounds of assigning a class attribute and
  reading the classmethod, a lookup on a 1,000-class chain measured x150 to x200 a
  fresh chain's on 3.13 and 3.14, and x1 on 3.10 and 3.12. The test asserts
  more than x10 on 3.13+ and under x3 before it. 2,000 assignments with no
  lookup between them, and 3,000 bumps of an itertools.count the class holds,
  each leave the lookup at x1 on every version;
* wrapping property: `@classmethod` over `@property` reads as the property's
  value on 3.10 to 3.12 and as a bound method on 3.13+, run on 3.10, 3.11,
  3.12, 3.13 and 3.14;
* copied attributes and `__wrapped__`;
* every fenced block runs in a subprocess; the blocks assert their own results.

Not settled here:

* O(1) for applying the decorator and for calling the bound method: cm_init
  copies four attributes and the call prepends one argument, neither of which
  depends on the function. That is read from source, not measured.
* O(d) space for the first lookup after a change: assign_version_tag recurses
  through the bases to give each invalidated one a new tag, so modifying the
  root of a chain costs C stack proportional to d. Read from source; the
  recursion allocates nothing tracemalloc sees.
* The bounds exclude the method body, which is the caller's.
* Not varied: multiple inheritance (every chain is single inheritance, so d is
  the chain depth plus `object`), metaclasses and their data descriptors such
  as `__name__`, which a lookup on the class finds without its MRO, and classes
  with a custom `mro()`, which are never cached.
"""

from __future__ import annotations

import itertools
import pathlib
import re
import subprocess
import sys
import textwrap
import time
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "classmethod.md"
EXPECTED_BLOCKS = 8

SHALLOW = 10
DEEP = 1_000


def best_time(func: Callable[[], Any], repeats: int = 7, loops: int = 20_000) -> float:
    """The fastest of several runs of `loops` calls, the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        for _ in range(loops):
            func()
        times.append(time.perf_counter() - start)
    return min(times) / loops


def chain(depth: int) -> type:
    """The leaf of a single-inheritance chain of `depth` classes whose root
    defines a classmethod `create` and a class attribute `count`."""

    class Root:
        count = 0

        @classmethod
        def create(cls) -> type:
            return cls

    leaf: type = Root
    for index in range(depth - 1):
        leaf = type(f"C{index}", (leaf,), {})
    assert len(leaf.__mro__) == depth + 1
    return leaf


class TestBindingTheClass:
    """Row: `Cls.method`, `obj.method` - O(1), a new bound method on each access
    with the class as `__self__`."""

    def test_each_access_builds_a_new_bound_method(self) -> None:
        class Example:
            @classmethod
            def info(cls) -> str:
                return cls.__name__

        first = Example.info
        second = Example.info

        assert first is not second
        assert first == second
        assert first.__self__ is Example
        assert first.__func__ is Example.__dict__["info"].__func__

    def test_an_instance_passes_its_class(self) -> None:
        class Example:
            @classmethod
            def who(cls) -> type:
                return cls

        obj = Example()

        assert obj.who.__self__ is Example
        assert obj.who() is Example

    def test_an_instance_attribute_shadows_the_classmethod(self) -> None:
        class Example:
            @classmethod
            def info(cls) -> str:
                return cls.__name__

        obj = Example()
        obj.info = lambda: "shadowed"  # type: ignore[method-assign]

        assert obj.info() == "shadowed"
        assert obj.info is obj.info
        assert Example.info() == "Example"

    def test_the_class_stores_the_descriptor(self) -> None:
        class Example:
            @classmethod
            def info(cls) -> None:
                pass

        assert type(Example.__dict__["info"]) is classmethod
        assert Example.__dict__["info"] is Example.__dict__["info"]

    def test_a_staticmethod_reads_back_as_the_same_function(self) -> None:
        class Both:
            @classmethod
            def from_class(cls) -> type:
                return cls

            @staticmethod
            def plain() -> str:
                return "no binding"

        assert Both.plain is Both.plain
        assert Both.from_class is not Both.from_class


class TestInheritance:
    """Inheritance and the MRO: an inherited classmethod receives the class it
    was looked up on; a staticmethod naming its class builds that class."""

    def test_a_subclass_receives_itself(self) -> None:
        leaf = chain(5)

        assert leaf.create() is leaf
        assert leaf().create() is leaf

    def test_a_hardcoded_factory_builds_the_base(self) -> None:
        class HardcodedBase:
            @staticmethod
            def create() -> HardcodedBase:
                return HardcodedBase()

        class HardcodedChild(HardcodedBase):
            pass

        assert type(HardcodedChild.create()) is HardcodedBase


class TestAttributeCache:
    """Rows: Looking up an inherited classmethod - O(1); First lookup after the
    class or a base changes - O(d); Lookup on a class modified over and over
    (3.13+) - O(d)."""

    @pytest.mark.timing
    def test_a_cached_lookup_does_not_depend_on_depth(self) -> None:
        shallow = chain(2)
        deep = chain(DEEP)
        shallow.create  # noqa: B018 - warm the cache
        deep.create  # noqa: B018

        ratio = best_time(lambda: deep.create) / best_time(lambda: shallow.create)

        assert ratio < 3, f"x{ratio:.1f} for x{DEEP // 2} in depth"

    @pytest.mark.timing
    def test_a_miss_walks_the_mro(self) -> None:
        shallow = chain(SHALLOW)
        deep = chain(DEEP)

        def modify_then_look_up(cls: type) -> Callable[[], Any]:
            def run() -> Any:
                cls.count = 1  # type: ignore[attr-defined]
                return cls.create  # type: ignore[attr-defined]

            return run

        ratio = best_time(modify_then_look_up(deep), loops=2_000) / best_time(
            modify_then_look_up(shallow), loops=2_000
        )

        assert ratio > 10, f"x{ratio:.1f} for x{DEEP // SHALLOW} in depth"

    @pytest.mark.timing
    def test_a_class_modified_over_and_over_loses_the_cache_on_3_13(self) -> None:
        fresh = chain(DEEP)
        churned = chain(DEEP)
        for value in range(2_000):
            churned.count = value  # type: ignore[attr-defined]
            churned.create  # type: ignore[attr-defined] # noqa: B018
        fresh.create  # noqa: B018 - warm the cache

        ratio = best_time(lambda: churned.create) / best_time(lambda: fresh.create)

        if sys.version_info >= (3, 13):
            assert ratio > 10, f"x{ratio:.1f}: the churned class is still cached"
        else:
            assert ratio < 3, f"x{ratio:.1f}: the churned class lost the cache"

    @pytest.mark.timing
    def test_assignments_with_no_lookup_between_keep_the_cache(self) -> None:
        fresh = chain(DEEP)
        written = chain(DEEP)
        written.create  # noqa: B018
        for value in range(2_000):
            written.count = value  # type: ignore[attr-defined]
        written.create  # noqa: B018 - re-caches the class
        fresh.create  # noqa: B018

        ratio = best_time(lambda: written.create) / best_time(lambda: fresh.create)

        assert ratio < 3, f"x{ratio:.1f}: the class lost the cache"

    @pytest.mark.timing
    def test_a_counter_the_class_holds_keeps_the_cache(self) -> None:
        fresh = chain(DEEP)
        holder = chain(DEEP)
        holder.ids = itertools.count(1)  # type: ignore[attr-defined]
        for _ in range(3_000):
            next(holder.ids)  # type: ignore[attr-defined]
            holder.create  # type: ignore[attr-defined] # noqa: B018
        fresh.create  # noqa: B018 - warm the cache

        ratio = best_time(lambda: holder.create) / best_time(lambda: fresh.create)

        assert ratio < 3, f"x{ratio:.1f}: the class lost the cache"


class TestVersionNotes:
    """Version Notes: descriptor chaining ends in 3.13; a classmethod copies its
    function's attributes and exposes it as `__wrapped__`."""

    def test_wrapping_a_property(self) -> None:
        class Named:
            @classmethod  # type: ignore[misc]
            @property
            def name(cls) -> str:
                return cls.__name__

        value: Any = Named.name

        if sys.version_info >= (3, 13):
            assert type(value).__name__ == "method"
            assert value.__self__ is Named
        else:
            assert value == "Named"

    def test_copied_attributes_and_wrapped(self) -> None:
        def make(cls: type) -> type:
            """Docstring."""
            return cls

        wrapped = classmethod(make)

        assert wrapped.__wrapped__ is make  # type: ignore[attr-defined]
        assert wrapped.__func__ is make
        assert wrapped.__name__ == "make"  # type: ignore[attr-defined]
        assert wrapped.__qualname__ == make.__qualname__  # type: ignore[attr-defined]
        assert wrapped.__module__ == make.__module__
        assert wrapped.__doc__ == "Docstring."


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

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        block = next(source for _, source in _blocks() if "class HardcodedBase" in source)
        broken = block.replace(
            "type(HardcodedChild.create()) is HardcodedBase",
            "type(HardcodedChild.create()) is HardcodedChild",
            1,
        )
        assert broken != block, "the mutation did not change the block"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "AssertionError" in result.stderr
