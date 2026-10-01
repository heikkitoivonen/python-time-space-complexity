"""Tests for docs/stdlib/copy.md.

The page prices a shallow copy by the object's top level and a deep copy by
the object graph: v distinct reachable objects and e references followed.
Identity settles which objects are returned rather than copied; a counting
memo and counting hooks settle that each reference is followed once and each
object copied once; traced allocation settles the shallow bounds; timing is
used only for the deep copy's growth and shape and for `copy.replace()`.
The allocation tests are serial, since tracemalloc also traces xdist's I/O
thread.

Measurement scope:

* `copy.copy()` of a list, dict, set and bytearray returns a new, equal
  container; for the list and the dict, the elements are asserted to be the
  original's objects. Its traced peak grows more than
  50x when a list goes from 1,000 to 100,000 elements, and when an instance
  goes from 100 to 10,000 attributes; the instance copy's attribute values
  are the original's objects and `__init__` is not called.
* `copy.copy()` returns the same object for a 10,000,000-character `str`,
  `bytes`, `tuple`, `frozenset`, `int`, `float`, `complex`, a function and a
  class, and peaks under 4 KB on the string after a warm-up call.
  `copy.deepcopy()` returns the same object for the same str, bytes, numbers,
  function and class; for a tuple of ints it returns the tuple, and for a tuple
  holding a list a new tuple with a new list.
* `copy.deepcopy()` with a counting memo looks up 1,001 references for a list
  holding one empty inner list 1,000 times, and ends with two copies (outer and
  inner) plus the keep-alive list; the copy's 1,000 slots are all one new list. A
  leaf whose `__deepcopy__` counts calls is copied once when referenced 1,000
  times. After a call, the memo has one entry per copied list plus one. A
  self-containing list is copied into a list containing itself.
* A tuple holding one leaf whose `__deepcopy__` returns itself, referenced
  1,000 times, is returned unchanged, is not in the memo afterwards, and its
  leaf's hook runs 1,000 times; the same leaf in a list referenced 1,000 times
  runs once.
* Timing: deep copying 1,000, 10,000 and 100,000 one-element lists costs
  between 4x and 40x more per 10x step (linear predicts 10x, quadratic 100x).
  About 300 lists holding about 10,000 ints cost within 3x of each other
  nested 300 deep and nested one deep, where a bound in elements times depth
  predicts a 300x gap. `copy.replace()` on a 2,000-field named tuple costs more than
  10x a 10-field one.
* Nesting: in a fresh interpreter at the default recursion limit, the deepest
  list that deep copies without `RecursionError` is between 200 and 1,000
  levels; in the test process, 100 levels copy, 2,000 raise, and a flat list
  of 100,000 lists copies, so the limit is depth, not size.
* `copy.copy()` calls a plain instance's `__reduce_ex__` once, with 4. A
  reducer registered with `copyreg.pickle()` is called once by each of
  `copy()` and `deepcopy()`. A `__deepcopy__` that passes the memo on keeps
  two attributes that share a list sharing one copy; one that does not makes
  two copies.
* A lock and a generator raise `TypeError` from both functions; an object
  whose `__reduce_ex__` and `__reduce__` are `None` raises `copy.Error`, and
  `copy.error is copy.Error`.
* `copy.replace()` exists from 3.13 and not before. It builds a new named
  tuple, dataclass and `SimpleNamespace` whose unchanged field is the
  original's object, and a `datetime` equal to the expected one, and raises
  `TypeError` for a list.
* Every fenced Python block runs in its own subprocess, the `copy.replace()`
  block only on 3.13+, and a mutated assertion in one of them is asserted to
  fail.

Not settled here:

* O(v + e) for `deepcopy()` is read from Lib/copy.py on 3.10 to 3.14: one
  dispatch per reference, at most one memo lookup each, one copy per memoized
  object, no other loop. The
  timing tests vary list counts only; dicts, tuples and instances follow the
  same dispatch but are not timed. Treating hashing and memo lookups as O(1)
  is a cost-model assumption.
* The cost of a custom `__copy__`, `__deepcopy__`, `__replace__`, reduction,
  state hook or `copyreg` reducer is the type's and is outside every bound
  but `copy.replace()`'s, which is that cost by definition. A dataclass's `__replace__` passes
  every field as a keyword argument; at hundreds of fields keyword binding
  grows faster than linearly, which is the type's cost, not the module's.
  Only the named tuple's is timed.
* Types with their own `__copy__` or `__reduce__` (`deque`, `OrderedDict`,
  arrays) copy through those methods and are not measured.
* The exact recursion depth depends on frames per level, which differs for
  lists, dicts and instances; only lists are measured.
"""

from __future__ import annotations

