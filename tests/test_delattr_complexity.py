"""Tests for docs/builtins/delattr.md.

delattr() is builtin_delattr in Python/bltinmodule.c, which calls
PyObject_SetAttr(obj, name, NULL) - the same call `del obj.name` compiles to.
For an ordinary instance that reaches PyObject_GenericSetAttr in
Objects/object.c: one _PyType_Lookup on type(obj) (the type attribute cache, a
walk of the MRO on a miss) for a data descriptor, then a dict deletion. On a
class it reaches type_setattro in Objects/typeobject.c, which calls
PyType_Modified and so invalidates the version tag of the class and of every
subclass that has one. The same shape holds in the v3.10.19, v3.11.14,
v3.12.12, v3.13.11 and v3.14.2 tags.

Measurement scope:

* `del` and delattr() call the same `__delattr__`: a counting `__delattr__`
  sees both;
* a data descriptor wins over the instance `__dict__`: a property deleter runs
  even when the instance `__dict__` holds the same name, and a property
  without a deleter raises AttributeError;
* deleting through an instance never reaches a class attribute;
* `__slots__`: the slot is cleared, and a second delete raises;
* `vars(obj).clear()` bypasses a class's `__delattr__` (the counter stays 0);
* instance deletion does not grow with the attributes on the instance: one
  delete from a dict of 10 against one of 100,000 keys, 200,000 deletes each,
  accepted below x3; a linear scan would predict about x10,000;
* class deletion grows with subclasses: deleting a class attribute with 20,000
  version-tagged subclasses against none, measured about x4,000 on the pinned
  interpreter (aarch64, CPython 3.14) and x4,000 on 3.10; accepted above x50;
* space: tracemalloc's traced peak for a warmed instance delattr() is zero;
* every fenced block runs in a subprocess and asserts its own results.

Not settled here:

* O(d) on a type cache miss is source-only: the MRO walk in _PyType_Lookup.
* Module deletion is source-only: module_setattro falls through to the
  generic dict deletion.
* On 3.10 only, the first deletion from a key-sharing (split) instance dict
  converts it to a combined table: sys.getsizeof() of a 20-attribute dict goes
  from 232 to 640 bytes. It is O(a) in that instance's attributes once per
  instance, so the page keeps the O(1) row; 3.11+ keep the size unchanged.
* The Best Practices lists are advice; the class-attribute item rests on the
  subclass measurement above.
* Not tested: the 3.10 split-dict conversion above, which the page does not
  claim.
* Not varied: hierarchy depth for class deletion (the 20,000 subclasses are
  direct children), name length (hashing is priced at O(1)), and C types with their
  own tp_setattro other than modules.
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

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "delattr.md"
EXPECTED_BLOCKS = 8


def best_time(func: Callable[[], Any], repeats: int = 7) -> float:
    """The fastest of several runs, the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return min(times)


class Counting:
    deletes: list[str]

    def __init__(self) -> None:
        object.__setattr__(self, "deletes", [])

    def __delattr__(self, name: str) -> None:
        self.deletes.append(name)
        super().__delattr__(name)


class TestSameAsDel:
    """Intro: delattr(obj, "name") is exactly `del obj.name`."""

    def test_both_spellings_call_delattr(self) -> None:
        obj = Counting()
        obj.x = 1  # type: ignore[attr-defined]
        obj.y = 2  # type: ignore[attr-defined]
        delattr(obj, "x")
        del obj.y  # type: ignore[attr-defined]
        assert obj.deletes == ["x", "y"]

    def test_name_must_be_a_string(self) -> None:
        obj = Counting()
        with pytest.raises(TypeError):
            delattr(obj, 1)  # type: ignore[arg-type]
        assert obj.deletes == []


