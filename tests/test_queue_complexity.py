"""Tests for docs/stdlib/queue.md.

The page prices each queue class by the container under it: a deque for
`Queue`, a list used as a stack for `LifoQueue`, a list kept as a heap for
`PriorityQueue`, and a C buffer for `SimpleQueue`. The heap's O(log n)
comparisons are counted, which needs no tolerance; the O(1) ends are settled by
timing one put-and-get pair on queues a thousand times apart in length; the
blocking, task-tracking and shutdown rows are settled by threads that are
first seen registered as waiters on the queue's condition, then observed still
blocked, or returned normally, a moment later.

Measurement scope:

* Construction allocates nothing per slot: `Queue`, `LifoQueue` and
  `PriorityQueue` built with `maxsize=10**9`, and `SimpleQueue()`, each peak
  under 20 KB of traced allocation. The containers are asserted directly: a
  `deque` under `Queue`, a `list` under the other two, and `SimpleQueue` from
  the C `_queue` module.
* One `put()` followed by one `get()` costs the same on a queue holding 1,000
  items as on one holding 1,000,000, within 5x, for `Queue`, `LifoQueue` and
  `SimpleQueue`; a linear end would be 1,000x. Items are `None`, so no item
  allocation is timed.
* `PriorityQueue.put()` of a new minimum and `get()` each make between
  log2(n) - 1 and 2*log2(n) + 2 comparisons at n = 1,024 and 65,536, counted by
  `__lt__` on the items; the heap is built in ascending order, so the push
  climbs from a leaf to the root. `Queue.put()` into a queue of 100,000 items
  peaks under 5 KB.
* `full()` stays `False` for a queue of 10,000 items with `maxsize` 0 or -1, and
  `put_nowait()` never raises `Full` on it; `qsize()`, `empty()` and `full()`
  are asserted against the number of items put on a bounded queue.
* `task_done()` past the number of items put raises `ValueError`. `join()`
  returns at once with nothing outstanding, stays blocked for 0.1 s while one
  item taken by `get()` lacks its `task_done()`, and three threads blocked in
  it are all released by that one call.
* The worker-pool claim that a bounded queue caps pending work: a producer
  putting 100 items into `Queue(maxsize=4)` with no consumer is still blocked
  0.1 s later with exactly 4 items queued.
* On Python 3.13+, `shutdown()` makes `put()` raise `ShutDown`, lets `get()`
  return the items already queued and then raise, and releases threads
  blocked in `get()` on an empty queue and in `put()` on a full one with
  `ShutDown`. `shutdown(immediate=True)` is observed through a `Queue`
  subclass counting `_get()` calls: it removes each of 1,000 items exactly
  once, leaves `qsize()` at 0, and lets `join()` return when no item was
  taken; with one item taken and not marked done, `join()` stays blocked for
  0.1 s and returns after that item's `task_done()`.
* `SimpleQueue` returns items first-in-first-out, accepts `put(block=False)`
  and `put(timeout=0)` 10,000 times without raising, raises `Empty` from
  `get_nowait()` and from an expired `get()` timeout, and has no
  `task_done`, `join`, `maxsize` or `shutdown`.
* `Empty` and `Full` are asserted as what the non-blocking and timed calls
  raise. The claim that `Queue` differs from a `deque` by waiting, and the
  check-then-pop race, are covered by `TestQueueVersusDeque` in
  tests/test_stdlib_claims.py.
* Every fenced Python block runs in its own subprocess, the page's shutdown
  block only on 3.13+ where it does more than skip itself, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* That `SimpleQueue.put()` is safe to call from `__del__` or a signal handler
  is the reentrancy guarantee in the official documentation; no test can make
  a signal land inside a C call on demand.
* The w terms - `shutdown()` and the last `task_done()` waking every waiter
  with `Condition.notify_all()` - and the O(n log n) drain of
  `PriorityQueue.shutdown(immediate=True)` are read from Lib/queue.py.
  `SimpleQueue`'s amortized bounds are read from Modules/_queuemodule.c: a
  list compacted when half consumed before 3.13, a ring buffer that doubles
  and halves from 3.13. The timing test above shows the ends do not grow
  with n; it does not isolate the occasional resize.
* `LifoQueue` and `PriorityQueue` space is list growth, amortized, and not
  measured per call. As on heapq.md and list.md, a list resize is folded into
  the amortized bound rather than given as an O(n) worst case per call. Item comparison cost, lock contention between many
  threads, and timeouts that expire while other threads wait are not varied.
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
import tracemalloc
from collections import deque
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "queue.md"
EXPECTED_BLOCKS = 8
SHUTDOWN_BLOCK_MARKER = "q.shutdown(immediate=True)"


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 1_000) -> float:
    """Fastest of `repeats` runs, in nanoseconds per call."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        for _ in range(inner):
            func()
        elapsed = (time.perf_counter_ns() - start) / inner
        best = elapsed if best is None else min(best, elapsed)
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


