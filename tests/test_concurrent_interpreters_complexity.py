"""Tests for docs/stdlib/concurrent.interpreters.md.

The module exists from Python 3.14, so this file skips on older interpreters.
The page prices every crossing as linear in the data that crosses, because
values arrive as copies, and every call that enters an interpreter from the
main thread on glibc Linux as linear in the process's memory mappings too.
Copying is settled by identity and mutation checks, a size-dependent cost by
timing the same call on payloads more than four orders of magnitude apart, the
mapping term by timing calls with and without 20,000 extra mappings, and the
fixed rows by observation.

Measurement scope:

* `prepare_main()`, `call()` and a queue's `put()` + `get()` are timed with a
  1,000-byte and a 20,000,000-byte `bytes` value, the fastest of ten runs
  each; the large one costs more than 20x, where a shared reference would
  cost the same. `prepare_main()` and `call()` are timed from a worker thread,
  where the mapping term below is absent, and measure x395 to x455 and x136 to
  x173 on 3.14.10 and 3.15.2 on aarch64; the queue does not enter an
  interpreter, is timed from the main thread, and measures x749 to x1,623.
  That excludes a constant-cost transfer; that the growth is linear rather than faster is
  read from the copy paths, not asserted. The returned or received object is
  not the one sent, a dict sent through a queue arrives equal and distinct,
  and a `memoryview` of a `bytearray` sees a later write to the original.
* `create()` alone, with `close()` outside the timer, is timed against
  `call()` of a trivial function on an existing interpreter and costs more
  than 20x. No argument of its own moves it; the process's mappings do. Both
  run on the main thread at the process's ambient mapping count, as does the
  `close()` comparison below; each side pays the `v` term.
* `list_all()` gains one entry per `create()` and loses it on `close()`;
  `get_current()` is the main interpreter while one is held.
* `close()` makes `exec()` raise `InterpreterNotFoundError`; its O(m) is
  timed as an interpreter holding 1,000,000 objects against an empty one,
  more than 1.2x.
* The `v` term, on glibc Linux only: `prepare_main()` of 1,000 bytes,
  `exec("pass")` and `call(len, ...)` of 1,000 bytes are timed from the main
  thread before and while 20,000 extra two-page mappings are held, and from a
  worker thread before and while they are held, each the fastest of 20 runs.
  The main thread's cost must grow more than 5x, the worker thread's less
  than 3x, and with the mappings held the main thread's must exceed the
  worker thread's by more than 20x. On 3.14.10 and 3.15.2 on aarch64 they
  measure x291 to x449, x0.92 to x1.09, and x866 to x7,655. `create()` and
  `close()`, the fastest of three, must grow more than 2x on the main thread
  and less than 2x on a worker thread, and exceed the worker thread's by more
  than 2x; they measure x8.5 to x11.9, x0.81 to x1.01, and x10.8 to x15.9.
  Neighbouring mappings alternate between read-only and read-write so the
  kernel cannot merge them, and the helper asserts the count rose.
* `is_shareable()` answers `True` for a tuple holding a list, which
  `prepare_main()` then rejects with `NotShareableError`; it is timed on
  1,000- and 100,000-element tuples, under 3x apart.
* `exec()` of an uncaught `ValueError` raises `ExecutionFailed` whose
  `excinfo` carries the type name and message. `call_in_thread()` of a
  queue's `get` returns a started `threading.Thread`; `is_running()` is true
  while that call waits and false once it returns.
* A `maxsize=1` queue is `full()` after one `put()` and raises `QueueFull`
  from `put_nowait()`; an empty one raises `QueueEmpty` from `get_nowait()`,
  and from `get(timeout=0.9)` in under 0.6s, the timeout truncated to zero.
  `QueueEmpty` and `QueueFull` subclass `queue.Empty` and `queue.Full`.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* `exec()`'s O(p) is compilation of the source, read from the interpreter's
  exec path; it is not timed.
* The official documentation names `QueueEmptyError` and `QueueFullError`;
  the module defines `QueueEmpty` and `QueueFull`, which the page uses. The
  audit reports the two documented names as unresolved.
* Payload shape is not varied beyond flat `bytes` and a small dict; nested
  pickled values are priced by pickle.
* That `v` drops out on other platforms is source-only: `hardware_stack_limits()`
  in `Python/ceval.c` (v3.14.10, v3.15.2) reads the stack bounds with
  `GetCurrentThreadStackLimits()` on Windows and `pthread_get_stackaddr_np()`
  on macOS, and does not call `pthread_getattr_np()` on musl. The timing job
  runs on Linux only, so no run here times another platform.
* The mapping term is varied in count only: the mappings are untouched,
  anonymous and two pages each, and how many times `create()` and `close()`
  scan them is not pinned.
"""

