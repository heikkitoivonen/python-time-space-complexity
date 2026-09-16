"""Tests to verify documented behaviour of the asyncio module.

docs/stdlib/asyncio.md prices the scheduling asyncio does around a coroutine,
never the coroutine or the I/O it waits on. Nothing here opens a socket or
spawns a process: streams are driven by feeding a `StreamReader` directly, and
the loop's two schedules are observed through their own containers. Most rows
are settled by counting or by identity rather than by a clock.

Measurement scope:

* The ready queue is a `deque` and the timer schedule is a heap, so a counting
  `heapq.heappush` substituted into `asyncio.base_events` separates the two
  with no tolerance: `call_soon` pushes 0, `call_later` pushes 1. `sleep(0)`
  pushes 0 and `sleep(0.001)` pushes 1, which is the whole of the two `sleep`
  rows. The substitution is asserted to have been reached before any count is
  believed.
* `TimerHandle.cancel()` leaves its entry on the heap, and two separate paths
  reclaim it. Cancelling the 33 earliest of 64 timers pops them from the head
  and leaves 31; cancelling the 33 *latest* leaves all 64, because the head
  stays live and 64 is under the bulk sweep's 100-timer minimum. The sweep
  itself is pinned at both of its thresholds: 101 cancelled of 200 reclaims
  them, 99 of 200 does not. Cancelling at the head is what the first case
  measures, so a test that cancels only the earliest entries would report the
  sweep working when it never ran.
* `gather`'s n is established by counting, not by a clock: a counting
  `loop.create_task` shows all seven wraps happening inside the `gather()` call
  and before the returned future is awaited. Timing it would have been weaker,
  because expanding the awaitables into positional arguments is itself O(n) and
  would move the measurement whatever `gather` did with them. `wait` is counted
  the same way: it partitions n inputs into two sets, and from 3.11 it refuses
  a bare coroutine.
* `all_tasks()` returns a new `set` on every call. `first == second` with
  `first is not second` settles the space column with no tolerance - a stored
  view would return the same object. `.copy()` on the result is the control
  that the comparison is not vacuous.
* `Event.set()` resolves every queued waiter. The waiter deque is read
  directly, so eight waiters is eight futures, and the count after `set()` is
  exact rather than timed. `Condition.notify(2)` is checked the same way.
* `Queue`, `LifoQueue` and `PriorityQueue` are distinguished by the order they
  return three items in: a deque returns insertion order, a list-as-stack
  reverses it, and a heap returns lowest first. Ordering alone would not
  separate a heap from a list kept sorted on every insert, so the heap rows are
  pinned separately by asserting the heap invariant on `PriorityQueue`'s own
  list - which a sorted list also satisfies - together with the partial order
  that distinguishes them: a heap's list is not sorted.
* The eager task factory is observed by appending to a list from inside the
  coroutine and from the caller. The default factory produces
  `["after", "body"]` and the eager one `["body", "after"]` for the same
  coroutine, which is the only claim the row makes.
* `readuntil` keeps an offset rather than rescanning. Feeding 200 to 1600
  chunks of 1,000 bytes holds the per-chunk cost flat across an 8x size range;
  a rescan would make it grow with the buffer. The assertion is on the ratio of
  per-chunk costs, which separates linear from quadratic by a wide margin.
* Cancellation is a request only as far as the coroutine is concerned. The
  call still forwards to the future the task is suspended on, and a `gather()`
  of n children cancels all n synchronously - timed at 10, 1,000 and 10,000
  children, which is where the O(1) row would have been wrong. `shield()` is
  checked by asserting the inner task's *result*, not merely that it survived.
* The `to_thread` overlap test compares three concurrent calls against one
  measured call in the same process rather than against a fixed millisecond
  budget, so a loaded machine moves both sides together. Overlap alone would
  not show the loop staying free, so a second test counts a ticker task's
  iterations while the thread blocks.
* `Semaphore.locked()` consults the waiter deque, not only the counter, and a
  test that leaves the counter at zero cannot tell the two apart. The test
  drives the counter *positive* while a woken waiter is still queued, so a
  counter-only implementation returns the wrong answer.
* The registry `all_tasks()` scans is not the same population on every
  supported version: through 3.13 a finished task stays in it while anything
  references it, and 3.14 drops it on completion. Both halves are asserted, so
  the version that changes is the one that fails.
* Dimensions these tests do *not* vary: the separator length and tuple size in
  the `readuntil` timing test, which uses a single one-byte separator; the
  number of done callbacks on a cancelled future; the transport behind
  `writelines`, which is only ever the default one here; and the item cost in
  every queue test, which uses small integers throughout.

Claims execution cannot settle here, and why:

* Every "+ round trip" row - `open_connection`, `start_server`,
  `create_connection`, `getaddrinfo`, `drain`, `start_tls`, `sendfile` and the
  subprocess spawns. Their local bound is reached only with a peer or a child
  process on the other side; no test here supplies one, and the round trip the
  page excludes is the part that dominates.
* The transport and protocol tables. Transports are created by the loop against
  a real socket, pipe or subprocess, and protocol methods are callbacks whose
  cost belongs to the application. The rows state what asyncio does around each
  call, which is a source-level fact about the selector event loop.
* `loop.sendfile` and `loop.sock_sendfile` falling back when the kernel call is
  unavailable, and `SendfileNotAvailableError`: which path is taken is a
  property of the platform, not of the call.
* `Runner.close()` and `loop.shutdown_asyncgens()` costs are covered for the
  task and generator counts they walk, but the executor shutdown they wait on
  is the thread pool's, not asyncio's.
* The Windows-only submodules `asyncio.windows_events` and
  `asyncio.windows_utils` cannot be imported on this platform, so the page's
  API audit reports two inspection errors here and its gate cannot pass on
  Linux. The official API inventory lists no public names under either module,
  so this is a platform limitation rather than a documentation gap: the page's
  scoped audit reports zero missing names.
* `asyncio.EventLoop` being the platform's loop class is asserted only as a
  loop class, since which class it is differs by platform.
"""

import asyncio
import asyncio.base_events
import asyncio.tasks
import contextlib
import heapq
import inspect
import pathlib
import re
import subprocess
import sys
import textwrap
import threading
import time
import warnings
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "asyncio.md"

EXPECTED_BLOCKS = 8


def api(name: str) -> Any:
    """An asyncio name typeshed does not offer at the 3.10 floor pyright checks."""
    return getattr(asyncio, name)


def internal(obj: Any, name: str) -> Any:
    """A private attribute a row is asserted through, such as a waiter deque."""
    return getattr(obj, name)


class CountingHeappush:
    """Records every push onto a heap while delegating to the real one."""

    def __init__(self, original: Any) -> None:
        self.pushes = 0
        self.original = original

    def __call__(self, heap: Any, item: Any) -> Any:
        self.pushes += 1
        return self.original(heap, item)


@contextlib.contextmanager
def counting_heappush() -> Any:
    """Count pushes onto the timer heap.

    `asyncio.base_events` reaches its heap through `import heapq`, so the
    module attribute is the single point both it and the queues go through.
    """
    original = heapq.heappush
    assert internal(asyncio.base_events, "heapq") is heapq, (
        "asyncio.base_events no longer reaches its heap through the heapq module"
    )
    counter = CountingHeappush(original)
    heapq.heappush = counter  # type: ignore[assignment]
    try:
        yield counter
    finally:
        heapq.heappush = original  # type: ignore[assignment]


