"""Tests for docs/stdlib/threading.md.

The page prices each call on top of the time it spends blocked, so the tests
assert what a call does rather than how long it takes: which waiters a wake
releases, where a timed-out waiter is removed from its queue, whether a call
returns at once, and what it allocates. Waiter queues are observed directly
by replacing a Condition's deque with one that records the index of every
removal, which settles the O(n) and O(q) terms with no stopwatch.

Measurement scope:

* An unstarted Thread has no ident, is not alive and is absent from
  ``enumerate()``; ``start()`` returns with the ident set to what the new
  thread sees from ``get_ident()``; the target runs once, in that thread,
  with its args and kwargs, where a direct ``run()`` runs it in the caller
  and a Thread without a target runs nothing. ``join()`` on a finished
  thread returns in under 2.5 seconds with a five-second timeout, and on a
  blocked one returns after its 50 ms timeout with the thread still alive.
  Timeout measurements allow 5 ms of native-clock rounding.
* Each of the eight deprecated aliases emits exactly one DeprecationWarning
  per call, and from 3.14 so does an argument to ``RLock()``.
  ``settrace_all_threads`` and ``setprofile_all_threads`` exist exactly from
  3.12, and ``RLock().locked`` and ``Condition().locked`` exactly from 3.14.
* A cancelled 10-second Timer is joined within two seconds and never calls
  its function; a 50 ms one calls it once, after at least 45 ms; a cancel
  that arrives while the function is running does not stop it.
* A free Lock is taken by a non-blocking acquire; a held one refuses it and
  gives up a 50 ms timed acquire after at least 45 ms. A free lock accepts
  TIMEOUT_MAX as a timeout, and TIMEOUT_MAX + 1 raises OverflowError from
  RLock, Event, Semaphore and Barrier alike, and from a ``join()`` on a live
  thread on Linux and macOS.
  Releasing an unheld lock raises RuntimeError; a ``with`` block whose body
  raises leaves the lock free; an RLock held three times by its owner
  refuses another thread until the third release.
* Event, Semaphore, BoundedSemaphore and Barrier each hold a Condition. A
  Condition's ``acquire``, ``release`` and (3.14) ``locked`` act on the
  wrapped lock, and a waiting thread leaves that lock free. ``notify(2)`` on
  six waiters wakes the two that arrived first and leaves four queued; after
  ``notify_all()`` on three waiters none returns while the notifier still
  holds the lock. A wait that times out behind 20 waiters is removed from
  index 20 of the deque, through ``Condition.wait``, ``Event.wait``,
  ``Semaphore.acquire`` and ``Barrier.wait`` alike. A semaphore may repeat
  its condition wait before its deadline clock expires; a controlled clock
  forces two waits, both removed at index 20, leaving the original 20
  waiters queued. Each ``notify_all`` removal is from index 0. ``wait_for``
  calls its predicate once when it is already true and once more per wakeup.
* A thread blocked in ``Event.wait(0.2)`` uses under 50 ms of its own CPU
  time (``time.thread_time``), where a thread spinning on ``is_set()``
  reaches 0.1 s of its own CPU time.
* Semaphore(2) grants two non-blocking acquires and refuses the third;
  ``release(2)`` on six waiters wakes exactly two; BoundedSemaphore raises
  ValueError on the release that would exceed its initial value.
* ``Event.wait()`` on a set event returns True in under 2.5 seconds with a
  five-second timeout, on a cleared one returns False after its 50 ms
  timeout, and ``set()`` wakes all five waiters.
* Two of three barrier parties wait without returning; the third's arrival
  returns the indices 0, 1 and 2 across the three and runs the action once,
  and the barrier serves a second cycle. ``abort()`` and ``reset()`` each
  raise BrokenBarrierError in both waiters still filling it; ``abort()``
  leaves the barrier broken and ``reset()`` does not. A 50 ms ``wait()``
  timeout that expires raises BrokenBarrierError and leaves the barrier
  broken for the next caller; an ``abort()`` issued while a party is inside
  the action returns only once the action has.
* A ``local`` subclass's ``__init__`` runs once at construction and once
  more in each of three threads on their first attribute access, with the
  original argument, and a value assigned in one thread is not seen in
  another.
* With five threads blocked, ``active_count()`` equals ``len(enumerate())``
  and both grew by five; ``current_thread()`` is ``main_thread()`` on the
  main thread and the Thread object inside a worker; ``get_ident()`` and
  ``get_native_id()`` match the main thread's attributes. One
  ``enumerate()`` call allocates at least 8 bytes more per extra thread
  between 50 and 500 blocked threads, where ``active_count()`` allocates the
  same at both to within 64 bytes.
* ``settrace()`` and ``setprofile()`` leave a running thread's hook
  untouched where the ``_all_threads`` forms install it there; a thread
  started afterwards sees the hook, and the getters return what was stored.
* ``stack_size(1 << 20)`` returns the previous size, ``stack_size(28 KiB)``
  raises ValueError and leaves the 1 MiB in place, and a bare
  ``stack_size()`` returns that 1 MiB and resets the size to 0.
* A replacement ``excepthook`` is called once for a thread that raises, with
  a four-field record whose ``thread`` is that Thread; the default hook
  prints at least 45 more lines for a 50-frame traceback than for a 5-frame
  one.
* Every fenced Python block runs in its own subprocess and must exit cleanly
  with nothing on stderr, and a mutated assertion in one of them is asserted
  to fail.

Not settled here:

* u, w and s themselves: a thread's start-up latency, how long a wait blocks
  and the stack an OS thread reserves are the scheduler's and the
  platform's, so the tests assert the documented floors (a timeout is
  honoured, a finished thread is joined at once) rather than any duration.
  The platform minimum stack size above 32 KiB is the C library's
  (``PTHREAD_STACK_MIN``); only a size below 32 KiB is asserted to raise.
* That the default build runs bytecode in one thread at a time and the
  free-threaded build does not: the pinned interpreter is the default
  build, and a parallel speed-up is a timing claim about the machine. The
  O(T) bound of ``settrace_all_threads()`` is read from Python/sysmodule.c,
  which walks every thread state.
* ``current_thread()`` from a thread that ``threading`` did not start, which
  returns a dummy object and needs a foreign thread to reach, and the cost
  of printing one traceback frame, which is the traceback module's.
* Not varied: lock contention between more than two threads, ``Thread``
  subclasses that override ``run()``, threads arriving at a barrier while it
  drains, daemon threads at interpreter shutdown, and the registry's
  history. ``enumerate()`` walks the ``_active`` dict's entries, and a dict
  keeps a deleted entry's slot until an insertion finds the table full and
  resizes it, so after a burst of threads a call also walks the burst's
  vacated slots, and starting one more thread does not compact them
  (Objects/dictobject.c). T counts live threads only.
* API coverage is the page-scoped audit's, which reports no missing names.
  Its unclassified runtime names are left off the page on purpose:
  ``WeakSet`` and its methods (an import, not API), the ``Lock`` aliases
  ``acquire_lock``, ``release_lock`` and ``locked_lock`` (undocumented C
  spellings of the documented methods) and the struct-sequence fields of
  ``ExceptHookArgs``, which the record's row covers.

Every helper thread here is a daemon, so a failing assertion that leaves one
blocked cannot hang the interpreter at exit.
"""

