"""Tests for docs/builtins/ellipsis.md.

`Ellipsis` is the static `_Py_EllipsisObject` in Objects/sliceobject.c, the one
instance of PyEllipsis_Type. Every row of the page's table acts on that object,
so its O(1) bounds hold by construction: there is no size variable to grow, and
no timing test is needed. What the tests settle is what the rows and the prose
say beyond the bound - which object an operation returns, which methods a
comparison calls, what a subscript receives - by identity checks and call
counters, which need no tolerance.

Measurement scope:

* one object: `...` is `Ellipsis`, `type(...)` is `types.EllipsisType`, and
  `type(...)()`, `copy.copy()`, `copy.deepcopy()` and a pickle round trip at
  every protocol return the singleton itself; `type(...)` with an argument,
  `object.__new__(type(...))` and a subclass of the type all raise TypeError;
* comparison: `x is ...` calls no `__eq__` on a counting operand, `x == ...`
  calls it once; the type defines no `__eq__` of its own, so an operand whose
  `__eq__` always answers True makes `x == ...` True while `x is ...` stays
  False; `<` raises TypeError; `hash(...)` is stable and `...` works as a dict
  key and a set member;
* `bool(...)` is True, `repr()` and `str()` are 'Ellipsis';
* subscripting: a recording `__getitem__` receives the singleton itself for
  `obj[...]` and the tuple `(1, Ellipsis)` for `obj[1, ...]`; list, tuple, str,
  bytes and range raise TypeError;
* placeholder bodies: a function whose body is `...` returns None and loads no
  Ellipsis constant, matching a `pass` body; an ABC with an abstract `...`
  method cannot be instantiated, and a subclass calling it through `super()`
  gets None;
* type hints: `get_args()` keeps Ellipsis in `tuple[int, ...]` and
  `Callable[..., int]`;
* operator fallback, between two unrelated classes: a binary method returning
  `...` is the result of the expression, while one returning NotImplemented
  makes Python call the other operand's reflected method;
* every fenced Python block runs in its own subprocess with warnings as errors,
  and a mutated assertion in one of them is asserted to fail. The sentinel
  block asserts that its `get()` raises KeyError both with no default and with
  an explicit `...`, which is why the sentinel must be reserved.

Not settled here:

* What `...` means in a type hint ("any number of the same type", "arguments
  not checked") is the typing specification's definition; the tests check only
  that the hint keeps Ellipsis as an argument.
* The cost of the `__getitem__` or `__eq__` that receives `...` is that code's;
  the page names it once and the tests use O(1) receivers.
* The O(r), O(n), O(1) average and O(1) amortized annotations in the
  examples are the bounds of the list, tuple and dict operations they
  annotate, covered by those types' own tests; the examples here pin results
  only.
* `types.EllipsisType` exists from Python 3.10, below the supported range; the
  tests observe it on the running interpreter only.
"""

from __future__ import annotations

import copy
import dis
import pathlib
import pickle
import re
import subprocess
import sys
import textwrap
import types
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, get_args

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "ellipsis.md"
EXPECTED_BLOCKS = 6


class CountingEq:
    """An operand whose `__eq__` calls are counted."""

    calls = 0

    def __eq__(self, other: object) -> bool:
        CountingEq.calls += 1
        return False

    __hash__ = object.__hash__


class Recorder:
    """A subscriptable that records the key it receives."""

    def __init__(self) -> None:
        self.keys: list[object] = []

    def __getitem__(self, key: object) -> object:
        self.keys.append(key)
        return key


class TestOneObject:
    """Reference rows `Ellipsis`, `...`, `type(...)()` and copying: every
    route returns the existing singleton, and none builds another."""

    def test_both_spellings_name_one_object(self) -> None:
        assert ... is Ellipsis
        assert type(...) is types.EllipsisType

    def test_calling_the_type_returns_the_singleton(self) -> None:
        assert type(...)() is ...

    def test_calling_the_type_with_an_argument_raises(self) -> None:
        with pytest.raises(TypeError, match="takes no arguments"):
            ellipsis_type: Any = type(...)
            ellipsis_type(1)

    def test_object_new_cannot_build_a_second_instance(self) -> None:
        with pytest.raises(TypeError):
            object.__new__(types.EllipsisType)

    def test_the_type_cannot_be_subclassed(self) -> None:
        with pytest.raises(TypeError, match="not an acceptable base type"):
            type("MyEllipsis", (types.EllipsisType,), {})

    def test_copy_and_deepcopy_return_the_singleton(self) -> None:
        assert copy.copy(...) is ...
        assert copy.deepcopy(...) is ...
        assert copy.deepcopy([...])[0] is ...

    @pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
    def test_a_pickle_round_trip_returns_the_singleton(self, protocol: int) -> None:
        assert pickle.loads(pickle.dumps(..., protocol=protocol)) is ...


