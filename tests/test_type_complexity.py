"""Tests for docs/builtins/type_func.md.

`type(obj)` returns the object's type pointer, and the three-argument form is
type_new in Objects/typeobject.c: it copies the namespace, computes the MRO
through mro_implementation and stores it as a new tuple, readies the type
(inherit_slots for each class on the MRO, fixup_slot_dispatchers looking up a
fixed set of special-method names along it), registers the class with each
base, then calls `__set_name__` and `__init_subclass__`. mro_implementation
copies the single base's MRO for zero or one base. For several bases it checks
the bases for duplicates in O(b²) and runs pmerge: at most h output steps try
up to b + 1 candidate heads, each tested against b + 1 tails of at most h
entries with tail_contains, O(b²h²) time; the merge borrows the bases' tuples
and keeps O(b) cursors and an O(h) result, so O(h) space. `type.mro()`
converts that result to a list. `__subclasses__()` walks the class's dict of
weak references to its direct subclasses, skipping dead ones. tail_contains,
pmerge, mro_implementation and that walk do the same work in the v3.11.14,
v3.12.12, v3.13.11, v3.14.2 and v3.15.0rc3 tags. The source establishes the
upper bounds; finite timings cannot.

Measurement scope:

* `type(obj)` is the class itself for classes of 1 and 10,000 attributes, and
  ignores a `__class__` property that `obj.__class__` and `isinstance()`
  follow.
* Class creation copies the namespace: changing the dictionary afterwards
  leaves the class unchanged, and a dict built from the class `__dict__`
  grows 30x--150x from 100 to 10,000 attributes. Timed from 512 to 32,768 integer-valued
  attributes with no bases, a 64x step must cost 8x--512x (linear predicts
  64x, quadratic 4,096x).
* Class creation below a chain of single bases is timed at depths 16 and 256
  with the gc disabled and every class kept alive: h grows from 18 to 258,
  and the step must cost 4x--64x (linear predicts 14x, quadratic 205x). Each class has its own
  `__mro__` tuple, and creating one at depth 1,024 traces at least 7 KiB more
  than at depth 16, the h-entry tuple, and under 4x that tuple's size more.
* Class creation with several bases includes the merge: 9 to 129 bases at
  depth 80 (h from 170 to 290) must cost more than 25x, where a bound linear
  in b or h predicts at most 14x, and the stored `__mro__` equals
  `type.mro()`.
* `type.mro(C)` returns a new list each call, equal to `C.__mro__`, which it
  leaves in place, for `object`, a chain of 20 and a merging hierarchy. A
  metaclass overriding `mro()` stores its own order; `type.mro(C)` recomputes
  the C3 order without calling the override.
* `type.mro()` with one base is timed at depths 16 and 512: the 32x step must
  cost 5x--100x. The merge is timed growing the bases sharing a pivot from 8
  to 128 at depth 80 (9 to 129 bases, h from 170 to 290), and the chains
  from 8 to 128 at 33 bases (h from 50 to 290): each must cost more than 25x,
  where a bound linear in b or h predicts at most 14x.
* The peak traced allocation of `type.mro()` stays within 4x the returned
  list's size at depths 16 and 256, with one base and with five.
* `C.__mro__`, `C.__bases__`, `C.__base__`, `C.__name__` and `C.__qualname__`
  return the same object on every read. `C.__dict__` is a read-only
  `mappingproxy` that sees later class assignments, and reading it on a class
  of 100,000 attributes traces under 1 KiB.
* `C.__subclasses__()` returns a new list of exactly the direct subclasses,
  1,000 of them, without grandchildren, and drops a subclass once it has been
  collected.
* A class statement calls its metaclass once with the name, bases and
  namespace; `__set_name__` runs once for each of 50 namespace values that
  define it, and the base's `__init_subclass__` once.
* Every fenced block on the page runs in its own subprocess and asserts its
  own results, and a mutated assertion in one is asserted to fail.

Not settled here:

* The O(b²h²) merge bound is an upper bound from source; the timings show
  growth in both b and h but cannot show a worst case.
* A `__slots__` declaration of t names adds t descriptors and a sort of the
  names, O(t log t); the page treats a class's slots as few and does not
  price them.
* The cost of metaclass, `__prepare__`, `__init_subclass__` and
  `__set_name__` hooks is their own code's; the tests only count the calls.
* Not varied: namespace values other than ints and functions, descriptors
  with costly `__set_name__`, and metaclasses defined in C.
"""