from __future__ import annotations

import contextlib
import importlib
import mmap
import pathlib
import platform
import queue
import re
import subprocess
import sys
import textwrap
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any, ClassVar

import pytest

if sys.version_info < (3, 14):
    pytest.skip("version: concurrent.interpreters is new in Python 3.14", allow_module_level=True)
interpreters: Any = importlib.import_module("concurrent.interpreters")

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "concurrent.interpreters.md"
EXPECTED_BLOCKS = 4

SMALL = b"x" * 1_000
LARGE = b"x" * 20_000_000


def best_ns(func: Callable[[], Any], repeats: int = 5) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best = float("inf")
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        best = min(best, time.perf_counter_ns() - start)
    return best


def in_worker_thread(func: Callable[[], Any]) -> Any:
    """Run func on a new thread, not the main one, and return its result."""
    results: list[Any] = []
    worker = threading.Thread(target=lambda: results.append(func()))
    worker.start()
    worker.join()
    assert len(results) == 1, "the worker thread raised"
    return results[0]


def mapping_count() -> int:
    """Lines of /proc/self/maps: the memory mappings in this process."""
    with open("/proc/self/maps", encoding="ascii") as maps:
        return sum(1 for _ in maps)


@contextlib.contextmanager
def extra_mappings(count: int) -> Iterator[None]:
    """Hold `count` more memory mappings for the duration, then release them.

    Each mapping is two untouched pages, so none of its pages becomes
    resident. Neighbours alternate between read-only and read-write, so the kernel
    cannot merge adjacent ones into a single entry.
    """
    before = mapping_count()
    held = [
        mmap.mmap(-1, 2 * mmap.PAGESIZE, prot=mmap.PROT_READ | (mmap.PROT_WRITE * (n % 2)))
        for n in range(count)
    ]
    try:
        assert mapping_count() >= before + count * 9 // 10, "the mappings merged"
        yield
    finally:
        for mapping in held:
            mapping.close()


@pytest.fixture
def interp() -> Iterator[Any]:
    created = interpreters.create()
    try:
        yield created
    finally:
        created.close()


class TestInterpretersAreCostlyToCreate:
    """`create()` | O(v): the most expensive call on the page."""

    def test_list_all_tracks_create_and_close(self) -> None:
        before = len(interpreters.list_all())
        created = interpreters.create()
        assert len(interpreters.list_all()) == before + 1
        created.close()
        assert len(interpreters.list_all()) == before

    def test_the_current_interpreter_is_main_here(self) -> None:
        main = interpreters.get_main()
        assert interpreters.get_current() is main
        assert main.whence == "runtime init"
        assert isinstance(main.id, int)

    @pytest.mark.timing
    def test_create_dwarfs_a_call(self, interp: Any) -> None:
        call = best_ns(lambda: interp.call(int))

        create = float("inf")
        for _ in range(3):
            start = time.perf_counter_ns()
            created = interpreters.create()
            create = min(create, time.perf_counter_ns() - start)
            created.close()
        assert create > 20 * call, f"create {create:.0f}ns, call {call:.0f}ns"

    def test_a_closed_interpreter_is_gone(self) -> None:
        created = interpreters.create()
        created.close()
        with pytest.raises(interpreters.InterpreterNotFoundError):
            created.exec("pass")

    @pytest.mark.timing
    def test_close_grows_with_what_the_interpreter_holds(self) -> None:
        def close_cost(objects: int) -> float:
            costs = []
            for _ in range(3):
                created = interpreters.create()
                created.exec(f"held = [object() for _ in range({objects})]")
                start = time.perf_counter_ns()
                created.close()
                costs.append(time.perf_counter_ns() - start)
            return min(costs)

        empty = close_cost(0)
        full = close_cost(1_000_000)
        assert full > 1.2 * empty, f"close: {empty:.0f}ns empty, {full:.0f}ns holding 1e6"


