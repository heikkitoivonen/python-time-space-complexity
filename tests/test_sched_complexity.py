"""Tests for docs/stdlib/sched.md.

The page prices a `scheduler` as a `heapq` heap of events: entering one is a
push, running one is a pop, `cancel()` rebuilds the heap and `queue` sorts a
copy of it. Every time bound is settled by counting comparisons, with event
times that count their own `__eq__` and `__lt__` calls; that needs no
tolerance and does not depend on the machine. Space bounds are settled by
traced allocation, and the ordering and callback rows by observation.

Measurement scope:

* `enterabs()` of an event earlier than every queued one makes exactly
  2·log2(n) comparisons (one `==`, one `<` per level of the sift) on heaps of
  2^8, 2^12 and 2^16 events, where a scan of the largest could make 2^16.
  Ten thousand more `enterabs()` calls retain within 3x of each other on
  queues of 1,000 and 100,000 events (the list's own growth is the
  difference), so the per-event space does not grow with the queue.
* `enter()` calls `timefunc()` once and queues the event at that time plus
  the delay.
* `cancel()` of the next event due, which the scan finds first, makes more
  than 5x and less than 20x the comparisons on a 10,000-event heap than on a
  1,000-event one: the heap rebuild is linear even at the front, and not
  quadratic. Heap times are shuffled with a fixed seed. Its traced peak on a
  100,000-event queue stays under 1 KB. Cancelling an event that already ran,
  or was already cancelled, raises `ValueError`, and a distinct `Event` equal
  to a queued one cancels it as the one `enter()` returned does.
* `run()` over shuffled times makes comparisons per event that grow by 1.3x to
  3x from 2^8 to 2^14 events: log2 grows 1.75x there, where a constant per
  event gives 1x and a linear scan per event 64x. Tracing starts before the
  queue is built, so the list shrinking as events pop is not counted as new
  allocation, and every event stays referenced, so none is freed for a
  temporary to hide under: the peak above the built queue over 20,000 events
  stays under 10 KB, against a queue of several megabytes.
* `run()` calls `delayfunc(0)` after each action and a positive delay before
  each event not yet due, on the calling thread, and the actions run on that
  thread too. `run(blocking=False)` on a clock at 5 with events at 1, 2 and 10
  runs two actions and returns 5, the delay rather than the deadline, and
  `None` once the queue is empty; with one due event on a 2^14-event heap it
  makes fewer than 100 comparisons, which is the O(1 + d log n) bound at
  d = 1, and with none due it makes at most 4.
* `queue` makes comparisons per event that grow by 1.3x to 3x from 2^8 to
  2^14 events, as `run()` does, and returns a new list on every read, in run
  order. Its traced peak lies between 8 and 100 bytes per queued event on a
  100,000-event queue, and `empty()` makes no comparison and its peak there
  stays under 1 KB.
* Events at equal times run by priority, lower first, then in the order they
  were entered; `Event` carries the six fields the page names, and
  `sched.scheduler()` defaults to `time.monotonic` and `time.sleep`.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.
* The page-scoped API audit reports no missing names. `sched.Event` and its
  six fields are runtime discoveries outside the official inventory, which
  the audit lists for classification; the page documents them because
  `enter()` returns an `Event` and `queue` lists them.

Not settled here:

* Treating an event comparison as O(1) is the page's cost model: times are
  numbers. A time type with costly comparisons multiplies every bound by that
  cost; only the counting type is used here.
* Time spent inside actions, including unpacking their arguments, and inside
  a real `delayfunc` is outside every bound on the page and is not measured.
  `timefunc()` is taken as O(1) and each wait as lasting what it was asked
  for: a `delayfunc` that returns early makes `run()` loop once more per
  return, which no bound counts.
* List growth under `enterabs()` and set growth in the page's lazy
  cancellation example are amortized, as they are on the list and heapq
  pages; single-call worst cases are not measured.
* Thread safety across concurrent callers is not exercised; the tests run
  one thread.
* The comparison counts use times drawn as a fixed-seed shuffle of distinct
  integers and priority 1 throughout; heaps full of equal times, which fall
  through to the priority and sequence fields, are not varied. `queue` order
  is checked on distinct times only, ties through `run()`, and
  `run(blocking=False)` is counted at d = 0 and d = 1, not across larger d.
"""

from __future__ import annotations