class TestInstanceAttributes:
    """Rows: instance attribute O(1) avg, missing attribute raises."""

    def test_class_attribute_is_not_reached(self) -> None:
        class C:
            default = 1

        with pytest.raises(AttributeError):
            delattr(C(), "default")
        assert C.default == 1

    def test_missing_raises(self) -> None:
        class C:
            pass

        with pytest.raises(AttributeError):
            delattr(C(), "missing")

    def test_cost_does_not_grow_with_attribute_count(self) -> None:
        class C:
            pass

        deletes = 200_000

        def cost(size: int) -> float:
            obj = C()
            for i in range(size):
                setattr(obj, f"a{i}", i)

            def run() -> None:
                for _ in range(deletes):
                    obj.k = 0  # type: ignore[attr-defined]
                    delattr(obj, "k")

            return best_time(run)

        small, large = cost(10), cost(100_000)
        assert large / small < 3, f"x{large / small:.1f}"

    def test_a_delete_allocates_nothing(self) -> None:
        class C:
            pass

        obj = C()

        def once() -> None:
            obj.k = 0  # type: ignore[attr-defined]
            delattr(obj, "k")

        once()
        obj.k = 0  # type: ignore[attr-defined]
        tracemalloc.start()
        try:
            delattr(obj, "k")
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        assert peak == 0


class TestSlots:
    """Row: __slots__ attribute O(1); the slot is cleared."""

    def test_clear_then_raise(self) -> None:
        class P:
            __slots__ = ("x",)

        p = P()
        p.x = 1
        delattr(p, "x")
        assert not hasattr(p, "x")
        with pytest.raises(AttributeError):
            delattr(p, "x")


class TestDescriptors:
    """Rows: property or descriptor O(k), custom __delattr__ O(k)."""

    def test_deleter_wins_over_instance_dict(self) -> None:
        calls: list[str] = []

        class C:
            @property
            def v(self) -> int:
                return 1

            @v.deleter
            def v(self) -> None:
                calls.append("deleter")

        obj = C()
        obj.__dict__["v"] = 5
        delattr(obj, "v")
        assert calls == ["deleter"]
        assert obj.__dict__ == {"v": 5}

    def test_property_without_deleter_raises(self) -> None:
        class C:
            @property
            def v(self) -> int:
                return 1

        with pytest.raises(AttributeError):
            delattr(C(), "v")

    def test_vars_clear_bypasses_delattr(self) -> None:
        obj = Counting()
        deletes = obj.deletes
        for i in range(10):
            setattr(obj, f"a{i}", i)
        vars(obj).clear()
        assert deletes == []
        assert vars(obj) == {}


class TestClassAttributes:
    """Row: delattr(cls, name) is O(s) in the subclasses."""

    def test_cost_grows_with_subclasses(self) -> None:
        def cost(count: int) -> float:
            class Base:
                pass

            subs = [type(f"S{i}", (Base,), {}) for i in range(count)]
            times: list[float] = []
            for _ in range(5):
                Base.x = 1  # type: ignore[attr-defined]
                hasattr(Base, "x")  # the baseline's own cache is warm too
                for sub in subs:
                    hasattr(sub, "x")  # assigns each subclass a version tag
                start = time.perf_counter()
                delattr(Base, "x")
                times.append(time.perf_counter() - start)
            return min(times)

        alone, wide = cost(0), cost(20_000)
        assert wide / alone > 50, f"x{wide / alone:.1f}"

    def test_subclass_sees_the_deletion(self) -> None:
        class Base:
            flag = True

        class Child(Base):
            pass

        assert Child().flag
        delattr(Base, "flag")
        assert not hasattr(Child(), "flag")


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


class TestPageExamples:
    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        for line, source in _blocks():
            result = _run(source, tmp_path)
            assert result.returncode == 0, f"block at line {line}:\n{result.stderr}"

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        line, source = _blocks()[0]
        broken = source.replace("assert vars(config) == {}", 'assert vars(config) == {"x": 1}')
        assert broken != source, f"substitution did not apply to block at line {line}"
        assert _run(broken, tmp_path).returncode != 0
