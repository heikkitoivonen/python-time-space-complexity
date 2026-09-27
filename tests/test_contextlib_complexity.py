"""Tests for docs/stdlib/contextlib.md.

The page prices what `contextlib` adds around the caller's own setup and
cleanup code: O(1) per registration and per entry, one O(k) pass to unwind an
exit stack, and O(k²) when every exit raises while handling the exception
before it. The constant-time rows are settled by observation - call counters,
identity checks and recorded event orders - which needs no tolerance. The
unwinding bounds and the exception-group split are settled by timing, because
the quadratic term lives in the interpreter's exception chaining and the split
in C, neither of which Python code can count.

Measurement scope:

* Calling a `@contextmanager` function runs none of its body, and each call
  returns a new object with a new generator; entering runs to the `yield` and
  leaving runs past it, observed by a recorded event list. A second `with` on
  the same object raises `AttributeError`. Used as a decorator it runs the
  generator function once per call of the decorated function, over three
  calls. For `@asynccontextmanager`, calling runs none of the body, entering
  and leaving are observed the same way, a second `async with` raises
  `AttributeError`, and as a decorator it runs the generator once per call
  over two calls.
* `ExitStack` and `AsyncExitStack` unwind last-registered first, each callback
  exactly once, and leave the stack empty; a pushed `__exit__` that returns
  true suppresses the exception, and the callback below it sees `None`.
  `pop_all()` is asserted to move the very deque that holds the callbacks,
  which is what makes it O(1) at any k. Unwinding 100,000 no-op callbacks is
  asserted to peak under 20 KB of traced allocation.
* Registering and unwinding are timed together with garbage collection off,
  best of five, for `ExitStack` and `AsyncExitStack`, with the body raising.
  Exits that raise without handling the exception in flight - an `__exit__`
  method that raises, which the stack calls outside any `except` block - grow
  less than 100x from k = 250 to 8,000 (x19 to x47 measured on 3.10 and
  3.14). `@contextmanager` and `@asynccontextmanager` objects whose `finally`
  raises grow more than 160x from k = 250 to 16,000, where linear predicts
  64x and quadratic 4096x (x916 and x1017 on 3.14). At k = 250 per-exit
  overhead still dominates: from 250 to 8,000 they grow x220 to x390 on
  aarch64 and x99 and x119 in one x86_64 CI run. The final
  exception's `__context__` chain is asserted to hold all k exceptions, which
  is the O(k) space of that row.
* `closing()` and `aclosing()` call `close()` or `aclose()` exactly once, on a
  normal exit and on an exception; `nullcontext()` returns its argument under
  `with` and `async with`.
* `suppress()` is asserted to swallow a matching exception, skip the rest of
  the block and let others through. From 3.12 an `ExceptionGroup` of only
  matching exceptions is swallowed and a mixed one re-raised holding the
  others; on 3.11 the group passes through untouched. The split is timed over
  groups of 1,000 and 100,000 exceptions, which grows more than 20x.
* `redirect_stdout()`, `redirect_stderr()` and `chdir()` are asserted to
  restore the previous value, to work when the same object is nested in
  itself, and to be visible from another thread while the block runs.
  `chdir()` is guarded on 3.11.
* A `ContextDecorator` subclass used as a decorator is observed entering the
  same instance on every call. `__enter__` and `__aenter__` of the two
  abstract base classes return `self`; `isinstance()` recognises a class that
  only inherits the two methods, and after the first check deleting a method
  does not change the answer for a class already checked while a new subclass
  is refused, which is the per-class cache.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* That the O(1) rows exclude the caller's own `__enter__`, `__exit__`,
  callback and generator code is the page's cost model, not a measurement.
  Argument packing for `callback()` and `push_async_callback()`, and the
  number of exception types given to `suppress()`, are priced O(1) by the
  same model and are not varied.
* The first `isinstance()` check against the two abstract base classes walks
  the MRO, read from `_collections_abc._check_methods`; MRO depth is not
  varied, and a negative first check also consults the ABC's subclass
  registry, which is `abc`'s cost.
* The O(k²) unwinding row is timed for the case where every exit raises. A
  stack where only some exits raise, and nested exception groups, are not
  measured.
* Thread safety is asserted only as visibility of the swapped state from a
  second thread; races between threads entering at once are not exercised.
"""