class TestTheSchedulerIsADequeAndAHeap:
    """The two schedules, and the rows that differ only by which one is used."""

    def test_call_soon_does_not_touch_the_timer_heap(self) -> None:
        async def main() -> int:
            loop = asyncio.get_running_loop()
            with counting_heappush() as counter:
                loop.call_soon(lambda: None)
                return counter.pushes

        assert asyncio.run(main()) == 0

    def test_call_later_pushes_exactly_one_timer(self) -> None:
        async def main() -> int:
            loop = asyncio.get_running_loop()
            with counting_heappush() as counter:
                handle = loop.call_later(10, lambda: None)
                pushes = counter.pushes
            handle.cancel()
            return pushes

        assert asyncio.run(main()) == 1

    def test_call_at_pushes_one_timer_like_call_later(self) -> None:
        async def main() -> int:
            loop = asyncio.get_running_loop()
            with counting_heappush() as counter:
                handle = loop.call_at(loop.time() + 10, lambda: None)
                pushes = counter.pushes
            handle.cancel()
            return pushes

        assert asyncio.run(main()) == 1

    def test_the_counting_substitution_is_actually_reached(self) -> None:
        """A counter that never ran would make every count above a zero."""

        async def main() -> int:
            loop = asyncio.get_running_loop()
            with counting_heappush() as counter:
                assert heapq.heappush is counter
                handle = loop.call_later(10, lambda: None)
                pushes = counter.pushes
            handle.cancel()
            assert heapq.heappush is not counter, "the substitution was not restored"
            return pushes

        assert asyncio.run(main()) > 0

    def test_sleep_zero_schedules_no_timer(self) -> None:
        async def main() -> int:
            with counting_heappush() as counter:
                await asyncio.sleep(0)
                return counter.pushes

        assert asyncio.run(main()) == 0

    def test_a_positive_sleep_schedules_one_timer(self) -> None:
        async def main() -> int:
            with counting_heappush() as counter:
                await asyncio.sleep(0.001)
                return counter.pushes

        assert asyncio.run(main()) == 1

    def test_call_soon_appends_to_the_ready_deque(self) -> None:
        async def main() -> tuple[str, int]:
            loop = asyncio.get_running_loop()
            before = len(internal(loop, "_ready"))
            loop.call_soon(lambda: None)
            return type(internal(loop, "_ready")).__name__, len(internal(loop, "_ready")) - before

        name, added = asyncio.run(main())
        assert name == "deque"
        assert added == 1

    def test_the_timer_schedule_is_a_list_used_as_a_heap(self) -> None:
        async def main() -> tuple[str, list[float]]:
            loop = asyncio.get_running_loop()
            handles = [loop.call_later(delay, lambda: None) for delay in (5, 1, 3)]
            name = type(internal(loop, "_scheduled")).__name__
            # The heap invariant, not full sorted order: the earliest is first.
            deadlines = [handle.when() for handle in internal(loop, "_scheduled")]
            for handle in handles:
                handle.cancel()
            return name, deadlines

        name, deadlines = asyncio.run(main())
        assert name == "list"
        assert deadlines[0] == min(deadlines)

    def test_a_cancelled_timer_stays_on_the_heap(self) -> None:
        """cancel() clears the callback; it does not remove the entry."""

        async def main() -> tuple[int, int]:
            loop = asyncio.get_running_loop()
            handles = [loop.call_later(10 + i, lambda: None) for i in range(64)]
            before = len(internal(loop, "_scheduled"))
            handles[0].cancel()
            after = len(internal(loop, "_scheduled"))
            for handle in handles:
                handle.cancel()
            return before, after

        before, after = asyncio.run(main())
        assert before == 64
        assert after == 64

    def test_a_cancelled_head_entry_is_popped_every_iteration(self) -> None:
        """Cancelling the soonest timeouts costs nothing: they are at the head."""

        async def main() -> tuple[int, int]:
            loop = asyncio.get_running_loop()
            handles = [loop.call_later(100 + i, lambda: None) for i in range(64)]
            for handle in handles[:33]:  # the 33 earliest deadlines
                handle.cancel()
            before = len(internal(loop, "_scheduled"))
            await asyncio.sleep(0)
            after = len(internal(loop, "_scheduled"))
            for handle in handles:
                handle.cancel()
            return before, after

        before, after = asyncio.run(main())
        assert before == 64
        assert after == 31, f"the cancelled head run should be popped, heap is {after}"

    def test_entries_behind_a_live_timer_need_the_bulk_sweep(self) -> None:
        """Below its thresholds nothing reclaims them, which is the cost the page names."""

        async def main() -> tuple[int, int]:
            loop = asyncio.get_running_loop()
            handles = [loop.call_later(100 + i, lambda: None) for i in range(64)]
            for handle in handles[31:]:  # the 33 latest, so the head stays live
                handle.cancel()
            before = len(internal(loop, "_scheduled"))
            await asyncio.sleep(0)
            after = len(internal(loop, "_scheduled"))
            for handle in handles:
                handle.cancel()
            return before, after

        before, after = asyncio.run(main())
        assert before == 64
        assert after == 64, f"64 timers is under the sweep's 100 minimum, heap is {after}"

    def test_the_bulk_sweep_needs_both_thresholds(self) -> None:
        """More than 100 timers and over half cancelled; 99 of 200 is not enough."""

        async def sweep(cancel_from: int) -> int:
            loop = asyncio.get_running_loop()
            handles = [loop.call_later(100 + i, lambda: None) for i in range(200)]
            for handle in handles[cancel_from:]:  # always the latest, never the head
                handle.cancel()
            await asyncio.sleep(0)
            remaining = len(internal(loop, "_scheduled"))
            for handle in handles:
                handle.cancel()
            return remaining

        over_half = asyncio.run(sweep(99))  # 101 cancelled
        under_half = asyncio.run(sweep(101))  # 99 cancelled

        assert over_half == 99, f"101 of 200 cancelled should sweep, heap is {over_half}"
        assert under_half == 200, f"99 of 200 is under half, heap is {under_half}"


class TestHandles:
    """The Handle and TimerHandle rows."""

    def test_cancel_and_cancelled_are_flag_access(self) -> None:
        async def main() -> tuple[bool, bool]:
            loop = asyncio.get_running_loop()
            handle = loop.call_soon(lambda: None)
            before = handle.cancelled()
            handle.cancel()
            return before, handle.cancelled()

        before, after = asyncio.run(main())
        assert before is False
        assert after is True

    def test_a_cancelled_callback_does_not_run(self) -> None:
        async def main() -> list[str]:
            loop = asyncio.get_running_loop()
            ran: list[str] = []
            handle = loop.call_soon(ran.append, "kept")
            loop.call_soon(ran.append, "other")
            handle.cancel()
            await asyncio.sleep(0)
            return ran

        assert asyncio.run(main()) == ["other"]

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="Handle.get_context added in 3.12")
    def test_get_context_returns_the_context_scheduling_captured(self) -> None:
        """A fresh empty Context would satisfy an isinstance check, so read a value."""
        import contextvars

        marker: contextvars.ContextVar[str] = contextvars.ContextVar("marker")

        async def main() -> tuple[bool, str, str]:
            loop = asyncio.get_running_loop()
            marker.set("set before scheduling")
            handle = loop.call_soon(lambda: None)
            context = internal(handle, "get_context")()
            handle.cancel()

            # Changing the variable afterwards must not show through the capture.
            marker.set("set after scheduling")
            return (
                isinstance(context, contextvars.Context),
                context[marker],
                marker.get(),
            )

        is_context, captured, current = asyncio.run(main())
        assert is_context is True
        assert captured == "set before scheduling", "the scheduling context was not captured"
        assert current == "set after scheduling"

    def test_timer_handle_when_is_the_stored_deadline(self) -> None:
        async def main() -> float:
            loop = asyncio.get_running_loop()
            deadline = loop.time() + 10
            handle = loop.call_at(deadline, lambda: None)
            when = handle.when()
            handle.cancel()
            return when - deadline

        assert abs(asyncio.run(main())) < 1e-9


class TestGatherAndWaitAreLinear:
    """The n in the gather, wait and as_completed rows."""

    def test_gather_returns_results_in_argument_order(self) -> None:
        """Completion order is not argument order, and the row says argument order."""

        async def after(delay: float, value: int) -> int:
            await asyncio.sleep(delay)
            return value

        async def main() -> list[int]:
            return list(await asyncio.gather(after(0.03, 1), after(0.01, 2), after(0.02, 3)))

        assert asyncio.run(main()) == [1, 2, 3]

    def test_gather_wraps_every_awaitable_before_it_is_awaited(self) -> None:
        """The setup is eager: all n wraps happen in the call, not on the await."""

        async def value(x: int) -> int:
            return x

        async def main() -> int:
            loop = asyncio.get_running_loop()
            created = 0
            original = loop.create_task

            def counting(coro: Any, **kwargs: Any) -> Any:
                nonlocal created
                created += 1
                return original(coro, **kwargs)

            loop.create_task = counting  # type: ignore[method-assign]
            try:
                future = asyncio.gather(*[value(i) for i in range(7)])
                # Read the counter before awaiting: the row says the wrapping is
                # setup, so a gather that deferred it would show 0 here.
                eagerly = created
                await future
            finally:
                del loop.create_task  # type: ignore[attr-defined]
            return eagerly

        assert asyncio.run(main()) == 7

    def test_return_exceptions_collects_rather_than_propagates(self) -> None:
        async def boom() -> int:
            raise ValueError("no")

        async def fine() -> int:
            return 1

        async def main() -> list[Any]:
            return list(await asyncio.gather(boom(), fine(), return_exceptions=True))

        results = asyncio.run(main())
        assert isinstance(results[0], ValueError)
        assert results[1] == 1

    def test_wait_partitions_into_two_sets(self) -> None:
        async def main() -> tuple[int, int, type, type]:
            tasks = [asyncio.create_task(asyncio.sleep(0)) for _ in range(5)]
            done, pending = await asyncio.wait(tasks)
            return len(done), len(pending), type(done), type(pending)

        n_done, n_pending, done_type, pending_type = asyncio.run(main())
        assert (n_done, n_pending) == (5, 0)
        assert done_type is set and pending_type is set

    def test_first_completed_leaves_the_rest_pending(self) -> None:
        async def main() -> tuple[int, int]:
            slow = [asyncio.create_task(asyncio.sleep(10)) for _ in range(3)]
            quick = asyncio.create_task(asyncio.sleep(0))
            done, pending = await asyncio.wait([*slow, quick], return_when=asyncio.FIRST_COMPLETED)
            result = len(done), len(pending)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            return result

        assert asyncio.run(main()) == (1, 3)

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="coroutines allowed before 3.11")
    def test_wait_refuses_a_bare_coroutine_from_311(self) -> None:
        """Why wait's n is counted rather than timed the way gather's is."""

        async def main() -> None:
            async def value() -> int:
                return 1

            coro = value()
            try:
                with pytest.raises(TypeError):
                    await asyncio.wait([coro])  # type: ignore[arg-type]
            finally:
                coro.close()

        asyncio.run(main())

    def test_as_completed_yields_every_awaitable_once(self) -> None:
        async def value(x: int) -> int:
            return x

        async def main() -> list[int]:
            aws = [value(i) for i in range(6)]
            return [await future for future in internal(asyncio, "as_completed")(aws)]

        assert sorted(asyncio.run(main())) == [0, 1, 2, 3, 4, 5]

    def test_as_completed_yields_in_completion_order(self) -> None:
        async def after(delay: float, value: int) -> int:
            await asyncio.sleep(delay)
            return value

        async def main() -> list[int]:
            aws = [after(0.03, 1), after(0.01, 2), after(0.02, 3)]
            return [await future for future in internal(asyncio, "as_completed")(aws)]

        assert asyncio.run(main()) == [2, 3, 1]

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="async iteration added in 3.13")
    def test_async_iteration_yields_the_original_awaitables(self) -> None:
        """The 3.13 row: `async for` hands back the objects that were passed in."""

        async def value(x: int) -> int:
            return x

        async def main() -> tuple[bool, int]:
            task = asyncio.create_task(value(7))
            async for future in internal(asyncio, "as_completed")([task]):
                return future is task, await future
            raise AssertionError("as_completed yielded nothing")

        assert asyncio.run(main()) == (True, 7)

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="async iteration added in 3.13")
    def test_a_bare_coroutine_comes_back_as_its_wrapping_task(self) -> None:
        """Identity is preserved for tasks and futures, not for coroutines."""

        async def main() -> tuple[bool, str, int]:
            async def value(x: int) -> int:
                return x

            coro = value(3)
            async for future in internal(asyncio, "as_completed")([coro]):
                return future is coro, type(future).__name__, await future
            raise AssertionError("as_completed yielded nothing")

        same, kind, result = asyncio.run(main())
        assert same is False
        assert kind == "Task"
        assert result == 3

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="plain generator before 3.13")
    def test_before_313_as_completed_is_not_async_iterable(self) -> None:
        assert not hasattr(asyncio.as_completed([]), "__aiter__")