from __future__ import annotations

import gc
import pathlib
import re
import subprocess
import sys
import textwrap
import timeit
import tracemalloc
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import partial
from types import MappingProxyType
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "type_func.md"
EXPECTED_BLOCKS = 7


def chain(depth: int, base: type = object) -> type:
    for index in range(depth):
        base = type(f"Node{index}", (base,), {})
    return base


def merging_bases(width: int, depth: int) -> tuple[type, ...]:
    """Bases sharing a pivot, plus a final base with a chain above that pivot.

    The chain below the pivot keeps rejected candidates' tail scans long.
    """
    pivot = chain(depth)
    early = tuple(type(f"Early{i}", (pivot,), {}) for i in range(width))
    return (*early, chain(depth, pivot))


def merging_class(width: int, depth: int) -> type:
    return type("Merged", merging_bases(width, depth), {})


def create_and_keep(bases: tuple[type, ...], kept: list[type]) -> None:
    kept.append(type("X", bases, {}))


def fastest(call: Callable[[], Any], number: int = 10) -> float:
    """Fastest of five runs, in seconds per call."""
    return min(timeit.repeat(call, number=number, repeat=5)) / number


@contextmanager
def gc_disabled() -> Iterator[None]:
    gc.collect()
    gc.disable()
    try:
        yield
    finally:
        gc.enable()


def traced_peak(call: Callable[[], Any]) -> tuple[Any, int]:
    tracemalloc.start()
    try:
        result = call()
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    return result, peak


class TestTypeReturnsTheClass:
    """`type(obj)` is O(1): it returns the object's class, whatever `__class__` says."""

    def test_the_class_is_returned_itself(self) -> None:
        for size in (1, 10_000):
            cls = type("Sized", (), dict.fromkeys((f"a{i}" for i in range(size)), 0))
            assert type(cls()) is cls

    def test_an_overridden_class_attribute_is_ignored(self) -> None:
        class Proxy:
            @property
            def __class__(self) -> type:  # type: ignore[override]
                return int

        proxy = Proxy()
        assert type(proxy) is Proxy
        assert proxy.__class__ is int
        assert isinstance(proxy, int)


class TestClassCreationCopiesTheNamespace:
    """`type(name, bases, namespace)` is O(n) in the namespace it copies."""

    def test_the_class_holds_its_own_copy(self) -> None:
        sizes = []
        for count in (100, 10_000):
            namespace = dict.fromkeys((f"a{i}" for i in range(count)), 0)
            cls = type("Sized", (), namespace)
            namespace["a0"] = 42
            assert vars(cls)["a0"] == 0
            assert all(getattr(cls, name) == 0 for name in namespace)
            sizes.append(sys.getsizeof(dict(vars(cls))))
        assert 30 < sizes[1] / sizes[0] < 150, sizes

    @pytest.mark.timing
    def test_creation_scales_with_namespace_size(self) -> None:
        """A 64x namespace step: linear predicts 64x and quadratic 4,096x."""
        times = []
        for count in (512, 32_768):
            namespace = dict.fromkeys((f"a{i}" for i in range(count)), 0)
            times.append(fastest(partial(type, "Sized", (), namespace)))
        ratio = times[1] / times[0]
        assert 8 < ratio < 512, f"64x namespace: {times} seconds per class, ratio={ratio:.2f}"


