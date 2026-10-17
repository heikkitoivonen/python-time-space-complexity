"""Tests for docs/builtins/notimplemented.md.

The page prices NotImplemented in special-method calls: the constant itself is
one object read and tested in O(1), and an operator that meets it makes at most
two calls, or three for an in-place operator, before it answers or raises.
Every row is settled by observation, with recording special methods, identity
checks and the exception raised; nothing is timed.

The dispatch is binary_op1 and binary_iop1 in Objects/abstract.c and
do_richcompare in Objects/object.c; their order of calls is the same in the
v3.11.14, v3.12.12, v3.13.11, v3.14.2 and v3.15.0rc3 tags. notimplemented_bool
in Objects/object.c warns with DeprecationWarning and returns 1 in v3.11.14,
v3.12.12 and v3.13.11, and raises TypeError from v3.14.2.

Measurement scope:

* `NotImplemented` is one object: `type(NotImplemented)()` returns it and the
  type is `types.NotImplementedType`.
* `bool(NotImplemented)` raises TypeError naming "boolean context" from 3.14,
  and returns True with a DeprecationWarning before; each branch is guarded on
  `sys.version_info`, and both were run on 3.11 to 3.15.
* binary operators: the recorded calls are `__add__` then the other type's
  `__radd__` when the first declines; `__add__` alone when both operands have
  one type and it declines, followed by TypeError; and the subclass's
  `__radd__` alone when the right operand subclasses the left's, overrides
  `__radd__` and answers.
* in-place operators: `__iadd__`, `__add__`, then the other type's `__radd__`,
  stopping at the first that answers, and TypeError naming "+=" when all
  decline.
* `==`: two `__eq__` calls on operands of one type, then `a is b`; `!=` with
  the default `__ne__` makes the same two `__eq__` calls and answers
  `a is not b`, and `a.__ne__(b)` itself returns NotImplemented; `<`: `__lt__` then the reflected `__gt__`, then TypeError,
  and the subclass's `__gt__` first when the right operand subclasses the
  left's, whether or not it overrides it; `==` likewise calls a strict
  subclass's `__eq__` first.
* other hooks: `operator.length_hint()` returns its default for a
  `__length_hint__` returning NotImplemented, and `issubclass()` against an
  ABC whose `__subclasshook__` returns it is True for a registered class and
  False for an unrelated one.
* outside dispatch: a `__getitem__` returning NotImplemented hands it back as
  the item, a `__hash__` returning it raises TypeError, and an `__exit__`
  returning it while an exception propagates raises TypeError from 3.14 and
  suppresses the exception before, with a DeprecationWarning; on a normal
  exit its return value is not read, on any version.
* raising NotImplementedError from `__add__` keeps the other operand's
  `__radd__` from being called.
* every fenced block runs in its own subprocess and asserts its own results,
  and a mutated assertion in one is asserted to fail.

Not settled here:

* The cost of each special method's body is the caller's; the tests hold each
  at O(1) and count calls, not time.
* Not varied: the operators beyond `+`, `+=`, `==`, `!=` and `<`. The other
  binary and in-place operators go through binary_op1 and binary_iop1, `**`
  and `**=` through ternary_op and ternary_iop, and the ordering operators
  through do_richcompare; that they make the same calls is read from source,
  not run for each one.
"""

from __future__ import annotations

import abc
import operator
import pathlib
import re
import subprocess
import sys
import textwrap
import types
import warnings
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "notimplemented.md"
EXPECTED_BLOCKS = 8


