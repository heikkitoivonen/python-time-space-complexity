"""Evidence for the type() table and examples in docs/builtins/type_func.md.

Released CPython 3.10--3.14 Objects/typeobject.c implements type.mro through
mro_implementation and pmerge. Single inheritance copies the base's MRO.
For multiple inheritance, at most h output steps try b candidate heads, each
against b tails of at most h entries: O(b²h²) time. The merge borrows the base
tuples, retaining O(b) cursors and an O(h) result; b <= h, hence O(h) space.
This source argument establishes the upper bound; finite timings cannot.

The merge tests use several bases sharing a pivot, plus a final base with a
chain above that pivot. A chain below the pivot keeps rejected-candidate tail
scans long. Growing fan-in with both chains fixed, and growing the chains with
fan-in fixed, exposes both quadratic dimensions. Class construction is outside
the timed call. Single-base tests vary depth from 16 to 512. List size and traced
peak allocation cover fresh results and total working space. A custom metaclass
distinguishes recomputation from copying the cached tuple and checks that the
direct type.mro call bypasses an override without replacing the cached order.

type(obj) is checked by identity. Class creation varies ordinary integer-valued
attributes with fixed bases, checking namespace copying, storage and timing.
Custom hooks, descriptor work and unusual namespace keys are outside those
bounds. All ten examples execute independently; the new MRO example also has
semantic assertions. Existing advice about isinstance is not re-audited here.
"""

import pathlib
import re
import subprocess
import sys
import textwrap
import timeit
import tracemalloc
from collections.abc import Callable
from functools import partial
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs/builtins/type_func.md"


def chain(depth: int, base: type = object) -> type:
    for index in range(depth):
        base = type(f"Node{index}", (base,), {})
    return base


def merging_class(width: int, depth: int) -> type:
    pivot = chain(depth)
    early = tuple(type(f"Early{i}", (pivot,), {}) for i in range(width))
    return type("Merged", (*early, chain(depth, pivot)), {})


def fastest(call: Callable[[], Any], number: int = 10) -> float:
    return min(timeit.repeat(call, number=number, repeat=5)) / number


def test_type_returns_the_existing_class() -> None:
    for size in (1, 10_000):
        cls = type("Sized", (), dict.fromkeys((f"a{i}" for i in range(size)), 0))
        assert type(cls()) is cls


def test_class_creation_copies_the_namespace() -> None:
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
def test_class_creation_scales_with_namespace_size() -> None:
    times = []
    for count in (32, 4_096):
        namespace = dict.fromkeys((f"a{i}" for i in range(count)), 0)
        times.append(fastest(partial(type, "Sized", (), namespace)))
    assert times[1] / times[0] > 8, times


@pytest.mark.parametrize("cls", [object, chain(20), merging_class(4, 8)])
def test_mro_returns_a_fresh_list_without_replacing_the_tuple(cls: type) -> None:
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


def test_type_mro_recomputes_instead_of_copying_a_custom_cached_order() -> None:
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
def test_single_base_mro_scales_with_depth() -> None:
    shallow, deep = chain(16), chain(512)
    times = [fastest(partial(type.mro, cls), 2_000) for cls in (shallow, deep)]
    assert 5 < times[1] / times[0] < 100, times


@pytest.mark.timing
@pytest.mark.parametrize("dimension", ["width", "depth"])
def test_merge_cost_depends_on_both_width_and_depth(dimension: str) -> None:
    """A 16x step separates repeated C3 scans from linear list copying.

    Width varies from 8 to 128 at depth 80; depth varies from 8 to 128
    at width 32. No custom hooks or class construction are timed.
    """
    classes = (
        [merging_class(width, 80) for width in (8, 128)]
        if dimension == "width"
        else [merging_class(32, depth) for depth in (8, 128)]
    )
    times = [fastest(partial(type.mro, cls), 5) for cls in classes]
    assert times[1] / times[0] > 25, (dimension, times)


@pytest.mark.serial
@pytest.mark.parametrize("multiple", [False, True])
def test_mro_allocation_scales_with_result_length(multiple: bool) -> None:
    peaks, sizes = [], []
    for depth in (16, 256):
        cls = merging_class(4, depth) if multiple else chain(depth)
        tracemalloc.start()
        try:
            result = type.mro(cls)
            peaks.append(tracemalloc.get_traced_memory()[1])
        finally:
            tracemalloc.stop()
        assert result == list(cls.__mro__)
        sizes.append(sys.getsizeof(result))
    assert 5 < sizes[1] / sizes[0] < 25, sizes
    assert 5 < peaks[1] / peaks[0] < 25, peaks


def run_example(source: str, workdir: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        cwd=workdir,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )


def test_all_examples_execute_independently(tmp_path: pathlib.Path) -> None:
    text = PAGE.read_text()
    blocks = list(re.finditer(r"```python\n(.*?)```", text, re.DOTALL))
    assert len(blocks) == 10
    for index, block in enumerate(blocks):
        workdir = tmp_path / str(index)
        workdir.mkdir()
        result = run_example(block[1], workdir)
        line = text.count("\n", 0, block.start()) + 1
        assert result.returncode == 0, f"{PAGE}:{line}: {result.stdout}\n{result.stderr}"


def test_example_runner_detects_a_broken_mro_assertion(tmp_path: pathlib.Path) -> None:
    block = re.search(r"```python\n(.*?)```", PAGE.read_text(), re.DOTALL)
    assert block is not None
    source = block[1]
    broken = source.replace("[Child, Base, object]", "[Base, Child, object]")
    assert broken != source
    result = run_example(broken, tmp_path)
    assert result.returncode != 0
    assert "AssertionError" in result.stderr
