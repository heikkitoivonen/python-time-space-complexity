"""Tests for docs/builtins/object_func.md.

The page prices `object()` and the defaults every class inherits from it.
The behaviour in most rows is settled by observation: identity, a hash that
does not change when the instance's contents do, the exceptions a bare
instance raises, and the presence or absence of an instance `__dict__`.
Construction, freeing and attribute lookup are timed against the depth of a
class hierarchy, and instance space is a traced allocation.

Measurement scope:

* `object()`: two calls return distinct objects; `sys.getsizeof()` is the same
  for every instance; there is no `__dict__`; an argument raises TypeError
  naming "takes no arguments"; setting an attribute raises AttributeError.
* `==` and `hash()`: an instance equals only itself, two subclass instances
  with equal attributes are unequal, and `hash()` is unchanged after 1,000
  attributes are added. These check the identity semantics; that neither
  reads the contents, and so is O(1), is read from object_richcompare in
  Objects/typeobject.c and the pointer hash in Python/pyhash.c. A class defining
  `__eq__` alone has `__hash__` None, and hashing an instance raises
  TypeError.
* ordering raises TypeError; `repr()` starts "<object object at 0x" for
  `object()` and names the module and qualified name for a subclass; `str()`
  and `format(obj, "")` equal `repr()`; a non-empty spec raises TypeError.
* `cls()` on a class with neither `__init__` nor `__new__` nor `__slots__`:
  creating 2,000 instances that are kept alive costs under x3 per instance
  from an MRO of 10 to one of 1,000, which a walk of the MRO would make about x100. With either
  method defined, arguments are accepted.
* freeing those instances, with gc disabled, costs more than x4 per instance
  from an MRO of 100 to one of 1,000; linear predicts x10 and an O(1) free x1.
  The per-step cost of the walk rises at
  depths of thousands, as the class objects stop fitting in cache: 2,000 to
  4,000 measured about x4; the page's O(d) counts steps, not cache misses.
* attribute lookup on a chain of classes built with `type()`: an attribute
  defined on the root, one in the instance `__dict__`, and a missing one read
  with `getattr(obj, name, None)` each cost under x3 from an MRO of 10 to one
  of 1,000. Assigning to the leaf class before each lookup of the root's
  attribute costs more than x4 from an MRO of 100 to one of 1,000, where a
  walk of the MRO predicts about x10 and a cached lookup x1. The timing
  tests pass on 3.11, 3.13 and 3.15.
* lookup values are asserted with the timings. The uncached lookup's O(d)
  stack is read from assign_version_tag in Objects/typeobject.c, which
  recurses into each base whose version tag a modification invalidated; it is
  not measured, and the timed modification invalidates only the leaf.
* instance space: the traced peak of creating an instance and storing 1,000
  attributes is more than x20 that of storing 10, where linear predicts about
  x100. It runs serially, since xdist's I/O thread allocates while tracemalloc
  is tracing. An instance of a `__slots__` class whose only base is object
  has no `__dict__` and rejects an undeclared attribute, while a slotted
  subclass of a class without slots keeps a `__dict__`.
* every fenced block runs in its own subprocess and asserts its own results,
  and a mutated assertion in one is asserted to fail.

Not settled here:

* The O(1) of `repr()` treats the class's module and qualified names as
  constant length; it is not measured.
* The type attribute cache is finite and shared, so unrelated lookups can
  evict an entry; only invalidation by assignment to a class is measured.
  The page prices lookup at O(1) on that basis.
* Pickling and copying hooks (`__reduce_ex__`, `__getstate__`), `__dir__`
  and `__sizeof__` are priced on the pickle, copy, dir() and sys pages, not
  here.
* Not varied: multiple inheritance (every chain is single inheritance),
  attribute values (ints only), and the number of slots, whose cost per
  instance is read from type allocation zeroing the instance's fixed size.
"""

from __future__ import annotations

import gc
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

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "object_func.md"
EXPECTED_BLOCKS = 7


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 2_000) -> float:
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