import heapq
import pathlib
import random
import re
import sched
import subprocess
import sys
import textwrap
import threading
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "sched.md"
EXPECTED_BLOCKS = 6


class CountingTime:
    """An event time that counts the comparisons made on it."""

    calls = 0
    __slots__ = ("value",)

    def __init__(self, value: int) -> None:
        self.value = value

    def __eq__(self, other: object) -> bool:
        CountingTime.calls += 1
        assert isinstance(other, CountingTime)
        return self.value == other.value

    def __lt__(self, other: CountingTime) -> bool:
        CountingTime.calls += 1
        return self.value < other.value

    def __gt__(self, other: CountingTime) -> bool:
        CountingTime.calls += 1
        return self.value > other.value

    def __sub__(self, other: CountingTime) -> int:
        return self.value - other.value

    __hash__ = None  # type: ignore[assignment]


def noop() -> None:
    pass


class Clock:
    """Simulated time: sleeping advances the clock instead of waiting."""

    def __init__(self) -> None:
        self.now: float = 0

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def counting_scheduler(size: int, now: int = 10**9) -> tuple[sched.scheduler, list[Any]]:
    """A scheduler holding `size` events at shuffled distinct counted times.

    The clock reads `now`, so every event is already due by default.
    """

    def clock() -> Any:
        return CountingTime(now)

    scheduler = sched.scheduler(clock, lambda _: None)
    values = list(range(1, size + 1))
    random.Random(size).shuffle(values)
    events = [scheduler.enterabs(at(value), 1, noop) for value in values]
    return scheduler, events


def at(value: int) -> Any:
    """A counted time, typed loosely: typeshed declares event times as float."""
    return CountingTime(value)


def when(event: Any) -> int:
    """The integer behind an event's counted time."""
    return event.time.value


def comparisons(func: Callable[[], Any]) -> int:
    CountingTime.calls = 0
    func()
    return CountingTime.calls


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class TestEnteringIsAHeapPush:
    """`enterabs()` and `enter()` | O(log n) | O(1)."""

    @pytest.mark.parametrize("exponent", [8, 12, 16])
    def test_a_new_earliest_event_sifts_up_log_n_levels(self, exponent: int) -> None:
        scheduler, _ = counting_scheduler(2**exponent)

        count = comparisons(lambda: scheduler.enterabs(at(0), 1, noop))

        assert count == 2 * exponent, f"2^{exponent} events: {count} comparisons"

    def test_what_an_event_retains_does_not_grow_with_the_queue(self) -> None:
        retained = []
        for size in (1_000, 100_000):
            scheduler = sched.scheduler()
            for index in range(size):
                scheduler.enterabs(index, 1, noop)
            tracemalloc.start()
            try:
                for index in range(10_000):
                    scheduler.enterabs(-index, 1, noop)
                retained.append(tracemalloc.get_traced_memory()[0])
            finally:
                tracemalloc.stop()

        ratio = max(retained) / min(retained)
        assert ratio < 3, f"10,000 events on 1,000 and 100,000 retained {retained}"

    def test_enter_reads_the_clock_once_and_adds_the_delay(self) -> None:
        reads: list[None] = []

        def timefunc() -> int:
            reads.append(None)
            return 100

        scheduler = sched.scheduler(timefunc, lambda _: None)

        event = scheduler.enter(5, 1, noop)

        assert len(reads) == 1
        assert event.time == 105

    def test_enterabs_returns_the_queued_event(self) -> None:
        scheduler = sched.scheduler()

        event = scheduler.enterabs(7, 3, noop, argument=(1,), kwargs={"k": 2})

        assert scheduler.queue == [event]
        assert (event.time, event.priority, event.action) == (7, 3, noop)
        assert (event.argument, event.kwargs) == ((1,), {"k": 2})


