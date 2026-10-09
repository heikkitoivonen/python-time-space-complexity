"""Tests for docs/builtins/callable.md.

callable() is builtin_callable in Python/bltinmodule.c, which returns
PyCallable_Check(obj). In Objects/object.c that is
`Py_TYPE(x)->tp_call != NULL`: one read of a slot on the object's type, with no
attribute lookup. The slot is filled when a class or one of its bases defines
`__call__`, and updated when `__call__` is later assigned to or deleted from the
class. The function is the same in the v3.10.19, v3.11.14, v3.12.12, v3.13.11
and v3.14.2 tags, so no version is treated apart.

Measurement scope:

* no attribute lookup: counting `__getattribute__` and `__getattr__` on the
  object's class and on a metaclass record no calls during callable();
* the slot follows the class, not the instance: a `__call__` set on an instance
  is ignored, one assigned to the class after creation counts, deleting it
  clears it, and one inherited from a base counts;
* depth: callable() on an instance of a class 1,001 levels below the base that
  defines `__call__`, against an instance of that base, 200,000 calls each,
  measured x1.0 on the pinned interpreter (aarch64, CPython 3.14). The test
  accepts below x3; walking the MRO by name would predict about x1,000;
* space: tracemalloc's traced peak for a warmed callable() call is zero;
* a True result does not promise a successful call: a class with
  `__call__ = None` is callable and calling it raises TypeError, and so does
  calling len() with no argument;
* every class is callable, including built-in types and a class whose metaclass
  sets `__call__ = None`;
* every stated example value, and every fenced block runs in a subprocess;
  the blocks that print have their output compared with the page's comments.

Not settled here:

* O(1) is a source-only bound beyond the depth measurement: the check is the
  single slot read above.
* The vs isinstance() block makes no cost claim beyond O(1) for this input; the
  cost of isinstance() belongs to its own page.
* The Best Practices lists are advice with no measurable claim attached.
* The Version Notes entries about Python 2 and 3.0-3.1 concern versions this
  project does not run.
* Not varied: the number of attributes on the object or class, and C types
  other than the built-ins the examples name.
"""

from __future__ import annotations

import functools
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

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "callable.md"
EXPECTED_BLOCKS = 20

DEPTH = 1_000
CALLS = 200_000


