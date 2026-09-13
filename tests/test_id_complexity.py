"""Tests for docs/builtins/id.md.

`id(obj)` is `builtin_id` in `Python/bltinmodule.c`, which calls `PyLong_FromVoidPtr(obj)`.
It reads the pointer address of `obj` and constructs a Python `int` representing
`(uintptr_t)obj`. Because pointer access and fixed-width integer creation are constant-time
operations, `id()` is O(1) time and O(1) auxiliary space (allocating a single Python `int`
object of 28 to 36 bytes on 64-bit systems).

Direct observation settles the behavioral and space claims without a stopwatch:

* In CPython, `id(x)` is the object's memory address: `ctypes.cast(id(x), ctypes.py_object).value`
  recovers `x` itself;
* `id(x)` is constant as long as `x` is kept alive;
* Distinct objects existing concurrently have distinct IDs;
* Objects with non-overlapping lifetimes can share the same ID due to memory address
  recycling: `id([]) == id([])` evaluates to True in CPython while `[] is []` is False;
* The `is` operator performs direct pointer comparison at the bytecode level (`IS_OP`) and
  allocates 0 auxiliary bytes in tracemalloc, whereas `id(a) == id(b)` allocates integer objects;
* CPython caches small integers (-5 to 256) and singletons like `None`, so references to them
  share identity;
* Cycle detection tracks active ancestors separately from completed nodes, accepting shared
  acyclic containers and visiting each container once;
* Using raw `id()` values as cache keys can collide once objects are collected, whereas
  `weakref.WeakKeyDictionary` uses hashing and equality: identity-based keys stay separate,
  but equal keys share an entry tied to the originally inserted key's lifetime.

One timing test checks constant-time scaling:
* `id()` on an empty tuple versus a 100,000-element list scales at ratio close to 1.0, well
  below any input-size scaling.
"""

import ctypes
import gc
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "id.md"


def best_time(func: Callable[[], Any], repeats: int = 5, loops: int = 1_000) -> float:
    """The fastest of several runs of `loops` calls, which is the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        for _ in range(loops):
            func()
        times.append(time.perf_counter() - start)
    return min(times)


def traced_peak(func: Callable[[], Any]) -> int:
    """Peak bytes tracemalloc attributes to one call, after a warm-up call."""
    func()
    tracemalloc.start()
    try:
        func()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak


class TestIdComplexity:
    """Row: O(1) time and space, returns object identity as an integer."""

    def test_id_returns_int(self) -> None:
        obj = object()
        identity = id(obj)
        assert isinstance(identity, int)
        assert identity > 0

    def test_id_allocates_constant_space_regardless_of_object_size(self) -> None:
        small_obj = ()
        large_obj = list(range(100_000))

        # The integer returned by id() has fixed size (single machine word representation)
        assert sys.getsizeof(id(small_obj)) == sys.getsizeof(id(large_obj))

    @pytest.mark.timing
    def test_id_time_does_not_scale_with_object_size(self) -> None:
        small_obj = ()
        large_obj = list(range(100_000))

        small_time = best_time(lambda: id(small_obj))
        large_time = best_time(lambda: id(large_obj))

        ratio = large_time / small_time
        assert 0.2 < ratio < 5.0, (
            f"id() time scaled with object size: small={small_time:.2e}s, large={large_time:.2e}s"
        )


class TestCPythonAddress:
    """CPython implementation detail: id() is the object's memory address."""

    def test_recovering_object_from_id_via_ctypes(self) -> None:
        obj = [1, 2, 3]
        obj_id = id(obj)
        recovered = ctypes.cast(obj_id, ctypes.py_object).value
        assert recovered is obj

    def test_id_remains_constant_during_lifetime(self) -> None:
        obj = {"key": "value"}
        first_id = id(obj)
        for _ in range(10):
            assert id(obj) == first_id


class TestLifetimeAndReuse:
    """Simultaneous uniqueness vs non-overlapping lifetime recycling."""

    def test_concurrent_objects_have_distinct_ids(self) -> None:
        a = [1, 2, 3]
        b = [1, 2, 3]
        assert id(a) != id(b)
        assert a is not b

    def test_alias_shares_same_id(self) -> None:
        a = [1, 2, 3]
        alias = a
        assert id(a) == id(alias)
        assert a is alias

    def test_non_overlapping_lifetimes_can_recycle_id(self) -> None:
        # In CPython, evaluating id([]) twice consecutively frees the first list
        # before the second is allocated, commonly yielding the exact same memory address.
        recycled_equal = any(id([]) == id([]) for _ in range(100))
        assert recycled_equal, "expected address recycling for short-lived temporaries"

    def test_small_ints_and_singletons_share_identity(self) -> None:
        assert id(42) == id(42)
        assert id(0) == id(0)
        assert id(None) == id(None)
        assert id(True) == id(True)
        assert id(False) == id(False)