class TestCancelRebuildsTheHeap:
    """`cancel()` | O(n) | O(1) - even for the next event due."""

    def test_cancelling_the_front_is_linear_in_the_queue(self) -> None:
        counts = []
        for size in (1_000, 10_000):
            scheduler, events = counting_scheduler(size)
            front = min(events, key=when)
            counts.append(comparisons(lambda s=scheduler, e=front: s.cancel(e)))

        ratio = counts[1] / counts[0]
        assert 5 < ratio < 20, f"10x the queue cost x{ratio:.1f} comparisons: {counts}"

    def test_the_heap_stays_valid_after_a_cancel(self) -> None:
        scheduler, events = counting_scheduler(1_000)
        scheduler.cancel(events[500])

        values = [when(event) for event in scheduler.queue]

        assert len(values) == 999
        assert values == sorted(values)

    def test_cancel_allocates_nothing_that_grows(self) -> None:
        scheduler = sched.scheduler()
        events = [scheduler.enterabs(index, 1, noop) for index in range(100_000)]
        scheduler.cancel(events[0])  # warm

        peak = peak_bytes(lambda: scheduler.cancel(events[50_000]))

        assert peak < 1_000, f"cancel() on 100,000 events peaked at {peak} bytes"

    def test_an_event_that_already_ran_cannot_be_cancelled(self) -> None:
        clock = Clock()
        scheduler = sched.scheduler(clock.time, clock.sleep)
        event = scheduler.enter(1, 1, noop)
        scheduler.run()

        with pytest.raises(ValueError):
            scheduler.cancel(event)

    def test_an_event_cannot_be_cancelled_twice(self) -> None:
        scheduler = sched.scheduler()
        event = scheduler.enterabs(1, 1, noop)
        scheduler.cancel(event)

        with pytest.raises(ValueError):
            scheduler.cancel(event)

    def test_an_equal_event_from_queue_cancels_too(self) -> None:
        scheduler = sched.scheduler()
        scheduler.enterabs(1, 1, noop)

        found = sched.Event(*scheduler.queue[0])
        assert found is not scheduler.queue[0]
        assert found == scheduler.queue[0]

        scheduler.cancel(found)

        assert scheduler.empty()