def best_time(func: Callable[[], Any], repeats: int = 7) -> float:
    """The fastest of several runs, the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return min(times)


def traced_peak(func: Callable[[], Any]) -> int:
    """Peak bytes tracemalloc sees while `func` runs, after one warm-up call."""
    func()
    tracemalloc.start()
    try:
        func()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak


class WithCall:
    def __call__(self) -> str:
        return "called"


class TestNoAttributeLookup:
    """Row: Check callable status - reads the call slot on type(obj); no
    attribute lookup."""

    def test_getattribute_and_getattr_are_never_called(self) -> None:
        lookups: list[str] = []

        class Meta(type):
            def __getattribute__(cls, name: str) -> Any:
                lookups.append(f"meta:{name}")
                return super().__getattribute__(name)

        class Counting(metaclass=Meta):
            def __getattribute__(self, name: str) -> Any:
                lookups.append(name)
                return super().__getattribute__(name)

            def __getattr__(self, name: str) -> Any:
                lookups.append(f"missing:{name}")
                raise AttributeError(name)

        obj = Counting()
        lookups.clear()

        assert not callable(obj)
        assert callable(Counting)
        assert lookups == []

    @pytest.mark.serial
    def test_a_call_allocates_nothing(self) -> None:
        obj = WithCall()

        assert traced_peak(lambda: callable(obj)) == 0

    @pytest.mark.timing
    def test_cost_does_not_grow_with_hierarchy_depth(self) -> None:
        cls: type = WithCall
        for level in range(DEPTH):
            cls = type(f"Level{level}", (cls,), {})
        deep, shallow = cls(), WithCall()
        assert len(type(deep).__mro__) > DEPTH

        def calls(obj: object) -> None:
            for _ in range(CALLS):
                callable(obj)

        calls(deep)  # warm up
        ratio = best_time(lambda: calls(deep)) / best_time(lambda: calls(shallow))

        assert ratio < 3, f"x{ratio:.2f} for x{DEPTH} in MRO depth"


class TestTheSlotFollowsTheClass:
    """Row: Object with `__call__` - it must be defined on the class or a
    base; one set on the instance is ignored."""

    def test_an_instance_attribute_is_ignored(self) -> None:
        class Plain:
            pass

        obj = Plain()
        obj.__call__ = lambda: "instance"  # type: ignore[attr-defined]

        assert hasattr(obj, "__call__")  # noqa: B004 - the contrast under test
        assert not callable(obj)

    def test_assigning_and_deleting_on_the_class_updates_the_answer(self) -> None:
        class Plain:
            pass

        obj = Plain()
        assert not callable(obj)

        Plain.__call__ = lambda self: "class"  # type: ignore[attr-defined]
        assert callable(obj)

        del Plain.__call__  # type: ignore[attr-defined]
        assert not callable(obj)

    def test_inherited_from_a_base(self) -> None:
        class Child(WithCall):
            pass

        assert callable(Child())

    def test_changing_a_base_updates_existing_subclass_instances(self) -> None:
        class Base:
            pass

        class Child(Base):
            pass

        obj = Child()
        Base.__call__ = lambda self: "base"  # type: ignore[attr-defined]
        assert callable(obj)

        del Base.__call__  # type: ignore[attr-defined]
        assert not callable(obj)


class TestTrueDoesNotPromiseASuccessfulCall:
    """A True Result Does Not Promise a Successful Call: callable() only says
    the slot is filled."""

    def test_call_set_to_none(self) -> None:
        class Broken:
            __call__ = None

        assert callable(Broken())
        with pytest.raises(TypeError, match="not callable"):
            Broken()()  # type: ignore[misc]

    def test_wrong_arguments(self) -> None:
        assert callable(len)
        with pytest.raises(TypeError):
            len()  # type: ignore[call-arg]


class TestEveryClassIsCallable:
    """Row: Built-in types - every class is callable: its metaclass fills the
    slot."""

    @pytest.mark.parametrize("cls", [int, str, list, dict, type, object, WithCall])
    def test_classes_are_callable(self, cls: type) -> None:
        assert callable(cls)

    def test_even_when_the_metaclass_sets_call_to_none(self) -> None:
        class Meta(type):
            __call__ = None  # type: ignore[assignment]

        class Odd(metaclass=Meta):
            pass

        assert callable(Odd)


class TestStatedExampleValues:
    """The values the page's comments give, checked rather than trusted."""

    def test_basic_usage(self) -> None:
        def my_function() -> None:
            pass

        for obj in [my_function, len, "hi".upper, str.split, print, lambda x: x]:
            assert callable(obj)
        for obj in [42, "string", [1, 2, 3], {"key": "value"}, None]:
            assert not callable(obj)
        assert type("hi".upper).__name__ == "builtin_function_or_method"
        assert type(str.split).__name__ == "method_descriptor"

    def test_edge_cases(self) -> None:
        def generator() -> Any:
            yield 1

        class Example:
            @classmethod
            def class_method(cls) -> str:
                return "class"

            @staticmethod
            def static_method() -> str:
                return "static"

            def instance_method(self) -> str:
                return "instance"

        add_five = functools.partial(lambda x, y: x + y, 5)
        assert callable(add_five)
        assert add_five(10) == 15
        assert callable(generator)
        assert not callable(generator())
        assert callable(Example.class_method)
        assert callable(Example.static_method)
        assert callable(Example.instance_method)
        assert not callable(Example())

    def test_batch_processing(self) -> None:
        items: list[Any] = [42, lambda: 1, "str", len, [1, 2]]

        assert [x for x in items if callable(x)] == [items[1], len]


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

    @pytest.mark.parametrize(
        ("marker", "expected"),
        [
            ("def register_callback", ["callback must be callable, got <class 'int'>"]),
            ("def lazy_value", ["static: 100", "dynamic: 499500"]),
            ("class EventManager", ["Event: click"]),
        ],
    )
    def test_printed_output_matches_the_comments(
        self, tmp_path: pathlib.Path, marker: str, expected: list[str]
    ) -> None:
        block = next(source for _, source in _blocks() if marker in source)

        result = _run(block, tmp_path)

        assert result.returncode == 0, result.stderr
        assert result.stdout.splitlines() == expected

    @pytest.mark.parametrize(
        ("marker", "check"),
        [
            ("callable(obj)              # True (has __call__)", "assert obj() == 'called'"),
            ("def execute_if_callable", "assert (result, value) == (3, 42)"),
            ("def lazy_value", "assert (value1, value2) == (42, 42)"),
            ("def compose", "assert result == 100"),
            ('return "I was called"', "assert result == 'I was called'"),
        ],
    )
    def test_stated_values_hold_in_the_block(
        self, tmp_path: pathlib.Path, marker: str, check: str
    ) -> None:
        """The values the blocks state in comments, asserted after each block runs."""
        matching = [source for _, source in _blocks() if marker in source]
        assert len(matching) == 1, f"{len(matching)} blocks contain {marker!r}"

        result = _run(matching[0] + "\n" + check + "\n", tmp_path)

        assert result.returncode == 0, result.stderr

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        block = next(source for _, source in _blocks() if "class Plain:" in source)
        broken = block.replace("assert not callable(obj)", "assert callable(obj)", 1)
        assert broken != block, "the mutation did not change the block"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "AssertionError" in result.stderr