@pytest.mark.skipif(sys.version_info < (3, 11), reason="added in 3.11")
class TestTaskGroup:
    """The TaskGroup rows: O(1) per task, O(n) at exit."""

    def test_the_group_waits_for_every_task_at_exit(self) -> None:
        async def main() -> list[int]:
            done: list[int] = []

            async def work(i: int) -> None:
                await asyncio.sleep(0)
                done.append(i)

            async with api("TaskGroup")() as group:
                for i in range(5):
                    group.create_task(work(i))
            return sorted(done)

        assert asyncio.run(main()) == [0, 1, 2, 3, 4]

    def test_a_failure_cancels_the_siblings_and_raises_a_group(self) -> None:
        async def main() -> tuple[type, bool]:
            cancelled = False

            async def sibling() -> None:
                nonlocal cancelled
                try:
                    await asyncio.sleep(10)
                except asyncio.CancelledError:
                    cancelled = True
                    raise

            async def boom() -> None:
                raise ValueError("no")

            try:
                async with api("TaskGroup")() as group:
                    group.create_task(sibling())
                    group.create_task(boom())
            except BaseException as exc:  # noqa: BLE001 - the type is the assertion
                return type(exc), cancelled
            raise AssertionError("the group did not raise")

        raised, cancelled = asyncio.run(main())
        assert raised.__name__ == "ExceptionGroup"
        assert cancelled is True


class TestTaskSnapshots:
    """all_tasks builds a container; current_task reads a slot."""

    def test_all_tasks_returns_a_new_set_each_call(self) -> None:
        async def main() -> tuple[bool, bool]:
            tasks = [asyncio.create_task(asyncio.sleep(10)) for _ in range(4)]
            await asyncio.sleep(0)
            first = asyncio.all_tasks()
            second = asyncio.all_tasks()
            result = first == second, first is not second
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            return result

        equal, distinct = asyncio.run(main())
        assert equal is True, "the two snapshots should hold the same tasks"
        assert distinct is True, "a stored view would return the same object"

    def test_the_snapshot_grows_with_the_tracked_tasks(self) -> None:
        async def main() -> list[int]:
            sizes: list[int] = []
            tasks: list[asyncio.Task[None]] = []
            for _ in range(3):
                tasks.append(asyncio.create_task(asyncio.sleep(10)))
                await asyncio.sleep(0)
                sizes.append(len(asyncio.all_tasks()))
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            return sizes

        # One task each time, plus main() itself.
        assert asyncio.run(main()) == [2, 3, 4]

    def test_a_finished_task_leaves_the_registry_only_from_314(self) -> None:
        """Why the row warns about holding references to completed tasks."""

        async def main() -> int:
            finished = [asyncio.create_task(asyncio.sleep(0)) for _ in range(5)]
            await asyncio.gather(*finished)
            # The registry is _all_tasks through 3.11 and _scheduled_tasks from 3.12.
            name = "_all_tasks" if sys.version_info < (3, 12) else "_scheduled_tasks"
            registry = internal(asyncio.tasks, name)
            # finished is still in scope, so nothing has been collected.
            return sum(1 for task in list(registry) if task in finished)

        still_registered = asyncio.run(main())

        if sys.version_info >= (3, 14):
            assert still_registered == 0, "3.14 unregisters a task when it completes"
        else:
            assert still_registered == 5, "before 3.14 a referenced finished task is scanned"

    def test_current_task_is_the_running_task_and_is_in_the_snapshot(self) -> None:
        async def main() -> tuple[bool, bool]:
            current = asyncio.current_task()
            return current is asyncio.current_task(), current in asyncio.all_tasks()

        same, present = asyncio.run(main())
        assert same is True
        assert present is True

    def test_current_task_outside_a_task_is_none(self) -> None:
        loop = asyncio.new_event_loop()
        try:
            assert asyncio.current_task(loop) is None
        finally:
            loop.close()

    def test_a_finished_task_leaves_the_snapshot(self) -> None:
        async def main() -> tuple[int, int]:
            task = asyncio.create_task(asyncio.sleep(0))
            await asyncio.sleep(0)
            before = len(asyncio.all_tasks())
            await task
            return before, len(asyncio.all_tasks())

        before, after = asyncio.run(main())
        assert before == 2
        assert after == 1


class TestBroadcastsTouchEveryWaiter:
    """Event, Condition and Barrier: the rows where w reaches the bound."""

    def test_event_set_resolves_every_queued_waiter(self) -> None:
        async def main() -> tuple[int, list[bool]]:
            event = asyncio.Event()
            waiters = [asyncio.create_task(event.wait()) for _ in range(8)]
            await asyncio.sleep(0)
            queued = len(internal(event, "_waiters"))
            event.set()
            return queued, await asyncio.gather(*waiters)

        queued, results = asyncio.run(main())
        assert queued == 8
        assert results == [True] * 8

    def test_waiting_on_a_set_event_queues_nothing(self) -> None:
        async def main() -> tuple[bool, int]:
            event = asyncio.Event()
            event.set()
            await event.wait()
            return event.is_set(), len(internal(event, "_waiters"))

        assert asyncio.run(main()) == (True, 0)

    def test_clear_makes_wait_block_again(self) -> None:
        async def main() -> tuple[bool, int]:
            event = asyncio.Event()
            event.set()
            event.clear()
            waiter = asyncio.create_task(event.wait())
            await asyncio.sleep(0)
            result = event.is_set(), len(internal(event, "_waiters"))
            event.set()
            await waiter
            return result

        assert asyncio.run(main()) == (False, 1)

    def test_notify_wakes_exactly_n_waiters(self) -> None:
        async def main() -> tuple[int, int]:
            condition = asyncio.Condition()
            woken: list[int] = []

            async def waiter(i: int) -> None:
                async with condition:
                    await condition.wait()
                    woken.append(i)

            tasks = [asyncio.create_task(waiter(i)) for i in range(5)]
            while len(internal(condition, "_waiters")) < 5:
                await asyncio.sleep(0)

            async with condition:
                condition.notify(2)
            for _ in range(8):
                await asyncio.sleep(0)
            after_notify = len(woken)

            async with condition:
                condition.notify_all()
            await asyncio.gather(*tasks)
            return after_notify, len(woken)

        after_notify, total = asyncio.run(main())
        assert after_notify == 2, f"notify(2) woke {after_notify}"
        assert total == 5

    def test_notify_without_the_lock_raises(self) -> None:
        async def main() -> None:
            condition = asyncio.Condition()
            with pytest.raises(RuntimeError):
                condition.notify()

        asyncio.run(main())

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="added in 3.11")
    def test_the_last_arrival_releases_the_whole_barrier(self) -> None:
        async def main() -> tuple[list[int], int, int]:
            barrier = api("Barrier")(3)
            indexes: list[int] = []

            async def arrive() -> None:
                indexes.append(await barrier.wait())

            tasks = [asyncio.create_task(arrive()) for _ in range(2)]
            while barrier.n_waiting < 2:
                await asyncio.sleep(0)
            waiting = barrier.n_waiting
            tasks.append(asyncio.create_task(arrive()))
            await asyncio.gather(*tasks)
            return sorted(indexes), waiting, barrier.parties

        indexes, waiting, parties = asyncio.run(main())
        assert indexes == [0, 1, 2]
        assert waiting == 2
        assert parties == 3

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="added in 3.11")
    def test_a_barrier_cycles_and_both_broadcasts_land(self) -> None:
        """The row's two O(w) points: the filling arrival and the last departure.

        The second cycle can only begin once the departure broadcast wakes the
        tasks blocked on the draining state, so a barrier that reused its
        parties without that wake would hang here rather than return.
        """

        async def main() -> list[int]:
            barrier = api("Barrier")(3)
            rounds: list[int] = []

            async def participant() -> None:
                for cycle in range(2):
                    await barrier.wait()
                    rounds.append(cycle)

            await asyncio.wait_for(asyncio.gather(*[participant() for _ in range(3)]), timeout=5)
            return rounds

        rounds = asyncio.run(main())
        assert rounds.count(0) == 3, "the first cycle did not release all three"
        assert rounds.count(1) == 3, "the barrier did not drain into a second cycle"

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="added in 3.11")
    def test_abort_breaks_the_barrier_for_every_waiter(self) -> None:
        async def main() -> tuple[int, bool]:
            barrier = api("Barrier")(4)
            broken = 0

            async def arrive() -> None:
                nonlocal broken
                try:
                    await barrier.wait()
                except api("BrokenBarrierError"):
                    broken += 1

            tasks = [asyncio.create_task(arrive()) for _ in range(3)]
            while barrier.n_waiting < 3:
                await asyncio.sleep(0)
            await barrier.abort()
            await asyncio.gather(*tasks)
            return broken, barrier.broken

        broken, is_broken = asyncio.run(main())
        assert broken == 3
        assert is_broken is True


