"""Tests for docs/stdlib/concurrent.interpreters.md.

The module exists from Python 3.14, so this file skips on older interpreters.
The page prices creation as a large fixed cost and every crossing as linear in
the data that crosses, because values arrive as copies. Copying is settled by
identity and mutation checks, linearity by timing the same call on payloads
more than four orders of magnitude apart, and the fixed rows by observation.

Measurement scope:

* `prepare_main()`, `call()` and a queue's `put()` + `get()` are timed with a
  1,000-byte and a 50,000,000-byte `bytes` value; the large one costs more
  than 20x, where a shared reference would cost the same. That excludes a
  constant-cost transfer; that the growth is linear rather than faster is
  read from the copy paths, not asserted. The returned or received object is
  not the one sent, a dict sent through a queue arrives equal and distinct,
  and a `memoryview` of a `bytearray` sees a later write to the original.
* `create()` alone, with `close()` outside the timer, is timed against
  `call()` of a trivial function on an existing interpreter and costs more
  than 20x; it takes no argument whose size could move it.
* `list_all()` gains one entry per `create()` and loses it on `close()`;
  `get_current()` is the main interpreter while one is held.
* `close()` makes `exec()` raise `InterpreterNotFoundError`; its O(m) is
  timed as an interpreter holding 1,000,000 objects against an empty one,
  more than 1.2x.
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
"""

from __future__ import annotations

import pathlib
import queue
import re
import subprocess
import sys
import textwrap
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any

import pytest

interpreters: Any = pytest.importorskip("concurrent.interpreters")

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "concurrent.interpreters.md"
EXPECTED_BLOCKS = 4

SMALL = b"x" * 1_000
LARGE = b"x" * 50_000_000


def best_ns(func: Callable[[], Any], repeats: int = 5) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best = float("inf")
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        best = min(best, time.perf_counter_ns() - start)
    return best


@pytest.fixture
def interp() -> Iterator[Any]:
    created = interpreters.create()
    try:
        yield created
    finally:
        created.close()


class TestInterpretersAreCostlyToCreate:
    """`create()` | O(1): fixed, but the most expensive call on the page."""

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
        small = best_ns(lambda: interp.prepare_main(data=SMALL))
        large = best_ns(lambda: interp.prepare_main(data=LARGE))
        assert large > 20 * small, f"prepare_main: {small:.0f}ns vs {large:.0f}ns"

    @pytest.mark.timing
    def test_call_is_linear_in_the_arguments(self, interp: Any) -> None:
        small = best_ns(lambda: interp.call(len, SMALL))
        large = best_ns(lambda: interp.call(len, LARGE))
        assert large > 20 * small, f"call: {small:.0f}ns vs {large:.0f}ns"

    @pytest.mark.timing
    def test_a_queue_round_trip_is_linear_in_the_item(self) -> None:
        channel = interpreters.create_queue()

        def round_trip(item: bytes) -> Callable[[], None]:
            def run() -> None:
                channel.put(item)
                channel.get()

            return run

        small = best_ns(round_trip(SMALL))
        large = best_ns(round_trip(LARGE))
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
