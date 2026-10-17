"""Tests for docs/builtins/none.md.

`None` is the one instance of NoneType (Objects/object.c): `none_new` returns
it, `none_bool` returns 0, and from 3.12 `none_hash` returns a constant. Every
operation on None itself is O(1). Two rows depend on something else: `==`,
which NoneType leaves to the default comparison, so a user `__eq__` on the
other operand is called and can answer True; and a list scan for None, which
is linear in the list. Behaviour is settled by observation - identity, call
counting and exceptions - and the O(1) bounds by source, as listed below.

Measurement scope:

* `x is None` and `x is not None` call no method: a class whose `__eq__`
  records its calls and answers True is compared both ways, and the record
  stays empty. `x == None` and `None == x` each call it exactly once, with
  None as the argument, and return its answer; `None == None` is True.
* `bool(None)` is False; `0`, `""`, `[]` and `{}` are falsy and are not None.
* `type(None)` is `types.NoneType`, `type(None)()` is None, and calling it
  with an argument raises TypeError "takes no arguments". Assigning to None is
  a SyntaxError at compile time. A function without `return`, and one with a
  bare `return`, both return None.
* `hash(None)` equals itself across two calls; its value is not asserted.
* `None in seq` on a list stops at the first match: items with a counting
  `__eq__` placed before and after a None are compared only up to it.
  `list.count(None)` compares every item.
* a list default is shared between calls and a None default replaced inside
  the function is not; the page's Default Arguments block asserts both.
* every fenced block runs in its own subprocess and asserts its own results,
  and a mutated assertion in one is asserted to fail.

Not settled here:

* The O(1) of the singleton operations is read from Objects/object.c; it is
  not timed, since there is no size to vary.
* The cost of a user `__eq__` is the caller's; the tests hold it at O(1).
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap
import types
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "none.md"
EXPECTED_BLOCKS = 8


class RecordingEq:
    """Answers True to every `==` and records each call."""

    def __init__(self, calls: list[object]) -> None:
        self.calls = calls

    def __eq__(self, other: object) -> bool:
        self.calls.append(other)
        return True

    __hash__ = object.__hash__


class TestIdentityCallsNothing:
    """`x is None` compares identity and never calls a method on `x`;
    `x == None` and `None == x` call `x.__eq__`, which can answer True."""

    def test_is_calls_no_method(self) -> None:
        calls: list[object] = []
        value = RecordingEq(calls)

        assert value is not None
        assert not (value is None)  # noqa: E714 - the `not (... is ...)` spelling is the subject
        assert calls == []

    def test_eq_calls_the_other_operands_eq_once_each_way(self) -> None:
        calls: list[object] = []
        value = RecordingEq(calls)

        assert value == None  # noqa: E711 - the == comparison is the subject
        assert calls == [None]
        assert None == value  # noqa: E711 - the reflected comparison is the subject
        assert calls == [None, None]

    def test_none_equals_itself(self) -> None:
        none: Any = None
        assert none == None  # noqa: E711 - the == comparison is the subject


class TestTruthiness:
    """`bool(None)` is False, and so is every empty value, which is not None."""

    def test_none_is_falsy(self) -> None:
        assert bool(None) is False

    @pytest.mark.parametrize("empty", [0, "", [], {}], ids=["zero", "str", "list", "dict"])
    def test_empty_values_are_falsy_but_not_none(self, empty: object) -> None:
        assert not empty
        assert empty is not None


class TestSingleton:
    """`type(None)()` returns the one `None`; NoneType takes no arguments;
    the name cannot be rebound; functions without a value return it."""

    def test_the_type_is_types_none_type(self) -> None:
        assert type(None) is types.NoneType

    def test_calling_the_type_returns_none(self) -> None:
        assert type(None)() is None

    def test_the_type_takes_no_arguments(self) -> None:
        with pytest.raises(TypeError, match="takes no arguments"):
            type(None)(1)  # pyright: ignore[reportCallIssue]

    def test_none_cannot_be_assigned(self) -> None:
        with pytest.raises(SyntaxError, match="cannot assign to None"):
            compile("None = 1", "<test>", "exec")

    def test_functions_without_a_value_return_none(self) -> None:
        def no_return() -> None:
            pass

        def bare_return() -> None:
            return

        assert no_return() is None
        assert bare_return() is None

    def test_the_hash_is_stable(self) -> None:
        assert hash(None) == hash(None)


class TestScanningForNone:
    """`None in seq` on a list stops at the first match; `count` compares
    every item."""

    class Counted:
        def __init__(self, calls: list[int], tag: int) -> None:
            self.calls = calls
            self.tag = tag

        def __eq__(self, other: object) -> bool:
            self.calls.append(self.tag)
            return False

        __hash__ = object.__hash__

    def test_in_stops_at_the_first_none(self) -> None:
        calls: list[int] = []
        items = [self.Counted(calls, 0), self.Counted(calls, 1), None, self.Counted(calls, 3)]

        assert None in items
        assert calls == [0, 1]

    def test_count_compares_every_item(self) -> None:
        calls: list[int] = []
        items = [self.Counted(calls, 0), None, self.Counted(calls, 2), None]

        assert items.count(None) == 2
        assert calls == [0, 2]


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
        line, source = next((n, s) for n, s in _blocks() if "eq_calls == [None, None]" in s)
        mutated = source.replace("eq_calls == [None, None]", "eq_calls == []", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