class TestLocksAndSemaphores:
    """The O(1) acquire and release rows."""

    def test_an_uncontended_lock_queues_nothing(self) -> None:
        async def main() -> tuple[bool, Any, bool]:
            lock = asyncio.Lock()
            await lock.acquire()
            result = lock.locked(), internal(lock, "_waiters")
            lock.release()
            return result[0], result[1], lock.locked()

        locked, waiters, after = asyncio.run(main())
        assert locked is True
        assert waiters is None, "an uncontended acquire should not build a waiter deque"
        assert after is False

    def test_a_contended_lock_queues_one_future_per_waiter(self) -> None:
        async def main() -> int:
            lock = asyncio.Lock()
            await lock.acquire()
            waiters = [asyncio.create_task(lock.acquire()) for _ in range(3)]
            await asyncio.sleep(0)
            queued = len(internal(lock, "_waiters"))
            lock.release()
            for task in waiters:
                await task
                lock.release()
            return queued

        assert asyncio.run(main()) == 3

    def test_the_lock_is_handed_over_in_arrival_order(self) -> None:
        async def main() -> list[int]:
            lock = asyncio.Lock()
            order: list[int] = []
            await lock.acquire()

            async def claim(i: int) -> None:
                async with lock:
                    order.append(i)
                    await asyncio.sleep(0)

            tasks = [asyncio.create_task(claim(i)) for i in range(4)]
            while internal(lock, "_waiters") is None or len(internal(lock, "_waiters")) < 4:
                await asyncio.sleep(0)
            lock.release()
            await asyncio.gather(*tasks)
            return order

        assert asyncio.run(main()) == [0, 1, 2, 3]

    def test_a_semaphore_admits_its_value_and_no_more(self) -> None:
        async def main() -> tuple[int, bool]:
            semaphore = asyncio.Semaphore(2)
            peak = 0
            live = 0

            async def work() -> None:
                nonlocal peak, live
                async with semaphore:
                    live += 1
                    peak = max(peak, live)
                    await asyncio.sleep(0)
                    live -= 1

            await asyncio.gather(*[work() for _ in range(6)])
            return peak, semaphore.locked()

        peak, locked = asyncio.run(main())
        assert peak == 2, f"a Semaphore(2) let {peak} through at once"
        assert locked is False

    def test_locked_consults_the_waiter_queue_and_not_only_the_counter(self) -> None:
        """The row's O(w).

        A counter-only `locked()` would be O(1), so the test has to reach a
        state where the counter is *positive* and `locked()` is still true.
        Waking a waiter leaves its done future in the deque until that task
        resumes, so a second release restores the permit while the queue is
        still occupied.
        """

        async def main() -> tuple[int, bool, int, bool]:
            semaphore = asyncio.Semaphore(2)
            await semaphore.acquire()
            await semaphore.acquire()  # counter is now 0
            waiter = asyncio.create_task(semaphore.acquire())
            await asyncio.sleep(0)

            semaphore.release()  # wakes the waiter, which reserves the permit
            semaphore.release()  # no one left to wake, so the counter rises
            value, locked = internal(semaphore, "_value"), semaphore.locked()

            await waiter
            semaphore.release()
            return value, locked, internal(semaphore, "_value"), semaphore.locked()

        value, locked, drained_value, drained = asyncio.run(main())
        assert value > 0, "the counter must be positive or this proves nothing"
        assert locked is True, "a queued waiter should keep locked() true"
        assert drained_value > 0
        assert drained is False, "with the queue empty the counter alone decides"

    def test_a_bounded_semaphore_refuses_an_extra_release(self) -> None:
        async def main() -> None:
            plain = asyncio.Semaphore(1)
            plain.release()  # An ordinary Semaphore allows this
            bounded = asyncio.BoundedSemaphore(1)
            with pytest.raises(ValueError):
                bounded.release()

        asyncio.run(main())


class TestQueues:
    """A queue's cost is its container, which its ordering exposes."""

    def test_the_three_queues_return_three_different_orders(self) -> None:
        async def main() -> tuple[list[int], list[int], list[int]]:
            fifo: asyncio.Queue[int] = asyncio.Queue()
            lifo: asyncio.LifoQueue[int] = asyncio.LifoQueue()
            prio: asyncio.PriorityQueue[int] = asyncio.PriorityQueue()
            for item in (3, 1, 2):
                fifo.put_nowait(item)
                lifo.put_nowait(item)
                prio.put_nowait(item)
            return (
                [fifo.get_nowait() for _ in range(3)],
                [lifo.get_nowait() for _ in range(3)],
                [prio.get_nowait() for _ in range(3)],
            )

        first_in, last_in, lowest = asyncio.run(main())
        assert first_in == [3, 1, 2], "a deque returns insertion order"
        assert last_in == [2, 1, 3], "a list used as a stack reverses it"
        assert lowest == [1, 2, 3], "a heap returns lowest first"

    def test_the_containers_are_the_ones_the_rows_name(self) -> None:
        assert type(internal(asyncio.Queue(), "_queue")).__name__ == "deque"
        assert type(internal(asyncio.LifoQueue(), "_queue")).__name__ == "list"
        assert type(internal(asyncio.PriorityQueue(), "_queue")).__name__ == "list"

    def test_a_priority_queue_holds_a_heap_and_not_a_sorted_list(self) -> None:
        """Ordering alone cannot tell the O(log q) heap from an O(q) sorted insert."""
        queue: asyncio.PriorityQueue[int] = asyncio.PriorityQueue()
        for item in (5, 3, 8, 1, 9, 2, 7):
            queue.put_nowait(item)
        items = list(internal(queue, "_queue"))

        # The heap invariant holds ...
        for parent in range(len(items) // 2):
            for child in (2 * parent + 1, 2 * parent + 2):
                if child < len(items):
                    assert items[parent] <= items[child], f"heap broken at {parent}"

        # ... but the list is not sorted, which a sorted insert would have made it.
        assert items != sorted(items), f"{items} is fully sorted, so this is no heap"

    def test_qsize_empty_and_full_are_length_comparisons(self) -> None:
        async def main() -> tuple[int, bool, bool, int]:
            queue: asyncio.Queue[str] = asyncio.Queue(maxsize=2)
            empty = queue.empty()
            await queue.put("a")
            await queue.put("b")
            return queue.qsize(), empty, queue.full(), queue.maxsize

        size, empty, full, maxsize = asyncio.run(main())
        assert (size, empty, full, maxsize) == (2, True, True, 2)

    def test_a_full_queue_refuses_rather_than_growing(self) -> None:
        async def main() -> None:
            queue: asyncio.Queue[str] = asyncio.Queue(maxsize=1)
            queue.put_nowait("a")
            with pytest.raises(asyncio.QueueFull):
                queue.put_nowait("b")
            assert queue.qsize() == 1

        asyncio.run(main())

    def test_an_empty_queue_raises_rather_than_waiting(self) -> None:
        async def main() -> None:
            queue: asyncio.Queue[str] = asyncio.Queue()
            with pytest.raises(asyncio.QueueEmpty):
                queue.get_nowait()

        asyncio.run(main())

    def test_an_unbounded_queue_reports_maxsize_zero(self) -> None:
        queue: asyncio.Queue[int] = asyncio.Queue()
        assert queue.maxsize == 0
        assert queue.full() is False

    def test_join_returns_once_task_done_balances_the_puts(self) -> None:
        async def main() -> bool:
            queue: asyncio.Queue[int] = asyncio.Queue()
            for i in range(3):
                queue.put_nowait(i)
            waiter = asyncio.create_task(queue.join())
            await asyncio.sleep(0)
            assert not waiter.done(), "join() returned with work outstanding"
            for _ in range(3):
                queue.get_nowait()
                queue.task_done()
            await waiter
            return waiter.done()

        assert asyncio.run(main()) is True

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="Queue.shutdown added in 3.13")
    def test_shutdown_wakes_every_waiter(self) -> None:
        async def main() -> int:
            queue: asyncio.Queue[int] = asyncio.Queue()
            raised = 0

            async def consume() -> None:
                nonlocal raised
                try:
                    await queue.get()
                except api("QueueShutDown"):
                    raised += 1

            tasks = [asyncio.create_task(consume()) for _ in range(4)]
            await asyncio.sleep(0)
            internal(queue, "shutdown")()
            await asyncio.gather(*tasks)
            return raised

        assert asyncio.run(main()) == 4

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="Queue.shutdown added in 3.13")
    def test_a_plain_shutdown_leaves_join_waiting_on_unfinished_work(self) -> None:
        """The row says join() waiters are released only by immediate shutdown."""

        async def main() -> tuple[bool, bool]:
            queue: asyncio.Queue[int] = asyncio.Queue()
            queue.put_nowait(1)
            waiter = asyncio.create_task(queue.join())
            await asyncio.sleep(0)

            internal(queue, "shutdown")()
            await asyncio.sleep(0)
            after_plain = waiter.done()

            queue.get_nowait()
            queue.task_done()
            await waiter
            return after_plain, waiter.done()

        after_plain, eventually = asyncio.run(main())
        assert after_plain is False, "plain shutdown should not release join()"
        assert eventually is True

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="Queue.shutdown added in 3.13")
    def test_immediate_shutdown_drops_the_queued_items(self) -> None:
        async def main() -> tuple[int, int]:
            queue: asyncio.Queue[int] = asyncio.Queue()
            for i in range(5):
                queue.put_nowait(i)
            before = queue.qsize()
            internal(queue, "shutdown")(immediate=True)
            return before, queue.qsize()

        assert asyncio.run(main()) == (5, 0)

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="Queue.shutdown added in 3.13")
    def test_immediate_shutdown_drains_a_priority_queue_through_its_heap(self) -> None:
        """The q log q half of the row: the drain uses each subclass's own get."""

        async def main() -> tuple[int, int]:
            pops = 0
            prio: asyncio.PriorityQueue[int] = asyncio.PriorityQueue()
            original = type(prio)._get

            def counting(self: Any) -> Any:
                nonlocal pops
                pops += 1
                return original(self)

            for item in (5, 3, 8, 1, 9):
                prio.put_nowait(item)

            type(prio)._get = counting  # type: ignore[method-assign]
            try:
                internal(prio, "shutdown")(immediate=True)
            finally:
                type(prio)._get = original  # type: ignore[method-assign]
            return pops, prio.qsize()

        pops, remaining = asyncio.run(main())
        assert pops == 5, f"the drain should pop each of the 5 items, popped {pops}"
        assert remaining == 0