def start_blocked(target: Callable[[], Any]) -> tuple[threading.Thread, threading.Event]:
    """Run target in a daemon thread; the event is set only if target returns."""
    done = threading.Event()

    def run() -> None:
        target()
        done.set()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, done


def wait_for_waiters(condition: threading.Condition, count: int) -> None:
    """Return once `count` threads are waiting on `condition`."""
    waiters = getattr(condition, "_waiters")  # noqa: B009 - private, untyped in the stubs
    deadline = time.monotonic() + 5
    while len(waiters) < count:
        assert time.monotonic() < deadline, f"{len(waiters)} of {count} threads are waiting"
        time.sleep(0.001)


class Counted:
    """An item whose `<` comparisons are counted."""

    comparisons = 0

    def __init__(self, value: int) -> None:
        self.value = value

    def __lt__(self, other: Counted) -> bool:
        Counted.comparisons += 1
        return self.value < other.value


class TestConstructionIsConstant:
    """`queue.Queue(maxsize=0)` | O(1) | O(1): nothing is sized by `maxsize`.

    A queue that reserved its slots would allocate gigabytes for a billion; the
    traced peak stays under 20 KB for every class.
    """

    @pytest.mark.parametrize("cls", [queue.Queue, queue.LifoQueue, queue.PriorityQueue])
    def test_a_huge_maxsize_reserves_nothing(self, cls: type[queue.Queue[Any]]) -> None:
        peak = peak_bytes(lambda: cls(maxsize=10**9))
        assert peak < 20_000, f"{cls.__name__}(maxsize=10**9) allocated {peak} bytes"

    def test_a_simple_queue_starts_small(self) -> None:
        peak = peak_bytes(queue.SimpleQueue)
        assert peak < 20_000, f"SimpleQueue() allocated {peak} bytes"

    def test_the_containers_are_the_documented_ones(self) -> None:
        assert type(queue.Queue().queue) is deque
        assert type(queue.LifoQueue().queue) is list
        assert type(queue.PriorityQueue().queue) is list
        assert queue.SimpleQueue.__module__ == "_queue", "SimpleQueue is the C type"


class TestTheEndsDoNotGrowWithTheQueue:
    """`Queue`, `LifoQueue` and `SimpleQueue` put and get are O(1), amortized for
    the list and the C buffer.

    One put-and-get pair on 1,000,000 queued items against 1,000: a linear end
    would cost 1,000x, and the assertion allows 5x.
    """

    @pytest.mark.timing
    @pytest.mark.parametrize("cls", [queue.Queue, queue.LifoQueue, queue.SimpleQueue])
    def test_a_put_and_get_costs_the_same_at_any_length(self, cls: type[Any]) -> None:
        costs: dict[int, float] = {}
        for size in (1_000, 1_000_000):
            q = cls()
            for _ in range(size):
                q.put(None)

            def pair(q: Any = q) -> None:
                q.put(None)
                q.get()

            costs[size] = best_ns(pair)
            assert q.qsize() == size

        ratio = costs[1_000_000] / costs[1_000]
        assert ratio < 5, f"{cls.__name__}: 1,000x the items cost x{ratio:.2f} ({costs})"

    def test_a_put_into_a_long_queue_allocates_little(self) -> None:
        q: queue.Queue[None] = queue.Queue()
        for _ in range(100_000):
            q.put(None)
        q.put(None)  # warm the method and the deque's current block

        peak = peak_bytes(lambda: q.put(None))

        assert peak < 5_000, f"put() into 100,000 items allocated {peak} bytes"

    def test_fifo_and_lifo_order(self) -> None:
        fifo: queue.Queue[int] = queue.Queue()
        lifo: queue.LifoQueue[int] = queue.LifoQueue()
        for item in range(5):
            fifo.put(item)
            lifo.put(item)
        assert [fifo.get() for _ in range(5)] == [0, 1, 2, 3, 4]
        assert [lifo.get() for _ in range(5)] == [4, 3, 2, 1, 0]