def create_and_free_ns(cls: type, count: int = 2_000, repeats: int = 7) -> tuple[float, float]:
    """Fastest per-instance cost of creating `count` instances that are kept
    alive, and of then freeing them, in nanoseconds, with gc disabled."""
    best_create = best_free = float("inf")
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        for _ in range(repeats):
            start = time.perf_counter_ns()
            kept = [cls() for _ in range(count)]
            middle = time.perf_counter_ns()
            kept.clear()
            end = time.perf_counter_ns()
            best_create = min(best_create, (middle - start) / count)
            best_free = min(best_free, (end - middle) / count)
    finally:
        if was_enabled:
            gc.enable()
    return best_create, best_free


def chain(depth: int) -> type:
    """A single-inheritance class whose MRO has `depth` entries."""
    cls: type = type("Root", (), {"found": 1})
    for i in range(depth - 2):
        cls = type(f"Level{i}", (cls,), {})
    assert len(cls.__mro__) == depth
    return cls


class TestBareInstances:
    """`object()` is O(1) in time and space: a fixed-size instance with no
    `__dict__`, which takes no arguments and stores no attributes."""

    def test_each_call_is_a_new_fixed_size_instance(self) -> None:
        first, second = object(), object()

        assert first is not second
        assert sys.getsizeof(first) == sys.getsizeof(second)
        assert not hasattr(first, "__dict__")

    def test_an_argument_raises(self) -> None:
        with pytest.raises(TypeError, match="takes no arguments"):
            object(1)  # type: ignore[call-arg]

    def test_an_attribute_cannot_be_set(self) -> None:
        with pytest.raises(AttributeError):
            object().name = "x"  # type: ignore[attr-defined]


class TestIdentityDefaults:
    """`==` and `hash()` are O(1): both use identity, so neither reads what
    the object holds. Defining `__eq__` alone makes a class unhashable."""

    class Plain:
        pass

    def test_equality_is_identity(self) -> None:
        a, b = object(), object()
        assert a == a
        assert a != b
        assert not (a != a)

        first, second = self.Plain(), self.Plain()
        first.value = second.value = 1  # type: ignore[attr-defined]
        assert first != second, "equal contents must not make the default == true"

    def test_hash_ignores_the_contents(self) -> None:
        obj = self.Plain()
        before = hash(obj)
        for i in range(1_000):
            setattr(obj, f"attr{i}", i)

        assert hash(obj) == before

    def test_eq_without_hash_is_unhashable(self) -> None:
        class Point:
            def __eq__(self, other: object) -> bool:
                return True

        assert Point.__hash__ is None
        with pytest.raises(TypeError, match="unhashable"):
            hash(Point())


class TestOrderingReprAndFormat:
    """Ordering raises TypeError; `repr()` names the class and address,
    `str()` falls back to it, and `format()` accepts only an empty spec."""

    def test_ordering_raises(self) -> None:
        with pytest.raises(TypeError, match="not supported"):
            object() < object()  # type: ignore[operator]  # noqa: B015

    def test_repr_str_and_empty_format_agree(self) -> None:
        obj = object()
        text = repr(obj)

        assert text.startswith("<object object at 0x")
        assert str(obj) == text
        assert format(obj, "") == text

    def test_a_subclass_repr_names_its_class(self) -> None:
        class Widget:
            pass

        assert repr(Widget()).startswith(f"<{__name__}.{Widget.__qualname__} object at 0x")

    def test_a_format_spec_raises(self) -> None:
        with pytest.raises(TypeError, match="unsupported format string"):
            format(object(), ">20")