class TestRunPopsEachEvent:
    """`run()` | O(n log n) | O(1); `run(blocking=False)` | O(1 + d log n) | O(1)."""

    def test_comparisons_per_event_grow_like_log_n(self) -> None:
        per_event = []
        for exponent in (8, 14):
            scheduler, _ = counting_scheduler(2**exponent)
            per_event.append(comparisons(scheduler.run) / 2**exponent)

        ratio = per_event[1] / per_event[0]
        assert 1.3 < ratio < 3, f"2^8 to 2^14 events: per-event comparisons x{ratio:.2f}"

    def test_running_allocates_nothing_that_grows(self) -> None:
        tracemalloc.start()
        try:
            scheduler = sched.scheduler(lambda: 10**12, lambda _: None)
            # Held here, so popping frees no event for a temporary to hide under.
            events = [scheduler.enterabs(index, 1, noop) for index in range(20_000)]
            built = tracemalloc.get_traced_memory()[0]
            tracemalloc.reset_peak()
            scheduler.run()
            peak = tracemalloc.get_traced_memory()[1] - built
        finally:
            tracemalloc.stop()

        assert scheduler.empty()
        assert len(events) == 20_000
        assert built > 1_000_000, f"the queue traced only {built} bytes"
        assert peak < 10_000, f"run() over 20,000 events peaked {peak} bytes above the queue"

    def test_delayfunc_zero_follows_every_action_on_the_calling_thread(self) -> None:
        clock = Clock()
        calls: list[tuple[str, object, int]] = []

        def delay(seconds: float) -> None:
            calls.append(("delay", seconds, threading.get_ident()))
            clock.sleep(seconds)

        def action(name: str) -> None:
            calls.append(("action", name, threading.get_ident()))

        scheduler = sched.scheduler(clock.time, delay)
        scheduler.enterabs(0, 1, action, argument=("a",))
        scheduler.enterabs(3, 1, action, argument=("b",))

        scheduler.run()

        me = threading.get_ident()
        assert calls == [
            ("action", "a", me),
            ("delay", 0, me),
            ("delay", 3, me),
            ("action", "b", me),
            ("delay", 0, me),
        ]

    def test_non_blocking_returns_the_delay_not_the_deadline(self) -> None:
        clock = Clock()
        scheduler = sched.scheduler(clock.time, clock.sleep)
        ran: list[int] = []
        for when in (1, 2, 10):
            scheduler.enterabs(when, 1, ran.append, argument=(when,))

        clock.now = 5
        assert scheduler.run(blocking=False) == 5
        assert ran == [1, 2]

        clock.now = 10
        assert scheduler.run(blocking=False) is None
        assert ran == [1, 2, 10]

    def test_non_blocking_touches_only_the_due_events(self) -> None:
        scheduler, _ = counting_scheduler(2**14, now=1)

        count = comparisons(lambda: scheduler.run(blocking=False))

        assert scheduler.run(blocking=False) == 1  # the next event is at 2, the clock at 1
        assert len(scheduler.queue) == 2**14 - 1
        assert count < 100, f"one due event of 2^14 took {count} comparisons"

    def test_non_blocking_with_nothing_due_is_constant(self) -> None:
        scheduler, _ = counting_scheduler(2**14, now=0)

        count = comparisons(lambda: scheduler.run(blocking=False))

        assert len(scheduler.queue) == 2**14
        assert count <= 4, f"nothing due of 2^14 took {count} comparisons"

    def test_equal_times_run_by_priority_then_entry_order(self) -> None:
        clock = Clock()
        scheduler = sched.scheduler(clock.time, clock.sleep)
        ran: list[str] = []
        scheduler.enter(10, 1, ran.append, argument=("ten",))
        scheduler.enterabs(5, 2, ran.append, argument=("low",))
        scheduler.enterabs(5, 1, ran.append, argument=("high",))
        scheduler.enterabs(5, 1, ran.append, argument=("entered later",))

        scheduler.run()

        assert ran == ["high", "entered later", "low", "ten"]

    def test_the_queue_is_a_heapq_heap(self) -> None:
        scheduler, events = counting_scheduler(1_000)

        # The private list is where the heap shows.
        heap = scheduler._queue  # type: ignore[attr-defined]  # noqa: SLF001

        assert sorted(heap, key=when) == sorted(events, key=when)
        assert all(not heap[child] < heap[(child - 1) // 2] for child in range(1, len(heap)))
        assert heapq.heappop(heap) is min(events, key=when)


class TestInspectingTheQueue:
    """`queue` | O(n log n) | O(n); `empty()` | O(1) | O(1)."""

    def test_comparisons_per_event_grow_like_log_n(self) -> None:
        per_event = []
        for exponent in (8, 14):
            scheduler, _ = counting_scheduler(2**exponent)
            per_event.append(comparisons(lambda s=scheduler: s.queue) / 2**exponent)

        ratio = per_event[1] / per_event[0]
        assert 1.3 < ratio < 3, f"2^8 to 2^14 events: per-event comparisons x{ratio:.2f}"

    def test_queue_is_a_new_sorted_list_on_every_read(self) -> None:
        scheduler, events = counting_scheduler(100)

        first = scheduler.queue

        assert first is not scheduler.queue
        assert first == sorted(events, key=when)

    def test_queue_memory_follows_the_queue_and_empty_s_does_not(self) -> None:
        scheduler = sched.scheduler()
        for index in range(100_000):
            scheduler.enterabs(index, 1, noop)
        scheduler.empty()
        _ = scheduler.queue

        queue_peak = peak_bytes(lambda: scheduler.queue)
        empty_peak = peak_bytes(scheduler.empty)

        assert 8 * 100_000 < queue_peak < 100 * 100_000, f"queue peaked at {queue_peak} bytes"
        assert empty_peak < 1_000, f"empty() allocated {empty_peak} bytes"

    def test_empty_compares_nothing(self) -> None:
        scheduler, _ = counting_scheduler(1_000)

        assert comparisons(scheduler.empty) == 0
        assert scheduler.empty() is False
        assert sched.scheduler().empty() is True


class TestSchedulerAndEvent:
    """The constructor, its two attributes and the `Event` fields."""

    def test_defaults_are_monotonic_and_sleep(self) -> None:
        scheduler = sched.scheduler()

        assert scheduler.timefunc is time.monotonic
        assert scheduler.delayfunc is time.sleep

    def test_the_attributes_are_the_functions_given(self) -> None:
        clock = Clock()
        scheduler = sched.scheduler(clock.time, clock.sleep)

        assert scheduler.timefunc == clock.time
        assert scheduler.delayfunc == clock.sleep
        assert scheduler.empty()

    def test_event_fields(self) -> None:
        assert sched.Event._fields == (
            "time",
            "priority",
            "sequence",
            "action",
            "argument",
            "kwargs",
        )


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
    """Each block runs in its own subprocess, and every block that calls
    `run()` does so on a simulated clock, so none of them waits in real time;
    each asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "run(blocking=False) == 5" in s)
        mutated = source.replace("run(blocking=False) == 5", "run(blocking=False) == 10", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