from __future__ import annotations

import functools
import pathlib
import re
import subprocess
import sys
import textwrap
import threading
import time
import tracemalloc
import warnings
from collections import deque
from collections.abc import Callable, Iterator
from typing import Any, cast

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "threading.md"
EXPECTED_BLOCKS = 7
WAIT = 5.0
SHORT = 0.05
# Native waits (notably Windows' millisecond waits) and perf_counter use
# different clock resolutions. A 5 ms allowance still excludes immediate return.
SHORT_MIN = SHORT * 0.9


def wait_until(predicate: Callable[[], bool], timeout: float = WAIT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.001)
    return predicate()


def spawn(target: Callable[..., object], *args: object) -> threading.Thread:
    """Start a daemon thread, so a test that fails cannot hang the process at exit."""
    thread = threading.Thread(target=target, args=args, daemon=True)
    thread.start()
    return thread


def join_all(threads: list[threading.Thread]) -> None:
    for thread in threads:
        thread.join(WAIT)
    stuck = [thread for thread in threads if thread.is_alive()]
    assert not stuck, f"{len(stuck)} threads did not finish: {stuck}"


def waiters_of(condition: threading.Condition) -> deque[Any]:
    return cast("Any", condition)._waiters


def condition_of(primitive: object) -> threading.Condition:
    """The Condition inside an Event or a Semaphore."""
    return cast("Any", primitive)._cond


def traced_peak(func: Callable[[], Any]) -> int:
    tracemalloc.start()
    tracemalloc.reset_peak()
    try:
        func()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak


@pytest.fixture
def gate() -> Iterator[threading.Event]:
    """An Event that releases every thread blocked on it when the test ends."""
    event = threading.Event()
    yield event
    event.set()


class TestThreadsStartAndJoin:
    """`Thread()` is O(1) and inert, `start()` returns with the thread running,
    `run()` calls the target once, and `join()` costs only the wait.

    Each row is settled by observation: idents, registry membership and which
    thread ran the target separate a started thread from a built one.
    """

    def test_a_thread_object_is_inert_until_started(self) -> None:
        calls: list[int] = []
        thread = threading.Thread(target=lambda: calls.append(1))

        assert thread.ident is None
        assert thread.native_id is None
        assert not thread.is_alive()
        assert thread not in threading.enumerate()
        assert calls == []

    def test_start_returns_with_the_thread_started_under_its_ident(
        self, gate: threading.Event
    ) -> None:
        seen: dict[str, object] = {}

        def target() -> None:
            seen["ident"] = threading.get_ident()
            seen["native"] = threading.get_native_id()
            seen["current"] = threading.current_thread()
            gate.wait()

        thread = spawn(target)
        try:
            assert thread.ident is not None
            assert thread.is_alive()
            assert thread in threading.enumerate()
            assert wait_until(lambda: "current" in seen)
            assert seen["ident"] == thread.ident
            assert seen["native"] == thread.native_id
            assert seen["current"] is thread
        finally:
            gate.set()
            join_all([thread])

    def test_run_calls_the_target_once_in_the_new_thread(self) -> None:
        calls: list[tuple[int, tuple[int, ...], dict[str, int]]] = []

        def target(*args: int, **kwargs: int) -> None:
            calls.append((threading.get_ident(), args, kwargs))

        thread = threading.Thread(target=target, args=(1, 2), kwargs={"k": 3}, daemon=True)
        thread.start()
        join_all([thread])

        assert calls == [(thread.ident, (1, 2), {"k": 3})]
        assert thread.ident != threading.get_ident()

    def test_a_direct_run_call_runs_the_target_in_the_caller(self) -> None:
        calls: list[int] = []
        threading.Thread(target=lambda: calls.append(threading.get_ident())).run()

        assert calls == [threading.get_ident()]

        threading.Thread().run()

    def test_join_is_immediate_on_a_finished_thread_and_waits_out_its_timeout(
        self, gate: threading.Event
    ) -> None:
        finished = spawn(lambda: None)
        finished.join()
        start = time.perf_counter()
        finished.join(WAIT)
        assert time.perf_counter() - start < WAIT / 2

        blocked = spawn(gate.wait)
        try:
            start = time.perf_counter()
            blocked.join(SHORT)
            elapsed = time.perf_counter() - start
            assert elapsed >= SHORT_MIN, elapsed
            assert blocked.is_alive()
        finally:
            gate.set()
            join_all([blocked])
        assert not blocked.is_alive()

    def test_the_attributes_are_plain_reads(self) -> None:
        thread = threading.Thread(name="named", daemon=True)

        assert thread.name == "named"
        assert thread.daemon is True
        thread.name = "renamed"
        thread.daemon = False
        assert (thread.name, thread.daemon) == ("renamed", False)