class TestConstruction:
    """`cls()` with `object.__new__` and `object.__init__` is O(1) and does not
    grow with the MRO; arguments raise unless the class defines `__init__` or
    `__new__`."""

    @pytest.mark.timing
    def test_creating_an_instance_does_not_grow_with_depth(self) -> None:
        shallow_ns = create_and_free_ns(chain(10))[0]
        deep_ns = create_and_free_ns(chain(1_000))[0]

        ratio = deep_ns / shallow_ns
        assert ratio < 3, (
            f"creating with an MRO of 1,000 cost x{ratio:.2f} an MRO of 10 "
            f"({shallow_ns:.0f}ns to {deep_ns:.0f}ns); a walk of the MRO predicts about x100"
        )

    @pytest.mark.timing
    def test_freeing_an_instance_walks_the_bases(self) -> None:
        shallow_ns = create_and_free_ns(chain(100))[1]
        deep_ns = create_and_free_ns(chain(1_000))[1]

        ratio = deep_ns / shallow_ns
        assert ratio > 4, (
            f"freeing with an MRO 10x deeper cost x{ratio:.1f} ({shallow_ns:.0f}ns to "
            f"{deep_ns:.0f}ns); linear predicts x10 and an O(1) free x1"
        )

    def test_arguments_need_init_or_new(self) -> None:
        class Plain:
            pass

        class WithInit:
            def __init__(self, value: int) -> None:
                self.value = value

        class WithNew:
            def __new__(cls, value: int) -> WithNew:
                return super().__new__(cls)

        with pytest.raises(TypeError, match="takes no arguments"):
            Plain(1)  # type: ignore[call-arg]
        assert WithInit(1).value == 1
        assert isinstance(WithNew(1), WithNew)


class TestAttributeLookup:
    """`obj.attr` is O(1): the class-side lookup is cached per type, so it
    does not grow with the MRO, found or missing. After a class on the MRO
    is modified, the next lookup walks the MRO, O(d)."""

    @pytest.mark.timing
    @pytest.mark.parametrize("where", ["root", "instance", "missing"])
    def test_a_cached_lookup_does_not_grow_with_depth(self, where: str) -> None:
        timings: list[float] = []
        for depth in (10, 1_000):
            obj = chain(depth)()
            obj.own = 1
            if where == "root":
                assert obj.found == 1
                timings.append(best_ns(lambda obj=obj: obj.found))
            elif where == "instance":
                assert obj.own == 1
                timings.append(best_ns(lambda obj=obj: obj.own))
            else:
                assert getattr(obj, "absent", None) is None
                timings.append(best_ns(lambda obj=obj: getattr(obj, "absent", None)))

        ratio = timings[1] / timings[0]
        assert ratio < 3, (
            f"a {where} lookup with an MRO of 1,000 cost x{ratio:.2f} one with 10 "
            f"({timings[0]:.0f}ns to {timings[1]:.0f}ns); a walk of the MRO predicts x100"
        )

    @pytest.mark.timing
    def test_a_lookup_after_modifying_the_class_walks_the_mro(self) -> None:
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


class TestInstanceSpace:
    """Storing a attributes is O(a) space in the instance `__dict__`; a class
    has no `__dict__` only when it and every base other than object define
    `__slots__`."""

    class Plain:
        pass

    def _peak(self, count: int) -> int:
        names = [f"attr{i}" for i in range(count)]
        tracemalloc.start()
        try:
            obj = self.Plain()
            for name in names:
                setattr(obj, name, 1)
            return tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()

    @pytest.mark.serial
    def test_space_grows_with_the_attributes(self) -> None:
        self._peak(10)
        small, large = self._peak(10), self._peak(1_000)

        assert large > 20 * small, (
            f"1,000 attributes peaked at {large} bytes against {small} for 10; "
            "linear predicts about x100"
        )

    def test_slots_have_no_dict(self) -> None:
        class Slotted:
            __slots__ = ("x",)

        obj = Slotted()
        obj.x = 1
        assert not hasattr(obj, "__dict__")
        with pytest.raises(AttributeError):
            obj.y = 2  # type: ignore[attr-defined]

    def test_slots_below_a_class_with_a_dict_keep_it(self) -> None:
        class Base:
            pass

        class Slotted(Base):
            __slots__ = ("x",)

        obj = Slotted()
        obj.y = 2  # type: ignore[attr-defined]
        assert obj.__dict__ == {"y": 2}


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
        line, source = next((n, s) for n, s in _blocks() if "assert Point.__hash__ is None" in s)
        mutated = source.replace("Point.__hash__ is None", "Point.__hash__ is not None", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