class TestEagerTasks:
    """The default factory defers the body; the eager one runs it."""

    def test_the_default_factory_runs_the_body_after_create_task_returns(self) -> None:
        async def main() -> list[str]:
            order: list[str] = []

            async def body() -> None:
                order.append("body")

            task = asyncio.create_task(body())
            order.append("after")
            await task
            return order

        assert asyncio.run(main()) == ["after", "body"]

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="eager_task_factory added in 3.12")
    def test_an_eager_factory_runs_the_body_during_create_task(self) -> None:
        async def main() -> tuple[list[str], bool]:
            loop = asyncio.get_running_loop()
            order: list[str] = []

            async def body() -> None:
                order.append("body")

            loop.set_task_factory(api("eager_task_factory"))
            try:
                task = asyncio.create_task(body())
                order.append("after")
                done = task.done()
                await task
            finally:
                loop.set_task_factory(None)
            return order, done

        order, done = asyncio.run(main())
        assert order == ["body", "after"]
        assert done is True, "a coroutine that never suspends finishes inside create_task"

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="eager factories added in 3.12")
    def test_an_eager_task_that_suspends_is_still_pending(self) -> None:
        """Eager runs the body only as far as its first suspension."""

        async def main() -> bool:
            loop = asyncio.get_running_loop()
            loop.set_task_factory(api("eager_task_factory"))
            try:
                task = asyncio.create_task(asyncio.sleep(0.01))
                pending = not task.done()
                await task
            finally:
                loop.set_task_factory(None)
            return pending

        assert asyncio.run(main()) is True

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="eager factories added in 3.12")
    def test_create_eager_task_factory_builds_one_for_a_subclass(self) -> None:
        class MyTask(asyncio.Task):  # type: ignore[type-arg]
            pass

        async def main() -> tuple[bool, list[str]]:
            loop = asyncio.get_running_loop()
            order: list[str] = []

            async def body() -> None:
                order.append("body")

            loop.set_task_factory(api("create_eager_task_factory")(MyTask))
            try:
                task = asyncio.create_task(body())
                order.append("after")
                await task
            finally:
                loop.set_task_factory(None)
            return isinstance(task, MyTask), order

        subclassed, order = asyncio.run(main())
        assert subclassed is True
        assert order == ["body", "after"]


class TestCancellationIsARequest:
    """cancel() is O(1) because it only arranges for the raise."""

    def test_cancel_does_not_finish_the_task_itself(self) -> None:
        async def main() -> tuple[bool, bool]:
            task = asyncio.create_task(asyncio.sleep(10))
            await asyncio.sleep(0)
            task.cancel()
            immediately = task.cancelled()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            return immediately, task.cancelled()

        immediately, eventually = asyncio.run(main())
        assert immediately is False, "cancel() requests; it does not perform"
        assert eventually is True

    def test_a_task_may_catch_its_own_cancellation(self) -> None:
        async def main() -> tuple[str, bool]:
            async def stubborn() -> str:
                try:
                    await asyncio.sleep(10)
                except asyncio.CancelledError:
                    return "caught"
                return "never"

            task = asyncio.create_task(stubborn())
            await asyncio.sleep(0)
            task.cancel()
            return await task, task.cancelled()

        result, cancelled = asyncio.run(main())
        assert result == "caught"
        assert cancelled is False

    def test_shield_lets_the_inner_awaitable_finish(self) -> None:
        async def main() -> tuple[str, bool]:
            async def work() -> str:
                await asyncio.sleep(0.05)
                return "finished"

            inner = asyncio.create_task(work())
            outer = asyncio.shield(inner)
            await asyncio.sleep(0)
            outer.cancel()
            with pytest.raises(asyncio.CancelledError):
                await outer
            return await inner, inner.cancelled()

        result, cancelled = asyncio.run(main())
        assert result == "finished", "the shielded task should run to completion"
        assert cancelled is False

    @pytest.mark.timing
    def test_cancelling_a_task_awaiting_gather_cancels_n_children_here(self) -> None:
        """The row's "plus the awaited future's own cancel()": O(1) would not move."""

        async def measure(count: int) -> float:
            async def child() -> None:
                await asyncio.sleep(10)

            async def parent() -> None:
                await asyncio.gather(*[child() for _ in range(count)])

            task = asyncio.create_task(parent())
            for _ in range(3):
                await asyncio.sleep(0)
            start = time.perf_counter()
            task.cancel()
            elapsed = time.perf_counter() - start
            with contextlib.suppress(asyncio.CancelledError):
                await task
            return elapsed

        async def best(count: int) -> float:
            return min([await measure(count) for _ in range(5)])

        small = asyncio.run(best(10))
        large = asyncio.run(best(10_000))
        ratio = large / small

        assert ratio > 50, (
            f"1000x the children made cancel() only {ratio:.1f}x dearer; it looks constant"
        )

    def test_a_task_on_a_single_future_cancels_without_walking_anything(self) -> None:
        """The control for the row above.

        The cancel is still forwarded - to the one future `sleep()` is waiting
        on - but that future has no children to walk, so the cost does not
        follow any count. The timing test above is what establishes that the
        gather case does.
        """

        async def main() -> tuple[bool, int]:
            cancels = 0
            loop = asyncio.get_running_loop()
            future = loop.create_future()

            def counting_cancel(msg: Any = None) -> bool:
                nonlocal cancels
                cancels += 1
                return asyncio.Future.cancel(future, msg)

            async def waits() -> None:
                await future

            task = asyncio.create_task(waits())
            await asyncio.sleep(0)
            future.cancel = counting_cancel  # type: ignore[method-assign]
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            return task.cancelled(), cancels

        cancelled, forwards = asyncio.run(main())
        assert cancelled is True
        assert forwards == 1, f"the cancel should reach the awaited future once, got {forwards}"

    def test_cancelled_error_is_not_an_exception(self) -> None:
        """A bare `except Exception` must not swallow a cancellation."""
        assert issubclass(asyncio.CancelledError, BaseException)
        assert not issubclass(asyncio.CancelledError, Exception)

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="added in 3.11")
    def test_cancelling_and_uncancel_track_one_counter(self) -> None:
        async def main() -> tuple[int, int, int]:
            async def work() -> None:
                try:
                    await asyncio.sleep(10)
                except asyncio.CancelledError:
                    pass

            task = asyncio.create_task(work())
            await asyncio.sleep(0)
            before = internal(task, "cancelling")()
            task.cancel()
            after = internal(task, "cancelling")()
            remaining = internal(task, "uncancel")()
            await task
            return before, after, remaining

        assert asyncio.run(main()) == (0, 1, 0)