class TestTheConstant:
    """`NotImplemented` is one O(1) object, and `bool()` of it is version
    dependent: TypeError from 3.14, True with a DeprecationWarning before."""

    def test_the_type_returns_the_singleton(self) -> None:
        assert type(NotImplemented) is types.NotImplementedType
        assert type(NotImplemented)() is NotImplemented

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="version: TypeError from 3.14")
    def test_truth_value_raises(self) -> None:
        with pytest.raises(TypeError, match="boolean context"):
            bool(NotImplemented)

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="version: warns before 3.14")
    def test_truth_value_warns_and_is_true(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            assert bool(NotImplemented) is True
        assert [w.category for w in caught] == [DeprecationWarning]


def _recorder() -> tuple[list[str], type, type, type]:
    """Classes whose special methods record their calls and decline unless
    named otherwise."""
    calls: list[str] = []

    class Left:
        def __add__(self, other: Any) -> Any:
            calls.append("Left.__add__")
            return NotImplemented

        def __radd__(self, other: Any) -> Any:
            calls.append("Left.__radd__")
            return NotImplemented

        def __iadd__(self, other: Any) -> Any:
            calls.append("Left.__iadd__")
            return NotImplemented

        def __eq__(self, other: object) -> Any:
            calls.append("Left.__eq__")
            return NotImplemented

        def __lt__(self, other: Any) -> Any:
            calls.append("Left.__lt__")
            return NotImplemented

        def __gt__(self, other: Any) -> Any:
            calls.append("Left.__gt__")
            return NotImplemented

        __hash__ = object.__hash__

    class Sub(Left):
        def __radd__(self, other: Any) -> Any:
            calls.append("Sub.__radd__")
            return "sub"

        def __gt__(self, other: Any) -> Any:
            calls.append("Sub.__gt__")
            return NotImplemented

    class Other:
        def __radd__(self, other: Any) -> Any:
            calls.append("Other.__radd__")
            return "other"

    return calls, Left, Sub, Other


class TestBinaryDispatch:
    """`a + b` makes up to two calls: `a.__add__(b)`, then `b.__radd__(a)`
    only for a different type; a subclass overriding `__radd__` goes first."""

    def test_a_declined_add_reaches_the_other_type(self) -> None:
        calls, left, _, other = _recorder()
        assert left() + other() == "other"
        assert calls == ["Left.__add__", "Other.__radd__"]

    def test_one_type_gets_no_reflected_call(self) -> None:
        calls, left, _, _ = _recorder()
        with pytest.raises(TypeError, match="unsupported operand type"):
            _ = left() + left()
        assert calls == ["Left.__add__"]

    def test_a_subclass_overriding_radd_goes_first(self) -> None:
        calls, left, sub, _ = _recorder()
        assert left() + sub() == "sub"
        assert calls == ["Sub.__radd__"]


class TestInPlaceDispatch:
    """`a += b` makes up to three calls: `__iadd__`, `__add__`, `__radd__`."""

    def test_three_calls_then_the_answer(self) -> None:
        calls, left, _, other = _recorder()
        target: Any = left()
        target += other()
        assert target == "other"
        assert calls == ["Left.__iadd__", "Left.__add__", "Other.__radd__"]

    def test_all_declining_raises(self) -> None:
        calls, left, _, _ = _recorder()
        target: Any = left()
        with pytest.raises(TypeError, match=r"\+="):
            target += left()
        assert calls == ["Left.__iadd__", "Left.__add__"]


class TestComparisonDispatch:
    """`==` tries both `__eq__` methods, even for one type, then compares
    identity; `<` tries `__lt__` and the reflected `__gt__`, then raises."""

    def test_equality_falls_back_to_identity(self) -> None:
        calls, left, _, _ = _recorder()
        a, b = left(), left()
        assert (a == b) is False
        assert calls == ["Left.__eq__", "Left.__eq__"]
        assert (a == a) is True
        assert (a != b) is True
        assert (a != a) is False

    def test_ordering_raises_after_two_calls(self) -> None:
        calls, left, _, _ = _recorder()
        with pytest.raises(TypeError, match="'<' not supported"):
            _ = left() < left()
        assert calls == ["Left.__lt__", "Left.__gt__"]

    def test_inequality_calls_eq_twice(self) -> None:
        calls, left, _, _ = _recorder()
        a, b = left(), left()
        assert (a != b) is True
        assert calls == ["Left.__eq__", "Left.__eq__"]
        assert a.__ne__(b) is NotImplemented

    def test_a_subclass_overriding_the_reflection_goes_first(self) -> None:
        calls, left, sub, _ = _recorder()
        with pytest.raises(TypeError):
            _ = left() < sub()
        assert calls == ["Sub.__gt__", "Left.__lt__"]

    def test_a_strict_subclass_goes_first_without_overriding(self) -> None:
        calls, left, _, _ = _recorder()

        class Plain(left):
            pass

        with pytest.raises(TypeError):
            _ = left() < Plain()
        assert calls == ["Left.__gt__", "Left.__lt__"]

        calls.clear()

        class OwnEq(left):
            def __eq__(self, other: object) -> Any:
                calls.append("OwnEq.__eq__")
                return NotImplemented

            __hash__ = object.__hash__

        assert (left() == OwnEq()) is False
        assert calls == ["OwnEq.__eq__", "Left.__eq__"]


class TestOutsideDispatch:
    """Only operator dispatch reads NotImplemented as declining: elsewhere it is
    a value, a wrong return type, or a truth value."""

    def test_length_hint_falls_back_to_the_default(self) -> None:
        class NoHint:
            def __length_hint__(self) -> Any:
                return NotImplemented

        assert operator.length_hint(NoHint(), 10) == 10

    def test_subclasshook_defers_to_the_normal_check(self) -> None:
        class Hooked(abc.ABC):  # noqa: B024 - the hook is the subject, not abstract methods
            @classmethod
            def __subclasshook__(cls, subclass: type) -> Any:
                return NotImplemented

        class Registered:
            pass

        Hooked.register(Registered)
        assert issubclass(Registered, Hooked)
        assert not issubclass(int, Hooked)

    def test_getitem_returns_it_as_the_item(self) -> None:
        class Lookup:
            def __getitem__(self, key: object) -> Any:
                return NotImplemented

        assert Lookup()["key"] is NotImplemented

    def test_hash_rejects_it(self) -> None:
        class BadHash:
            def __hash__(self) -> Any:
                return NotImplemented

        with pytest.raises(TypeError, match="should return an integer"):
            hash(BadHash())

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="version: TypeError from 3.14")
    def test_exit_returning_it_raises(self) -> None:
        with pytest.raises(TypeError, match="boolean context"):
            with _ExitsWithNotImplemented():
                raise ValueError("inside")

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="version: truthy before 3.14")
    def test_exit_returning_it_suppresses(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with _ExitsWithNotImplemented():
                raise ValueError("inside")
        assert [w.category for w in caught] == [DeprecationWarning]

    def test_exit_returning_it_on_a_normal_exit_is_not_read(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            with _ExitsWithNotImplemented():
                pass

    def test_raising_not_implemented_error_stops_dispatch(self) -> None:
        reached: list[str] = []

        class Strict:
            def __add__(self, other: Any) -> Any:
                raise NotImplementedError

        class Accepting:
            def __radd__(self, other: Any) -> Any:
                reached.append("__radd__")
                return "handled"

        with pytest.raises(NotImplementedError):
            _ = Strict() + Accepting()
        assert reached == []


class _ExitsWithNotImplemented:
    def __enter__(self) -> _ExitsWithNotImplemented:
        return self

    def __exit__(self, *exc: object) -> Any:
        return NotImplemented


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
        [sys.executable, "-W", "error::SyntaxWarning", str(script)],
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
        line, source = next(
            (n, s) for n, s in _blocks() if 'assert calls == ["__eq__", "__eq__"]' in s
        )
        mutated = source.replace('calls == ["__eq__", "__eq__"]', 'calls == ["__eq__"]', 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