import collections
import copy
import copyreg
import dataclasses
import datetime
import pathlib
import re
import subprocess
import sys
import textwrap
import threading
import time
import tracemalloc
import types
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "copy.md"
EXPECTED_BLOCKS = 11
REPLACE_BLOCKS = 1  # the blocks that call copy.replace(), skipped before 3.13


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


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def nested(depth: int) -> list[Any]:
    value: list[Any] = []
    for _ in range(depth):
        value = [value]
    return value


class Plain:
    pass


def plain_with(attributes: int) -> Plain:
    obj = Plain()
    obj.__dict__.update({f"a{i}": [i] for i in range(attributes)})
    return obj


class TestShallowCopyIsTopLevel:
    """`copy.copy()` of a container or instance is O(n) in its top level: a new
    container holding the same objects."""

    @pytest.mark.parametrize(
        "original",
        [[[1], [2]], {"a": [1], "b": [2]}, {(1,), (2,)}, bytearray(b"ab")],
        ids=["list", "dict", "set", "bytearray"],
    )
    def test_a_container_copy_is_new_and_holds_the_same_objects(self, original: Any) -> None:
        shallow = copy.copy(original)
        assert shallow is not original
        assert shallow == original
        if isinstance(original, dict):
            assert all(shallow[k] is v for k, v in original.items())
        elif isinstance(original, list):
            assert all(a is b for a, b in zip(shallow, original, strict=True))

    @pytest.mark.serial
    def test_a_list_copy_grows_with_the_list(self) -> None:
        small = list(range(1_000))
        large = list(range(100_000))
        copy.copy(small)
        small_peak = peak_bytes(lambda: copy.copy(small))
        large_peak = peak_bytes(lambda: copy.copy(large))
        assert large_peak / small_peak > 50, f"{small_peak} B at 1,000, {large_peak} B at 100,000"

    def test_an_instance_copy_shares_its_attribute_values(self) -> None:
        inits = 0

        class Person:
            def __init__(self) -> None:
                nonlocal inits
                inits += 1
                self.tags = ["admin"]

        original = Person()
        shallow = copy.copy(original)
        assert shallow is not original
        assert shallow.__dict__ is not original.__dict__
        assert shallow.tags is original.tags
        assert inits == 1

    @pytest.mark.serial
    def test_an_instance_copy_grows_with_its_attributes(self) -> None:
        small = plain_with(100)
        large = plain_with(10_000)
        copy.copy(small)
        small_peak = peak_bytes(lambda: copy.copy(small))
        large_peak = peak_bytes(lambda: copy.copy(large))
        assert large_peak / small_peak > 50, f"{small_peak} B at 100, {large_peak} B at 10,000"


def _function() -> None:
    pass


IMMUTABLES: list[Any] = ["x" * 10_000_000, b"abc", 10**100, 1.5, 2j, _function, Plain]


class TestImmutablesAreReturned:
    """Copying an immutable object returns it, at O(1) whatever its size; a
    deep copy returns a tuple unchanged only when nothing in it was copied."""

    @pytest.mark.parametrize(
        "value",
        [*IMMUTABLES, (1, [2]), frozenset({1, 2})],
        ids=["str", "bytes", "int", "float", "complex", "function", "class", "tuple", "frozenset"],
    )
    def test_copy_returns_the_same_object(self, value: Any) -> None:
        assert copy.copy(value) is value

    @pytest.mark.parametrize(
        "value", IMMUTABLES, ids=["str", "bytes", "int", "float", "complex", "function", "class"]
    )
    def test_deepcopy_returns_the_same_leaf(self, value: Any) -> None:
        assert copy.deepcopy(value) is value

    @pytest.mark.serial
    def test_copying_a_long_string_allocates_nothing_of_its_size(self) -> None:
        text = IMMUTABLES[0]
        copy.copy(text)
        copy.deepcopy(text)
        assert peak_bytes(lambda: copy.copy(text)) < 4096
        assert peak_bytes(lambda: copy.deepcopy(text)) < 4096

    def test_a_tuple_of_leaves_is_returned_and_one_with_a_list_is_rebuilt(self) -> None:
        leaves = (1, 2, 3)
        assert copy.deepcopy(leaves) is leaves
        holder = ([1], 2)
        copied = copy.deepcopy(holder)
        assert copied is not holder and copied[0] is not holder[0]


class CountingMemo(dict[int, Any]):
    """A memo that counts the lookups deepcopy makes in it."""

    def __init__(self) -> None:
        super().__init__()
        self.gets = 0

    def get(self, key: int, default: Any = None) -> Any:
        self.gets += 1
        return super().get(key, default)