class TestFuturesAndTasks:
    """The Future and Task rows."""

    def test_set_result_schedules_every_done_callback(self) -> None:
        async def main() -> int:
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            calls = 0

            def callback(_: Any) -> None:
                nonlocal calls
                calls += 1

            for _ in range(5):
                future.add_done_callback(callback)
            future.set_result(1)
            assert calls == 0, "callbacks are scheduled, not called inline"
            await asyncio.sleep(0)
            return calls

        assert asyncio.run(main()) == 5

    def test_a_callback_added_to_a_done_future_still_runs(self) -> None:
        async def main() -> int:
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            future.set_result(1)
            calls = 0

            def callback(_: Any) -> None:
                nonlocal calls
                calls += 1

            future.add_done_callback(callback)
            await asyncio.sleep(0)
            return calls

        assert asyncio.run(main()) == 1

    def test_remove_done_callback_drops_them_and_not_only_reports_it(self) -> None:
        """The returned count is a report; the assertion is that none of them ran."""

        async def main() -> tuple[int, int, int]:
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            removed_calls = 0
            kept_calls = 0

            def removed_callback(_: Any) -> None:
                nonlocal removed_calls
                removed_calls += 1

            def kept_callback(_: Any) -> None:
                nonlocal kept_calls
                kept_calls += 1

            for _ in range(3):
                future.add_done_callback(removed_callback)
            future.add_done_callback(kept_callback)

            removed = future.remove_done_callback(removed_callback)
            future.set_result(1)
            await asyncio.sleep(0)
            return removed, removed_calls, kept_calls

        removed, removed_calls, kept_calls = asyncio.run(main())
        assert removed == 3, f"remove_done_callback reported {removed}"
        assert removed_calls == 0, "a removed callback still ran"
        assert kept_calls == 1, "the untouched callback should be unaffected"

    def test_reading_a_pending_future_raises_invalid_state(self) -> None:
        async def main() -> None:
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            with pytest.raises(asyncio.InvalidStateError):
                future.result()
            with pytest.raises(asyncio.InvalidStateError):
                future.exception()
            future.set_result(1)
            with pytest.raises(asyncio.InvalidStateError):
                future.set_result(2)

        asyncio.run(main())

    def test_a_cancelled_future_raises_rather_than_returning_the_error(self) -> None:
        async def main() -> None:
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            future.cancel()
            assert future.cancelled()
            with pytest.raises(asyncio.CancelledError):
                future.exception()

        asyncio.run(main())

    def test_get_loop_returns_the_loop_the_future_was_made_on(self) -> None:
        async def main() -> bool:
            loop = asyncio.get_running_loop()
            return loop.create_future().get_loop() is loop

        assert asyncio.run(main()) is True

    def test_a_task_refuses_set_result_and_set_exception(self) -> None:
        """The two Future rows a Task does not inherit."""

        async def main() -> None:
            task = asyncio.create_task(asyncio.sleep(0))
            with pytest.raises(RuntimeError):
                task.set_result(None)  # type: ignore[attr-defined]
            with pytest.raises(RuntimeError):
                task.set_exception(ValueError())  # type: ignore[attr-defined]
            await task

        asyncio.run(main())

    def test_get_stack_shows_one_frame_for_a_deep_suspended_chain(self) -> None:
        """A suspended task exposes where it is suspended, not the chain below."""

        async def main() -> int:
            async def inner() -> None:
                await asyncio.sleep(10)

            async def middle() -> None:
                await inner()

            async def outer() -> None:
                await middle()

            task = asyncio.create_task(outer())
            await asyncio.sleep(0)
            frames = task.get_stack()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            return len(frames)

        assert asyncio.run(main()) == 1

    def test_task_name_and_coro_are_stored_attributes(self) -> None:
        async def main() -> tuple[str, bool]:
            coro = asyncio.sleep(0)
            task = asyncio.create_task(coro, name="worker")
            name = task.get_name()
            same = task.get_coro() is coro
            task.set_name(42)
            assert task.get_name() == "42", "set_name stores str(value)"
            await task
            return name, same

        assert asyncio.run(main()) == ("worker", True)

    def test_get_stack_walks_the_coroutine_frames(self) -> None:
        async def main() -> int:
            async def outer() -> None:
                await asyncio.sleep(10)

            task = asyncio.create_task(outer())
            await asyncio.sleep(0)
            frames = task.get_stack()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            return len(frames)

        assert asyncio.run(main()) >= 1

    def test_ensure_future_wraps_only_what_is_not_a_future(self) -> None:
        async def main() -> tuple[bool, bool]:
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            future.set_result(1)
            unchanged = asyncio.ensure_future(future) is future

            async def value() -> int:
                return 1

            wrapped = asyncio.ensure_future(value())
            is_task = isinstance(wrapped, asyncio.Task)
            await wrapped
            return unchanged, is_task

        assert asyncio.run(main()) == (True, True)


class TestTimeouts:
    """wait_for, timeout and timeout_at."""

    def test_wait_for_raises_timeout_error_and_cancels_the_awaitable(self) -> None:
        async def main() -> bool:
            cancelled = False

            async def slow() -> None:
                nonlocal cancelled
                try:
                    await asyncio.sleep(10)
                except asyncio.CancelledError:
                    cancelled = True
                    raise

            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(slow(), timeout=0.01)
            return cancelled

        assert asyncio.run(main()) is True

    def test_wait_for_returns_the_result_inside_the_deadline(self) -> None:
        async def main() -> int:
            async def quick() -> int:
                return 7

            return await asyncio.wait_for(quick(), timeout=10)

        assert asyncio.run(main()) == 7

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="added in 3.11")
    def test_the_timeout_context_manager_reports_that_it_expired(self) -> None:
        async def main() -> bool:
            handle = api("timeout")(0.01)
            with pytest.raises(TimeoutError):
                async with handle:
                    await asyncio.sleep(10)
            return handle.expired()

        assert asyncio.run(main()) is True

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="added in 3.11")
    def test_reschedule_replaces_the_pending_timer(self) -> None:
        """Waiting past the *original* deadline is what shows the timer moved.

        Reporting a new `when()` while leaving the first timer armed would pass
        a test that only reads the attribute, so this one sleeps five times the
        original deadline inside the context and expects no timeout.
        """

        async def main() -> tuple[bool, bool]:
            async with api("timeout")(0.01) as handle:
                first = handle.when()
                handle.reschedule(asyncio.get_running_loop().time() + 10)
                moved = handle.when() > first
                await asyncio.sleep(0.05)
            return moved, handle.expired()

        moved, expired = asyncio.run(main())
        assert moved is True
        assert expired is False, "the original 0.01s deadline still fired"

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="added in 3.11")
    def test_timeout_at_takes_an_absolute_deadline(self) -> None:
        async def main() -> bool:
            loop = asyncio.get_running_loop()
            deadline = loop.time() + 0.01
            handle = api("timeout_at")(deadline)
            with pytest.raises(TimeoutError):
                async with handle:
                    await asyncio.sleep(10)
            return handle.when() == deadline

        assert asyncio.run(main()) is True

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="alias since 3.11")
    def test_asyncio_timeout_error_is_the_builtin(self) -> None:
        assert asyncio.TimeoutError is TimeoutError


class TestThreadBridges:
    """to_thread, run_coroutine_threadsafe and wrap_future."""

    def test_to_thread_runs_the_callable_off_the_loop_thread(self) -> None:
        async def main() -> tuple[int, int]:
            loop_thread = threading.get_ident()
            worker_thread = await asyncio.to_thread(threading.get_ident)
            return loop_thread, worker_thread

        loop_thread, worker_thread = asyncio.run(main())
        assert loop_thread != worker_thread

    @pytest.mark.timing
    def test_blocking_calls_on_threads_overlap(self) -> None:
        """Three waits against one measured wait, so load moves both sides together."""

        def blocking() -> str:
            time.sleep(0.05)
            return "done"

        async def main() -> tuple[list[str], float, float]:
            start = time.perf_counter()
            await asyncio.to_thread(blocking)
            one = time.perf_counter() - start

            start = time.perf_counter()
            results = list[str](
                await asyncio.gather(
                    asyncio.to_thread(blocking),
                    asyncio.to_thread(blocking),
                    asyncio.to_thread(blocking),
                )
            )
            return results, one, time.perf_counter() - start

        results, one, three = asyncio.run(main())
        assert results == ["done"] * 3
        assert three < 2 * one, (
            f"three overlapping waits took {three:.3f}s against {one:.3f}s for one; "
            "they look serialized"
        )

    def test_the_loop_keeps_running_while_a_thread_blocks(self) -> None:
        """Overlap is only half the claim; the other half is that the loop is free."""

        def blocking() -> str:
            time.sleep(0.05)
            return "done"

        async def main() -> tuple[str, int]:
            ticks = 0

            async def ticker() -> None:
                nonlocal ticks
                while True:
                    ticks += 1
                    await asyncio.sleep(0.001)

            counting = asyncio.create_task(ticker())
            result = await asyncio.to_thread(blocking)
            counting.cancel()
            await asyncio.gather(counting, return_exceptions=True)
            return result, ticks

        result, ticks = asyncio.run(main())
        assert result == "done"
        assert ticks > 5, f"the loop ran only {ticks} times while the thread blocked"

    def test_to_thread_carries_the_callers_context(self) -> None:
        import contextvars

        variable: contextvars.ContextVar[str] = contextvars.ContextVar("variable")

        async def main() -> str:
            variable.set("set in the coroutine")
            return await asyncio.to_thread(variable.get)

        assert asyncio.run(main()) == "set in the coroutine"

    def test_run_coroutine_threadsafe_returns_a_concurrent_future(self) -> None:
        import concurrent.futures

        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=loop.run_forever, daemon=True)
        thread.start()
        try:

            async def value() -> int:
                return 11

            future = asyncio.run_coroutine_threadsafe(value(), loop)
            assert isinstance(future, concurrent.futures.Future)
            assert future.result(timeout=5) == 11
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join(timeout=5)
            loop.close()

    def test_wrap_future_bridges_a_concurrent_future(self) -> None:
        import concurrent.futures

        async def main() -> int:
            source: concurrent.futures.Future[int] = concurrent.futures.Future()
            wrapped = asyncio.wrap_future(source)
            assert asyncio.isfuture(wrapped)
            source.set_result(5)
            return await wrapped

        assert asyncio.run(main()) == 5


