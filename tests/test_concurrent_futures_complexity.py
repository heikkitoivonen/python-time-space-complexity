"""Tests for docs/stdlib/concurrent_futures.md.

The page prices the pools' bookkeeping, not the tasks: building a pool starts
nothing, a submit queues one item and starts at most one worker, `map()`
submits its whole input up front, a `Future` hands back the stored object, and
`wait()` and `as_completed()` sort their futures once. Worker starts are
settled by counting threads, child processes and interpreters; laziness by a
generator that records what it has handed out; the sort by a counting
`sorted` injected into the module's globals; identity rows by `is`. Two
timing tests bound growth where no counter reaches.

Measurement scope:

* `ThreadPoolExecutor(8)` leaves `threading.active_count()` unchanged; three
  submits of a blocking task add three threads and twenty more stop at eight.
  Ten tasks, each submitted once the previous result is in and the worker
  has released the pool's idle semaphore, leave one thread in the pool. `ProcessPoolExecutor(4)` leaves `active_children()` empty; its first
  submit starts four children with the `fork` context and one with `spawn`,
  and a second submit after the first result starts none. On 3.14
  `InterpreterPoolExecutor(3)` adds nothing to `interpreters.list_all()` and
  its first submit adds one.
* `ThreadPoolExecutor.submit()` is timed with 100 and 100,000 tasks already
  queued behind a blocked single worker; the deeper queue costs under 3x.
  A task returning its argument returns the same object, so arguments pass by
  reference.
* A process pool's `submit()` of an argument whose `__reduce__` raises
  returns a future and the error arrives through `result()`. On 3.14 an
  `InterpreterPoolExecutor` argument's `__reduce__` runs on the worker
  thread, not in `submit()`, and a list the task appends to stays unchanged
  in the submitting interpreter.
  `ProcessPoolExecutor.map()` over 20 items with `chunksize=5` calls
  `submit()` four times. `terminate_workers()` and `kill_workers()` (3.14)
  leave no live child and make `submit()` raise `RuntimeError`.
* `map()` drains a 100-item generator before returning, on every version;
  with `buffersize=4` (3.14) it takes four, at most five once one result is
  taken, and the rest as results are consumed. Results come in input order, and a `map()` whose first task is
  blocked raises `TimeoutError` from `next()` although later tasks are done.
* `shutdown(cancel_futures=True)` behind a worker known to be running a
  blocked task cancels the five queued futures and leaves the running one to
  finish.
* `Future.result()` is the object passed to `set_result()`; `cancel()` runs
  each callback once, returns `True` again on a cancelled future without
  rerunning them, and returns `False` once `set_running_or_notify_cancel()`
  has run; a callback added before completion runs in the completing thread; a second `set_result()` raises `InvalidStateError`; a callback
  added to a done future runs before `add_done_callback()` returns, in the
  calling thread; `set_result()` runs each of 50 callbacks once.
* `wait()` and `as_completed()` each call `sorted` once, over the n distinct
  futures, for n = 50; duplicates are yielded once and already-finished
  futures come before one finished later. A timing test over 1,000, 10,000
  and 100,000 finished futures bounds each 10x step of `wait()` under 40x,
  where a quadratic would give 100x and n log n about 12x.
* `concurrent.futures.TimeoutError` is the builtin from 3.11 and a distinct
  class before; the `Broken*` classes subclass `BrokenExecutor`; the
  `return_when` constants are their own names as strings.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The O(a) cost of moving arguments and results through a process or
  interpreter pool is pickle's and the cross-interpreter copy's; it is read
  from Lib/concurrent/futures/process.py (the `_SafeQueue` feeder pickles)
  and interpreter.py (`Interpreter.call`), and not timed here. The
  concurrent.interpreters tests time the copy.
* `ThreadPoolExecutor.shutdown()`'s O(w + q) is read from thread.py: one
  join per thread and one `get_nowait()` per queued item when cancelling.
  `ProcessPoolExecutor.shutdown()` is read from process.py's manager thread;
  its O(w) space is the dictionary `cancel_futures=True` keeps of work
  already dispatched: running in the w workers or waiting in the w + 1
  call-queue slots.
* Treating the waiters on one future as O(1) is a cost-model choice; each
  concurrent `wait()` or `as_completed()` over a future adds one to the list
  `set_result()` walks.
* The `fork` start-method test is skipped where `fork` is unavailable; the
  default-start-method boundary at 3.14 is the multiprocessing module's and
  is read from its documentation, not asserted.
* The 3.14 extension hooks `ThreadPoolExecutor.prepare_context()` and
  `thread.WorkerContext` / `interpreter.WorkerContext` are undocumented and
  not priced; the audit lists them as unclassified runtime discoveries.
"""