class TestClassCreationScalesWithTheMro:
    """Creating a class is O(h) in its MRO, which it stores as its own tuple."""

    @pytest.mark.timing
    def test_creation_below_a_chain_is_linear_in_depth(self) -> None:
        """h from 18 to 258: linear predicts 14x, quadratic 205x, constant 1x."""
        times = []
        with gc_disabled():
            for depth in (16, 256):
                base, kept = chain(depth), []
                times.append(fastest(partial(create_and_keep, (base,), kept), 50))
        ratio = times[1] / times[0]
        assert 4 < ratio < 64, f"16x depth: {times} seconds per class, ratio={ratio:.2f}"

    def test_each_class_stores_its_own_mro(self) -> None:
        base = chain(100)
        cls = type("X", (base,), {})
        assert cls.__mro__ is not base.__mro__
        assert cls.__mro__[1:] == base.__mro__

    @pytest.mark.serial
    def test_creation_allocates_the_mro_tuple(self) -> None:
        peaks, tuple_sizes = [], []
        with gc_disabled():
            for depth in (16, 1_024):
                base = chain(depth)
                type("Warm", (base,), {})
                cls, peak = traced_peak(partial(type, "X", (base,), {}))
                peaks.append(peak)
                tuple_sizes.append(sys.getsizeof(cls.__mro__))
        grown, tuple_grown = peaks[1] - peaks[0], tuple_sizes[1] - tuple_sizes[0]
        assert 7 * 1024 < grown < 4 * tuple_grown, (peaks, tuple_sizes)

    @pytest.mark.timing
    def test_several_bases_add_the_merge(self) -> None:
        """9 to 129 bases at depth 80: linear in b or h predicts at most 14x."""
        times = []
        with gc_disabled():
            for width in (8, 128):
                bases, kept = merging_bases(width, 80), []
                times.append(fastest(partial(create_and_keep, bases, kept), 5))
        assert times[1] / times[0] > 25, times

    def test_the_stored_order_is_the_c3_merge(self) -> None:
        cls = merging_class(4, 8)
        assert cls.__mro__ == tuple(type.mro(cls))


class TestMethodResolutionOrder:
    """`C.__mro__` is stored; `type.mro(C)` computes a new list each call."""

    @pytest.mark.parametrize("cls", [object, chain(20), merging_class(4, 8)])
    def test_mro_returns_a_fresh_list_without_replacing_the_tuple(self, cls: type) -> None:
        stored = cls.__mro__
        result = type.mro(cls)
        other = type.mro(cls)
        assert isinstance(result, list)
        assert result == other == list(stored)
        assert result is not other
        assert cls.__mro__ is stored
        result.clear()
        assert type.mro(cls) == other
        assert cls.__mro__ is stored

    def test_type_mro_recomputes_instead_of_calling_an_override(self) -> None:
        calls = []

        class Meta(type):
            def mro(cls) -> list[type]:
                calls.append(cls)
                result = type.mro(cls)
                return [result[0], *reversed(result[1:-1]), result[-1]]

        left = type("Left", (), {})
        right = type("Right", (), {})
        cls = Meta("Custom", (left, right), {})
        stored = cls.__mro__
        assert stored == (cls, right, left, object)
        calls.clear()
        assert type.mro(cls) == [cls, left, right, object]
        assert calls == []
        assert cls.__mro__ is stored
        assert cls.mro() == list(stored)
        assert calls == [cls]

    @pytest.mark.timing
    def test_single_base_mro_scales_with_depth(self) -> None:
        shallow, deep = chain(16), chain(512)
        times = [fastest(partial(type.mro, cls), 2_000) for cls in (shallow, deep)]
        assert 5 < times[1] / times[0] < 100, times

    @pytest.mark.timing
    @pytest.mark.parametrize("dimension", ["width", "depth"])
    def test_merge_cost_depends_on_both_width_and_depth(self, dimension: str) -> None:
        """A 16x step separates repeated C3 scans from linear list copying."""
        classes = (
            [merging_class(width, 80) for width in (8, 128)]
            if dimension == "width"
            else [merging_class(32, depth) for depth in (8, 128)]
        )
        times = [fastest(partial(type.mro, cls), 5) for cls in classes]
        assert times[1] / times[0] > 25, (dimension, times)

    @pytest.mark.serial
    @pytest.mark.parametrize("multiple", [False, True])
    def test_mro_allocation_scales_with_result_length(self, multiple: bool) -> None:
        """The peak stays within a small multiple of the returned list's size.

        A list header reused from the freelist is not traced, so the depth-16
        peak can be the item array alone; the bound is per size, not a peak ratio.
        """
        peaks, sizes = [], []
        for depth in (16, 256):
            cls = merging_class(4, depth) if multiple else chain(depth)
            result, peak = traced_peak(partial(type.mro, cls))
            peaks.append(peak)
            assert result == list(cls.__mro__)
            sizes.append(sys.getsizeof(result))
        assert 5 < sizes[1] / sizes[0] < 25, sizes
        assert all(peak <= 4 * size for peak, size in zip(peaks, sizes, strict=True)), (
            peaks,
            sizes,
        )
        assert peaks[1] > 5 * sizes[0], (peaks, sizes)


