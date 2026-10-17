"""Tests for docs/builtins/issubclass.md.

The page prices `issubclass(cls, base)` for an ordinary `base` at O(d), d = len(cls.__mro__):
`object_issubclass` in `Objects/abstract.c` reaches `PyType_IsSubtype` in `Objects/typeobject.c`,
which compares each entry of the stored MRO tuple with `base` by pointer. A tuple or union is
walked one member at a time by the same function, and an ABC answers through
`_abc__abc_subclasscheck_impl` in `Modules/_abc.c`: positive and negative weak-set caches, then
`__subclasshook__`, the MRO, the registry and `__subclasses__()`, recursively. That code is the
same on 3.11.14, 3.12.12, 3.13.11, 3.14.2 and 3.15.0rc3. Call counts settle the tuple, union and
ABC rows without tolerance; only the MRO scan needs a stopwatch.

Measurement scope:

* MRO scan: single-inheritance chains with `__mro__` lengths 12, 102 and 1,002, each checked
  against a tuple of 100 copies of an unrelated class, fastest of five runs of 200 calls. Each
  10x step in length costs at least 3x, and the whole range at least 15x, against the 1x an
  O(1) check predicts. At length 1,002, the class's direct parent is found at least 4x faster
  than the class just before `object`.
* The scan compares by identity: a metaclass `__eq__` on every class in the MRO is never called.
* Tuples and unions: classes whose metaclass counts `__subclasscheck__` calls. A miss against
  five classes consults all five once each, in order; a match at the second consults two. A
  nested tuple of the same five gives the same count. A miss against a union of three
  consults all three, and a match at the second consults two.
* ABCs: a counting `__subclasshook__` inherited by t = 10 and 100 subclasses. A first miss
  calls it t + 1 times, and afterwards each visited subclass answers from its own cache with no
  call. A repeat miss or hit calls it zero times. With t = 10 and one grandchild, a cached hit
  calls it zero times after `register()` on an unrelated ABC, and the next miss calls it 12
  times, once per class in the tree. With a class registered on the first subclass, the walk
  stops after two calls.
* `list` is a `Sequence` and a `MutableSequence` with neither in its MRO, and `MutableSequence`
  is a subclass of `Sequence`.
* A metaclass `__subclasscheck__` receives the first argument and its result is converted with
  `bool`.
* A non-class first argument raises `TypeError` against a plain class, an ABC and a tuple.

Not settled here:

* The O(t) space of an uncached ABC check is observed through the caches each visited ABC
  fills, not measured in bytes.
* A first argument that is not a type but has `__bases__` takes `abstract_issubclass`, a
  recursive walk of `__bases__`; the page does not price it.
* Stack depth from deeply nested tuples and the cost of clearing a stale negative cache, which
  discards entries an earlier check paid to add, are not priced.
* A metaclass whose `mro()` returns a custom tuple, free-threaded builds and other Python
  implementations are not varied.
* The Python 3.10 boundary for union arguments predates the supported range; unions are
  checked on the running interpreter only.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap
import time
from abc import ABC
from collections.abc import Callable, MutableSequence, Sequence
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "issubclass.md"
EXPECTED_BLOCKS = 17


def best_time(func: Callable[[], Any], repeats: int = 5, loops: int = 200) -> float:
    """The fastest of several runs of `loops` calls, which is the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        for _ in range(loops):
            func()
        times.append(time.perf_counter() - start)
    return min(times)


def chain(length: int) -> type:
    """A single-inheritance chain whose leaf has `length + 2` entries in its MRO."""
    cls: type = type("C0", (), {})
    for index in range(length):
        cls = type(f"C{index + 1}", (cls,), {})
    return cls


class CountingMeta(type):
    """A metaclass that counts the `__subclasscheck__` calls made on its classes."""

    calls: list[str] = []

    def __subclasscheck__(cls, subclass: type) -> bool:
        CountingMeta.calls.append(cls.__name__)
        return super().__subclasscheck__(subclass)