class TestIsOperatorComparison:
    """The `is` operator compares pointers directly without id() integer allocation."""

    def test_is_allocates_zero_bytes(self) -> None:
        a = [1, 2, 3]
        b = [1, 2, 3]
        peak = traced_peak(lambda: a is b)
        assert peak == 0, f"is operator allocated {peak} bytes"

    def test_id_comparison_allocates_integers(self) -> None:
        a = [1, 2, 3]
        b = [1, 2, 3]
        peak = traced_peak(lambda: id(a) == id(b))
        assert peak >= sys.getsizeof(id(a)), "id() comparison did not allocate integers"

    def test_is_prevents_false_positives_from_address_recycling(self) -> None:
        # id([]) == id([]) can be True due to reuse, but [] is [] is always False
        assert ([] is []) is False  # noqa: F632 - testing that literal empty lists do not share identity


class TestCommonPatterns:
    """Cycle detection and weak reference caching patterns."""

    def test_cycle_detection_on_containers(self, tmp_path: pathlib.Path) -> None:
        source = next(src for _, src in _blocks() if "def has_cycle(" in src)
        assertions = """
shared = [1, 2]
assert has_cycle([1, 1]) is False
assert has_cycle([shared, shared]) is False
assert has_cycle({"left": shared, "right": shared}) is False
assert has_cycle((shared, {1, 2}, shared)) is False
assert has_cycle([[], []]) is False
node = {}
node["child"] = node
assert has_cycle(node) is True
sequence = []
sequence.append(sequence)
assert has_cycle(sequence) is True
parent = {"child": []}
parent["child"].append(parent)
assert has_cycle(parent) is True
assert has_cycle([shared, shared, parent]) is True

# A shared DAG must not expand each completed container again.
class CountedList(list):
    visits = 0
    def __iter__(self):
        type(self).visits += 1
        return super().__iter__()

root = CountedList()
for _ in range(12):
    root = CountedList([root, root])
assert has_cycle(root) is False
assert CountedList.visits == 13
"""
        result = _run(source + assertions, tmp_path)
        assert result.returncode == 0, result.stderr

    def test_equal_weak_keys_share_the_original_keys_lifetime(self) -> None:
        @dataclass(frozen=True)
        class EqualKey:
            value: int

        first = EqualKey(1)
        second = EqualKey(1)
        assert first is not second
        assert first == second
        assert hash(first) == hash(second)
        registry = weakref.WeakKeyDictionary({first: "first"})
        registry[second] = "second"
        assert len(registry) == 1
        assert registry[first] == "second"
        assert next(iter(registry)) is first
        original = weakref.ref(first)
        del first
        gc.collect()
        assert original() is None
        assert second.value == 1
        assert len(registry) == 0

    def test_weak_key_dictionary_cleans_up_on_collection(self) -> None:
        class Tracked:
            pass

        registry: weakref.WeakKeyDictionary[Tracked, str] = weakref.WeakKeyDictionary()
        item: Tracked | None = Tracked()
        other = Tracked()
        assert item is not other
        assert item != other
        registry[other] = "other metadata"
        registry[item] = "metadata"
        assert len(registry) == 2

        item = None
        gc.collect()
        assert len(registry) == 1
        assert registry[other] == "other metadata"


EXPECTED_BLOCKS = 6


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
    """Every block runs under the interpreter running the tests."""

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

    def test_every_block_binds_the_names_it_uses(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        for line, source in _blocks():
            result = _run(source, tmp_path)
            if "NameError" in result.stderr:
                failures.append(f"{PAGE.name}:{line}: {result.stderr.strip()}")
        assert not failures, "\n".join(failures)

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        blocks = _blocks()
        weakref_block = next(src for _, src in blocks if "weakref.WeakKeyDictionary" in src)
        broken = weakref_block.replace("import weakref\n", "", 1)
        assert broken != weakref_block, "mutation did not change target"

        result = _run(broken, tmp_path)
        assert result.returncode != 0
        assert "NameError" in result.stderr
