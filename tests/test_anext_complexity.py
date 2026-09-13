"""Tests for docs/builtins/anext.md.

anext() is builtin_anext_impl in Python/bltinmodule.c, the same in effect
from 3.10 to 3.14: it reads the ``am_anext`` slot of the argument's type (TypeError
before anything else when the slot is missing), calls it once, and returns
the awaitable that comes back. For an async generator that awaitable is an
``async_generator_asend``; for an ``async def __anext__`` it is a coroutine
object; either way none of the body has run yet. With a default the awaitable
is wrapped in an ``anext_awaitable`` (Objects/iterobject.c) whose
``__next__``, ``send``, ``throw`` and ``close`` each call
anextawaitable_getiter and then forward one step. getiter runs
_PyCoro_GetAwaitableIter on the wrapped object: a coroutine or asend object is
returned as it is (a coroutine then gets a fresh ``coroutine_wrapper`` around
the same frame, so it resumes where it stopped), where any other awaitable
has its ``__await__()`` called again, which for a generator-function
``__await__`` starts a new generator from its first line. A
StopAsyncIteration coming out of the forwarded step is replaced with
StopIteration(default); every other exception passes through.

Observation settles every row:

* after anext() returns, an async generator's body has run zero statements
  and a counting ``async def __anext__`` has been entered zero times, where a
  plain ``def __anext__`` has run exactly once; the first await runs an
  ``async def`` body up to its next ``yield`` and no further, and each later
  await advances it by one item;
* a list, a list iterator and an int raise TypeError from the call itself,
  before any await;
* the awaitables anext() returns are the same size for a started generator
  whose frame holds a 10-element list as for one holding 100,000, and
  building both allocates under 1 KiB;
* the caller of ``await anext(it)`` and of ``await anext(it, default)`` is
  suspended exactly as many times as the ``__anext__`` step awaits inside
  itself, at 3 and at 1,000 awaits, for an ``async def __anext__`` and for an
  async generator alike, and the traced peak of one such await stays under
  1 KiB from 10 suspensions to 10,000 with and without a default;
* one await deep in a 100,000-item generator allocates under 1 KiB both after
  10 items and after 50,000;
* on exhaustion the default comes back by identity, before exhaustion the
  item does and the default is untouched, ``__anext__`` is still called once
  per attempt on an exhausted iterator but an exhausted generator's body does
  not run again, and a ValueError raised inside ``__anext__`` propagates
  through the default form;
* a class whose ``__await__`` is a generator function that suspends 3 times
  completes in 3 steps and one ``__await__`` call without a default, where
  with a default 20 steps make 20 ``__await__`` calls and it has still not
  completed; one that suspends only on its first ``__await__`` call completes
  in one step and two calls.

Elapsed time settles the wrapper's per-suspension cost on the pinned
interpreter (aarch64, CPython 3.14): an ``async def __anext__`` that awaits
10,000 times costs x80 what one awaiting 100 times does without a default and
x105 with one, against x10,000 for work that grew with each suspension.

Not varied: the cost of the item itself (every step here yields a small
int), the work a plain ``def __anext__`` does before returning its awaitable
(the page keeps it outside the call's O(1) and the test only counts it), the event loop (the suspension counts are taken by driving the
coroutine with ``send(None)`` directly, so no loop scheduling is measured),
and a C-implemented async iterator other than an async generator.
"""

import functools
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import AsyncGenerator, Awaitable, Callable, Coroutine, Generator
from typing import Any, cast

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "anext.md"
EXPECTED_BLOCKS = 5


class Suspend:
    """An awaitable that suspends its awaiter exactly once."""

    def __await__(self) -> Generator[None, None, None]:
        yield