def counting_classes(count: int) -> list[type]:
    CountingMeta.calls = []
    return [CountingMeta(f"K{index}", (), {}) for index in range(count)]


def abc_with_subclasses(count: int) -> tuple[type, list[type], list[str]]:
    """An ABC with `count` direct subclasses, all sharing a counting `__subclasshook__`."""
    calls: list[str] = []

    class Base(ABC):  # noqa: B024 - the cache, not abstract methods, is under test
        @classmethod
        def __subclasshook__(cls, subclass: type) -> Any:
            calls.append(cls.__name__)
            return NotImplemented

    subclasses = [type(f"Sub{index}", (Base,), {}) for index in range(count)]
    return Base, subclasses, calls


class TestPlainClassScansTheMro:
    """Row: `issubclass(cls, base)` is O(d), d = len(cls.__mro__), stopping at a match.

    A tuple of 100 copies of an unrelated class repeats the full scan 100 times per call, so the
    per-call overhead does not hide the growth.
    """

    @pytest.mark.timing
    def test_a_miss_grows_with_mro_length(self) -> None:
        class Unrelated:
            pass

        misses = (Unrelated,) * 100
        times = {}
        for length in (10, 100, 1_000):
            leaf = chain(length)
            assert len(leaf.__mro__) == length + 2
            times[length] = best_time(lambda leaf=leaf: issubclass(leaf, misses))

        steps = [times[100] / times[10], times[1_000] / times[100]]
        overall = times[1_000] / times[10]
        assert all(step > 3 for step in steps), f"steps {steps}, times {times}"
        assert overall > 15, f"overall {overall:.1f}, times {times}"

    @pytest.mark.timing
    def test_a_match_near_the_front_returns_early(self) -> None:
        leaf = chain(1_000)
        front, back = leaf.__mro__[1], leaf.__mro__[-2]
        front_time = best_time(lambda: issubclass(leaf, front), loops=2_000)
        back_time = best_time(lambda: issubclass(leaf, back), loops=2_000)
        assert issubclass(leaf, front) and issubclass(leaf, back)
        ratio = back_time / front_time
        assert ratio > 4, f"front {front_time:.2e}s, back {back_time:.2e}s, ratio {ratio:.1f}"

    def test_the_scan_compares_by_identity(self) -> None:
        eq_calls: list[str] = []

        class EqMeta(type):
            def __eq__(cls, other: object) -> bool:
                eq_calls.append(cls.__name__)
                return super().__eq__(other)

            __hash__ = type.__hash__

        root = EqMeta("Root", (), {})
        leaf = EqMeta("Leaf", (EqMeta("Middle", (root,), {}),), {})

        class Unrelated:
            pass

        assert issubclass(leaf, root)
        assert not issubclass(leaf, Unrelated)
        assert eq_calls == []


class TestTuplesAndUnionsStopAtTheFirstMatch:
    """Rows: a tuple or a union costs O(k·d), one check per class in order until a match."""

    def test_a_miss_checks_every_class_once(self) -> None:
        classes = counting_classes(5)
        assert not issubclass(int, tuple(classes))
        assert CountingMeta.calls == ["K0", "K1", "K2", "K3", "K4"]

    def test_a_match_stops_the_walk(self) -> None:
        classes = counting_classes(5)
        subclass = type("Derived", (classes[1],), {})
        CountingMeta.calls = []
        assert issubclass(subclass, tuple(classes))
        assert CountingMeta.calls == ["K0", "K1"]

    def test_nested_tuples_are_searched_in_order(self) -> None:
        classes = counting_classes(5)
        nested = (classes[0], (classes[1], (classes[2],)), classes[3], classes[4])
        assert not issubclass(int, nested)
        assert CountingMeta.calls == ["K0", "K1", "K2", "K3", "K4"]

    def test_a_union_is_checked_as_its_members(self) -> None:
        classes = counting_classes(3)
        union = classes[0] | classes[1] | classes[2]
        assert not issubclass(int, union)
        assert CountingMeta.calls == ["K0", "K1", "K2"]

        subclass = type("Derived", (classes[1],), {})
        CountingMeta.calls = []
        assert issubclass(subclass, union)
        assert CountingMeta.calls == ["K0", "K1"]