from __future__ import annotations

import importlib
import multiprocessing
import pathlib
import re
import subprocess
import sys
import textwrap
import threading
import time
from collections.abc import Callable, Iterator
from concurrent import futures
from concurrent.futures import _base
from typing import Any, cast

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "concurrent_futures.md"
EXPECTED_BLOCKS = 10

PY314 = sys.version_info >= (3, 14)


def best_ns(func: Callable[[], Any], repeats: int = 7) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best = float("inf")
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        best = min(best, time.perf_counter_ns() - start)
    return best


def wait_until(predicate: Callable[[], bool], timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        assert time.monotonic() < deadline, "condition not reached"
        time.sleep(0.001)


class Unpicklable:
    def __reduce__(self) -> Any:
        raise TypeError("cannot pickle this")


def identity(value: Any) -> Any:
    return value


class TestPoolsStartNothing:
    """Every constructor row is O(1): no worker exists until the first submit."""

    def test_a_thread_pool_starts_no_threads(self) -> None:
        before = threading.active_count()
        executor = futures.ThreadPoolExecutor(max_workers=8)
        try:
            assert threading.active_count() == before
        finally:
            executor.shutdown()

    def test_a_process_pool_starts_no_processes(self) -> None:
        executor = futures.ProcessPoolExecutor(max_workers=4)
        try:
            assert multiprocessing.active_children() == []
        finally:
            executor.shutdown()

    @pytest.mark.skipif(not PY314, reason="InterpreterPoolExecutor is 3.14+")
    def test_an_interpreter_pool_creates_interpreters_on_submit(self) -> None:
        interpreters: Any = importlib.import_module("concurrent.interpreters")
        before = len(interpreters.list_all())
        executor = futures.InterpreterPoolExecutor(max_workers=3)  # type: ignore[attr-defined]
        try:
            assert len(interpreters.list_all()) == before
            assert executor.submit(pow, 2, 10).result() == 1024
            assert len(interpreters.list_all()) == before + 1
        finally:
            executor.shutdown()
        assert len(interpreters.list_all()) == before


class TestThreadWorkersStartOnDemand:
    """`ThreadPoolExecutor.submit` | O(1): starts at most one thread, only when
    none is idle and fewer than w run."""

    def test_busy_tasks_add_one_thread_each_up_to_max_workers(self) -> None:
        before = threading.active_count()
        release = threading.Event()
        executor = futures.ThreadPoolExecutor(max_workers=8)
        try:
            submitted = [executor.submit(release.wait) for _ in range(3)]
            assert threading.active_count() == before + 3
            submitted += [executor.submit(release.wait) for _ in range(20)]
            assert threading.active_count() == before + 8
        finally:
            release.set()
            executor.shutdown()
        assert all(future.result() is True for future in submitted)

    def test_an_idle_worker_is_reused(self) -> None:
        executor = futures.ThreadPoolExecutor(max_workers=8)
        try:
            for _ in range(10):
                executor.submit(int).result()
                # the worker marks itself idle just after the result is set
                wait_until(lambda: executor._idle_semaphore._value >= 1)  # type: ignore[attr-defined]
            assert len(executor._threads) == 1  # type: ignore[attr-defined]
        finally:
            executor.shutdown()

    def test_arguments_pass_by_reference(self) -> None:
        payload = [object()]
        with futures.ThreadPoolExecutor(max_workers=1) as executor:
            assert executor.submit(identity, payload).result() is payload

    @pytest.mark.timing
    def test_submit_does_not_grow_with_the_queue(self) -> None:
        def submit_cost(depth: int) -> float:
            release = threading.Event()
            executor = futures.ThreadPoolExecutor(max_workers=1)
            try:
                executor.submit(release.wait)
                for _ in range(depth):
                    executor.submit(int)
                return best_ns(lambda: [executor.submit(int) for _ in range(200)])
            finally:
                release.set()
                executor.shutdown()

        shallow = submit_cost(100)
        deep = submit_cost(100_000)
        assert deep < 3 * shallow, f"200 submits: {shallow:.0f}ns at depth 100, {deep:.0f}ns deep"


class TestProcessPoolStartsWorkers:
    """`ProcessPoolExecutor.submit`: all w workers on the first call with
    `fork`, at most one per call otherwise; pickling happens later."""

    @pytest.mark.skipif(
        "fork" not in multiprocessing.get_all_start_methods(), reason="fork unavailable"
    )
    def test_fork_starts_every_worker_on_the_first_submit(self) -> None:
        context = multiprocessing.get_context("fork")
        with futures.ProcessPoolExecutor(max_workers=4, mp_context=context) as executor:
            assert executor.submit(pow, 2, 10).result() == 1024
            assert len(multiprocessing.active_children()) == 4

    def test_spawn_starts_one_worker_and_reuses_it_when_idle(self) -> None:
        context = multiprocessing.get_context("spawn")
        with futures.ProcessPoolExecutor(max_workers=4, mp_context=context) as executor:
            assert executor.submit(pow, 2, 10).result() == 1024
            assert len(multiprocessing.active_children()) == 1
            wait_until(lambda: executor._idle_worker_semaphore._value >= 1)  # type: ignore[attr-defined]
            assert executor.submit(pow, 2, 3).result() == 8
            assert len(multiprocessing.active_children()) == 1

    def test_an_unpicklable_argument_fails_through_the_future(self) -> None:
        with futures.ProcessPoolExecutor(max_workers=1) as executor:
            future = executor.submit(abs, cast(Any, Unpicklable()))
            with pytest.raises(TypeError, match="cannot pickle"):
                future.result(timeout=60)

    def test_map_sends_one_task_per_chunk(self) -> None:
        with futures.ProcessPoolExecutor(max_workers=2) as executor:
            calls: list[int] = []
            submit = executor.submit

            def counting_submit(fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> Any:
                calls.append(1)
                return submit(fn, *args, **kwargs)

            executor.submit = counting_submit  # type: ignore[method-assign]
            results = list(executor.map(abs, range(-20, 0), chunksize=5))
        assert results == list(range(20, 0, -1))
        assert len(calls) == 4

    @pytest.mark.skipif(not PY314, reason="terminate_workers and kill_workers are 3.14+")
    @pytest.mark.parametrize("method", ["terminate_workers", "kill_workers"])
    def test_forced_shutdown_leaves_no_worker(self, method: str) -> None:
        executor = futures.ProcessPoolExecutor(max_workers=2)
        assert executor.submit(abs, -1).result() == 1
        getattr(executor, method)()
        wait_until(lambda: multiprocessing.active_children() == [])
        with pytest.raises(RuntimeError, match="after shutdown"):
            executor.submit(abs, -1)


class TestMapIsEager:
    """`map()` | O(n) | O(n): consumes the input and submits every task before
    returning; `buffersize` (3.14+) holds b in flight."""

    @staticmethod
    def recording(taken: list[int], count: int) -> Iterator[int]:
        for index in range(count):
            taken.append(index)
            yield index

    def test_map_consumes_the_whole_input_up_front(self) -> None:
        taken: list[int] = []
        with futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = executor.map(abs, self.recording(taken, 100))
            assert len(taken) == 100
            assert list(results) == list(range(100))

    @pytest.mark.skipif(not PY314, reason="buffersize is 3.14+")
    def test_buffersize_bounds_what_is_taken(self) -> None:
        taken: list[int] = []
        with futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = executor.map(abs, self.recording(taken, 100), buffersize=4)  # type: ignore[call-arg]
            assert len(taken) == 4
            assert next(results) == 0
            assert len(taken) <= 5
            assert list(results) == list(range(1, 100))

    def test_a_blocked_first_task_holds_back_finished_results(self) -> None:
        gate = threading.Event()
        finished: list[int] = []

        def task(index: int) -> int:
            if index == 0:
                gate.wait()
            finished.append(index)
            return index

        with futures.ThreadPoolExecutor(max_workers=4) as executor:
            try:
                results = executor.map(task, range(4), timeout=1)
                wait_until(lambda: len(finished) == 3)
                with pytest.raises(futures.TimeoutError):
                    next(results)
            finally:
                gate.set()


class TestShutdown:
    """`shutdown(cancel_futures=True)` | O(w + q): the queued tasks are
    cancelled, not run."""

    def test_cancel_futures_cancels_the_queue(self) -> None:
        entered, release = threading.Event(), threading.Event()

        def blocked() -> bool:
            entered.set()
            return release.wait()

        executor = futures.ThreadPoolExecutor(max_workers=1)
        try:
            running = executor.submit(blocked)
            assert entered.wait(timeout=10)
            queued = [executor.submit(int) for _ in range(5)]
            executor.shutdown(wait=False, cancel_futures=True)
        finally:
            release.set()
            executor.shutdown()
        assert running.result(timeout=10) is True
        assert all(future.cancelled() for future in queued)


class TestFuture:
    """The Future rows: O(1) accessors returning stored objects, O(c) for
    completion and cancellation."""

    def test_result_is_the_stored_object(self) -> None:
        payload = list(range(1000))
        future: futures.Future[list[int]] = futures.Future()
        future.set_result(payload)
        assert future.result() is payload
        assert future.exception() is None
        assert future.done() and not future.running() and not future.cancelled()

    def test_exception_is_the_stored_exception(self) -> None:
        error = ValueError("bad")
        future: futures.Future[None] = futures.Future()
        future.set_exception(error)
        assert future.exception() is error
        with pytest.raises(ValueError) as raised:
            future.result()
        assert raised.value is error

    def test_a_second_result_is_rejected(self) -> None:
        future: futures.Future[int] = futures.Future()
        future.set_result(1)
        with pytest.raises(futures.InvalidStateError):
            future.set_result(2)

    def test_completion_runs_each_callback_once(self) -> None:
        calls: list[int] = []
        future: futures.Future[int] = futures.Future()
        for index in range(50):
            future.add_done_callback(lambda _, index=index: calls.append(index))
        assert calls == []
        future.set_result(0)
        assert calls == list(range(50))

    def test_cancel_runs_callbacks_and_fails_once_running(self) -> None:
        calls: list[bool] = []
        pending: futures.Future[int] = futures.Future()
        pending.add_done_callback(lambda done: calls.append(done.cancelled()))
        assert pending.cancel() is True
        assert calls == [True]
        assert pending.cancel() is True
        assert calls == [True]
        assert pending.set_running_or_notify_cancel() is False
        with pytest.raises(futures.CancelledError):
            pending.result()

        started: futures.Future[int] = futures.Future()
        assert started.set_running_or_notify_cancel() is True
        assert started.running()
        assert started.cancel() is False

    def test_an_early_callback_runs_in_the_completing_thread(self) -> None:
        seen: list[threading.Thread] = []
        future: futures.Future[int] = futures.Future()
        future.add_done_callback(lambda _: seen.append(threading.current_thread()))
        worker = threading.Thread(target=future.set_result, args=(1,))
        worker.start()
        worker.join()
        assert seen == [worker]

    def test_a_late_callback_runs_at_once_in_the_calling_thread(self) -> None:
        seen: list[threading.Thread] = []
        future: futures.Future[int] = futures.Future()
        future.set_result(1)
        future.add_done_callback(lambda _: seen.append(threading.current_thread()))
        assert seen == [threading.current_thread()]


class TestWaitingSortsOnce:
    """`wait()` and `as_completed()` | O(n log n) | O(n): one sort by `id()`
    over the distinct futures."""

    @pytest.fixture
    def sort_sizes(self, monkeypatch: pytest.MonkeyPatch) -> list[int]:
        sizes: list[int] = []

        def counting_sorted(iterable: Any, **kwargs: Any) -> list[Any]:
            result = sorted(iterable, **kwargs)
            sizes.append(len(result))
            return result

        monkeypatch.setattr(_base, "sorted", counting_sorted, raising=False)
        return sizes

    @staticmethod
    def finished(count: int) -> list[futures.Future[int]]:
        made: list[futures.Future[int]] = [futures.Future() for _ in range(count)]
        for future in made:
            future.set_result(0)
        return made

    def test_wait_sorts_once(self, sort_sizes: list[int]) -> None:
        done, not_done = futures.wait(self.finished(50))
        assert len(done) == 50 and not not_done
        assert sort_sizes == [50]

    def test_as_completed_sorts_once_and_collapses_duplicates(self, sort_sizes: list[int]) -> None:
        made = self.finished(50)
        assert len(list(futures.as_completed(made + made))) == 50
        assert sort_sizes == [50]

    def test_finished_futures_come_first(self) -> None:
        late: futures.Future[int] = futures.Future()
        early = self.finished(3)
        iterator = futures.as_completed([late, *early])
        first = [next(iterator) for _ in range(3)]
        assert set(first) == set(early)
        late.set_result(1)
        assert next(iterator) is late

    def test_wait_returns_early_when_the_condition_holds(self) -> None:
        done_ok, failed, pending = futures.Future(), futures.Future(), futures.Future()
        done_ok.set_result("ok")
        failed.set_exception(ValueError("bad"))
        result = futures.wait([done_ok, pending], return_when=futures.FIRST_COMPLETED)
        assert result.done == {done_ok} and result.not_done == {pending}
        result = futures.wait([done_ok, failed, pending], return_when=futures.FIRST_EXCEPTION)
        assert failed in result.done and pending in result.not_done

    @pytest.mark.timing
    def test_wait_grows_well_below_quadratic(self) -> None:
        costs = {
            n: best_ns(lambda made=self.finished(n): futures.wait(made), repeats=5)
            for n in (1_000, 10_000, 100_000)
        }
        for small, large in ((1_000, 10_000), (10_000, 100_000)):
            ratio = costs[large] / costs[small]
            assert ratio < 40, f"wait() on {small} -> {large} futures cost x{ratio:.1f}"


class TestConstantsAndExceptions:
    def test_return_when_constants_are_their_names(self) -> None:
        for name in ("FIRST_COMPLETED", "FIRST_EXCEPTION", "ALL_COMPLETED"):
            assert getattr(futures, name) == name

    def test_timeout_error_is_the_builtin_from_3_11(self) -> None:
        if sys.version_info >= (3, 11):
            assert futures.TimeoutError is TimeoutError
        else:
            assert futures.TimeoutError is not TimeoutError

    def test_broken_pools_share_a_base(self) -> None:
        from concurrent.futures import process, thread

        assert issubclass(thread.BrokenThreadPool, futures.BrokenExecutor)
        assert issubclass(process.BrokenProcessPool, futures.BrokenExecutor)
        assert issubclass(futures.BrokenExecutor, RuntimeError)
        if PY314:
            interpreter: Any = importlib.import_module("concurrent.futures.interpreter")
            assert issubclass(interpreter.BrokenInterpreterPool, thread.BrokenThreadPool)

    def test_executor_leaves_submit_to_subclasses(self) -> None:
        with pytest.raises(NotImplementedError):
            futures.Executor().submit(int)


@pytest.mark.skipif(not PY314, reason="InterpreterPoolExecutor is 3.14+")
class TestInterpreterPoolCopies:
    """`InterpreterPoolExecutor.submit`: arguments cross by copy or pickle."""

    def test_a_mutated_argument_is_a_copy(self) -> None:
        original: list[int] = []
        with futures.InterpreterPoolExecutor(max_workers=1) as executor:  # type: ignore[attr-defined]
            executor.submit(list.append, original, 1).result()
        assert original == []

    def test_the_worker_thread_pickles_the_arguments(self) -> None:
        pickled_in: list[str] = []

        class Recording:
            def __reduce__(self) -> Any:
                pickled_in.append(threading.current_thread().name)
                return (int, ())

        with futures.InterpreterPoolExecutor(max_workers=1) as executor:  # type: ignore[attr-defined]
            future = executor.submit(abs, cast(Any, Recording()))
            assert future.result() == 0
        assert pickled_in and threading.main_thread().name not in pickled_in


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
    """Each block runs in its own subprocess, so pools, threads and children
    cannot leak between them, and asserts its own result."""

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
        needle = "assert future.result() is payload"
        line, source = next((n, s) for n, s in _blocks() if needle in s)
        mutated = source.replace(needle, "assert future.result() is not payload", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
