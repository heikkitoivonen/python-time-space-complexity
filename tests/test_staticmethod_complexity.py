"""Tests for docs/builtins/staticmethod.md.

staticmethod is PyStaticMethod_Type in Objects/funcobject.c. sm_init stores
the callable without calling it and copies `__module__`, `__name__`,
`__qualname__` and `__doc__` into the wrapper's own `__dict__` through
functools_wraps; it takes exactly one positional argument and no keywords.
sm_descr_get returns the stored object itself for both a class and an
instance access, and sm_call forwards a call to it. `__func__` and
`__wrapped__` are members reading the same stored object. These paths do the
same work in the v3.11.14, v3.12.12, v3.13.11, v3.14.2 and v3.15.0rc3 tags;
v3.11.14 to v3.13.11 also copy `__annotations__` when the wrapper is built,
and v3.14.2 on read it from the function on first access.

Most rows are settled by observation: identity, a call counter and the
instance `__dict__`. Only the claim that an inherited static method's lookup
does not grow with the MRO needs a stopwatch.

Measurement scope:

* building a wrapper calls nothing; `__func__` and `__wrapped__` are the
  wrapped function; `__module__`, `__name__`, `__qualname__` and `__doc__`
  are copied into the wrapper's `__dict__`; a non-callable such as 42 is
  accepted and returned by an access; zero or two arguments, a keyword in
  place of the function, or a keyword beside it raise TypeError.
* `Class.method` and `obj.method` are the wrapped function itself, the same
  object on every access, where an ordinary method gives a new bound method
  each time. Calling the wrapper, the class attribute or the instance
  attribute calls the function once with exactly the positional and keyword
  arguments given.
* an instance `__dict__` entry with the method's name is returned for that
  instance only; the class and other instances still see the function.
* timing: reading a static method defined on the root of a chain of 1,000
  classes costs under x3 reading it from a chain of 10, where a walk of the
  MRO predicts x100. Assigning to the leaf class before every read, which
  drops the cached lookup, makes 10x the depth cost more than x4.
* a static method that is also abstract is listed in `__abstractmethods__`.
* every fenced block runs in its own subprocess and asserts its own results,
  and a mutated assertion in one is asserted to fail.

Not settled here:

* What the wrapped function costs is the caller's; the tests hold it at O(1).
* On 3.11 to 3.13 building the wrapper reads the function's
  `__annotations__`, which turns a function's annotation tuple into a dict
  once per function, O(a) in its a annotations. That is read from source,
  not timed; the page treats a function's annotations, and a call's
  arguments, as fixed-size.
* Not varied: static methods on classes with multiple inheritance, and
  staticmethod subclasses.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "staticmethod.md"
EXPECTED_BLOCKS = 6


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 10_000) -> float:
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


def chain(depth: int) -> type:
    """A single-inheritance chain whose MRO has `depth` classes, object
    included, with a static method on the root."""

    class Root:
        @staticmethod
        def found() -> int:
            return 1

    leaf: type = Root
    for index in range(depth - 2):
        leaf = type(f"Level{index}", (leaf,), {})
    assert len(leaf.__mro__) == depth
    return leaf


class TestBuildingAStaticMethod:
    """`staticmethod(function)` is O(1): it stores the object without calling
    it and copies the function's name and docstring."""

    def test_building_calls_nothing_and_keeps_the_function(self) -> None:
        calls: list[tuple[Any, ...]] = []

        def helper(*args: Any) -> str:
            """Help."""
            calls.append(args)
            return "done"

        wrapper = staticmethod(helper)

        assert calls == []
        assert wrapper.__func__ is helper
        assert wrapper.__wrapped__ is helper  # type: ignore[attr-defined]

    def test_the_name_and_docstring_are_copied(self) -> None:
        def helper() -> None:
            """Help."""

        wrapper = staticmethod(helper)
        copied = vars(wrapper)

        assert copied["__name__"] == "helper"
        assert copied["__qualname__"] == helper.__qualname__
        assert copied["__module__"] == __name__
        assert copied["__doc__"] == "Help."

    def test_any_object_is_accepted(self) -> None:
        class Holder:
            value = staticmethod(42)  # type: ignore[arg-type]

        assert Holder.value == 42
        assert Holder().value == 42

    @pytest.mark.parametrize(
        ("args", "kwargs"),
        [((), {}), ((len, len), {}), ((), {"function": len}), ((len,), {"unexpected": True})],
        ids=["none", "two", "keyword", "extra-keyword"],
    )
    def test_exactly_one_positional_argument(
        self, args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> None:
        with pytest.raises(TypeError):
            staticmethod(*args, **kwargs)


class TestAccessReturnsTheFunction:
    """`Class.method` and `obj.method` are O(1) and return the wrapped
    function itself; no bound object is created, and each call passes only
    the arguments given."""

    def test_class_and_instance_access_give_the_same_object(self) -> None:
        def helper(x: int) -> int:
            return x

        class Host:
            method = staticmethod(helper)

            def bound(self) -> None:
                pass

        host = Host()
        assert Host.method is helper
        assert host.method is helper
        assert host.method is host.method
        assert host.bound is not host.bound, "an ordinary method binds on every access"

    def test_each_call_passes_only_its_arguments(self) -> None:
        calls: list[tuple[Any, ...]] = []

        def record(*args: Any, **kwargs: Any) -> None:
            calls.append((args, kwargs))

        wrapper = staticmethod(record)

        class Host:
            method = wrapper

        Host.method(1)
        Host().method(2, key="a")
        wrapper(3, key="b")
        assert calls == [((1,), {}), ((2,), {"key": "a"}), ((3,), {"key": "b"})]


class TestInstanceAttributesShadow:
    """A static method is a non-data descriptor, so an instance `__dict__`
    entry of the same name wins for that instance."""

    def test_an_instance_entry_shadows_for_that_instance_only(self) -> None:
        class Host:
            @staticmethod
            def greet() -> str:
                return "hello"

        custom = Host()
        custom.greet = lambda: "hi"  # type: ignore[method-assign]

        assert custom.greet() == "hi"
        assert Host().greet() == "hello"
        assert Host.greet() == "hello"


class TestInheritedLookup:
    """An inherited static method is found by the cached class-side lookup,
    so an access does not grow with the MRO; dropping the cache makes the next
    lookup walk it, O(d)."""

    @pytest.mark.timing
    def test_a_cached_lookup_does_not_grow_with_depth(self) -> None:
        timings: list[float] = []
        for depth in (10, 1_000):
            obj = chain(depth)()
            assert obj.found() == 1
            timings.append(best_ns(lambda obj=obj: obj.found))

        ratio = timings[1] / timings[0]
        assert ratio < 3, (
            f"reading an inherited static method through an MRO of 1,000 cost x{ratio:.2f} "
            f"one of 10 ({timings[0]:.0f}ns to {timings[1]:.0f}ns); a walk of the MRO "
            "predicts x100"
        )

    @pytest.mark.timing
    def test_an_uncached_lookup_walks_the_mro(self) -> None:
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


class TestAbstractStaticMethods:
    """`abstractmethod` under `staticmethod` keeps the class abstract."""

    def test_the_method_is_listed_as_abstract(self) -> None:
        class Parser(ABC):
            @staticmethod
            @abstractmethod
            def parse(text: str) -> list[str]: ...

        assert Parser.__abstractmethods__ == frozenset({"parse"})
        with pytest.raises(TypeError, match="abstract"):
            Parser()  # type: ignore[abstract]


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
        line, source = next((n, s) for n, s in _blocks() if "is Vector  # Ignores" in s)
        mutated = source.replace("is Vector  # Ignores", "is Velocity  # Ignores", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