class TestComparison:
    """Rows `x is ...` and `x == ...`, and Comparing With Ellipsis: identity
    calls nothing, equality asks the other operand."""

    def test_is_calls_no_eq(self) -> None:
        CountingEq.calls = 0
        value = CountingEq()

        assert (value is ...) is False

        assert CountingEq.calls == 0

    def test_eq_asks_the_other_operand(self) -> None:
        CountingEq.calls = 0
        value = CountingEq()

        assert (value == ...) is False

        assert CountingEq.calls == 1

    def test_the_type_defines_no_eq_of_its_own(self) -> None:
        assert "__eq__" not in vars(types.EllipsisType)
        assert types.EllipsisType.__eq__ is object.__eq__

    def test_an_operand_eq_can_answer_true(self) -> None:
        class EqualsEverything:
            def __eq__(self, other: object) -> bool:
                return True

            __hash__ = object.__hash__

        value = EqualsEverything()
        assert (value == ...) is True
        assert (... == value) is True
        assert (value is ...) is False

    def test_equality_with_itself_and_none(self) -> None:
        assert (... == ...) is True
        none: Any = None
        assert (... == none) is False

    def test_ordering_is_not_defined(self) -> None:
        other: Any = ...
        with pytest.raises(TypeError, match="'<' not supported"):
            _ = ... < other

    def test_hash_is_stable_and_works_as_a_key(self) -> None:
        assert hash(...) == hash(Ellipsis)
        mapping = {1: "a", ...: "rest"}
        assert mapping[...] == "rest"
        assert ... in {1, ...}


class TestBoolReprStr:
    """Rows `bool(...)` and `repr(...)`, `str(...)`."""

    def test_bool_is_true(self) -> None:
        assert bool(...) is True

    def test_repr_and_str(self) -> None:
        assert repr(...) == "Ellipsis"
        assert str(...) == "Ellipsis"


class TestSubscripting:
    """Row `obj[...]` and Subscripting With Ellipsis: the receiving
    `__getitem__` gets the singleton itself, and the listed built-ins reject it."""

    def test_getitem_receives_the_singleton(self) -> None:
        recorder = Recorder()

        recorder[...]

        assert recorder.keys == [...]
        assert recorder.keys[0] is ...

    def test_a_tuple_subscript_carries_the_singleton(self) -> None:
        recorder = Recorder()

        recorder[1, ...]

        assert recorder.keys == [(1, Ellipsis)]
        key: Any = recorder.keys[0]
        assert key[1] is ...

    @pytest.mark.parametrize("sequence", [[1], (1,), "a", b"a", range(3)], ids=type)
    def test_builtin_sequences_reject_ellipsis(self, sequence: Any) -> None:
        with pytest.raises(TypeError, match="indices must be integers"):
            sequence[...]


class TestPlaceholderBodies:
    """Placeholder Bodies: a `...` body is a no-op that returns None, and an
    abstract method's `...` body returns None when a subclass calls it through
    `super()`."""

    def test_an_ellipsis_body_returns_none_like_pass(self) -> None:
        def with_ellipsis() -> None: ...

        def with_pass() -> None:
            pass

        assert with_ellipsis() is None
        assert with_pass() is None

    def test_an_ellipsis_body_loads_no_ellipsis(self) -> None:
        def with_ellipsis() -> None: ...

        loaded = [i.argval for i in dis.get_instructions(with_ellipsis)]
        assert not any(value is ... for value in loaded)

    def test_an_abstract_method_with_an_ellipsis_body(self) -> None:
        class DataStore(ABC):
            @abstractmethod
            def save(self, data: object) -> None: ...

        class MemoryStore(DataStore):
            def save(self, data: object) -> None:
                self.result = super().save(data)  # pyright: ignore[reportAbstractUsage]

        with pytest.raises(TypeError, match="abstract"):
            DataStore()  # pyright: ignore[reportAbstractUsage]
        store = MemoryStore()
        store.save("x")
        assert store.result is None


class TestTypeHints:
    """Type Hints: the hint keeps Ellipsis as an argument."""

    def test_variable_length_tuple(self) -> None:
        assert get_args(tuple[int, ...]) == (int, Ellipsis)
        assert get_args(tuple[int, ...])[1] is ...
        assert get_args(tuple[int, int]) == (int, int)

    def test_callable_with_unchecked_arguments(self) -> None:
        args = get_args(Callable[..., int])
        assert args == (Ellipsis, int)
        assert args[0] is ...


class TestOperatorFallback:
    """Avoid list: with two unrelated operand types, a method that returns `...`
    has produced the result, while NotImplemented makes Python try the other
    operand's reflected method."""

    class Reflected:
        def __radd__(self, other: object) -> str:
            return "radd"

    def test_returning_ellipsis_is_the_result(self) -> None:
        class ReturnsEllipsis:
            def __add__(self, other: object) -> Any:
                return ...

        assert (ReturnsEllipsis() + self.Reflected()) is ...

    def test_returning_notimplemented_tries_the_reflected_method(self) -> None:
        class ReturnsNotImplemented:
            def __add__(self, other: object) -> Any:
                return NotImplemented

        assert (ReturnsNotImplemented() + self.Reflected()) == "radd"


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
        [sys.executable, "-W", "error", script.name],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Every block runs with warnings as errors, under the interpreter running
    the tests."""

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
        block = next(source for _, source in _blocks() if "class Grid" in source)
        broken = block.replace("assert grid[..., 0] == [1, 4]", "assert grid[..., 0] == [1, 2]", 1)
        assert broken != block, "the mutation did not change the column assertion"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "AssertionError" in result.stderr