class TestStreams:
    """StreamReader bounds, driven by feeding the reader directly."""

    def test_readexactly_reports_what_it_managed_to_read(self) -> None:
        async def main() -> tuple[bytes, int | None]:
            reader = asyncio.StreamReader()
            reader.feed_data(b"abc")
            reader.feed_eof()
            try:
                await reader.readexactly(10)
            except asyncio.IncompleteReadError as error:
                return error.partial, error.expected
            raise AssertionError("expected IncompleteReadError")

        assert asyncio.run(main()) == (b"abc", 10)

    def test_readuntil_over_the_limit_leaves_the_data_in_the_buffer(self) -> None:
        async def main() -> tuple[int, int]:
            reader = asyncio.StreamReader(limit=100)
            reader.feed_data(b"y" * 500)
            try:
                await reader.readuntil(b"\n")
            except asyncio.LimitOverrunError as error:
                return error.consumed, len(internal(reader, "_buffer"))
            raise AssertionError("expected LimitOverrunError")

        consumed, buffered = asyncio.run(main())
        assert consumed == 500
        assert buffered == 500, "the row says the data stays in the buffer"

    def test_readline_returns_the_partial_line_rather_than_raising(self) -> None:
        """readline differs from readuntil exactly here."""

        async def main() -> bytes:
            reader = asyncio.StreamReader()
            reader.feed_data(b"no newline")
            reader.feed_eof()
            return await reader.readline()

        assert asyncio.run(main()) == b"no newline"

    def test_readline_over_the_limit_raises_and_drops_the_data(self) -> None:
        """readline differs from readuntil at both ends, not only at EOF."""

        async def main() -> int:
            reader = asyncio.StreamReader(limit=16)
            reader.feed_data(b"y" * 500)
            reader.feed_eof()
            with pytest.raises(ValueError):
                await reader.readline()
            # readuntil leaves the data; readline clears it
            return len(internal(reader, "_buffer"))

        assert asyncio.run(main()) == 0

    def test_read_minus_one_holds_the_whole_stream(self) -> None:
        async def main() -> tuple[int, bytes]:
            reader = asyncio.StreamReader(limit=16)
            reader.feed_data(b"z" * 1000)
            reader.feed_eof()
            data = await reader.read(-1)
            return len(data), await reader.read(-1)

        size, after = asyncio.run(main())
        assert size == 1000, "read(-1) ignores the limit and returns everything"
        assert after == b""

    def test_a_positive_n_returns_at_most_n_bytes(self) -> None:
        async def main() -> tuple[int, int]:
            reader = asyncio.StreamReader()
            reader.feed_data(b"z" * 100)
            reader.feed_eof()
            first = await reader.read(10)
            return len(first), len(await reader.read(-1))

        assert asyncio.run(main()) == (10, 90)

    def test_at_eof_is_true_only_once_the_buffer_drains(self) -> None:
        async def main() -> tuple[bool, bool]:
            reader = asyncio.StreamReader()
            reader.feed_data(b"abc")
            reader.feed_eof()
            with_data = reader.at_eof()
            await reader.read(-1)
            return with_data, reader.at_eof()

        assert asyncio.run(main()) == (False, True)

    def test_async_iteration_yields_lines(self) -> None:
        async def main() -> list[bytes]:
            reader = asyncio.StreamReader()
            reader.feed_data(b"one\ntwo\nthree\n")
            reader.feed_eof()
            return [line async for line in reader]

        assert asyncio.run(main()) == [b"one\n", b"two\n", b"three\n"]

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="tuple separators added in 3.13")
    def test_a_tuple_of_separators_stops_at_the_shortest_match(self) -> None:
        async def main() -> bytes:
            reader = asyncio.StreamReader()
            # Both separators match, and they start at different offsets: b"abcd"
            # at 0 and b"b" at 1. Returning the *shortest* result means the later
            # separator wins. An earliest-separator rule would return b"abcd", and
            # a first-listed rule would too, so only the shortest rule gives b"ab".
            reader.feed_data(b"abcd")
            reader.feed_eof()
            return await internal(reader, "readuntil")((b"abcd", b"b"))

        assert asyncio.run(main()) == b"ab"

    @pytest.mark.timing
    def test_readuntil_does_not_rescan_what_it_already_searched(self) -> None:
        """A rescan would make the per-chunk cost grow with the buffer."""

        async def feed(chunks: int) -> float:
            reader = asyncio.StreamReader(limit=10**9)
            pending = asyncio.ensure_future(reader.readuntil(b"\n"))
            start = time.perf_counter()
            for _ in range(chunks):
                reader.feed_data(b"x" * 1000)
                await asyncio.sleep(0)
            reader.feed_data(b"\n")
            await pending
            return (time.perf_counter() - start) / chunks

        small = min(asyncio.run(feed(200)) for _ in range(3))
        large = min(asyncio.run(feed(1600)) for _ in range(3))
        ratio = large / small

        assert ratio < 3, (
            f"8x the buffer made each chunk {ratio:.1f}x dearer; the scan looks quadratic"
        )


class TestVersionBoundaries:
    """The Version Notes section, one assertion per boundary that moves."""

    def test_the_311_additions_match_the_running_version(self) -> None:
        expected = sys.version_info >= (3, 11)
        for name in ("TaskGroup", "timeout", "timeout_at", "Runner", "Barrier"):
            assert hasattr(asyncio, name) is expected, name
        assert hasattr(asyncio.Task, "uncancel") is expected

    def test_the_312_additions_match_the_running_version(self) -> None:
        expected = sys.version_info >= (3, 12)
        assert hasattr(asyncio, "eager_task_factory") is expected
        assert hasattr(asyncio, "create_eager_task_factory") is expected
        assert hasattr(asyncio.Handle, "get_context") is expected

    def test_the_313_additions_match_the_running_version(self) -> None:
        expected = sys.version_info >= (3, 13)
        assert hasattr(asyncio, "EventLoop") is expected
        assert hasattr(asyncio, "QueueShutDown") is expected
        assert hasattr(asyncio.Queue, "shutdown") is expected
        assert hasattr(asyncio.Server, "close_clients") is expected

    def test_the_314_additions_match_the_running_version(self) -> None:
        expected = sys.version_info >= (3, 14)
        for name in (
            "capture_call_graph",
            "format_call_graph",
            "print_call_graph",
            "future_add_to_awaited_by",
            "future_discard_from_awaited_by",
        ):
            assert hasattr(asyncio, name) is expected, name

    def test_the_child_watcher_api_is_gone_from_314(self) -> None:
        assert hasattr(asyncio, "get_child_watcher") is (sys.version_info < (3, 14))

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="raises only from 3.14")
    def test_get_event_loop_outside_a_loop_raises_from_314(self) -> None:
        asyncio.set_event_loop(None)
        with pytest.raises(RuntimeError):
            asyncio.get_event_loop()

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="deprecated in 3.14")
    def test_the_314_deprecations_warn(self) -> None:
        async def coro() -> None:
            pass

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            asyncio.iscoroutinefunction(coro)
            asyncio.get_event_loop_policy()

        categories = [warning.category for warning in caught]
        assert categories.count(DeprecationWarning) == 2, [str(w.message) for w in caught]

    def test_a_worker_thread_never_gets_a_loop_created_for_it(self) -> None:
        """The pre-3.14 "creates one and warn" is the main thread only."""
        outcome: list[str] = []

        def worker() -> None:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                try:
                    asyncio.get_event_loop()
                except RuntimeError:
                    outcome.append("raised")
                else:
                    outcome.append("created")

        thread = threading.Thread(target=worker)
        thread.start()
        thread.join(timeout=5)

        assert outcome == ["raised"], (
            "get_event_loop() on a worker thread should raise on every supported version"
        )

    def test_the_main_thread_loop_is_cleared_once_asyncio_run_returns(self) -> None:
        """Which is why the main-thread exception is narrower than it reads."""

        async def main() -> None:
            pass

        asyncio.run(main())

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with pytest.raises(RuntimeError):
                asyncio.get_event_loop()

    def test_get_event_loop_inside_a_loop_returns_the_running_one(self) -> None:
        """The deprecation applies outside a loop; inside one it is the running loop."""

        async def main() -> bool:
            return asyncio.get_event_loop() is asyncio.get_running_loop()

        assert asyncio.run(main()) is True


class TestLoopReferences:
    """The event loop reference rows."""

    def test_get_running_loop_outside_a_loop_raises(self) -> None:
        with pytest.raises(RuntimeError):
            asyncio.get_running_loop()

    def test_new_event_loop_starts_with_empty_schedules(self) -> None:
        loop = asyncio.new_event_loop()
        try:
            assert len(internal(loop, "_scheduled")) == 0
            assert loop.is_running() is False
            assert loop.is_closed() is False
        finally:
            loop.close()
        assert loop.is_closed() is True

    def test_set_event_loop_stores_it_for_this_thread(self) -> None:
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            assert asyncio.get_event_loop() is loop
        finally:
            asyncio.set_event_loop(None)
            loop.close()

    def test_run_until_complete_returns_the_result(self) -> None:
        async def value() -> int:
            return 3

        loop = asyncio.new_event_loop()
        try:
            assert loop.run_until_complete(value()) == 3
        finally:
            loop.close()

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="asyncio.EventLoop added in 3.13")
    def test_event_loop_is_a_loop_class(self) -> None:
        assert issubclass(api("EventLoop"), asyncio.AbstractEventLoop)

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="added in 3.11")
    def test_the_runner_reuses_one_loop_across_runs(self) -> None:
        async def which() -> Any:
            return asyncio.get_running_loop()

        with api("Runner")() as runner:
            first = runner.run(which())
            second = runner.run(which())
            assert first is second
            assert runner.get_loop() is first
        assert first.is_closed(), "Runner.close() should close the loop it made"

    def test_loop_time_is_monotonic(self) -> None:
        async def main() -> bool:
            loop = asyncio.get_running_loop()
            first = loop.time()
            await asyncio.sleep(0.01)
            return loop.time() >= first

        assert asyncio.run(main()) is True

    def test_run_cancels_what_is_left_and_closes_the_loop(self) -> None:
        leftover: list[asyncio.Task[None]] = []

        async def main() -> Any:
            leftover.append(asyncio.create_task(asyncio.sleep(10)))
            await asyncio.sleep(0)
            return asyncio.get_running_loop()

        loop = asyncio.run(main())
        assert loop.is_closed()
        assert leftover[0].cancelled()