class TestDeprecatedAndVersionGatedNames:
    """The deprecated-alias rows and the Python 3.12+ and 3.14+ markers.

    Each alias is asserted to warn exactly once per call, and each gated name
    to exist exactly from the version its row names.
    """

    @pytest.mark.parametrize(
        "call",
        [
            lambda: threading.Thread().getName(),
            lambda: threading.Thread().setName("x"),
            lambda: threading.Thread().isDaemon(),
            lambda: threading.Thread().setDaemon(False),
            lambda: threading.activeCount(),
            lambda: threading.currentThread(),
            lambda: threading.Event().isSet(),
            lambda: _notify_all_alias(),
        ],
        ids=[
            "getName",
            "setName",
            "isDaemon",
            "setDaemon",
            "activeCount",
            "currentThread",
            "isSet",
            "notifyAll",
        ],
    )
    def test_each_deprecated_alias_warns_once_per_call(self, call: Callable[[], object]) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            call()

        assert [w.category for w in caught] == [DeprecationWarning]

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="version: deprecated from 3.14")
    def test_arguments_to_rlock_warn_from_3_14(self) -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            cast("Any", threading.RLock)(1)

        assert [w.category for w in caught] == [DeprecationWarning]

    def test_the_all_threads_hooks_exist_from_3_12(self) -> None:
        expected = sys.version_info >= (3, 12)

        assert hasattr(threading, "settrace_all_threads") is expected
        assert hasattr(threading, "setprofile_all_threads") is expected

    def test_rlock_and_condition_locked_exist_from_3_14(self) -> None:
        expected = sys.version_info >= (3, 14)

        assert hasattr(threading.RLock(), "locked") is expected
        assert hasattr(threading.Condition(), "locked") is expected


class TestTimerCancels:
    """`Timer.run()` is O(w + f) and `Timer.cancel()` ends a waiting timer at once.

    A 10-second timer joined within two seconds after a cancel separates an
    interrupted wait from one that runs out its interval.
    """

    def test_timer_cancel_ends_a_waiting_timer_at_once(self) -> None:
        calls: list[float] = []
        timer = threading.Timer(10, lambda: calls.append(time.perf_counter()))
        timer.daemon = True
        timer.start()
        timer.cancel()
        timer.join(2)

        assert not timer.is_alive()
        assert calls == []

    def test_timer_runs_its_function_once_after_the_interval(self) -> None:
        calls: list[float] = []
        start = time.perf_counter()
        timer = threading.Timer(SHORT, lambda: calls.append(time.perf_counter()))
        timer.daemon = True
        timer.start()
        join_all([timer])

        assert len(calls) == 1
        assert calls[0] - start >= SHORT_MIN

    def test_timer_cancel_does_not_stop_a_function_already_running(
        self, gate: threading.Event
    ) -> None:
        entered = threading.Event()
        calls: list[int] = []

        def function() -> None:
            entered.set()
            gate.wait()
            calls.append(1)

        timer = threading.Timer(0, function)
        timer.daemon = True
        timer.start()
        try:
            assert entered.wait(WAIT)
            timer.cancel()
            assert timer.is_alive()
        finally:
            gate.set()
            join_all([timer])
        assert calls == [1]


def _notify_all_alias() -> None:
    condition = threading.Condition()
    with condition:
        condition.notifyAll()


