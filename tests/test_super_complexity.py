"""Tests for docs/builtins/super.md.

`super` is implemented in Objects/typeobject.c. `supercheck()` confirms that
the object derives from the starting class with `PyType_IsSubtype`, which
scans the object's MRO tuple. `_super_lookup_descr()` (inlined in
`super_getattro()` on 3.11) scans the same tuple to the starting class, then
reads each later class's `__dict__` until one holds the name; nothing is
cached. From 3.12 `super().name` compiles to `LOAD_SUPER_ATTR`, whose
specialized forms call `_PySuper_Lookup()`; it builds a `super` object only
when the name falls through to the proxy's own attributes, and runs the same
check and scan. The scan is the same in the v3.11.14, v3.12.12, v3.13.11, v3.14.2
and v3.15.0rc3 tags, so no version is treated apart.

Lookup cost is settled with a stopwatch, since the scan reads type
dictionaries directly and no hook observes it. Call order, binding and errors
are settled by observation.

Measurement scope:

* a chain of 10 and of 2,000 classes, the method defined on the root and
  called through `super()` from the leaf: the 2,000-class chain costs more
  than x20, where an O(p) scan predicts about x200 and a cached lookup x1.
  The same chains looking up a name defined in the class right after the
  leaf cost under x3, as does `Root.method(self)`, a cached class attribute.
* a missing name on the same chains costs more than x20.
* the starting class near the end of a 10- and a 2,000-class MRO, its target
  right after it: more than x5, so finding the starting class is part of the
  cost even when the name is found at once.
* the traced peak of a `super()` lookup across a 2,000-class MRO is under
  1 KB.
* call order in a diamond, a cooperative `__init__` with `**rest`, the
  zero-argument and two-argument forms agreeing, `super()` in a
  classmethod, a parent property read through `super()`, assignment and
  deletion through `super()` raising, `super(cls)` being unbound, the
  `RuntimeError` and `TypeError` cases, `super(cls, None)` being unbound too,
  each cooperative `__init__` running once, and a diamond mixing `super()` with
  an explicit parent call running one class twice and skipping another.
* every fenced block runs in its own subprocess and asserts its own results,
  and a mutated assertion in one is asserted to fail.

Not settled here:

* That the MRO is scanned from the front, rather than from the starting
  class's position remembered somewhere, is read from `_super_lookup_descr()`;
  the timings show only that cost grows with the positions involved.
* Not varied: the number of free variables a function has, which the
  zero-argument form scans for `__class__`, and descriptors whose `__get__`
  does work of its own.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "super.md"
EXPECTED_BLOCKS = 8


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 1_000) -> float:
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


def chain(length: int) -> Any:
    """An instance whose MRO is `length` classes long: Leaf, the levels, Root, object."""

    class Root:
        def far(self) -> int:
            return 1

    cls: type = Root
    for i in range(length - 3):
        cls = type(f"Level{i}", (cls,), {})
    cls.near = lambda self: 2  # type: ignore[attr-defined]

    class Leaf(cls):  # type: ignore[valid-type, misc]
        def call_far(self) -> int:
            return super().far()

        def call_near(self) -> int:
            return super().near()

        def call_missing(self) -> None:
            try:
                super().missing  # noqa: B018
            except AttributeError:
                return None
            raise AssertionError("expected AttributeError")

        def call_direct(self) -> int:
            return Root.far(self)

    instance = Leaf()
    assert len(type(instance).__mro__) == length
    return instance


def start_near_the_end(length: int) -> Any:
    """An instance whose starting class sits just before Root in a `length`-class MRO."""

    class Root:
        def target(self) -> int:
            return 3

    class Low(Root):
        def call(self) -> int:
            return super().target()

    cls: type = Low
    for i in range(length - 3):
        cls = type(f"Upper{i}", (cls,), {})
    instance = cls()
    assert len(type(instance).__mro__) == length
    return instance


SHORT, LONG = 10, 2_000


def outside_a_class(self: object) -> Any:
    """Defined at module level: a function nested in a method shares its `__class__` cell."""
    return super()  # pyright: ignore[reportGeneralTypeIssues]


class TestLookupIsNotCached:
    """`super().name` is O(p): it scans the MRO to the class defining the name
    on every call, where `Parent.method(self)` is a cached O(1) lookup."""

    @pytest.mark.timing
    def test_a_name_far_along_the_mro_costs_its_position(self) -> None:
        short, long = chain(SHORT), chain(LONG)

        ratio = best_ns(long.call_far, inner=200) / best_ns(short.call_far)
        assert ratio > 20, f"x{ratio:.1f} for x{LONG // SHORT} the MRO; a cached lookup is x1"

    @pytest.mark.timing
    def test_a_name_in_the_next_class_does_not_grow(self) -> None:
        short, long = chain(SHORT), chain(LONG)

        ratio = best_ns(long.call_near) / best_ns(short.call_near)
        assert ratio < 3, f"x{ratio:.2f} for x{LONG // SHORT} the MRO"

    @pytest.mark.timing
    def test_naming_the_class_does_not_grow(self) -> None:
        short, long = chain(SHORT), chain(LONG)

        ratio = best_ns(long.call_direct) / best_ns(short.call_direct)
        assert ratio < 3, f"x{ratio:.2f} for x{LONG // SHORT} the MRO"

    @pytest.mark.timing
    def test_a_missing_name_scans_the_whole_mro(self) -> None:
        short, long = chain(SHORT), chain(LONG)

        ratio = best_ns(long.call_missing, inner=200) / best_ns(short.call_missing)
        assert ratio > 20, f"x{ratio:.1f} for x{LONG // SHORT} the MRO"

    @pytest.mark.timing
    def test_finding_the_starting_class_costs_its_position(self) -> None:
        short, long = start_near_the_end(SHORT), start_near_the_end(LONG)

        ratio = best_ns(long.call, inner=200) / best_ns(short.call)
        assert ratio > 5, f"x{ratio:.1f} for x{LONG // SHORT} the MRO; O(1) predicts x1"

    @pytest.mark.serial
    def test_a_long_scan_allocates_almost_nothing(self) -> None:
        long = chain(LONG)
        long.call_far()

        tracemalloc.start()
        try:
            long.call_far()
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        assert peak < 1_000, peak


class TestCallOrder:
    """`super()` follows the instance's MRO, so cooperative methods each run
    once; an explicit parent call in a diamond breaks that."""

    def test_a_diamond_runs_each_class_once(self) -> None:
        calls: list[str] = []

        class A:
            def setup(self) -> None:
                calls.append("A")

        class B(A):
            def setup(self) -> None:
                calls.append("B")
                super().setup()

        class C(A):
            def setup(self) -> None:
                calls.append("C")
                super().setup()

        class D(B, C):
            def setup(self) -> None:
                calls.append("D")
                super().setup()

        D().setup()
        assert calls == ["D", "B", "C", "A"]
        calls.clear()
        B().setup()
        assert calls == ["B", "A"]

    def test_an_explicit_parent_call_runs_one_class_twice_and_skips_another(self) -> None:
        calls: list[str] = []

        class A:
            def setup(self) -> None:
                calls.append("A")

        class B(A):
            def setup(self) -> None:
                calls.append("B")
                A.setup(self)

        class C(A):
            def setup(self) -> None:
                calls.append("C")
                super().setup()

        class D(B, C):
            def setup(self) -> None:
                calls.append("D")
                super().setup()
                C.setup(self)

        D().setup()
        assert calls == ["D", "B", "A", "C", "A"]

        calls.clear()

        class E(B, C):
            def setup(self) -> None:
                super().setup()

        E().setup()
        assert "C" not in calls, "B's explicit call skips C, which follows B in E's MRO"

    def test_cooperative_init_passes_keywords_along(self) -> None:
        calls: list[str] = []

        class Named:
            def __init__(self, *, name: str, **rest: Any) -> None:
                calls.append("Named")
                super().__init__(**rest)
                self.name = name

        class Sized:
            def __init__(self, *, size: int, **rest: Any) -> None:
                calls.append("Sized")
                super().__init__(**rest)
                self.size = size

        class Item(Named, Sized):
            pass

        class Other(Sized, Named):
            pass

        for cls in (Item, Other):
            calls.clear()
            item = cls(name="box", size=3)
            assert (item.name, item.size) == ("box", 3)
            assert sorted(calls) == ["Named", "Sized"], "each __init__ runs exactly once"


class TestBinding:
    """The two forms agree, a classmethod binds to the class, and a found
    descriptor is bound with `__get__`."""

    def test_zero_and_two_argument_forms_agree(self) -> None:
        class Parent:
            def method(self) -> str:
                return "parent"

        class Child(Parent):
            def both(self) -> tuple[str, str]:
                return super().method(), super(Child, self).method()

            def proxies(self) -> tuple[Any, Any]:
                proxy: Any = super()
                return proxy.__thisclass__, proxy.__self__

        child = Child()
        assert child.both() == ("parent", "parent")
        assert child.proxies() == (Child, child)

    def test_a_classmethod_binds_to_the_class(self) -> None:
        class Parent:
            @classmethod
            def create(cls) -> Any:
                return cls()

        class Child(Parent):
            @classmethod
            def create(cls) -> Any:
                return super().create()

        assert type(Child.create()) is Child

    def test_a_parent_property_runs_its_getter(self) -> None:
        reads: list[str] = []

        class Parent:
            @property
            def value(self) -> int:
                reads.append("Parent")
                return 7

        class Child(Parent):
            @property
            def value(self) -> int:
                return super().value

        assert Child().value == 7
        assert reads == ["Parent"]


class TestErrors:
    """Assignment and deletion through `super()` raise; the zero-argument form
    needs an argument and a `__class__` cell; the two-argument form checks its
    object; an unbound `super(cls)` finds no bound methods."""

    def test_assignment_and_deletion_raise(self) -> None:
        class Parent:
            value = 1

        class Child(Parent):
            def assign(self) -> None:
                super().value = 2

            def delete(self) -> None:
                del super().value

        child = Child()
        with pytest.raises(AttributeError, match="has no attribute 'value'"):
            child.assign()
        with pytest.raises(AttributeError, match="has no attribute 'value'"):
            child.delete()
        assert Parent.value == 1

    def test_zero_arguments_in_a_function_without_arguments(self) -> None:
        class Example:
            @staticmethod
            def static() -> Any:
                return super()  # pyright: ignore[reportGeneralTypeIssues]

        with pytest.raises(RuntimeError, match="no arguments"):
            Example.static()

    def test_zero_arguments_outside_a_class(self) -> None:
        with pytest.raises(RuntimeError, match="__class__ cell not found"):
            outside_a_class(object())

    def test_an_unrelated_object_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="instance or subtype of type"):
            super(int, "text")  # pyright: ignore[reportArgumentType]

    def test_an_unbound_super_finds_no_methods(self) -> None:
        for unbound in (super(bool), super(bool, None)):  # pyright: ignore[reportArgumentType]
            proxy: Any = unbound
            assert proxy.__self__ is None
            with pytest.raises(AttributeError, match="bit_length"):
                proxy.bit_length  # noqa: B018


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
        line, source = next((n, s) for n, s in _blocks() if 'assert calls == ["D", "B", "C"' in s)
        mutated = source.replace('["D", "B", "C", "A"]', '["D", "B", "A", "C"]', 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