class CoroutineIterator:
    """An ``async def __anext__`` that awaits ``steps`` times per item."""

    def __init__(self, steps: int, items: int = 2) -> None:
        self.steps = steps
        self.items = items
        self.entered = 0
        self.produced = 0

    def __aiter__(self) -> "CoroutineIterator":
        return self

    async def __anext__(self) -> int:
        self.entered += 1
        if self.produced >= self.items:
            raise StopAsyncIteration
        for _ in range(self.steps):
            await Suspend()
        self.produced += 1
        return self.produced


class GeneratorAwaitable:
    """An awaitable whose ``__await__`` is a generator function."""

    calls = 0

    def __init__(self, steps: int) -> None:
        self.steps = steps

    def __await__(self) -> Generator[None, None, str]:
        GeneratorAwaitable.calls += 1
        for _ in range(self.steps):
            yield
        return "item"


class SuspendOnceEver:
    """An awaitable whose ``__await__`` suspends on its first call only."""

    def __init__(self) -> None:
        self.calls = 0

    def __await__(self) -> Generator[None, None, str]:
        self.calls += 1
        if self.calls == 1:
            yield
        return "item"


class HandWrittenIterator:
    """A plain ``def __anext__`` returning a GeneratorAwaitable rather than a coroutine."""

    def __init__(self, steps: int) -> None:
        self.steps = steps
        self.calls = 0

    def __anext__(self) -> GeneratorAwaitable:
        self.calls += 1
        return GeneratorAwaitable(self.steps)


def counting_generator(items: int, steps: int, log: list[int]) -> AsyncGenerator[int, None]:
    async def generate() -> AsyncGenerator[int, None]:
        for i in range(items):
            for _ in range(steps):
                await Suspend()
            log.append(i)
            yield i

    return generate()


async def use(iterator: object, *default: object) -> object:
    return await anext(cast("Any", iterator), *default)


def drive(coroutine: Coroutine[Any, Any, Any], limit: int | None = None) -> tuple[object, int]:
    """Run a coroutine to completion with send(None); return its value and step count.

    With a limit, stop after that many steps and return ("unfinished", limit),
    leaving the coroutine suspended for the caller to inspect and close.
    """
    steps = 0
    while limit is None or steps < limit:
        try:
            coroutine.send(None)
        except StopIteration as stop:
            return stop.value, steps
        steps += 1
    return "unfinished", steps


def close(awaitable: Awaitable[object]) -> None:
    cast("Any", awaitable).close()