class TestPriorityQueueIsAHeap:
    """`PriorityQueue.put()` and `get()` | O(log n): a heap push and pop.

    Comparisons are counted on the items. A new minimum pushed onto a heap of
    n climbs to the root and a pop sifts a leaf down, so both counts sit near
    log2(n); O(1) would stay flat and O(n) would reach the thousands.
    """

    @pytest.mark.parametrize("exponent", [10, 16])
    def test_push_and_pop_compare_about_log_n_times(self, exponent: int) -> None:
        size = 2**exponent
        pq: queue.PriorityQueue[Counted] = queue.PriorityQueue()
        pq.queue.extend(Counted(value) for value in range(size))  # ascending: a valid heap

        Counted.comparisons = 0
        pq.put(Counted(-1))
        pushed = Counted.comparisons

        Counted.comparisons = 0
        smallest = pq.get()
        popped = Counted.comparisons

        assert smallest.value == -1
        low, high = exponent - 1, 2 * exponent + 2
        assert low <= pushed <= high, f"put() on {size} items made {pushed} comparisons"
        assert low <= popped <= high, f"get() on {size} items made {popped} comparisons"

    def test_the_smallest_item_comes_out_first(self) -> None:
        pq: queue.PriorityQueue[tuple[int, str]] = queue.PriorityQueue()
        for item in [(3, "low"), (1, "high"), (2, "medium")]:
            pq.put(item)
        assert [pq.get() for _ in range(3)] == [(1, "high"), (2, "medium"), (3, "low")]


class TestSizeAndBlocking:
    """`qsize()`, `empty()`, `full()` | O(1), and `put()` waits for room only on a
    bounded queue that is full.

    The snapshots are compared with the number of items put. The worker-pool
    claim is observed as a producer still blocked with exactly `maxsize` items
    queued.
    """

    def test_the_snapshots_track_the_items_put(self) -> None:
        q: queue.Queue[int] = queue.Queue(maxsize=3)
        assert q.empty() and not q.full() and q.qsize() == 0
        for item in range(3):
            q.put(item)
        assert q.qsize() == 3 and q.full() and not q.empty()

    @pytest.mark.parametrize("maxsize", [0, -1])
    def test_an_unbounded_queue_is_never_full(self, maxsize: int) -> None:
        q: queue.Queue[int] = queue.Queue(maxsize=maxsize)
        for item in range(10_000):
            q.put_nowait(item)
        assert q.qsize() == 10_000 and not q.full()

    def test_a_bounded_queue_caps_pending_work(self) -> None:
        q: queue.Queue[int] = queue.Queue(maxsize=4)

        def produce() -> None:
            for item in range(100):
                q.put(item)

        producer, done = start_blocked(produce)
        try:
            wait_for_waiters(q.not_full, 1)
            assert not done.wait(0.1), "the producer is still waiting for room"
            assert q.qsize() == 4
        finally:
            for _ in range(100):
                q.get(timeout=5)
            producer.join(5)
        assert done.is_set()

    def test_nowait_and_timeouts_raise_empty_and_full(self) -> None:
        q: queue.Queue[str] = queue.Queue(maxsize=1)
        with pytest.raises(queue.Empty):
            q.get_nowait()
        with pytest.raises(queue.Empty):
            q.get(timeout=0.01)
        q.put("item")
        with pytest.raises(queue.Full):
            q.put_nowait("more")
        with pytest.raises(queue.Full):
            q.put("more", timeout=0.01)


class TestTaskTracking:
    """`task_done()` | O(1) and `join()` | O(1): `join()` waits for every item put
    to have its `task_done()`, and the call finishing the last one wakes every
    thread in `join()`.
    """

    def test_join_returns_at_once_with_nothing_outstanding(self) -> None:
        q: queue.Queue[str] = queue.Queue()
        q.join()
        q.put("item")
        q.get()
        q.task_done()
        q.join()

    def test_join_waits_for_task_done_not_get(self) -> None:
        q: queue.Queue[str] = queue.Queue()
        q.put("item")
        assert q.get() == "item"

        joiners = [start_blocked(q.join) for _ in range(3)]
        try:
            wait_for_waiters(q.all_tasks_done, 3)
            assert not any(done.wait(0.1) for _, done in joiners), "taken is not finished"
        finally:
            q.task_done()
            for thread, _ in joiners:
                thread.join(5)
        assert all(done.is_set() for _, done in joiners), "one task_done() released all three"

    def test_an_extra_task_done_raises(self) -> None:
        q: queue.Queue[str] = queue.Queue()
        q.put("item")
        q.get()
        q.task_done()
        with pytest.raises(ValueError, match="too many times"):
            q.task_done()


# Python 3.13+; the tests using them are skipped before that.
SHUT_DOWN: type[Exception] = getattr(queue, "ShutDown", Exception)


def shut_down(q: queue.Queue[Any], immediate: bool = False) -> None:
    q.shutdown(immediate=immediate)  # pyright: ignore[reportAttributeAccessIssue]