from __future__ import annotations

import asyncio
import builtins
import gc
import io
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import threading
import time
import tracemalloc
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import (
    AbstractAsyncContextManager,
    AbstractContextManager,
    AsyncExitStack,
    ContextDecorator,
    ExitStack,
    aclosing,
    asynccontextmanager,
    closing,
    contextmanager,
    nullcontext,
    redirect_stderr,
    redirect_stdout,
    suppress,
)
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "contextlib.md"
EXPECTED_BLOCKS = 12
GROUP: Any = getattr(builtins, "ExceptionGroup", None)


def best_seconds(func: Callable[[], Any], repeats: int = 5) -> float:
    """Fastest of `repeats` runs, in seconds, with garbage collection off."""
    best: float | None = None
    enabled = gc.isenabled()
    gc.disable()
    try:
        for _ in range(repeats):
            start = time.perf_counter()
            func()
            elapsed = time.perf_counter() - start
            best = elapsed if best is None else min(best, elapsed)
    finally:
        if enabled:
            gc.enable()
        gc.collect()
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


class Recorder:
    """A closable object that records its name when closed."""

    def __init__(self, log: list[str], name: str) -> None:
        self.log = log
        self.name = name

    def close(self) -> None:
        self.log.append(self.name)


def context_chain(error: BaseException | None) -> list[BaseException]:
    chain: list[BaseException] = []
    while error is not None:
        chain.append(error)
        error = error.__context__
    return chain


class TestGeneratorContextManagers:
    """`@contextmanager` | O(1): calling builds a generator and runs nothing;
    entering runs to the `yield`, leaving past it; each object is single use,
    and the decorator form builds a new generator per call."""

    def test_calling_runs_nothing_and_builds_a_new_generator(self) -> None:
        events: list[str] = []

        @contextmanager
        def tag() -> Iterator[str]:
            events.append("setup")
            yield "value"
            events.append("cleanup")

        first, second = tag(), tag()

        assert events == []
        assert first is not second
        assert first.gen is not second.gen  # type: ignore[attr-defined]
        with first as value:
            assert value == "value"
            assert events == ["setup"]
        assert events == ["setup", "cleanup"]

    def test_a_second_with_on_the_same_object_raises(self) -> None:
        @contextmanager
        def once() -> Iterator[None]:
            yield

        manager = once()
        with manager:
            pass

        with pytest.raises(AttributeError), manager:
            pass

    def test_the_exception_is_thrown_in_at_the_yield(self) -> None:
        seen: list[type[BaseException]] = []

        @contextmanager
        def catch() -> Iterator[None]:
            try:
                yield
            except KeyError as error:
                seen.append(type(error))

        with catch():
            raise KeyError("x")

        assert seen == [KeyError]

    def test_as_a_decorator_it_runs_the_generator_once_per_call(self) -> None:
        calls: list[str] = []

        @contextmanager
        def counted() -> Iterator[None]:
            calls.append("enter")
            yield

        @counted()
        def work(x: int) -> int:
            return x * 2

        assert [work(n) for n in range(3)] == [0, 2, 4]
        assert calls == ["enter", "enter", "enter"]

    def test_the_async_form_behaves_the_same(self) -> None:
        events: list[str] = []

        @asynccontextmanager
        async def tag() -> AsyncIterator[str]:
            events.append("setup")
            yield "value"
            events.append("cleanup")

        @tag()
        async def decorated() -> None:
            events.append("body")

        async def main() -> None:
            manager = tag()
            assert events == []
            async with manager as value:
                assert value == "value"
                assert events == ["setup"]
            await decorated()
            await decorated()

        asyncio.run(main())

        assert events == ["setup", "cleanup"] + ["setup", "body", "cleanup"] * 2

    def test_an_async_object_is_single_use_too(self) -> None:
        @asynccontextmanager
        async def once() -> AsyncIterator[None]:
            yield

        async def main() -> None:
            manager = once()
            async with manager:
                pass
            with pytest.raises(AttributeError):
                async with manager:
                    pass

        asyncio.run(main())