def best_time(func: Callable[[], Any], repeats: int = 5) -> float:
    """Return the fastest of several runs, which is the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return min(times)


def traced_peak(func: Callable[[], Any]) -> int:
    tracemalloc.start()
    tracemalloc.reset_peak()
    try:
        func()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak


class TestCallRow:
    """anext() call | O(1) | O(1) | Plus the ``__anext__()`` call, which for async def only builds."""

    def test_the_call_runs_none_of_the_body(self) -> None:
        log: list[int] = []
        generator = counting_generator(3, 0, log)
        awaitable = anext(generator)
        wrapped = anext(generator, None)

        assert log == []
        close(awaitable)
        close(wrapped)

    def test_a_coroutine_anext_is_not_entered_by_the_call(self) -> None:
        iterator = CoroutineIterator(steps=0)
        awaitable = anext(iterator)

        assert iterator.entered == 0
        close(awaitable)

    def test_a_plain_def_anext_runs_once_at_the_call(self) -> None:
        iterator = HandWrittenIterator(0)
        awaitable = anext(iterator)

        assert iterator.calls == 1
        assert isinstance(awaitable, GeneratorAwaitable)

    def test_the_first_await_runs_the_body_to_the_first_yield_only(self) -> None:
        log: list[int] = []
        generator = counting_generator(3, 0, log)

        for expected in range(3):
            value, _ = drive(use(generator))
            assert value == expected
            assert log == list(range(expected + 1)), f"await {expected} ran {log}"

    @pytest.mark.parametrize("bad", [[1], iter([1]), 3], ids=["list", "list-iterator", "int"])
    def test_a_non_async_iterator_is_rejected_by_the_call(self, bad: object) -> None:
        with pytest.raises(TypeError, match="is not an async iterator"):
            anext(cast("Any", bad))

    def test_the_awaitables_do_not_grow_with_the_iterator(self) -> None:
        sizes: list[tuple[int, int]] = []
        peaks: list[int] = []

        async def holding(count: int) -> AsyncGenerator[int, None]:
            data = list(range(count))
            yield len(data)
            yield 0

        for count in (10, 100_000):
            generator = holding(count)
            assert drive(use(generator)) == (count, 0)
            tracemalloc.start()
            tracemalloc.reset_peak()
            plain = anext(generator)
            wrapped = anext(generator, None)
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            sizes.append((sys.getsizeof(plain), sys.getsizeof(wrapped)))
            peaks.append(peak)
            close(plain)
            close(wrapped)

        assert sizes[0] == sizes[1], sizes
        assert max(peaks) < 1024, peaks


class TestAwaitRow:
    """Awaiting result | O(k) | O(1) | k = one ``__anext__()`` step, including its awaits."""

    @pytest.mark.parametrize("steps", [3, 1000])
    def test_the_caller_suspends_once_per_await_inside_the_step(self, steps: int) -> None:
        iterator = CoroutineIterator(steps)

        assert drive(use(iterator)) == (1, steps)
        assert drive(use(iterator, None)) == (2, steps)
        assert iterator.entered == 2

    @pytest.mark.parametrize("steps", [3, 1000])
    def test_an_async_generator_step_costs_its_own_awaits(self, steps: int) -> None:
        log: list[int] = []
        generator = counting_generator(2, steps, log)

        assert drive(use(generator)) == (0, steps)
        assert drive(use(generator, None)) == (1, steps)
        assert drive(use(generator, "done")) == ("done", 0)
        assert log == [0, 1]

    def test_one_await_allocates_the_same_deep_into_the_iteration(self) -> None:
        log: list[int] = []
        generator = counting_generator(100_000, 0, log)
        peaks: list[int] = []

        async def advance_then_measure(items: int) -> None:
            for _ in range(items):
                await anext(generator)
            tracemalloc.start()
            tracemalloc.reset_peak()
            await anext(generator)
            await anext(generator, None)
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            peaks.append(peak)

        drive(advance_then_measure(10))
        drive(advance_then_measure(50_000 - 12))

        assert len(log) == 50_002
        assert max(peaks) < 1024, peaks


class TestDefaultRow:
    """With default | O(k) | O(1) | Returns default if exhausted."""

    def test_the_item_and_then_the_default_come_back_by_identity(self) -> None:
        default = object()
        item = object()

        class Once:
            def __init__(self) -> None:
                self.done = False

            async def __anext__(self) -> object:
                if self.done:
                    raise StopAsyncIteration
                self.done = True
                return item

        iterator = Once()

        assert drive(use(iterator, default))[0] is item
        assert drive(use(iterator, default))[0] is default
        assert drive(use(iterator, default))[0] is default

    def test_an_exhausted_generator_does_not_run_again(self) -> None:
        log: list[int] = []
        generator = counting_generator(2, 5, log)

        assert drive(use(generator)) == (0, 5)
        assert drive(use(generator)) == (1, 5)
        assert drive(use(generator, "END")) == ("END", 0)
        assert drive(use(generator, "END")) == ("END", 0)
        assert log == [0, 1]

        with pytest.raises(StopAsyncIteration):
            drive(use(generator))
        assert log == [0, 1]

    def test_anext_is_still_called_once_per_attempt_when_exhausted(self) -> None:
        iterator = CoroutineIterator(steps=0, items=0)

        assert drive(use(iterator, None)) == (None, 0)
        assert drive(use(iterator, None)) == (None, 0)
        assert iterator.entered == 2

    @pytest.mark.parametrize("default", [(), (None,)], ids=["plain", "default"])
    def test_a_suspending_step_retains_nothing_across_suspensions(
        self, default: tuple[object, ...]
    ) -> None:
        peaks: list[int] = []

        for steps in (10, 10_000):
            coroutine = use(CoroutineIterator(steps), *default)
            peaks.append(traced_peak(functools.partial(drive, coroutine)))

        assert max(peaks) < 1024, peaks

    @pytest.mark.timing
    @pytest.mark.parametrize("default", [(), (None,)], ids=["plain", "default"])
    def test_the_cost_per_suspension_is_flat(self, default: tuple[object, ...]) -> None:
        """x100 suspensions costs about x100: an O(1) wrapper step, not one that grows."""
        small = best_time(lambda: drive(use(CoroutineIterator(100), *default)))
        large = best_time(lambda: drive(use(CoroutineIterator(10_000), *default)))
        ratio = large / small

        assert 10 < ratio < 1000, f"x100 suspensions cost x{ratio:.0f}"

    def test_other_exceptions_pass_through_the_default(self) -> None:
        class Broken:
            async def __anext__(self) -> object:
                raise ValueError("inside the step")

        with pytest.raises(ValueError, match="inside the step"):
            drive(use(Broken(), None))


class TestHandWrittenAwaitableWarning:
    """The default form restarts a generator-function ``__await__`` at every suspension."""

    def test_without_a_default_the_awaitable_runs_once_to_the_end(self) -> None:
        GeneratorAwaitable.calls = 0

        assert drive(use(HandWrittenIterator(3))) == ("item", 3)
        assert GeneratorAwaitable.calls == 1

    def test_with_a_default_it_restarts_on_every_step_and_never_finishes(self) -> None:
        GeneratorAwaitable.calls = 0
        coroutine = use(HandWrittenIterator(3), None)

        assert drive(coroutine, limit=20) == ("unfinished", 20)
        assert GeneratorAwaitable.calls == 20
        coroutine.close()

    def test_with_a_default_an_awaitable_that_stops_suspending_completes(self) -> None:
        awaitable = SuspendOnceEver()

        class Iterator:
            def __anext__(self) -> SuspendOnceEver:
                return awaitable

        assert drive(use(Iterator(), None)) == ("item", 1)
        assert awaitable.calls == 2

    def test_with_a_default_an_awaitable_that_never_suspends_completes(self) -> None:
        GeneratorAwaitable.calls = 0

        assert drive(use(HandWrittenIterator(0), None)) == ("item", 0)
        assert GeneratorAwaitable.calls == 1


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


def _block_containing(marker: str) -> str:
    matches = [source for _, source in _blocks() if marker in source]
    assert len(matches) == 1, f"{len(matches)} blocks contain {marker!r}"
    return matches[0]


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
            if result.returncode != 0 or result.stderr.strip():
                failures.append(f"{PAGE.name}:{line}: {result.stderr.strip()}")

        assert not failures, "\n".join(failures)

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        source = _block_containing("except StopAsyncIteration:")
        broken = source.replace("except StopAsyncIteration:", "except ValueError:", 1)
        assert broken != source, "the mutation did not change the handler"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "StopAsyncIteration" in result.stderr

    @pytest.mark.parametrize(
        ("marker", "stdout"),
        [
            ("for i in range(3):", ["0", "1"]),
            ('anext(async_iter, "END")', ["1", "2", "END"]),
            ("except StopAsyncIteration:", ["1", "Iterator exhausted"]),
            ("fetch_items", ["First: a", "Second: b", "Item: c"]),
            ("sync_iter = iter(sync_gen())", ["1", "1"]),
        ],
        ids=["next-item", "default", "no-default", "practical", "comparison"],
    )
    def test_the_stated_output_is_what_the_block_produces(
        self, marker: str, stdout: list[str], tmp_path: pathlib.Path
    ) -> None:
        result = _run(_block_containing(marker), tmp_path)

        assert result.returncode == 0, result.stderr.strip()
        assert result.stdout.splitlines() == stdout