class CountingQueue(queue.Queue[int]):
    """A Queue that counts the items removed from its container."""

    removed = 0

    def _get(self) -> int:
        self.removed += 1
        return super()._get()


@pytest.mark.skipif(sys.version_info < (3, 13), reason="Queue.shutdown() is Python 3.13+")
class TestShutdown:
    """`Queue.shutdown(immediate=False)` | O(w) and `shutdown(immediate=True)` |
    O(n + w), with `ShutDown` raised by `put()` and by `get()` once empty.

    The immediate drain is observed as one `_get()` per queued item; waking
    blocked threads is observed as each one returning with `ShutDown`.
    """

    def test_put_raises_and_get_drains_before_raising(self) -> None:
        q: queue.Queue[str] = queue.Queue()
        q.put("a")
        q.put("b")
        shut_down(q)

        with pytest.raises(SHUT_DOWN):
            q.put("c")
        assert q.get() == "a" and q.get() == "b"
        with pytest.raises(SHUT_DOWN):
            q.get()

    def test_blocked_callers_are_released(self) -> None:
        empty: queue.Queue[str] = queue.Queue()
        full: queue.Queue[str] = queue.Queue(maxsize=1)
        full.put("item")
        raised: list[type[BaseException]] = []

        def call(func: Callable[[], Any]) -> Callable[[], None]:
            def run() -> None:
                try:
                    func()
                except BaseException as error:  # noqa: BLE001 - recorded, asserted below
                    raised.append(type(error))

            return run

        getter, got = start_blocked(call(empty.get))
        putter, stored = start_blocked(call(lambda: full.put("more")))
        try:
            wait_for_waiters(empty.not_empty, 1)
            wait_for_waiters(full.not_full, 1)
            assert not got.wait(0.1) and not stored.wait(0.1), "both are waiting"
            shut_down(empty)
            shut_down(full)
            assert got.wait(5) and stored.wait(5)
        finally:
            getter.join(5)
            putter.join(5)
        assert raised == [SHUT_DOWN, SHUT_DOWN]

    def test_immediate_removes_each_item_once(self) -> None:
        q = CountingQueue()
        for item in range(1_000):
            q.put(item)

        shut_down(q, immediate=True)

        assert q.removed == 1_000
        assert q.qsize() == 0
        q.join()

    def test_immediate_join_still_waits_for_taken_items(self) -> None:
        q: queue.Queue[int] = queue.Queue()
        for item in range(3):
            q.put(item)
        q.get()
        shut_down(q, immediate=True)

        joiner, done = start_blocked(q.join)
        try:
            wait_for_waiters(q.all_tasks_done, 1)
            assert not done.wait(0.1), "the taken item has not had task_done()"
        finally:
            q.task_done()
            joiner.join(5)
        assert done.is_set()


class TestSimpleQueue:
    """`SimpleQueue` | O(1) amortized ends; `put()` never waits and ignores
    `block` and `timeout`; no task tracking, size limit or shutdown.
    """

    def test_put_ignores_block_and_timeout(self) -> None:
        sq: queue.SimpleQueue[int] = queue.SimpleQueue()
        for item in range(10_000):
            sq.put(item, block=False)
            sq.put(item, timeout=0)
        assert sq.qsize() == 20_000
        sq.put_nowait(-1)
        assert sq.qsize() == 20_001

    def test_get_is_fifo_and_raises_empty(self) -> None:
        sq: queue.SimpleQueue[str] = queue.SimpleQueue()
        sq.put("a")
        sq.put("b")
        assert sq.get() == "a" and sq.get_nowait() == "b" and sq.empty()
        with pytest.raises(queue.Empty):
            sq.get_nowait()
        with pytest.raises(queue.Empty):
            sq.get(timeout=0.01)

    def test_it_has_no_task_tracking_or_limit(self) -> None:
        sq: queue.SimpleQueue[str] = queue.SimpleQueue()
        for name in ("task_done", "join", "maxsize", "shutdown"):
            assert not hasattr(sq, name), name


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
    """Each block runs in its own subprocess and asserts its own result. The
    shutdown block guards itself on `sys.version_info`, so it is only counted
    as exercised on 3.13+; the threaded blocks join or `join()` before they
    assert, so none of them depends on timing.
    """

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            if SHUTDOWN_BLOCK_MARKER in source and sys.version_info < (3, 13):
                continue  # the block would only skip its own body
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        expected = EXPECTED_BLOCKS if sys.version_info >= (3, 13) else EXPECTED_BLOCKS - 1
        assert ran == expected
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "lifo.get() for _" in s)
        original = "== ['c', 'b', 'a']"
        mutated = source.replace(original, "== ['a', 'b', 'c']", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