class TestValuesCrossAsCopies:
    """`prepare_main()`, `call()`, `Queue.put()`/`get()` | O(s)."""

    @pytest.mark.timing
    def test_prepare_main_is_linear_in_the_value(self, interp: Any) -> None:
        small, large = in_worker_thread(
            lambda: (
                best_ns(lambda: interp.prepare_main(data=SMALL), 10),
                best_ns(lambda: interp.prepare_main(data=LARGE), 10),
            )
        )
        assert large > 20 * small, f"prepare_main: {small:.0f}ns vs {large:.0f}ns"

    @pytest.mark.timing
    def test_call_is_linear_in_the_arguments(self, interp: Any) -> None:
        small, large = in_worker_thread(
            lambda: (
                best_ns(lambda: interp.call(len, SMALL), 10),
                best_ns(lambda: interp.call(len, LARGE), 10),
            )
        )
        assert large > 20 * small, f"call: {small:.0f}ns vs {large:.0f}ns"

    @pytest.mark.timing
    def test_a_queue_round_trip_is_linear_in_the_item(self) -> None:
        channel = interpreters.create_queue()

        def round_trip(item: bytes) -> Callable[[], None]:
            def run() -> None:
                channel.put(item)
                channel.get()

            return run

        small = best_ns(round_trip(SMALL), 10)
        large = best_ns(round_trip(LARGE), 10)
        assert large > 20 * small, f"queue: {small:.0f}ns vs {large:.0f}ns"

    def test_received_objects_are_new(self, interp: Any) -> None:
        channel = interpreters.create_queue()
        payload = {"rows": [1, 2, 3]}
        channel.put(payload)
        received = channel.get()
        assert received == payload and received is not payload
        channel.put(SMALL)
        assert channel.get() is not SMALL
        assert interp.call(bytes, SMALL) is not SMALL

    def test_a_memoryview_shares_its_buffer(self) -> None:
        channel = interpreters.create_queue()
        buffer = bytearray(b"abc")
        channel.put(memoryview(buffer))
        received = channel.get()
        buffer[0] = ord("z")
        assert bytes(received) == b"zbc"

    def test_is_shareable_checks_the_outer_type_only(self, interp: Any) -> None:
        assert interpreters.is_shareable(([],)) is True
        with pytest.raises(interpreters.NotShareableError):
            interp.prepare_main(nested=([],))
        interp.prepare_main(flat=(1, "a"))
        interp.exec("assert flat == (1, 'a')")

    @pytest.mark.timing
    def test_is_shareable_does_not_walk_a_tuple(self) -> None:
        short = tuple(range(1_000))
        long = tuple(range(100_000))
        small = best_ns(lambda: interpreters.is_shareable(short))
        large = best_ns(lambda: interpreters.is_shareable(long))
        assert large < 3 * small, f"is_shareable: {small:.0f}ns vs {large:.0f}ns"


GLIBC_MAIN_THREAD = (
    "platform: glibc's pthread_getattr_np() reads /proc/self/maps to find the main thread's stack"
)
ON_GLIBC = platform.libc_ver()[0] == "glibc"
EXTRA_MAPPINGS = 20_000