class TestDeepCopyFollowsEachReferenceOnce:
    """`copy.deepcopy()` is O(v + e): each reference is followed once and each
    distinct object copied once, so sharing and cycles survive."""

    def test_each_reference_is_looked_up_and_each_object_copied_once(self) -> None:
        inner: list[Any] = []  # no ints: before 3.14 they are looked up too
        outer = [inner] * 1_000
        memo = CountingMemo()
        deep = copy.deepcopy(outer, memo)
        assert memo.gets == 1_001
        assert len(memo) == 3  # outer, inner, and the keep-alive list
        assert all(item is deep[0] for item in deep)
        assert deep[0] is not inner

    def test_a_shared_leaf_is_deep_copied_once(self) -> None:
        calls = 0

        class Leaf:
            def __deepcopy__(self, memo: dict[int, Any]) -> Leaf:
                nonlocal calls
                calls += 1
                return Leaf()

        leaf = Leaf()
        deep = copy.deepcopy([leaf] * 1_000)
        assert calls == 1
        assert all(item is deep[0] for item in deep)

    def test_the_memo_holds_every_copied_object(self) -> None:
        data = [[i] for i in range(500)]
        memo: dict[int, Any] = {}
        copy.deepcopy(data, memo)
        assert len(memo) == 501 + 1

    def test_an_unchanged_tuple_is_scanned_at_every_reference(self) -> None:
        calls = 0

        class Leaf:
            def __deepcopy__(self, memo: dict[int, Any]) -> Leaf:
                nonlocal calls
                calls += 1
                return self

        leaf = Leaf()
        shared_tuple = (leaf,)
        memo: dict[int, Any] = {}
        deep = copy.deepcopy([shared_tuple] * 1_000, memo)
        assert calls == 1_000
        assert deep[0] is shared_tuple
        assert id(shared_tuple) not in memo

        calls = 0
        copy.deepcopy([[leaf]] * 1_000)
        assert calls == 1  # a shared list is memoized and scanned once

    def test_a_cycle_is_copied_into_a_cycle(self) -> None:
        circular: list[Any] = [1, 2, 3]
        circular.append(circular)
        deep = copy.deepcopy(circular)
        assert deep is not circular
        assert deep[3] is deep


@pytest.mark.timing
class TestDeepCopyIsLinearInTheGraph:
    """Deep copy time grows with the objects copied, and does not multiply by
    nesting depth."""

    def test_ten_times_the_lists_costs_about_ten_times(self) -> None:
        times = {}
        for n in (1_000, 10_000, 100_000):
            data = [[i] for i in range(n)]
            times[n] = best_ns(lambda data=data: copy.deepcopy(data), repeats=5)
        for low, high in ((1_000, 10_000), (10_000, 100_000)):
            ratio = times[high] / times[low]
            assert 4 < ratio < 40, f"{low} -> {high}: x{ratio:.1f} ({times})"

    def test_depth_does_not_multiply_the_cost(self) -> None:
        flat = [list(range(33)) for _ in range(301)]
        chain: list[Any] = list(range(33))
        for _ in range(300):
            chain = [chain, *range(33)]
        flat_ns = best_ns(lambda: copy.deepcopy(flat))
        chain_ns = best_ns(lambda: copy.deepcopy(chain))
        ratio = max(flat_ns, chain_ns) / min(flat_ns, chain_ns)
        assert ratio < 3, f"flat {flat_ns:.0f} ns, 300 deep {chain_ns:.0f} ns"


_MAX_DEPTH_PROBE = """
import copy

def nested(depth):
    value = []
    for _ in range(depth):
        value = [value]
    return value

low, high = 1, 5_000
while low < high:
    mid = (low + high + 1) // 2
    try:
        copy.deepcopy(nested(mid))
    except RecursionError:
        high = mid - 1
    else:
        low = mid
print(low)
"""


class TestDeepCopyRecursesPerLevel:
    """Nesting a few hundred levels deep raises `RecursionError` at the default
    recursion limit, however few objects the structure holds."""

    def test_the_deepest_copyable_nesting_is_a_few_hundred_levels(self) -> None:
        result = subprocess.run(
            [sys.executable, "-c", _MAX_DEPTH_PROBE],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
        )
        depth = int(result.stdout)
        assert 200 < depth < 1_000, depth

    def test_depth_raises_where_size_does_not(self) -> None:
        copy.deepcopy(nested(100))
        copy.deepcopy([[i] for i in range(100_000)])
        with pytest.raises(RecursionError):
            copy.deepcopy(nested(2_000))


