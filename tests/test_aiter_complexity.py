"""Tests for docs/builtins/aiter.md.

aiter() is builtin_aiter in Python/bltinmodule.c, which is PyObject_GetAIter in
Objects/abstract.c: it reads the argument type's ``am_aiter`` slot (TypeError
when there is none), calls it once, and checks that the result's type has an
``am_anext`` slot (TypeError when it does not). It builds nothing of its own.
The function is the same in effect from 3.10 to 3.14; the only change between
the released branches is a Py_SETREF cleanup in 3.12. An async generator's
``__aiter__`` is PyObject_SelfIter, so it returns the generator itself.

Observation settles every row, with no stopwatch:

* ``aiter(agen) is agen``, the generator's body has run zero statements
  afterwards, and tracemalloc attributes no bytes to the call;
* a counting ``__aiter__`` is entered exactly once and its result comes back
  by identity, and a plain ``def __anext__`` that counts its own call is
  called zero times;
* a list, an int, and an object whose ``__aiter__`` returns something without
  ``__anext__`` raise TypeError from the call itself - the last after its
  ``__aiter__`` has run once;
* ``async for`` enters a counting ``__aiter__`` exactly once, as aiter() does;
* ``__anext__()`` on the result of aiter() returns an awaitable, not the item,
  where next() on the result of iter() returns the item.

Not varied: the cost of a custom ``__aiter__`` body (the page prices aiter()
as O(1) plus that one call, and the tests only count the call), and C-implemented
async iterables other than the async generator.
"""

from __future__ import annotations

import asyncio
import inspect
import pathlib
import re
import subprocess
import sys
import textwrap
import tracemalloc
from collections.abc import AsyncGenerator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "aiter.md"
EXPECTED_BLOCKS = 4


class Counting:
    """An async iterable whose __aiter__ and its iterator's __anext__ count their calls."""

    def __init__(self) -> None:
        self.aiter_calls = 0
        self.anext_calls = 0

    def __aiter__(self) -> Counting:
        self.aiter_calls += 1
        return self

    async def __anext__(self) -> int:
        self.anext_calls += 1
        if self.anext_calls > 3:
            raise StopAsyncIteration
        return self.anext_calls


class TestAiterDelegatesToDunderAiter:
    """Row: aiter() is O(1) plus one __aiter__() call, whose result it returns."""

    def test_dunder_aiter_is_called_exactly_once(self) -> None:
        counting = Counting()
        aiter(counting)
        assert counting.aiter_calls == 1

    def test_the_result_is_returned_by_identity(self) -> None:
        class Iterator:
            async def __anext__(self) -> int:
                raise StopAsyncIteration

        iterator = Iterator()

        class Iterable:
            def __aiter__(self) -> Iterator:
                return iterator

        assert aiter(Iterable()) is iterator

    def test_no_item_is_fetched(self) -> None:
        calls = 0

        class Eager:
            """A plain-def __anext__ counts the call itself, not only an awaited step."""

            def __aiter__(self) -> Eager:
                return self

            def __anext__(self) -> asyncio.Future[int]:
                nonlocal calls
                calls += 1
                raise AssertionError("aiter() asked for an item")

        aiter(Eager())
        assert calls == 0


class TestAiterRejectsWhatIsNotAsyncIterable:
    """Row: TypeError if the argument has no __aiter__() or the result has no __anext__()."""

    @pytest.mark.parametrize("value", [[1, 2, 3], 7], ids=["list", "int"])
    def test_a_plain_iterable_or_scalar_is_rejected(self, value: object) -> None:
        with pytest.raises(TypeError, match="is not an async iterable"):
            aiter(value)  # pyright: ignore[reportArgumentType, reportCallIssue]

    def test_a_result_without_dunder_anext_is_rejected_after_one_call(self) -> None:
        calls = 0

        class Broken:
            def __aiter__(self) -> object:
                nonlocal calls
                calls += 1
                return object()

        with pytest.raises(TypeError, match="returned not an async iterator of type 'object'"):
            aiter(Broken())  # pyright: ignore[reportArgumentType]
        assert calls == 1


class TestAnAsyncGeneratorIsItsOwnIterator:
    """Row: __aiter__() of an async generator is O(1) and returns the generator itself."""

    @staticmethod
    def started() -> tuple[AsyncGenerator[int, None], list[int]]:
        ran: list[int] = []

        async def agen() -> AsyncGenerator[int, None]:
            ran.append(1)
            yield 1

        return agen(), ran

    def test_aiter_returns_the_generator_itself(self) -> None:
        agen, _ = self.started()
        assert aiter(agen) is agen
        assert agen.__aiter__() is agen

    def test_the_body_does_not_run(self) -> None:
        agen, ran = self.started()
        aiter(agen)
        assert ran == []

    @pytest.mark.serial
    def test_allocates_nothing(self) -> None:
        agen, _ = self.started()
        aiter(agen)
        tracemalloc.start()
        try:
            aiter(agen)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        assert peak == 0


class TestAsyncForMakesTheSameCall:
    """Prose: aiter is implicit in async for - the loop calls __aiter__() once itself."""

    def test_async_for_calls_dunder_aiter_once(self) -> None:
        counting = Counting()

        async def main() -> list[int]:
            return [value async for value in counting]

        assert asyncio.run(main()) == [1, 2, 3]
        assert counting.aiter_calls == 1


class TestComparisonWithIter:
    """Prose: next() returns the item, an async iterator's step must be awaited."""

    def test_anext_returns_an_awaitable_not_the_item(self) -> None:
        async def agen() -> AsyncGenerator[int, None]:
            yield 1

        step: Any = aiter(agen()).__anext__()
        assert step != 1
        assert inspect.isawaitable(step)
        with pytest.raises(StopIteration) as stop:
            step.__await__().send(None)
        assert stop.value.value == 1

    def test_next_returns_the_item(self) -> None:
        def gen() -> Any:
            yield 1

        assert next(iter(gen())) == 1


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


EXPECTED_OUTPUT = [
    "0\n",
    "1\n2\n3\n",
    "Data from url1\nData from url2\nData from url3\n",
    "1\n1\n",
]
"""What each block prints, in page order, as its trailing comments state."""


class TestDocumentedExamples:
    """Every block runs and prints what its comments say."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_every_block_runs_and_prints_its_stated_output(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []

        for (line, source), expected in zip(_blocks(), EXPECTED_OUTPUT, strict=True):
            result = _run(source, tmp_path)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()}")
            elif result.stdout != expected:
                failures.append(f"{PAGE.name}:{line} printed {result.stdout!r}, not {expected!r}")

        assert not failures, "\n".join(failures)

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        iterable = next(source for _, source in _blocks() if "class AsyncIterable" in source)
        broken = iterable.replace("    def __aiter__(self):\n        return self\n", "", 1)
        assert broken != iterable, "the mutation did not remove the iterator's __aiter__"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "requires an object with __aiter__ method" in result.stderr