class TestExitStackUnwindsOnce:
    """`ExitStack` registration | O(1); `close()` | O(k) | O(1): every callback
    once, last registered first, and the stack is left empty."""

    def test_callbacks_run_last_registered_first(self) -> None:
        order: list[str] = []

        with ExitStack() as stack:
            for name in "abc":
                stack.enter_context(closing(Recorder(order, name)))
            stack.callback(order.append, "callback")
            assert order == []

        assert order == ["callback", "c", "b", "a"]

    def test_enter_context_returns_what_enter_returned(self) -> None:
        with ExitStack() as stack:
            assert stack.enter_context(nullcontext("x")) == "x"

    def test_close_runs_each_callback_once_and_empties_the_stack(self) -> None:
        calls: list[int] = []
        stack = ExitStack()
        for n in range(5):
            stack.callback(calls.append, n)

        stack.close()
        stack.close()

        assert calls == [4, 3, 2, 1, 0]

    def test_a_pushed_exit_can_suppress_and_hides_the_exception_below(self) -> None:
        seen: list[type[BaseException] | None] = []

        def record(exc_type: Any, exc: Any, tb: Any) -> bool:
            seen.append(exc_type)
            return False

        def swallow(exc_type: Any, exc: Any, tb: Any) -> bool:
            seen.append(exc_type)
            return True

        with ExitStack() as stack:
            stack.push(record)
            stack.push(swallow)
            raise ValueError

        assert seen == [ValueError, None]

    def test_push_takes_an_object_s_exit(self) -> None:
        class Suppressor:
            def __enter__(self) -> Suppressor:
                return self

            def __exit__(self, *exc: Any) -> bool:
                return True

        with ExitStack() as stack:
            stack.push(Suppressor())
            raise ValueError

    def test_a_callback_cannot_suppress(self) -> None:
        with pytest.raises(ValueError), ExitStack() as stack:
            stack.callback(lambda: True)
            raise ValueError

    def test_pop_all_moves_the_same_deque(self) -> None:
        stack = ExitStack()
        for n in range(100_000):
            stack.callback(int, n)
        # The private deque is where the O(1) move shows.
        held = stack._exit_callbacks  # type: ignore[attr-defined]  # noqa: SLF001

        moved = stack.pop_all()

        assert moved._exit_callbacks is held  # type: ignore[attr-defined]  # noqa: SLF001
        assert len(stack._exit_callbacks) == 0  # type: ignore[attr-defined]  # noqa: SLF001
        assert type(moved) is ExitStack

    def test_unwinding_100_000_callbacks_peaks_under_20_kb(self) -> None:
        stack = ExitStack()
        for _ in range(100_000):
            stack.callback(int)

        peak = peak_bytes(stack.close)

        assert peak < 20_000, f"closing 100,000 callbacks peaked at {peak} bytes"


class TestAsyncExitStack:
    """`AsyncExitStack`: both kinds of callback on one stack, one LIFO pass."""

    def test_sync_and_async_callbacks_unwind_in_one_lifo_pass(self) -> None:
        order: list[str] = []

        @asynccontextmanager
        async def resource(name: str) -> AsyncIterator[str]:
            yield name
            order.append(f"close {name}")

        async def async_callback(name: str) -> None:
            order.append(name)

        class AsyncSuppressor:
            async def __aenter__(self) -> AsyncSuppressor:
                return self

            async def __aexit__(self, *exc: Any) -> bool:
                order.append(f"aexit {exc[0].__name__ if exc[0] else None}")
                return True

        async def main() -> None:
            async with AsyncExitStack() as stack:
                stack.push(lambda *exc: order.append(f"push {exc[0]}"))
                assert await stack.enter_async_context(resource("db")) == "db"
                stack.enter_context(closing(Recorder(order, "sync cm")))
                stack.callback(order.append, "sync callback")
                stack.push_async_callback(async_callback, "async callback")
                stack.push_async_exit(AsyncSuppressor())
                raise ValueError

        asyncio.run(main())

        assert order == [
            "aexit ValueError",
            "async callback",
            "sync callback",
            "sync cm",
            "close db",
            "push None",
        ]

    def test_pop_all_and_aclose(self) -> None:
        order: list[int] = []

        async def main() -> None:
            stack = AsyncExitStack()
            held = stack._exit_callbacks  # type: ignore[attr-defined]  # noqa: SLF001
            for n in range(3):
                stack.callback(order.append, n)
            moved = stack.pop_all()
            await stack.aclose()
            assert order == []
            assert moved._exit_callbacks is held  # type: ignore[attr-defined]  # noqa: SLF001
            await moved.aclose()

        asyncio.run(main())

        assert order == [2, 1, 0]