class TestClassAttributes:
    """Stored attributes are O(1); `__dict__` is a view; `__subclasses__()` is O(s)."""

    def test_stored_attributes_are_the_same_object_each_read(self) -> None:
        cls = type("Leaf", (chain(10),), {})
        for name in ("__mro__", "__bases__", "__base__", "__name__", "__qualname__"):
            assert getattr(cls, name) is getattr(cls, name), name

    def test_dict_is_a_live_read_only_view(self) -> None:
        cls = type("Holder", (), {"limit": 10})
        view = cls.__dict__
        assert isinstance(view, MappingProxyType)
        cls.extra = 1  # type: ignore[attr-defined]
        assert view["extra"] == 1
        with pytest.raises(TypeError):
            view["limit"] = 20  # type: ignore[index]

    @pytest.mark.serial
    def test_reading_dict_copies_nothing(self) -> None:
        cls = type("Large", (), dict.fromkeys((f"a{i}" for i in range(100_000)), 0))
        cls.__dict__  # noqa: B018 - warm the attribute lookup
        view, peak = traced_peak(lambda: cls.__dict__)
        assert len(view) > 100_000
        assert peak < 1024, f"traced peak {peak} bytes"

    def test_subclasses_lists_only_direct_subclasses(self) -> None:
        base = type("Base", (), {})
        children = [type(f"Child{i}", (base,), {}) for i in range(1_000)]
        grandchild = type("Grandchild", (children[0],), {})
        first, second = base.__subclasses__(), base.__subclasses__()
        assert first == children
        assert grandchild not in first
        assert first is not second

    def test_a_collected_subclass_is_dropped(self) -> None:
        base = type("Base", (), {})
        kept = type("Kept", (base,), {})
        type("Gone", (base,), {})
        gc.collect()
        assert base.__subclasses__() == [kept]


class TestCreationHooksAreCalledOnce:
    """The metaclass, `__set_name__` and `__init_subclass__` run as part of creation."""

    def test_a_class_statement_calls_its_metaclass_once(self) -> None:
        calls: list[tuple[str, tuple[type, ...], dict[str, Any]]] = []

        class Recording(type):
            def __new__(
                mcs, name: str, bases: tuple[type, ...], namespace: dict[str, Any]
            ) -> Recording:
                calls.append((name, bases, dict(namespace)))
                return super().__new__(mcs, name, bases, namespace)

        class Plugin(metaclass=Recording):
            value = 1

        assert len(calls) == 1
        name, bases, namespace = calls[0]
        assert (name, bases, namespace["value"]) == ("Plugin", (), 1)
        assert type(Plugin) is Recording

    def test_set_name_and_init_subclass_run_once_each(self) -> None:
        set_names: list[str] = []
        subclasses: list[type] = []

        class Field:
            def __set_name__(self, owner: type, name: str) -> None:
                set_names.append(name)

        class Base:
            def __init_subclass__(cls) -> None:
                subclasses.append(cls)

        namespace: dict[str, Any] = {f"f{i}": Field() for i in range(50)}
        namespace.update({f"x{i}": i for i in range(50)})
        cls = type("Model", (Base,), namespace)
        assert sorted(set_names) == sorted(f"f{i}" for i in range(50))
        assert subclasses == [cls]


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
        line, source = next((n, s) for n, s in _blocks() if "[Child, Base, object]" in s)
        mutated = source.replace("[Child, Base, object]", "[Base, Child, object]", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