class TestTypeChecks:
    """iscoroutine, isfuture and iscoroutinefunction."""

    def test_iscoroutine_distinguishes_the_object_from_the_function(self) -> None:
        async def coro() -> None:
            pass

        obj = coro()
        try:
            assert asyncio.iscoroutine(obj) is True
            assert asyncio.iscoroutine(coro) is False
        finally:
            obj.close()

    def test_isfuture_accepts_futures_and_tasks_but_not_coroutines(self) -> None:
        async def main() -> tuple[bool, bool, bool]:
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            future.set_result(None)
            task = asyncio.create_task(asyncio.sleep(0))
            await task
            coro = asyncio.sleep(0)
            try:
                return asyncio.isfuture(future), asyncio.isfuture(task), asyncio.isfuture(coro)
            finally:
                coro.close()

        assert asyncio.run(main()) == (True, True, False)

    def test_iscoroutinefunction_matches_inspect(self) -> None:
        async def coro() -> None:
            pass

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            assert asyncio.iscoroutinefunction(coro) is inspect.iscoroutinefunction(coro) is True
            assert asyncio.iscoroutinefunction(len) is False


class TestExtendingHooks:
    """The four hooks an alternative Task implementation calls."""

    def test_register_and_unregister_move_a_task_through_all_tasks(self) -> None:
        async def main() -> tuple[bool, bool]:
            loop = asyncio.get_running_loop()
            stand_in = loop.create_future()
            api("_register_task")(stand_in)
            present = stand_in in asyncio.all_tasks()
            api("_unregister_task")(stand_in)
            absent = stand_in not in asyncio.all_tasks()
            stand_in.set_result(None)
            return present, absent

        assert asyncio.run(main()) == (True, True)

    def test_enter_and_leave_set_the_current_task_slot(self) -> None:
        async def main() -> tuple[bool, bool]:
            loop = asyncio.get_running_loop()
            outer = asyncio.current_task()
            assert outer is not None
            stand_in = loop.create_future()
            api("_leave_task")(loop, outer)
            api("_enter_task")(loop, stand_in)
            entered = asyncio.current_task() is stand_in
            api("_leave_task")(loop, stand_in)
            api("_enter_task")(loop, outer)
            stand_in.set_result(None)
            return entered, asyncio.current_task() is outer

        assert asyncio.run(main()) == (True, True)

    def test_entering_while_another_task_runs_raises(self) -> None:
        async def main() -> None:
            loop = asyncio.get_running_loop()
            stand_in = loop.create_future()
            with pytest.raises(RuntimeError):
                api("_enter_task")(loop, stand_in)
            stand_in.set_result(None)

        asyncio.run(main())


@pytest.mark.skipif(sys.version_info < (3, 14), reason="call graph API added in 3.14")
class TestCallGraphIntrospection:
    """The 3.14 introspection rows."""

    def test_capture_call_graph_returns_a_graph_of_frames(self) -> None:
        async def main() -> tuple[bool, int]:
            graph = api("capture_call_graph")()
            assert graph is not None
            return isinstance(graph, api("FutureCallGraph")), len(graph.call_stack)

        is_graph, frames = asyncio.run(main())
        assert is_graph is True
        assert frames >= 1

    def test_the_frames_are_call_graph_entries(self) -> None:
        async def main() -> bool:
            graph = api("capture_call_graph")()
            assert graph is not None
            return all(isinstance(entry, api("FrameCallGraphEntry")) for entry in graph.call_stack)

        assert asyncio.run(main()) is True

    def test_format_call_graph_renders_the_capture(self) -> None:
        async def main() -> str:
            return api("format_call_graph")()

        text = asyncio.run(main())
        assert isinstance(text, str)
        assert text.strip()

    def test_print_call_graph_renders_what_format_call_graph_does(self) -> None:
        """Both render the same graph; only print's own frame and a newline differ.

        `print_call_graph()` captures from inside itself, so its stack carries
        one extra frame - the `graph.py` line for the call in progress - that a
        direct `format_call_graph()` does not have. Everything else must match,
        which is what distinguishes rendering the graph from rendering nothing.
        """
        import io

        async def main() -> tuple[str, str]:
            buffer = io.StringIO()
            api("print_call_graph")(file=buffer)
            return buffer.getvalue(), api("format_call_graph")()

        printed, formatted = asyncio.run(main())

        def frames(text: str) -> list[str]:
            # Drop the line numbers: the two calls sit on different lines here.
            return [re.sub(r"line \d+", "line N", line) for line in text.splitlines()]

        printed_lines, formatted_lines = frames(printed), frames(formatted)

        assert printed_lines[0] == formatted_lines[0], "the two describe different tasks"
        assert printed_lines[1] == formatted_lines[1] == "  + Call stack:"

        # format's frames are a suffix of print's, which adds its own on top.
        assert printed_lines[-len(formatted_lines) + 2 :] == formatted_lines[2:]
        assert len(printed_lines) == len(formatted_lines) + 1, (
            f"expected exactly one extra frame, got {printed_lines}"
        )
        assert printed.endswith("\n"), "print_call_graph should terminate its output"

    def test_the_normalization_does_not_hide_a_missing_stack(self) -> None:
        """The comparison above would be empty of content if the render were."""

        async def main() -> str:
            return api("format_call_graph")()

        text = asyncio.run(main())
        body = [line for line in text.splitlines() if "line " in line]

        assert body, f"the rendering carries no frame lines: {text!r}"

    def test_awaited_by_registration_is_reversible(self) -> None:
        async def main() -> tuple[int, int]:
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            waiter = asyncio.current_task()
            api("future_add_to_awaited_by")(future, waiter)
            after_add = len(internal(future, "_asyncio_awaited_by") or ())
            api("future_discard_from_awaited_by")(future, waiter)
            after_discard = len(internal(future, "_asyncio_awaited_by") or ())
            future.set_result(None)
            return after_add, after_discard

        assert asyncio.run(main()) == (1, 0)


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


def _run(source: str, cwd: Any) -> subprocess.CompletedProcess[str]:
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


# The calls that reach a peer without one of asyncio's own sockets already
# being connected. `send`/`sendall` are deliberately left alone: the event
# loop's self-pipe writes to itself with `send`, so blocking it deadlocks the
# loop rather than catching anything, and reaching the network through it still
# requires a `connect` this guard does refuse.
_NETWORK_GUARD = (
    "import socket\n"
    "def _blocked(*args, **kwargs):\n"
    "    raise AssertionError('this example opened a socket')\n"
    "socket.socket.connect = _blocked\n"
    "socket.socket.sendto = _blocked\n"
    "socket.create_connection = _blocked\n"
    "socket.getaddrinfo = _blocked\n"
)


class TestDocumentedExamples:
    """Every block runs and asserts its own claim; none needs a peer."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0

        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()[-400:]}")

        assert not failures, "\n".join(failures)
        assert ran == EXPECTED_BLOCKS

    def test_every_block_asserts_something(self) -> None:
        """Execution alone would pass a block that demonstrated nothing."""
        for line, source in _blocks():
            assert "assert" in source, f"{PAGE.name}:{line} runs but claims nothing"

    def test_no_block_reaches_the_network(self, tmp_path: pathlib.Path) -> None:
        """Enforced by breaking the socket, not by grepping for call names."""
        guard = _NETWORK_GUARD

        for line, source in _blocks():
            workdir = tmp_path / f"guard{line}"
            workdir.mkdir()
            result = _run(guard + source, workdir)
            assert result.returncode == 0, (
                f"{PAGE.name}:{line} failed under the socket guard: {result.stderr.strip()[-400:]}"
            )

    def test_the_socket_guard_catches_a_block_that_connects(self, tmp_path: pathlib.Path) -> None:
        """A guard that cannot fail would not enforce anything."""
        guard = _NETWORK_GUARD
        reaching_out = {
            "connect": "import socket\nsocket.socket().connect(('example.com', 80))\n",
            "create_connection": ("import socket\nsocket.create_connection(('example.com', 80))\n"),
            "getaddrinfo": "import socket\nsocket.getaddrinfo('example.com', 80)\n",
            "sendto": (
                "import socket\n"
                "s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)\n"
                "s.sendto(b'x', ('192.0.2.1', 9))\n"
            ),
        }

        for name, source in reaching_out.items():
            workdir = tmp_path / f"control_{name}"
            workdir.mkdir()
            result = _run(guard + source, workdir)
            assert result.returncode != 0, f"the guard let {name} through"
            assert "opened a socket" in result.stderr, f"{name} failed for another reason"

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = next(source for _, source in _blocks() if "import asyncio" in source)
        broken = original.replace("import asyncio", "import asyncio_missing as asyncio", 1)
        assert broken != original, "the mutation did not reach the import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "ModuleNotFoundError" in result.stderr

    def test_the_runner_catches_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        """Execution alone would pass a block whose claim had been negated."""
        target = "assert first is not second"
        original = next(source for _, source in _blocks() if target in source)
        broken = original.replace(target, "assert first is second", 1)
        assert broken != original, "the mutation did not reach the assertion"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "AssertionError" in result.stderr