class RaisingExit:
    """An `__exit__` that raises without handling the exception it is given."""

    def __enter__(self) -> RaisingExit:
        return self

    def __exit__(self, *exc: Any) -> None:
        raise RuntimeError


class AsyncRaisingExit:
    async def __aenter__(self) -> AsyncRaisingExit:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        raise RuntimeError


@contextmanager
def raising_cleanup() -> Iterator[None]:
    try:
        yield
    finally:
        raise RuntimeError


@asynccontextmanager
async def async_raising_cleanup() -> AsyncIterator[None]:
    try:
        yield
    finally:
        raise RuntimeError


def unwind_sync(factory: Callable[[], Any], k: int) -> Callable[[], None]:
    def run() -> None:
        stack = ExitStack()
        for _ in range(k):
            stack.enter_context(factory())
        try:
            with stack:
                raise KeyError
        except RuntimeError:
            pass

    return run


def unwind_async(factory: Callable[[], Any], k: int) -> Callable[[], None]:
    async def unwind() -> None:
        stack = AsyncExitStack()
        for _ in range(k):
            await stack.enter_async_context(factory())
        try:
            async with stack:
                raise KeyError
        except RuntimeError:
            pass

    loop = asyncio.new_event_loop()

    def run() -> None:
        loop.run_until_complete(unwind())

    run.loop = loop  # type: ignore[attr-defined]
    return run


class TestRaisingExitsDuringUnwinding:
    """`close()` stays O(k) when the exits ignore the exception they are
    handed, and is O(k²) | O(k) when each raises while handling it: every raise
    walks the context chain of the exception being handled, which holds every
    earlier exit's exception."""

    SMALL = 250

    def test_the_chain_holds_every_exception(self) -> None:
        k = 50
        stack = ExitStack()
        for _ in range(k):
            stack.enter_context(raising_cleanup())

        with pytest.raises(RuntimeError) as raised, stack:
            raise KeyError

        chain = context_chain(raised.value)
        assert len(chain) == k + 1
        assert isinstance(chain[-1], KeyError)

    def test_the_async_chain_holds_every_exception(self) -> None:
        k = 50

        async def main() -> BaseException:
            stack = AsyncExitStack()
            for _ in range(k):
                await stack.enter_async_context(async_raising_cleanup())
            try:
                async with stack:
                    raise KeyError
            except RuntimeError as error:
                return error
            raise AssertionError("the cleanups did not raise")

        chain = context_chain(asyncio.run(main()))
        assert len(chain) == k + 1

    def growth(
        self, build: Callable[[Any, int], Callable[[], None]], factory: Any, count: int
    ) -> float:
        runs = [build(factory, k) for k in (self.SMALL, count)]
        try:
            for run in runs:
                run()
            small, large = (best_seconds(run) for run in runs)
        finally:
            for run in runs:
                loop = getattr(run, "loop", None)
                if loop is not None:
                    loop.close()
        return large / small

    @pytest.mark.timing
    @pytest.mark.parametrize(
        ("build", "factory"),
        [(unwind_sync, RaisingExit), (unwind_async, AsyncRaisingExit)],
        ids=["ExitStack", "AsyncExitStack"],
    )
    def test_exits_that_raise_outside_a_handler_unwind_in_linear_time(
        self, build: Any, factory: Any
    ) -> None:
        ratio = self.growth(build, factory, 8_000)

        assert ratio < 100, f"32x the raising exits cost x{ratio:.1f}; linear predicts x32"

    @pytest.mark.timing
    @pytest.mark.parametrize(
        ("build", "factory"),
        [(unwind_sync, raising_cleanup), (unwind_async, async_raising_cleanup)],
        ids=["ExitStack", "AsyncExitStack"],
    )
    def test_cleanups_that_raise_while_handling_unwind_in_quadratic_time(
        self, build: Any, factory: Any
    ) -> None:
        ratio = self.growth(build, factory, 16_000)

        assert ratio > 160, f"64x the raising cleanups cost x{ratio:.1f}; quadratic predicts x4096"