class TestLocksWaitOnlyWhenHeld:
    """Lock and RLock `acquire()` are O(w): immediate when free or, for an RLock,
    for its owner; `release()` is O(1); TIMEOUT_MAX bounds every blocking wait.
    """

    def test_acquire_is_immediate_when_free_and_waits_out_its_timeout_when_held(self) -> None:
        lock = threading.Lock()

        assert lock.acquire(blocking=False) is True
        assert lock.locked()
        assert lock.acquire(blocking=False) is False
        start = time.perf_counter()
        assert lock.acquire(timeout=SHORT) is False
        elapsed = time.perf_counter() - start
        assert elapsed >= SHORT_MIN, elapsed

        lock.release()
        assert not lock.locked()
        with pytest.raises(RuntimeError):
            lock.release()

    def test_a_release_lets_a_blocked_acquirer_through(self) -> None:
        lock = threading.Lock()
        lock.acquire()
        got: list[bool] = []
        thread = spawn(lambda: got.append(lock.acquire(timeout=WAIT)))

        assert not wait_until(lambda: bool(got), timeout=SHORT)
        lock.release()
        join_all([thread])
        assert got == [True]
        assert lock.locked()
        lock.release()

    def test_a_with_block_releases_the_lock_when_its_body_raises(self) -> None:
        lock = threading.Lock()

        with pytest.raises(ValueError), lock:
            raise ValueError("in the body")

        assert not lock.locked()

    def test_rlock_owner_reenters_and_others_wait_for_every_release(self) -> None:
        rlock = threading.RLock()
        for _ in range(3):
            assert rlock.acquire(blocking=False) is True

        def other_can_take_it() -> bool:
            result: list[bool] = []

            def attempt() -> None:
                taken = rlock.acquire(blocking=False)
                result.append(taken)
                if taken:
                    rlock.release()

            join_all([spawn(attempt)])
            return result[0]

        rlock.release()
        rlock.release()
        assert other_can_take_it() is False
        rlock.release()
        assert other_can_take_it() is True

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="version: RLock.locked() is 3.14+")
    def test_rlock_locked_exists_from_3_14(self) -> None:
        rlock = threading.RLock()
        locked = cast("Any", rlock).locked

        assert not locked()
        with rlock:
            assert locked()

    def test_timeout_max_is_the_largest_accepted_timeout(self) -> None:
        lock = threading.Lock()

        assert lock.acquire(timeout=threading.TIMEOUT_MAX) is True
        lock.release()
        with pytest.raises(OverflowError):
            lock.acquire(timeout=threading.TIMEOUT_MAX + 1)

    @pytest.mark.parametrize(
        "wait",
        [
            lambda gate: threading.RLock().acquire(timeout=threading.TIMEOUT_MAX + 1),
            lambda gate: threading.Event().wait(threading.TIMEOUT_MAX + 1),
            lambda gate: threading.Semaphore(0).acquire(timeout=threading.TIMEOUT_MAX + 1),
            lambda gate: threading.Barrier(2).wait(threading.TIMEOUT_MAX + 1),
        ],
        ids=["RLock", "Event", "Semaphore", "Barrier"],
    )
    def test_every_blocking_wait_rejects_a_timeout_above_timeout_max(
        self, wait: Callable[[threading.Event], object], gate: threading.Event
    ) -> None:
        with pytest.raises(OverflowError):
            wait(gate)

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="platform: Windows join() waits instead of rejecting the timeout",
    )
    def test_join_on_a_live_thread_rejects_a_timeout_above_timeout_max(
        self, gate: threading.Event
    ) -> None:
        """A live thread: up to 3.12 a finished thread's handle is gone and a
        timeout given to its join() is never looked at."""
        thread = spawn(gate.wait)
        try:
            with pytest.raises(OverflowError):
                thread.join(threading.TIMEOUT_MAX + 1)
        finally:
            gate.set()
            join_all([thread])


class RecordingDeque(deque[Any]):
    """A waiter queue that records where each removal found its item."""

    def __init__(self) -> None:
        super().__init__()
        self.removed_at: list[int] = []

    def remove(self, value: Any) -> None:
        self.removed_at.append(self.index(value))
        super().remove(value)


def _all_queued(gate: threading.Event, count: int) -> bool:
    """True once ``count`` threads are in the gate's waiter queue."""
    return len(waiters_of(condition_of(gate))) == count


def _queued(condition: threading.Condition, arrived: list[int], number: int) -> bool:
    """True once ``number`` waiters have both arrived and joined the waiter queue."""
    return len(arrived) == number and len(waiters_of(condition)) == number


def _woke_and_requeued(calls: list[int], condition: threading.Condition, expected: int) -> bool:
    """True once the predicate has run ``expected`` times and the waiter is queued again."""
    return len(calls) == expected and len(waiters_of(condition)) == 1


def start_waiters(
    condition: threading.Condition, count: int, woke: list[int]
) -> list[threading.Thread]:
    """``count`` daemon threads waiting on the condition, queued in index order."""
    arrived: list[int] = []

    def wait(index: int) -> None:
        with condition:
            arrived.append(index)
            condition.wait()
            woke.append(index)

    threads: list[threading.Thread] = []
    for index in range(count):
        threads.append(spawn(wait, index))
        assert wait_until(functools.partial(_queued, condition, arrived, index + 1))
    return threads