class TestAbcCache:
    """Rows: an uncached ABC check is O(t·d) time and O(t) space; a cached one is O(1).

    The inherited `__subclasshook__` runs once per ABC the check visits, so its call count is
    the number of classes walked, t + 1 for an ABC with t subclasses and an empty registry.
    """

    @pytest.mark.parametrize("count", [10, 100])
    def test_a_first_miss_visits_every_subclass(self, count: int) -> None:
        base, _, calls = abc_with_subclasses(count)
        assert not issubclass(int, base)
        assert len(calls) == count + 1

    def test_every_visited_abc_caches_its_answer(self) -> None:
        base, subclasses, calls = abc_with_subclasses(10)
        assert not issubclass(int, base)
        calls.clear()
        assert not any(issubclass(int, subclass) for subclass in subclasses)
        assert calls == []

    def test_cached_answers_call_nothing(self) -> None:
        base, subclasses, calls = abc_with_subclasses(100)
        member = type("Member", (subclasses[50],), {})
        assert not issubclass(int, base)
        assert issubclass(member, base)
        calls.clear()
        assert not issubclass(int, base)
        assert issubclass(member, base)
        assert calls == []

    def test_a_match_in_the_walk_stops_it(self) -> None:
        base, subclasses, calls = abc_with_subclasses(100)
        subclasses[0].register(int)
        calls.clear()
        assert issubclass(int, base)
        assert calls == ["Base", "Sub0"]

    def test_register_on_any_abc_forgets_false_answers_only(self) -> None:
        base, subclasses, calls = abc_with_subclasses(10)
        member = type("Member", (subclasses[3],), {})
        assert not issubclass(int, base)
        assert issubclass(member, base)

        class Unrelated(ABC):  # noqa: B024 - only register() is used
            pass

        Unrelated.register(float)
        calls.clear()
        assert issubclass(member, base)
        assert calls == []
        assert not issubclass(int, base)
        assert len(calls) == 12  # Base, its 10 subclasses and Member below Sub3

    def test_list_is_a_sequence_without_it_in_its_mro(self) -> None:
        assert Sequence not in list.__mro__
        assert MutableSequence not in list.__mro__
        assert MutableSequence in Sequence.__subclasses__()
        assert issubclass(list, MutableSequence)
        assert issubclass(list, Sequence)


class TestOtherArguments:
    """Rows: a custom `__subclasscheck__` decides; a non-class first argument raises."""

    def test_a_custom_subclasscheck_decides_and_is_converted_to_bool(self) -> None:
        seen: list[object] = []

        class Meta(type):
            def __subclasscheck__(cls, subclass: object) -> Any:
                seen.append(subclass)
                return 1 if subclass is int else ""

        target = Meta("Target", (), {})
        assert issubclass(int, target) is True
        assert issubclass(str, target) is False
        assert seen == [int, str]

    @pytest.mark.parametrize("classinfo", [int, Sequence, (str, int)])
    def test_a_non_class_first_argument_raises(self, classinfo: Any) -> None:
        with pytest.raises(TypeError, match="arg 1 must be a class"):
            issubclass(42, classinfo)  # pyright: ignore[reportArgumentType]


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

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        cache_block = next(src for _, src in _blocks() if "Unrelated.register(float)" in src)
        broken = cache_block.replace(
            "assert Plugin.hook_calls == 202", "assert Plugin.hook_calls == 101"
        )
        assert broken != cache_block, "mutation did not change target"

        result = _run(broken, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