class TestSingleCleanupHelpers:
    """`closing`, `aclosing` and `nullcontext` | O(1)."""

    class Closable:
        def __init__(self) -> None:
            self.closes = 0

        def close(self) -> None:
            self.closes += 1

        async def aclose(self) -> None:
            self.closes += 1

    def test_closing_calls_close_once_either_way(self) -> None:
        normal, failing = self.Closable(), self.Closable()

        with closing(normal) as value:
            assert value is normal
        with pytest.raises(ValueError), closing(failing):
            raise ValueError

        assert (normal.closes, failing.closes) == (1, 1)

    def test_aclosing_awaits_aclose_once_either_way(self) -> None:
        normal, failing = self.Closable(), self.Closable()

        async def main() -> None:
            async with aclosing(normal) as value:
                assert value is normal
            with pytest.raises(ValueError):
                async with aclosing(failing):
                    raise ValueError

        asyncio.run(main())

        assert (normal.closes, failing.closes) == (1, 1)

    def test_nullcontext_returns_its_argument_sync_and_async(self) -> None:
        marker = object()
        with nullcontext(marker) as value:
            assert value is marker
        with nullcontext() as nothing:
            assert nothing is None

        async def main() -> object:
            async with nullcontext(marker) as inner:
                return inner

        assert asyncio.run(main()) is marker


class TestSuppress:
    """`suppress(*exceptions)` | O(1); an exception group is split in O(g)
    from 3.12."""

    def test_a_match_ends_the_block_and_others_pass(self) -> None:
        reached: list[str] = []

        with suppress(KeyError, IndexError):
            {}["missing"]  # noqa: B018
            reached.append("after")

        with pytest.raises(ValueError), suppress(KeyError):
            raise ValueError

        assert reached == []

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="exception groups from 3.12")
    def test_a_group_is_split(self) -> None:
        with suppress(ValueError):
            raise GROUP("all", [ValueError(1), ValueError(2)])

        with pytest.raises(GROUP) as raised, suppress(ValueError):
            raise GROUP("mixed", [ValueError(1), KeyError(2)])

        assert [type(e) for e in raised.value.exceptions] == [KeyError]

    @pytest.mark.skipif(sys.version_info[:2] != (3, 11), reason="3.11 has groups, not the split")
    def test_on_311_a_group_passes_through(self) -> None:
        group = GROUP("all", [ValueError(1)])

        with pytest.raises(GROUP) as raised, suppress(ValueError):
            raise group

        assert raised.value is group

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 12), reason="exception groups from 3.12")
    def test_the_split_grows_with_the_group(self) -> None:
        def splitting(g: int) -> Callable[[], None]:
            group = GROUP("g", [ValueError(n) for n in range(g)])

            def run() -> None:
                group.__traceback__ = None
                with suppress(ValueError):
                    raise group

            return run

        small, large = splitting(1_000), splitting(100_000)
        small()
        large()

        ratio = best_seconds(large) / best_seconds(small)

        assert ratio > 20, f"100x the group cost x{ratio:.1f}; a constant split gives x1"