@pytest.mark.skipif(not ON_GLIBC, reason=GLIBC_MAIN_THREAD)
class TestMainThreadCrossingsScanTheMappings:
    """`create()`, `close()`, `prepare_main()`, `exec()`, `call()` | the `+ v` term.

    Each is timed from the main thread and from a worker thread, with and
    without 20,000 extra memory mappings. The main thread's cost has to grow
    with the mappings, the worker thread's has to stay flat, and with the
    mappings held the main thread's has to stay far above the worker's.
    """

    CROSSINGS: ClassVar[dict[str, Callable[[Any], Callable[[], Any]]]] = {
        "prepare_main": lambda interp: lambda: interp.prepare_main(data=SMALL),
        "exec": lambda interp: lambda: interp.exec("pass"),
        "call": lambda interp: lambda: interp.call(len, SMALL),
    }

    @pytest.mark.timing
    @pytest.mark.parametrize("name", sorted(CROSSINGS))
    def test_a_main_thread_crossing_pays_for_every_mapping(self, interp: Any, name: str) -> None:
        crossing = self.CROSSINGS[name](interp)
        few = best_ns(crossing, 20)
        worker_few = in_worker_thread(lambda: best_ns(crossing, 20))
        with extra_mappings(EXTRA_MAPPINGS):
            many = best_ns(crossing, 20)
            worker = in_worker_thread(lambda: best_ns(crossing, 20))

        assert many > 5 * few, f"{name}: {few:.0f}ns, {many:.0f}ns with {EXTRA_MAPPINGS} more"
        assert worker < 3 * worker_few, f"{name}: worker {worker_few:.0f}ns, then {worker:.0f}ns"
        assert many > 20 * worker, f"{name}: main {many:.0f}ns, worker thread {worker:.0f}ns"

    @pytest.mark.timing
    def test_create_and_close_pay_for_every_mapping(self) -> None:
        def costs() -> tuple[float, float]:
            create = close = float("inf")
            for _ in range(3):
                start = time.perf_counter_ns()
                created = interpreters.create()
                create = min(create, time.perf_counter_ns() - start)
                start = time.perf_counter_ns()
                created.close()
                close = min(close, time.perf_counter_ns() - start)
            return create, close

        few = costs()
        worker_few = in_worker_thread(costs)
        with extra_mappings(EXTRA_MAPPINGS):
            many = costs()
            worker = in_worker_thread(costs)

        for index, name in enumerate(("create", "close")):
            assert many[index] > 2 * few[index], f"{name}: {few[index]:.0f}ns, {many[index]:.0f}ns"
            assert worker[index] < 2 * worker_few[index], (
                f"{name}: worker {worker_few[index]:.0f}ns, then {worker[index]:.0f}ns"
            )
            assert many[index] > 2 * worker[index], (
                f"{name}: main {many[index]:.0f}ns, worker thread {worker[index]:.0f}ns"
            )


class TestExecutionAndThreads:
    def test_an_uncaught_exception_comes_back_summarised(self, interp: Any) -> None:
        with pytest.raises(interpreters.ExecutionFailed) as raised:
            interp.exec('raise ValueError("boom")')
        assert raised.value.excinfo.type.__name__ == "ValueError"
        assert raised.value.excinfo.msg == "boom"
        assert issubclass(interpreters.ExecutionFailed, interpreters.InterpreterError)

    def test_call_in_thread_returns_a_started_thread(self, interp: Any) -> None:
        gate = interpreters.create_queue()
        worker = interp.call_in_thread(gate.get)
        try:
            assert isinstance(worker, threading.Thread)
            deadline = time.monotonic() + 10
            while not interp.is_running():
                assert time.monotonic() < deadline, "the call never started"
                time.sleep(0.001)
        finally:
            gate.put(None)
            worker.join()
        assert not interp.is_running()


class TestQueues:
    """The Queue rows: bounded, O(1) counters, and whole-second timeouts."""

    def test_a_bounded_queue_fills(self) -> None:
        channel = interpreters.create_queue(maxsize=1)
        assert channel.maxsize == 1 and channel.empty() and not channel.full()
        channel.put(1)
        assert channel.full() and channel.qsize() == 1
        with pytest.raises(interpreters.QueueFull):
            channel.put_nowait(2)
        assert channel.get() == 1
        with pytest.raises(interpreters.QueueEmpty):
            channel.get_nowait()

    def test_a_sub_second_timeout_does_not_wait(self) -> None:
        channel = interpreters.create_queue()
        start = time.monotonic()
        with pytest.raises(interpreters.QueueEmpty):
            channel.get(timeout=0.9)
        assert time.monotonic() - start < 0.6

    def test_queue_errors_are_the_queue_modules(self) -> None:
        assert issubclass(interpreters.QueueEmpty, queue.Empty)
        assert issubclass(interpreters.QueueFull, queue.Full)

    def test_a_queue_crosses_by_id(self, interp: Any) -> None:
        channel = interpreters.create_queue()
        interp.prepare_main(channel=channel)
        interp.exec("channel.put(channel.id)")
        assert channel.get() == channel.id


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
    """Each block runs in its own subprocess and asserts its own result."""

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
        needle = "assert received == payload and received is not payload"
        line, source = next((n, s) for n, s in _blocks() if needle in s)
        mutated = source.replace(needle, "assert received is payload", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