class TestConditionQueuesItsWaiters:
    """`notify(n)` is O(n) and wakes the n oldest, `notify_all()` is O(q), and a
    wait whose timeout expires pays O(q) to leave the queue.

    A RecordingDeque in place of the Condition's waiter queue records the index
    of every removal: index 0 for a wake, the waiter's own position for a
    timeout. That separates a front removal from a scan with no timing.
    """

    @pytest.mark.parametrize(
        "build",
        [threading.Event, threading.Semaphore, threading.BoundedSemaphore, threading.Barrier],
        ids=["Event", "Semaphore", "BoundedSemaphore", "Barrier"],
    )
    def test_the_other_primitives_are_built_on_a_condition(self, build: Callable[..., Any]) -> None:
        primitive = build(2) if build is threading.Barrier else build()

        assert isinstance(condition_of(primitive), threading.Condition)

    def test_acquire_release_and_locked_are_the_wrapped_locks(self) -> None:
        lock = threading.Lock()
        condition = threading.Condition(lock)

        assert condition.acquire(blocking=False) is True
        assert lock.locked()
        assert condition.acquire(blocking=False) is False
        if sys.version_info >= (3, 14):
            assert cast("Any", condition).locked() is True
        condition.release()
        assert not lock.locked()

    def test_a_waiter_leaves_the_lock_free_while_blocked(self) -> None:
        condition = threading.Condition()
        woke: list[int] = []
        threads = start_waiters(condition, 1, woke)
        try:
            # Blocking, not non-blocking: the waiter joins the queue a moment
            # before it releases the lock, and a timed acquire rides that out.
            assert condition.acquire(timeout=WAIT) is True
            condition.notify()
            condition.release()
        finally:
            with condition:
                condition.notify_all()
        join_all(threads)
        assert woke == [0]

    def test_notify_wakes_the_n_oldest_waiters_and_notify_all_the_rest(self) -> None:
        condition = threading.Condition()
        woke: list[int] = []
        threads = start_waiters(condition, 6, woke)
        try:
            with condition:
                condition.notify(2)
            assert wait_until(lambda: len(woke) == 2)
            assert sorted(woke) == [0, 1]
            assert not wait_until(lambda: len(woke) > 2, timeout=SHORT)
            assert len(waiters_of(condition)) == 4
        finally:
            with condition:
                condition.notify_all()
        join_all(threads)
        assert sorted(woke) == [0, 1, 2, 3, 4, 5]
        assert len(waiters_of(condition)) == 0

    def test_notify_all_wakes_waiters_that_must_each_retake_the_lock(self) -> None:
        condition = threading.Condition()
        woke: list[int] = []
        threads = start_waiters(condition, 3, woke)
        try:
            with condition:
                condition.notify_all()
                assert len(waiters_of(condition)) == 0
                assert not wait_until(lambda: bool(woke), timeout=SHORT)
        finally:
            with condition:
                condition.notify_all()
        join_all(threads)
        assert sorted(woke) == [0, 1, 2]

    def test_a_timed_out_wait_is_removed_from_behind_every_earlier_waiter(self) -> None:
        condition = threading.Condition()
        queue = RecordingDeque()
        cast("Any", condition)._waiters = queue
        woke: list[int] = []
        threads = start_waiters(condition, 20, woke)
        try:
            with condition:
                assert condition.wait(timeout=SHORT) is False
            assert queue.removed_at == [20]
        finally:
            with condition:
                condition.notify_all()
        join_all(threads)
        assert queue.removed_at == [20] + [0] * 20

    @pytest.mark.parametrize(
        ("build", "block", "timed", "release", "clock_ticks"),
        [
            (
                threading.Event,
                lambda event: event.wait(),
                lambda event: event.wait(SHORT),
                lambda event: event.set(),
                None,
            ),
            (
                lambda: threading.Semaphore(0),
                lambda semaphore: semaphore.acquire(),
                lambda semaphore: semaphore.acquire(timeout=SHORT),
                lambda semaphore: semaphore.release(20),
                None,
            ),
            (
                lambda: threading.Semaphore(0),
                lambda semaphore: semaphore.acquire(),
                lambda semaphore: semaphore.acquire(timeout=SHORT),
                lambda semaphore: semaphore.release(20),
                (0.0, SHORT / 2, SHORT),
            ),
        ],
        ids=["Event.wait", "Semaphore.acquire", "Semaphore.acquire-retry"],
    )
    def test_the_wrappers_timed_waits_pay_the_same_removal(
        self,
        build: Callable[[], Any],
        block: Callable[[Any], object],
        timed: Callable[[Any], bool],
        release: Callable[[Any], object],
        clock_ticks: tuple[float, ...] | None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Each timeout scans past the earlier waiters, including on a retry.

        Native lock waits and the deadline clock can have different resolutions.
        The controlled clock keeps half the timeout after the first wait and
        expires after the second, exercising that path on every platform.
        """
        primitive = build()
        queue = RecordingDeque()
        cast("Any", condition_of(primitive))._waiters = queue
        threads = [spawn(block, primitive) for _ in range(20)]
        try:
            assert wait_until(lambda: len(queue) == 20)
            with monkeypatch.context() as patch:
                if clock_ticks is not None:
                    ticks = iter(clock_ticks)
                    patch.setattr(threading, "_time", lambda: next(ticks))
                assert timed(primitive) is False
            assert set(queue.removed_at) == {20}
            assert len(queue) == 20
            if clock_ticks is not None:
                assert queue.removed_at == [20, 20]
        finally:
            release(primitive)
            join_all(threads)

    def test_a_barrier_timeout_pays_the_same_removal_before_breaking(self) -> None:
        """The expired party leaves from index 20; breaking then wakes the rest
        from index 0."""
        barrier = threading.Barrier(22)
        queue = RecordingDeque()
        cast("Any", condition_of(barrier))._waiters = queue
        outcomes: list[str] = []

        def wait() -> None:
            try:
                barrier.wait()
            except threading.BrokenBarrierError:
                outcomes.append("broken")

        threads = [spawn(wait) for _ in range(20)]
        try:
            assert wait_until(lambda: len(queue) == 20)
            with pytest.raises(threading.BrokenBarrierError):
                barrier.wait(SHORT)
        finally:
            barrier.abort()
        join_all(threads)
        assert queue.removed_at == [20] + [0] * 20
        assert outcomes == ["broken"] * 20

    def test_wait_for_calls_the_predicate_once_per_wakeup(self) -> None:
        condition = threading.Condition()
        flag = False
        calls: list[int] = []

        def predicate() -> bool:
            calls.append(1)
            return flag

        with condition:
            assert condition.wait_for(lambda: calls.append(1) or True) is True
        assert len(calls) == 1
        calls.clear()

        result: list[bool] = []

        def wait() -> None:
            with condition:
                result.append(condition.wait_for(predicate))

        thread = spawn(wait)
        try:
            assert wait_until(lambda: len(waiters_of(condition)) == 1)
            assert len(calls) == 1
            for expected in (2, 3):
                with condition:
                    condition.notify()
                assert wait_until(functools.partial(_woke_and_requeued, calls, condition, expected))
        finally:
            with condition:
                flag = True
                condition.notify()
        join_all([thread])
        assert result == [True]
        assert len(calls) == 4


class TestSemaphoreCountsAndWakesN:
    """`Semaphore.acquire()` is immediate while the counter is positive and
    `release(n)` is O(n): it wakes n waiters, not every one."""

    def test_acquire_is_immediate_while_the_counter_is_positive(self) -> None:
        semaphore = threading.Semaphore(2)

        assert semaphore.acquire(blocking=False) is True
        assert semaphore.acquire(blocking=False) is True
        assert semaphore.acquire(blocking=False) is False
        semaphore.release(2)
        assert semaphore.acquire(blocking=False) is True

    def test_release_wakes_exactly_n_waiters(self) -> None:
        semaphore = threading.Semaphore(0)
        acquired: list[int] = []

        def take(index: int) -> None:
            semaphore.acquire()
            acquired.append(index)

        threads = [spawn(take, index) for index in range(6)]
        condition = condition_of(semaphore)
        try:
            assert wait_until(lambda: len(waiters_of(condition)) == 6)

            semaphore.release(2)
            assert wait_until(lambda: len(acquired) == 2)
            assert not wait_until(lambda: len(acquired) > 2, timeout=SHORT)
            assert len(waiters_of(condition)) == 4
        finally:
            semaphore.release(6)
        join_all(threads)
        assert sorted(acquired) == [0, 1, 2, 3, 4, 5]

    def test_a_bounded_semaphore_refuses_to_exceed_its_initial_value(self) -> None:
        bounded = threading.BoundedSemaphore(1)
        plain = threading.Semaphore(1)

        with pytest.raises(ValueError):
            bounded.release()
        plain.release()
        assert plain.acquire(blocking=False) is True
        assert plain.acquire(blocking=False) is True
        assert plain.acquire(blocking=False) is False


class TestEventWakesEveryWaiter:
    """`Event.wait()` is immediate once set and `Event.set()` wakes all q waiters."""

    def test_wait_is_immediate_once_set_and_waits_out_its_timeout_otherwise(self) -> None:
        event = threading.Event()
        event.set()

        assert event.is_set()
        start = time.perf_counter()
        assert event.wait(WAIT) is True
        assert time.perf_counter() - start < WAIT / 2

        event.clear()
        assert not event.is_set()
        start = time.perf_counter()
        assert event.wait(SHORT) is False
        elapsed = time.perf_counter() - start
        assert elapsed >= SHORT_MIN, elapsed

    def test_a_blocked_wait_uses_no_cpu_where_polling_does(self) -> None:
        """CPU time of the waiting thread itself, so other load on the machine
        does not count. The polling control spins until its own CPU time reaches
        0.1 s, which shows the probe sees a spinning thread's time at all."""
        event = threading.Event()
        cpu: dict[str, float] = {}

        def blocked() -> None:
            start = time.thread_time()
            event.wait(0.2)
            cpu["blocked"] = time.thread_time() - start

        def polling() -> None:
            start = time.thread_time()
            deadline = time.monotonic() + WAIT
            while time.monotonic() < deadline and not event.is_set():
                if time.thread_time() - start >= 0.1:
                    break
            cpu["polling"] = time.thread_time() - start

        join_all([spawn(blocked)])
        join_all([spawn(polling)])

        assert cpu["blocked"] < 0.05, cpu
        assert cpu["polling"] >= 0.1, cpu

    def test_set_wakes_every_waiter(self) -> None:
        event = threading.Event()
        results: list[bool] = []
        threads = [spawn(lambda: results.append(event.wait())) for _ in range(5)]
        try:
            assert wait_until(lambda: len(waiters_of(condition_of(event))) == 5)
        finally:
            event.set()
        join_all(threads)
        assert results == [True] * 5


class TestBarrierReleasesOnTheLastParty:
    """`Barrier.wait()` returns when the last party arrives, which runs the action
    once; `reset()` and `abort()` wake every waiter and wait out a running action.
    """

    def test_the_last_party_releases_all_runs_the_action_once_and_the_barrier_is_reusable(
        self,
    ) -> None:
        actions: list[int] = []
        barrier = threading.Barrier(3, action=lambda: actions.append(1))
        indices: list[int] = []

        for cycle in (1, 2):
            threads = [spawn(lambda: indices.append(barrier.wait())) for _ in range(2)]
            try:
                assert wait_until(lambda: barrier.n_waiting == 2)
                assert len(indices) == 3 * (cycle - 1)
                assert len(actions) == cycle - 1
                assert barrier.parties == 3
                indices.append(barrier.wait())
            finally:
                if barrier.n_waiting:
                    barrier.abort()
            join_all(threads)
            assert sorted(indices[-3:]) == [0, 1, 2]
            assert len(actions) == cycle
            assert barrier.n_waiting == 0

    def test_abort_waits_for_a_running_action(self, gate: threading.Event) -> None:
        """The action runs under the barrier's lock, which abort() needs too."""
        entered = threading.Event()

        def action() -> None:
            entered.set()
            gate.wait()

        barrier = threading.Barrier(1, action=action)
        party = spawn(barrier.wait)
        aborted: list[int] = []
        try:
            assert entered.wait(WAIT)
            calling = threading.Event()
            aborter = spawn(lambda: (calling.set(), barrier.abort(), aborted.append(1)))
            assert calling.wait(WAIT)
            assert not wait_until(lambda: bool(aborted), timeout=SHORT)
        finally:
            gate.set()
        join_all([party, aborter])
        assert aborted == [1]
        assert barrier.broken

    def test_an_expired_timeout_breaks_the_barrier(self) -> None:
        barrier = threading.Barrier(2)

        with pytest.raises(threading.BrokenBarrierError):
            barrier.wait(SHORT)
        assert barrier.broken
        with pytest.raises(threading.BrokenBarrierError):
            barrier.wait(SHORT)

    @pytest.mark.parametrize("breaker", ["abort", "reset"])
    def test_abort_and_reset_wake_every_waiter_with_broken_barrier_error(
        self, breaker: str
    ) -> None:
        barrier = threading.Barrier(3)
        outcomes: list[str] = []

        def wait() -> None:
            try:
                barrier.wait()
            except threading.BrokenBarrierError:
                outcomes.append("broken")
            else:
                outcomes.append("released")

        threads = [spawn(wait) for _ in range(2)]
        try:
            assert wait_until(lambda: barrier.n_waiting == 2)
        finally:
            getattr(barrier, breaker)()
        join_all(threads)
        assert outcomes == ["broken", "broken"]
        assert barrier.broken is (breaker == "abort")
        if breaker == "abort":
            with pytest.raises(threading.BrokenBarrierError):
                barrier.wait()
            barrier.reset()
        assert not barrier.broken
        assert barrier.n_waiting == 0


class TestLocalIsPerThread:
    """One dict per thread; a subclass's __init__ runs again in each."""

    def test_each_thread_gets_its_own_dict_and_a_fresh_init(self, gate: threading.Event) -> None:
        """The workers stay alive together on the gate: glibc reuses a finished
        thread's ident, and four distinct idents is part of what is asserted."""
        inits: list[tuple[int, str]] = []

        class Context(threading.local):
            def __init__(self, user: str) -> None:
                inits.append((threading.get_ident(), user))
                self.user = user

        context = Context("default")
        assert inits == [(threading.get_ident(), "default")]

        seen: list[tuple[int, str, str]] = []

        def worker() -> None:
            before = context.user
            context.user = "worker"
            seen.append((threading.get_ident(), before, context.user))
            gate.wait()

        threads = [spawn(worker) for _ in range(3)]
        try:
            assert wait_until(lambda: len(seen) == 3)
        finally:
            gate.set()
        join_all(threads)

        assert context.user == "default"
        assert sorted(seen) == sorted(
            (thread.ident or 0, "default", "worker") for thread in threads
        )
        assert [user for _, user in inits] == ["default"] * 4
        assert len({ident for ident, _ in inits}) == 4

    def test_a_plain_local_hides_one_thread_s_attributes_from_another(self) -> None:
        data = threading.local()
        data.value = 1
        seen: list[object] = []

        def worker() -> None:
            seen.append(hasattr(data, "value"))
            data.value = 2

        join_all([spawn(worker)])

        assert seen == [False]
        assert data.value == 1


class TestRegistryCountsLiveThreads:
    """`active_count()` is O(1) where `enumerate()` builds an O(T) list; the other
    registry functions agree with them about which threads are alive."""

    def test_the_registry_functions_agree_about_who_is_alive(self, gate: threading.Event) -> None:
        before = threading.active_count()
        assert before == len(threading.enumerate())
        assert threading.current_thread() is threading.main_thread()
        assert threading.get_ident() == threading.main_thread().ident
        assert threading.get_native_id() == threading.main_thread().native_id

        unstarted = threading.Thread(target=gate.wait)
        threads = [spawn(gate.wait) for _ in range(5)]
        try:
            assert threading.active_count() == before + 5
            assert len(threading.enumerate()) == before + 5
            assert set(threads) <= set(threading.enumerate())
            assert unstarted not in threading.enumerate()
        finally:
            gate.set()
        join_all(threads)
        assert threading.active_count() == before

    def test_enumerate_allocates_per_thread_and_active_count_does_not(
        self, gate: threading.Event
    ) -> None:
        """A list of T references is at least 8 bytes per thread; a count is an int."""
        peaks: dict[int, tuple[int, int]] = {}
        for count in (50, 500):
            threads = [spawn(gate.wait) for _ in range(count)]
            try:
                # Measure only once every worker is queued on the gate, so no
                # thread is still allocating its way to the wait.
                assert wait_until(functools.partial(_all_queued, gate, count))
                peaks[count] = (
                    min(traced_peak(threading.enumerate) for _ in range(5)),
                    min(traced_peak(threading.active_count) for _ in range(5)),
                )
            finally:
                gate.set()
            join_all(threads)
            gate.clear()

        assert peaks[500][0] - peaks[50][0] >= 8 * 450, peaks
        assert abs(peaks[500][1] - peaks[50][1]) < 64, peaks


class TestHooksAndStackSizeApplyToLaterThreads:
    """`settrace()`/`setprofile()` reach threads started afterwards only, the
    `_all_threads` forms running ones too, and `stack_size()` returns the
    previous size."""

    @pytest.mark.parametrize(
        ("setter", "getter", "sys_setter", "sys_getter", "all_threads"),
        [
            ("settrace", "gettrace", sys.settrace, sys.gettrace, "settrace_all_threads"),
            ("setprofile", "getprofile", sys.setprofile, sys.getprofile, "setprofile_all_threads"),
        ],
        ids=["trace", "profile"],
    )
    def test_the_setter_reaches_new_threads_and_only_the_all_threads_form_running_ones(
        self,
        setter: str,
        getter: str,
        sys_setter: Callable[[Any], object],
        sys_getter: Callable[[], object],
        all_threads: str,
        gate: threading.Event,
    ) -> None:
        """threading's stored default and this thread's own sys hook are separate
        settings, saved and restored separately."""

        def hook(frame: Any, event: str, arg: Any) -> None:
            return None

        module = cast("Any", threading)
        seen: dict[str, object] = {}
        started = threading.Event()

        def spin() -> None:
            started.set()
            while not gate.is_set():
                seen["running"] = sys_getter()
                time.sleep(0.001)

        running = spawn(spin)
        previous = getattr(module, getter)()
        own = sys_getter()
        try:
            assert started.wait(WAIT)
            getattr(module, setter)(hook)
            assert getattr(module, getter)() is hook
            later = spawn(lambda: seen.__setitem__("later", sys_getter()))
            join_all([later])
            assert seen["later"] is hook
            assert not wait_until(lambda: seen.get("running") is hook, timeout=SHORT)

            if hasattr(module, all_threads):
                try:
                    getattr(module, all_threads)(hook)
                    assert wait_until(lambda: seen.get("running") is hook)
                finally:
                    getattr(module, all_threads)(previous)
                assert wait_until(lambda: seen.get("running") is previous)
        finally:
            getattr(module, setter)(previous)
            sys_setter(own)
            gate.set()
        join_all([running])
        assert getattr(module, getter)() is previous
        assert sys_getter() is own

    def test_stack_size_returns_the_previous_size_and_no_argument_means_the_default(self) -> None:
        previous = threading.stack_size()  # a bare call resets to 0, so put it back
        threading.stack_size(previous)
        try:
            assert threading.stack_size(1 << 20) == previous
            with pytest.raises(ValueError):
                threading.stack_size(28 * 1024)
            assert threading.stack_size() == 1 << 20
            assert threading.stack_size() == 0
        finally:
            threading.stack_size(previous)


class TestExceptHookSeesEachUnhandledException:
    """`excepthook()` is called once per unhandled exception with a four-field
    `ExceptHookArgs`, and the default hook's output grows with the traceback."""

    def test_a_replacement_hook_is_called_once_with_a_four_field_record(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[Any] = []
        monkeypatch.setattr(threading, "excepthook", calls.append)

        def fail() -> None:
            raise ValueError("in the thread")

        thread = spawn(fail)
        join_all([thread])

        assert len(calls) == 1
        args = calls[0]
        assert len(args) == 4
        assert args.exc_type is ValueError
        assert str(args.exc_value) == "in the thread"
        assert args.thread is thread

        built = threading.ExceptHookArgs((ValueError, ValueError("x"), None, thread))
        assert (built.exc_type, built.thread) == (ValueError, thread)
        assert len(built) == 4

    def test_the_default_hook_prints_at_least_a_line_per_frame(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """pytest swaps ``threading.excepthook`` for its own during a test, so the
        default hook is reached through ``threading.__excepthook__``."""

        def lines_for(depth: int) -> int:
            source = "\n".join(f"def f{i}():\n    return f{i + 1}()" for i in range(depth))
            source += f"\ndef f{depth}():\n    raise ValueError('deep')\n"
            namespace: dict[str, Any] = {}
            exec(source, namespace)
            try:
                namespace["f0"]()
            except ValueError as error:
                caught = error
            else:
                raise AssertionError("the generated chain did not raise")
            args = threading.ExceptHookArgs(
                (type(caught), caught, caught.__traceback__, threading.current_thread())
            )
            threading.__excepthook__(args)
            return len(capsys.readouterr().err.splitlines())

        shallow = lines_for(5)
        deep = lines_for(50)

        assert deep - shallow >= 45, (shallow, deep)

    def test_the_exception_names(self) -> None:
        assert threading.ThreadError is RuntimeError
        assert issubclass(threading.BrokenBarrierError, RuntimeError)
        assert threading.BrokenBarrierError is not RuntimeError


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
    """Every block runs under the interpreter running the tests, and its asserts hold."""

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
        source = _block_containing("condition.wait_for(lambda: items)")
        broken = source.replace("assert sorted(taken) == [0, 1, 2]", "assert taken == []", 1)
        assert broken != source, "the mutation did not change the assertion"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "AssertionError" in result.stderr