class TestCustomObjects:
    """Instances without hooks go through the pickle protocol; hooks decide what
    is copied, and a `__deepcopy__` must pass the memo on to keep sharing."""

    def test_copy_calls_reduce_ex_once_with_protocol_4(self) -> None:
        protocols: list[int] = []

        class Recorded:
            def __reduce_ex__(self, protocol: Any) -> Any:
                protocols.append(protocol)
                return object.__reduce_ex__(self, protocol)

        copy.copy(Recorded())
        assert protocols == [4]

    def test_a_copyreg_reducer_is_used_by_both_functions(self) -> None:
        calls = 0

        class Registered:
            pass

        def reducer(obj: Registered) -> tuple[type[Registered], tuple[()]]:
            nonlocal calls
            calls += 1
            return Registered, ()

        copyreg.pickle(Registered, reducer)
        try:
            copy.copy(Registered())
            assert calls == 1
            copy.deepcopy(Registered())
            assert calls == 2
        finally:
            del copyreg.dispatch_table[Registered]

    @pytest.mark.parametrize("pass_memo", [True, False])
    def test_passing_the_memo_on_keeps_sharing(self, pass_memo: bool) -> None:
        class Pair:
            def __init__(self, first: list[int], second: list[int]) -> None:
                self.first = first
                self.second = second

            def __deepcopy__(self, memo: dict[int, Any]) -> Pair:
                if pass_memo:
                    return Pair(copy.deepcopy(self.first, memo), copy.deepcopy(self.second, memo))
                return Pair(copy.deepcopy(self.first), copy.deepcopy(self.second))

        shared = [1, 2]
        deep = copy.deepcopy(Pair(shared, shared))
        assert deep.first is not shared
        assert (deep.first is deep.second) is pass_memo


class TestUncopyableObjects:
    """A lock and a generator, whose reductions refuse, raise `TypeError`;
    `copy.Error` is raised only when there is no reduction method at all."""

    @pytest.mark.parametrize(
        "make", [threading.Lock, lambda: (x for x in [])], ids=["lock", "generator"]
    )
    @pytest.mark.parametrize("func", [copy.copy, copy.deepcopy], ids=["copy", "deepcopy"])
    def test_an_unpicklable_object_raises_type_error(
        self, make: Callable[[], Any], func: Callable[[Any], Any]
    ) -> None:
        with pytest.raises(TypeError, match="pickle"):
            func(make())

    @pytest.mark.parametrize("func", [copy.copy, copy.deepcopy], ids=["copy", "deepcopy"])
    def test_no_reduction_method_raises_copy_error(self, func: Callable[[Any], Any]) -> None:
        class Opaque:
            __reduce_ex__ = None  # pyright: ignore[reportAssignmentType]
            __reduce__ = None  # pyright: ignore[reportAssignmentType]

        with pytest.raises(copy.Error):
            func(Opaque())

    def test_error_is_an_alias(self) -> None:
        assert copy.error is copy.Error


class TestReplace:
    """`copy.replace()` (3.13+) delegates to `__replace__`; a named tuple
    builds the new object from every field."""

    def test_it_exists_from_3_13(self) -> None:
        assert hasattr(copy, "replace") is (sys.version_info >= (3, 13))

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="version: copy.replace() is 3.13+")
    def test_the_named_types_support_it(self) -> None:
        replace: Callable[..., Any] = getattr(copy, "replace")  # noqa: B009

        point_type = collections.namedtuple("point_type", ["x", "y"])
        tag = ["kept"]
        point = point_type(1, tag)
        assert replace(point, x=2) == point_type(2, tag) and replace(point, x=2).y is tag

        @dataclasses.dataclass(frozen=True)
        class Config:
            timeout: int
            tags: list[str]

        config = Config(30, tag)
        updated = replace(config, timeout=5)
        assert updated is not config and updated.tags is tag

        moment = datetime.datetime(2024, 1, 1)
        assert replace(moment, year=2025) == datetime.datetime(2025, 1, 1)

        space = types.SimpleNamespace(a=1, b=tag)
        changed = replace(space, a=2)
        assert changed is not space and changed.b is tag and space.a == 1

        with pytest.raises(TypeError, match="does not support list"):
            replace([1, 2])

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 13), reason="version: copy.replace() is 3.13+")
    def test_the_cost_follows_the_field_count(self) -> None:
        replace: Callable[..., Any] = getattr(copy, "replace")  # noqa: B009

        def cost(fields: int) -> float:
            record_type = collections.namedtuple("record_type", [f"f{i}" for i in range(fields)])
            record = record_type(*range(fields))
            return best_ns(lambda: replace(record, f0=-1), repeats=9, inner=20)

        small = cost(10)
        large = cost(2_000)
        assert large / small > 10, f"{small:.0f} ns at 10 fields, {large:.0f} ns at 2,000"


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
        skipped: list[int] = []
        for line, source in _blocks():
            if "copy.replace(" in source and sys.version_info < (3, 13):
                skipped.append(line)  # copy.replace() was added in 3.13
                continue
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran + len(skipped) == EXPECTED_BLOCKS
        assert len(skipped) == (REPLACE_BLOCKS if sys.version_info < (3, 13) else 0), skipped
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        needle = "assert deep[0] is deep[1]"
        line, source = next((n, s) for n, s in _blocks() if needle in s)
        mutated = source.replace(needle, "assert deep[0] is not deep[1]", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