class TestProcessWideSwaps:
    """`redirect_stdout`, `redirect_stderr` and `chdir` | O(1): process-wide
    state, restored on exit, and the same object nests in itself."""

    @staticmethod
    def seen_from_another_thread(read: Callable[[], Any]) -> Any:
        box: list[Any] = []
        thread = threading.Thread(target=lambda: box.append(read()))
        thread.start()
        thread.join()
        return box[0]

    @pytest.mark.parametrize(
        ("redirect", "name"),
        [(redirect_stdout, "stdout"), (redirect_stderr, "stderr")],
    )
    def test_redirect_restores_nests_and_is_process_wide(self, redirect: Any, name: str) -> None:
        original = getattr(sys, name)
        buffer = io.StringIO()
        manager = redirect(buffer)

        with manager:
            with manager:
                getattr(sys, name).write("x")
            assert getattr(sys, name) is buffer
            assert self.seen_from_another_thread(lambda: getattr(sys, name)) is buffer

        assert getattr(sys, name) is original
        assert buffer.getvalue() == "x"

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="chdir is 3.11+")
    def test_chdir_restores_nests_and_is_process_wide(self, tmp_path: pathlib.Path) -> None:
        from contextlib import chdir  # type: ignore[attr-defined]

        start = os.getcwd()
        manager = chdir(tmp_path)

        with manager:
            (tmp_path / "inner").mkdir()
            with chdir("inner"):
                assert os.path.samefile(os.getcwd(), tmp_path / "inner")
            with manager:
                assert os.path.samefile(os.getcwd(), tmp_path)
            assert os.path.samefile(os.getcwd(), tmp_path)
            assert os.path.samefile(self.seen_from_another_thread(os.getcwd), tmp_path)

        assert os.getcwd() == start


class TestBaseClasses:
    """`ContextDecorator` enters the same instance per call;
    `AbstractContextManager` checks structurally, cached per class."""

    def test_a_context_decorator_enters_the_same_instance_every_call(self) -> None:
        entered: list[object] = []

        class Tracked(ContextDecorator):
            def __enter__(self) -> Tracked:
                entered.append(self)
                return self

            def __exit__(self, *exc: Any) -> None:
                return None

        tracked = Tracked()

        @tracked
        def work() -> None:
            pass

        work()
        work()

        assert entered == [tracked, tracked]
        assert all(item is tracked for item in entered)

    def test_enter_returns_self(self) -> None:
        class Plain(AbstractContextManager):  # type: ignore[type-arg]
            def __exit__(self, *exc: Any) -> None:
                return None

        class AsyncPlain(AbstractAsyncContextManager):  # type: ignore[type-arg]
            async def __aexit__(self, *exc: Any) -> None:
                return None

        plain, async_plain = Plain(), AsyncPlain()
        with plain as value:
            assert value is plain

        async def main() -> object:
            async with async_plain as inner:
                return inner

        assert asyncio.run(main()) is async_plain

    def test_isinstance_is_structural_and_cached_per_class(self) -> None:
        class Base:
            def __enter__(self) -> None:
                return None

            def __exit__(self, *exc: Any) -> None:
                return None

        class Child(Base):
            pass

        assert isinstance(Child(), AbstractContextManager)

        del Base.__exit__

        class Unchecked(Base):
            pass

        assert not isinstance(Unchecked(), AbstractContextManager)
        assert isinstance(Child(), AbstractContextManager), "the answer was not cached"

    def test_the_async_abc_is_structural(self) -> None:
        class Async:
            async def __aenter__(self) -> None:
                return None

            async def __aexit__(self, *exc: Any) -> None:
                return None

        assert isinstance(Async(), AbstractAsyncContextManager)
        assert not isinstance(object(), AbstractAsyncContextManager)

        del Async.__aexit__

        assert isinstance(Async(), AbstractAsyncContextManager), "the answer was not cached"


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
    """Each block runs in its own subprocess and working directory, since
    several change process-wide state, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "chain == [0, 1, 2, " in s)
        mutated = source.replace("chain == [0, 1, 2, ", "chain == [2, 1, 0, ", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
