"""Tests for docs/stdlib/multiprocessing.md.

The page prices the module by what crosses between processes: the time to
start one, the time a call spends blocked, and the pickled bytes sent. None of
those three can be pinned by a test on a shared machine, so the tests settle
what the bounds are made of instead - who pickles, in which thread and how
often, how many messages a call sends, which calls wait and which return at
once, and what is shared rather than copied. Counting ``__getstate__`` and
``__setstate__``, counting messages on a connection, and checking identity
need no tolerance; the waits are settled by a gate the test holds and then
releases, with a timeout far longer than the release takes.

Measurement scope:

* ``Process``: an unstarted one has no pid, ident or exitcode, is not alive,
  raises ValueError for ``sentinel`` and is absent from ``active_children()``;
  a list passed as ``args`` is copied; the target runs once, in a process
  whose pid is the Process's and whose ``parent_process()`` is the caller,
  while a direct ``run()`` runs it in the caller. ``join()`` on a finished
  child returns at once and on a blocked one after its 50 ms timeout with the
  child alive. ``terminate()`` and ``kill()`` leave exit codes of -SIGTERM
  and -SIGKILL, and ``terminate()`` returns at once from a child that ignores
  SIGTERM; on 3.14 ``interrupt()`` reaches the child's SIGINT handler.
  ``close()`` refuses a live child, and afterwards ``is_alive()``, ``join()``,
  ``exitcode`` and ``pid`` raise ValueError. With three live children,
  ``active_children()`` polls each once and returns a new list, and
  ``start()`` polls all three. An argument's ``__getstate__`` runs once in
  the parent during ``start()`` under ``spawn`` and ``forkserver``, never
  under ``fork``.
* Start methods: in a fresh interpreter the first ``forkserver`` start sets
  the server's pid and a second start keeps it; a ``fork`` start with a
  second thread running warns DeprecationWarning from 3.12 and not before;
  the resource tracker has no pid before the first ``Lock()`` or ``Queue()``
  and one afterwards under ``spawn`` and ``forkserver``, none under ``fork``,
  while the first ``SharedMemory`` or ``SharedMemoryManager()`` starts it
  under all three.
  ``get_all_start_methods()`` is a new list each call, an unknown method
  raises ValueError, and a second ``set_start_method()`` raises RuntimeError
  unless forced.
* ``Pool``: ``Pool(2)`` adds two children and ``close()`` + ``join()``
  removes them, a default ``Pool()`` adds the CPU count. ``map()`` returns
  results in order and exhausts a generator; ``map_async()`` has exhausted
  one, in the calling thread, by the time it returns, with its tasks held
  behind a file gate. Over 1000 items on two workers the function's
  ``__getstate__`` runs 1000 times with ``chunksize=1``, 8 with the default
  and once with ``chunksize=1000``; ``imap`` pickles it 100 times over 100
  items and 10 with ``chunksize=10``. ``imap()`` yields its first item while
  its input generator is still gated, and with nothing consumed it reads a
  100-item generator to the end and buffers all six results of another
  call. Over a gated first task and a free second, ``imap`` parks the free
  result where ``imap_unordered`` yields it. Results of ``apply_async`` and
  ``imap`` are unpickled once, in a thread that is not the main one, before
  ``get()`` or ``next()``, which do not unpickle them again. A callback runs
  in the pool's result-handler thread and sees ``ready()`` false, and while one is held, a result
  submitted after it does not become ready. ``get(timeout=0.05)`` raises
  ``multiprocessing.TimeoutError``, which is not the builtin. ``join()``
  before ``close()`` and ``apply_async()`` after it raise ValueError; a task
  that has started when a ``with`` block ends never finishes, and its worker
  is gone by then. A ``ThreadPool`` starts no children, pickles nothing and
  returns the function's own objects; its ``terminate()`` returns while a
  running task is still blocked, and that task then finishes.
* ``Queue``: with the feeder held inside one object's ``__getstate__``, a
  later ``put()`` has returned without pickling its object, which arrives
  with a mutation made after ``put()``. Putting a lambda prints a traceback
  in the feeder and ``get(timeout)`` raises Empty. ``maxsize=1`` raises Full
  on the second ``put_nowait`` and after a 50 ms timed put. A payload's
  ``__setstate__`` finds the reader lock free during ``get()``. With the
  feeder held ``qsize()`` is 1 while ``empty()`` stays true, until the
  feeder writes. After ``close()``, ``put`` and ``get`` raise ValueError,
  ``join_thread()`` waits for the held feeder, and the items buffered behind
  it still reach a child. ``JoinableQueue.join()`` waits for both of two
  ``task_done()`` calls, and a third raises ValueError. ``SimpleQueue.put``
  pickles once, in the calling thread, before returning. On macOS
  ``qsize()`` raises NotImplementedError.
* ``Connection``: ``send`` pickles once, in the calling thread; a one-way
  pipe's ends refuse the other direction; ``recv_bytes(maxlength)`` raises
  OSError for a longer message and ``recv_bytes_into`` a short buffer raises
  BufferTooShort carrying it; ``poll()`` is false at once, false after a
  50 ms timeout and true after a send; a 4 MiB ``send_bytes`` is still
  blocked after 300 ms with no reader and finishes once one reads; a closed
  connection refuses ``recv`` and ``fileno``.
* ``Listener`` and ``Client``: ``last_accepted`` is None before a client and
  set after, a connection round-trips a message, and a closed listener
  refuses ``accept()``. A mismatched ``authkey`` raises AuthenticationError
  on both ends. ``deliver_challenge()`` sends two messages and
  ``answer_challenge()`` one, of the same lengths for a 1-byte and a
  100,000-byte key. ``wait()`` asks each of five objects for its descriptor
  on every call, returns only the ready one in a new list, and returns an
  empty one after its 50 ms timeout.
* Locks and conditions: a held Lock refuses a non-blocking acquire and gives
  up a 50 ms one after at least 45 ms; an unheld Lock raises ValueError on
  release and an unheld RLock AssertionError; an RLock held three times is
  refused to another thread until the third release; on 3.14 ``locked()``
  follows the state; Semaphore(2) grants two and refuses a third, and
  BoundedSemaphore refuses a release past its value. ``notify(2)`` wakes
  exactly two of six waiters and ``notify_all()`` the rest; three timed-out
  waits leave three acknowledgements that the next ``notify()`` clears; after
  a child asleep on an Event is killed, ``set()`` is still blocked after
  200 ms. A waiter releases a doubly held RLock for the notifier and holds it
  twice again on return. ``wait_for`` calls a true predicate once and one
  made true by a notify twice. ``Event.set()`` wakes five sleeping waiters;
  ``wait()`` returns at once when set and False after its timeout when not.
  The third of three barrier parties releases the others and runs the action
  once; ``abort()`` and ``reset()`` raise BrokenBarrierError in both waiters,
  ``abort()`` leaving the barrier broken; an expired 50 ms timeout breaks it.
* Shared ctypes: ``Value(lock=False)`` is the bare ctypes object; a counting
  lock passed to ``Value`` is taken once per read or write of ``value`` -
  twice for ``+=`` - and by ``Array`` once per item, once per slice and never
  for ``len()``. ``Array`` from a sequence is a copy, its slice a new list
  each time, bytes for ``'c'`` and str for ``'u'``; a Structure RawValue is
  zeroed and a ``c_char`` value is a fresh bytes object. A child's writes to
  a Value, an Array and a RawArray are visible in the parent.
  ``synchronized()`` returns a wrapper whose ``get_obj()`` is the object
  passed in, and two calls on one Structure type share a wrapper class with
  a property per field. A Value, an Array, a RawValue and a RawArray passed to
  ``Pool.apply()`` each raise RuntimeError.
* ``SharedMemory``, in a timing test: creating a 16 MiB block costs under
  50 times a 4 KiB one, fastest of seven, against the 4096x a linear cost
  would give. ``buf`` is the same object on every access, a slice of it
  writes into the block, and ``close()`` raises BufferError while the slice
  is alive. A 64-byte and a 16 MiB block each pickle to under 200 bytes. A
  block a child interpreter creates and does not unlink is gone
  from /dev/shm once the child exits; so is one this process created and
  unregistered that a child merely attached to; one created with
  ``track=False`` (3.13+) is still there. ``ShareableList`` keeps its length,
  takes a 7-byte str in the 8-byte slot of a 4-byte one and refuses 9 bytes
  with ValueError, and gives an 8-byte value a 16-byte slot, shares writes with a
  list attached by name, grows by at least 9,000 bytes for a 10,000-character
  str, reads every one of 100 items for ``count()`` and at most seven for
  ``index(5)``, and returns a new ``format`` string per access.
* Managers: ``Manager()`` adds one child and its ``with`` block removes it; a
  ``SyncManager()`` adds none until ``start()``, has no ``shutdown`` before
  it, and refuses a second ``start()`` with ProcessError. On the thread's
  server connection, ``append`` and ``[:]`` on a five-item list proxy each
  send one message, iteration six and ``list()`` seven; a dict proxy's
  ``copy()``, ``keys()``, ``values()`` and ``items()`` send one each,
  ``dict()`` six and iteration seven; ``_getvalue()`` and ``_callmethod()``
  send one each. ``connect()`` adds no child and its list lands in the first
  server; ``get_server()`` on a started manager raises ProcessError.
  ``register()`` on a subclass adds the factory there only, copies the
  inherited registry on its first call and not on a second.
  ``SharedMemoryManager.SharedMemory()`` and ``.ShareableList()`` each make
  one ``track_segment`` call, and both blocks are gone once the ``with``
  block ends.
* ``multiprocessing.dummy``: ``Pipe()`` delivers the sent object itself
  without pickling it, ``Process`` is a Thread subclass, ``Queue`` is
  ``queue.Queue``, ``Manager()`` is the module and ``Pool()`` a ThreadPool.
* ``cpu_count()`` is ``os.cpu_count()``; ``get_logger()`` is one object and
  two ``log_to_stderr()`` calls add two handlers; the exceptions subclass
  ProcessError; ``SUBDEBUG`` and ``SUBWARNING`` are 5 and 25; ``reducer`` is
  the ``reduction`` module.
* Every fenced Python block runs as a script in its own interpreter and
  directory, asserting its own results, and a mutated assertion in one of
  them is asserted to fail.

Not settled here:

* s, w and b themselves: how long a start takes, how long a call blocks, and
  how many bytes an object pickles to belong to the platform and to pickle.
  So do the ``m`` of a manager round trip and the challenge's HMAC.
* ``RawArray``'s zeroing and the ``ShareableList`` attach cost of one offset
  per item are read from Lib/multiprocessing/sharedctypes.py and
  shared_memory.py; the tests see only the results. So is the O(g²) of
  ``SharedMemoryManager.shutdown()``: ``_SharedMemoryTracker.unlink()`` in
  Lib/multiprocessing/managers.py removes each name from the front of a
  list, and blocks enough to show it do not fit in a container's /dev/shm.
* The cost of the HMAC over the key itself is not priced: the page treats
  the challenge as a round trip of fixed-size messages.
* ``freeze_support()`` inside a frozen executable, and ``set_executable()``
  and ``set_forkserver_preload()`` beyond storing their value, which only the
  next child start reads.
* The deadlock of two peers that both send a large message before receiving
  is inferred from the one-way block, not staged.
* macOS, where ``Queue.qsize()`` and ``Semaphore.get_value()`` raise
  NotImplementedError and a ``BoundedSemaphore`` checks over-release only
  for an initial value of 1: the tests skip those assertions or guard them
  on ``sys.platform``, so no run here verifies them. The SharedMemory and
  ShareableList tests look blocks up in /dev/shm and run on Linux only.
* Windows, where ``Pipe()`` returns a PipeConnection, ``Listener`` uses a
  named pipe whose ``last_accepted`` stays None, the signals are
  TerminateProcess, ``interrupt()`` is missing, there is no resource
  tracker, ``SharedMemory.unlink()`` does nothing, and
  ``multiprocessing.popen_spawn_win32`` imports ``msvcrt``, which is also why
  the page-scoped audit reports that module as an inspection error here.

Not varied: pool workers beyond two except for the default count, pickled
sizes beyond a few kilobytes except for the 4 MiB blocking send, manager
serializers other than pickle, ``initializer`` and ``maxtasksperchild``, and
contention between more than one child process on a primitive.

Every helper thread is a daemon and every child is joined or killed, so a
failing assertion cannot hang the interpreter at exit. A child is never killed
while it waits on a primitive the test uses again, since the killed-sleeper
test shows what that does to the next ``set()``.
"""

from __future__ import annotations

import builtins
import ctypes
import math
import multiprocessing
import multiprocessing.connection
import multiprocessing.dummy
import multiprocessing.managers
import multiprocessing.pool
import multiprocessing.queues
import multiprocessing.shared_memory
import multiprocessing.sharedctypes
import multiprocessing.synchronize
import os
import pathlib
import pickle
import queue
import re
import signal
import subprocess
import sys
import textwrap
import threading
import time
import warnings
from collections.abc import Callable, Iterator
from typing import Any, cast

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "multiprocessing.md"
EXPECTED_BLOCKS = 12
WAIT = 10.0
SHORT = 0.05
POSIX = sys.platform != "win32"


def wait_until(predicate: Callable[[], bool], timeout: float = WAIT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.001)
    return predicate()


def spawn_thread(target: Callable[..., object], *args: object) -> threading.Thread:
    """Start a daemon thread, so a test that fails cannot hang the process at exit."""
    thread = threading.Thread(target=target, args=args, daemon=True)
    thread.start()
    return thread


def join_threads(threads: list[threading.Thread]) -> None:
    for thread in threads:
        thread.join(WAIT)
    stuck = [thread for thread in threads if thread.is_alive()]
    assert not stuck, f"{len(stuck)} threads did not finish: {stuck}"


def join_process(process: multiprocessing.Process) -> None:
    process.join(WAIT)
    if process.is_alive():
        process.kill()
        process.join(WAIT)
        raise AssertionError(f"{process} did not finish and was killed")


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


# Every callable a child process runs lives at module level, so that spawn
# and forkserver children can import it by reference.

PICKLES: list[str] = []
PICKLERS: list[threading.Thread] = []


class Counting:
    """Records, in the process that pickles it, each time and in which thread it is pickled."""

    def __init__(self, tag: str) -> None:
        self.tag = tag

    def __getstate__(self) -> dict[str, str]:
        PICKLES.append(self.tag)
        PICKLERS.append(threading.current_thread())
        return {"tag": self.tag}

    def __call__(self, value: int) -> int:
        return value * 2


UNPICKLES: list[threading.Thread] = []


class Reconstructed:
    """Records, in the process that unpickles it, which thread did so."""

    def __init__(self, tag: str) -> None:
        self.tag = tag

    def __setstate__(self, state: dict[str, str]) -> None:
        UNPICKLES.append(threading.current_thread())
        self.__dict__.update(state)


def make_reconstructed(tag: str) -> Reconstructed:
    return Reconstructed(tag)


LOCK_PROBE: dict[str, Any] = {}


class LockProbing:
    """Records, while being unpickled, whether the lock left in LOCK_PROBE is free."""

    def __init__(self) -> None:
        self.tag = "probe"  # a state to unpickle, so __setstate__ runs

    def __setstate__(self, state: dict[str, str]) -> None:
        lock = LOCK_PROBE["lock"]
        free = lock.acquire(False)
        if free:
            lock.release()
        LOCK_PROBE["free"] = free
        self.__dict__.update(state)


FEEDER_ENTERED = threading.Event()
FEEDER_GATE = threading.Event()


class Blocking:
    """Holds whichever thread pickles it until the test opens the gate."""

    def __getstate__(self) -> dict[str, int]:
        FEEDER_ENTERED.set()
        FEEDER_GATE.wait(WAIT)
        return {}


def identity(value: Any) -> Any:
    return value


def double(value: int) -> int:
    return value * 2


def add(left: int, right: int) -> int:
    return left + right


def signal_then_wait_then_write(started: str, gate_path: str, done: str) -> None:
    pathlib.Path(started).write_text("started", encoding="utf-8")
    wait_for_file(gate_path)
    pathlib.Path(done).write_text("done", encoding="utf-8")


def wait_for_file(path: str | None) -> None:
    """Block until the parent creates the file; a task's gate that survives pickling."""
    if path is not None:
        deadline = time.monotonic() + WAIT
        while not os.path.exists(path) and time.monotonic() < deadline:
            time.sleep(0.001)


def gated_task(task: tuple[str | None, str]) -> str:
    gate_path, value = task
    wait_for_file(gate_path)
    return value


def gated_return(gate_path: str | None, value: int = 0) -> int:
    wait_for_file(gate_path)
    return value


def report(conn: Any, *args: Any, **kwargs: Any) -> None:
    parent = multiprocessing.parent_process()
    conn.send(
        {
            "pid": os.getpid(),
            "current": multiprocessing.current_process().pid,
            "parent": None if parent is None else parent.pid,
            "args": args,
            "kwargs": kwargs,
        }
    )
    conn.close()


def wait_on(event: Any) -> None:
    event.wait(WAIT)


def handle_sigint_then_wait(ready: Any, event: Any) -> None:
    signal.signal(signal.SIGINT, lambda *_: sys.exit(3))
    ready.set()
    event.wait(WAIT)


def ignore_sigterm_then_wait(ready: Any, gate_path: str) -> None:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    ready.set()
    wait_for_file(gate_path)


def write_shared(value: Any, array: Any, raw: Any) -> None:
    value.value = 42
    for index in range(len(array)):
        array[index] = index * 10
    for index in range(len(raw)):
        raw[index] = index + 1


def produce(target: Any, items: Any) -> None:
    for item in items:
        target.put(item)


def drain_queue(source: Any, count: int, conn: Any) -> None:
    """Report what arrived by value or, for an object, by type name, which pickles freely."""
    received = [source.get(timeout=WAIT) for _ in range(count)]
    conn.send([item if isinstance(item, int) else type(item).__name__ for item in received])
    conn.close()


def echo(conn: Any) -> None:
    conn.send(conn.recv())
    conn.close()


def drain(iterable: Any) -> None:
    for _ in iterable:
        pass


def run_python(source: str) -> subprocess.CompletedProcess[str]:
    """Run a dedented snippet in a fresh interpreter, for state that only a new process has."""
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        capture_output=True,
        text=True,
        timeout=60,
        stdin=subprocess.DEVNULL,
        check=False,
    )


def shm_exists(name: str) -> bool:
    """Whether a POSIX shared-memory block exists, looked up without attaching to it."""
    return os.path.exists(os.path.join("/dev/shm", name.lstrip("/")))


class CountingFileno:
    """Counts how often ``wait()`` asks it for its descriptor."""

    def __init__(self, conn: Any) -> None:
        self.conn = conn
        self.calls = 0

    def fileno(self) -> int:
        self.calls += 1
        return self.conn.fileno()


class CountingLock:
    """A lock that only counts, for observing what the shared-ctypes wrappers hold it for."""

    def __init__(self) -> None:
        self.acquires = 0
        self.releases = 0

    def acquire(self, *args: object) -> bool:
        self.acquires += 1
        return True

    def release(self) -> None:
        self.releases += 1

    def __enter__(self) -> bool:
        return self.acquire()

    def __exit__(self, *args: object) -> None:
        self.release()


@pytest.fixture
def gate() -> Iterator[Any]:
    """A process-shared Event that releases every child blocked on it when the test ends."""
    event = multiprocessing.Event()
    yield event
    event.set()


@pytest.fixture
def pool() -> Iterator[multiprocessing.pool.Pool]:
    with multiprocessing.Pool(2) as running:
        yield running


class TestProcessRows:
    """Process(), start(), run(), join(), the signals, close() and the registry."""

    def test_a_process_object_is_inert_until_started(self) -> None:
        parent_end, child_end = multiprocessing.Pipe()
        process = multiprocessing.Process(target=report, args=(child_end,))

        assert process.pid is None
        assert process.ident is None
        assert process.exitcode is None
        assert not process.is_alive()
        assert process not in multiprocessing.active_children()
        with pytest.raises(ValueError):
            _ = process.sentinel
        assert not parent_end.poll(SHORT), "the target ran without start()"

    def test_start_runs_the_target_once_in_the_child_with_a_copy_of_the_arguments(self) -> None:
        parent_end, child_end = multiprocessing.Pipe()
        args = [child_end, 1, 2]
        process = multiprocessing.Process(target=report, args=args, kwargs={"k": 3})
        args.append(4)

        process.start()
        child_end.close()
        try:
            assert parent_end.poll(WAIT)
            seen = parent_end.recv()
            with pytest.raises(EOFError):
                parent_end.recv()
        finally:
            join_process(process)

        assert seen["pid"] == process.pid != os.getpid()
        assert seen["current"] == process.pid
        assert seen["parent"] == os.getpid()
        assert seen["args"] == (1, 2)
        assert seen["kwargs"] == {"k": 3}
        assert process.exitcode == 0
        assert isinstance(process.sentinel, int)

    def test_a_direct_run_call_runs_the_target_in_the_caller(self) -> None:
        calls: list[int] = []
        multiprocessing.Process(target=lambda: calls.append(os.getpid())).run()

        assert calls == [os.getpid()]

        multiprocessing.Process().run()

    def test_join_is_immediate_on_a_finished_child_and_bounded_by_its_timeout(
        self, gate: Any
    ) -> None:
        finished = multiprocessing.Process(target=identity, args=(1,))
        finished.start()
        join_process(finished)
        start = time.perf_counter()
        finished.join(WAIT)
        assert time.perf_counter() - start < WAIT / 2

        blocked = multiprocessing.Process(target=wait_on, args=(gate,))
        blocked.start()
        try:
            start = time.perf_counter()
            blocked.join(SHORT)
            elapsed = time.perf_counter() - start
            assert elapsed >= SHORT * 0.9, elapsed
            assert blocked.is_alive()
        finally:
            gate.set()
            join_process(blocked)
        assert not blocked.is_alive()
        assert blocked.exitcode == 0

    @pytest.mark.skipif(not POSIX, reason="exit codes are signal numbers only on POSIX")
    def test_terminate_and_kill_return_at_once_and_join_reports_the_signal(
        self, tmp_path: pathlib.Path
    ) -> None:
        never_opened = str(tmp_path / "never-opened")
        for method, signum in (("terminate", signal.SIGTERM), ("kill", signal.SIGKILL)):
            process = multiprocessing.Process(target=wait_for_file, args=(never_opened,))
            process.start()
            getattr(process, method)()
            join_process(process)

            assert process.exitcode == -signum, method

        ready = multiprocessing.Event()
        stubborn = multiprocessing.Process(
            target=ignore_sigterm_then_wait, args=(ready, never_opened)
        )
        stubborn.start()
        try:
            assert ready.wait(WAIT)
            start = time.perf_counter()
            stubborn.terminate()
            assert time.perf_counter() - start < WAIT / 2, "terminate() waited for the exit"
            stubborn.join(SHORT)
            assert stubborn.is_alive(), "the child should have ignored SIGTERM"
        finally:
            stubborn.kill()
            join_process(stubborn)
        assert stubborn.exitcode == -signal.SIGKILL

    @pytest.mark.skipif(
        not POSIX or sys.version_info < (3, 14),
        reason="Process.interrupt() was added in Python 3.14",
    )
    def test_interrupt_sends_sigint(self, gate: Any) -> None:
        ready = multiprocessing.Event()
        process = multiprocessing.Process(target=handle_sigint_then_wait, args=(ready, gate))
        process.start()
        try:
            assert ready.wait(WAIT)
            cast("Any", process).interrupt()
        finally:
            gate.set()
            join_process(process)

        assert process.exitcode == 3

    def test_close_refuses_a_live_child_and_then_disables_the_object(self, gate: Any) -> None:
        process = multiprocessing.Process(target=wait_on, args=(gate,))
        process.start()
        try:
            with pytest.raises(ValueError):
                process.close()
        finally:
            gate.set()
            join_process(process)

        process.close()

        for probe in (
            process.is_alive,
            process.join,
            lambda: process.exitcode,
            lambda: process.pid,
        ):
            with pytest.raises(ValueError):
                probe()

    def test_active_children_polls_each_live_child_and_so_does_start(self, gate: Any) -> None:
        before = multiprocessing.active_children()
        children = [multiprocessing.Process(target=wait_on, args=(gate,)) for _ in range(3)]
        for child in children:
            child.start()
        popen_type = type(cast("Any", children[0])._popen)
        original_poll = popen_type.poll
        polls: list[int] = []

        def counting_poll(self: Any, *args: Any) -> Any:
            polls.append(1)
            return original_poll(self, *args)

        popen_type.poll = counting_poll
        extra: multiprocessing.Process | None = None
        try:
            first = multiprocessing.active_children()
            second = multiprocessing.active_children()
            assert set(children) <= set(first)
            assert len(first) == len(before) + 3
            assert len(polls) == 2 * len(first), polls
            assert first == second and first is not second

            polls.clear()
            extra = multiprocessing.Process(target=identity, args=(1,))
            extra.start()
            assert len(polls) == len(first), "start() should have polled every live child"
        finally:
            popen_type.poll = original_poll
            gate.set()
            if extra is not None:
                join_process(extra)
            for child in children:
                join_process(child)

        assert not set(children) & set(multiprocessing.active_children())

    def test_the_main_process_has_no_parent(self) -> None:
        assert multiprocessing.current_process().name == "MainProcess"
        assert multiprocessing.current_process().pid == os.getpid()
        assert multiprocessing.parent_process() is None

    @pytest.mark.parametrize("method", ["fork", "spawn", "forkserver"])
    def test_start_pickles_the_arguments_under_spawn_and_forkserver_only(self, method: str) -> None:
        if method not in multiprocessing.get_all_start_methods():
            pytest.skip(f"the {method} start method is not available here")
        context = multiprocessing.get_context(method)
        argument = Counting("argument")
        PICKLES.clear()

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            process = cast("Any", context).Process(target=identity, args=(argument,))
            process.start()
        join_process(process)

        assert process.exitcode == 0
        assert PICKLES.count("argument") == (0 if method == "fork" else 1), PICKLES


class TestPoolRows:
    """Pool(), the map family, AsyncResult, close(), join() and terminate()."""

    def test_the_pool_starts_its_workers_and_join_reaps_them(self) -> None:
        before = len(multiprocessing.active_children())

        pool = multiprocessing.Pool(2)
        try:
            assert len(multiprocessing.active_children()) == before + 2
        finally:
            pool.close()
            pool.join()

        assert len(multiprocessing.active_children()) == before

    def test_the_default_worker_count_is_the_cpu_count(self) -> None:
        before = len(multiprocessing.active_children())
        if sys.version_info >= (3, 13):
            expected = os.process_cpu_count() or 1
        else:
            expected = os.cpu_count() or 1

        pool = multiprocessing.Pool()
        try:
            assert len(multiprocessing.active_children()) == before + expected
        finally:
            pool.close()
            pool.join()

    def test_map_returns_results_in_order_and_lists_an_unsized_input(
        self, pool: multiprocessing.pool.Pool
    ) -> None:
        items = iter(range(50))

        assert pool.map(double, items) == [value * 2 for value in range(50)]
        assert next(items, None) is None, "the generator should have been exhausted"
        assert pool.starmap(add, [(1, 2), (3, 4)]) == [3, 7]

    def test_map_async_lists_an_unsized_input_before_returning(
        self, pool: multiprocessing.pool.Pool, tmp_path: pathlib.Path
    ) -> None:
        gate_path = tmp_path / "open"
        consumers: list[threading.Thread] = []

        def gates() -> Iterator[str]:
            for _ in range(3):
                consumers.append(threading.current_thread())
                yield str(gate_path)

        generator = gates()
        result = pool.map_async(gated_return, generator)

        assert next(generator, None) is None, "map_async returned without listing the input"
        assert consumers == [threading.main_thread()] * 3
        assert not result.ready()
        gate_path.write_text("", encoding="utf-8")
        assert result.get(WAIT) == [0, 0, 0]

    def test_map_pickles_the_function_once_per_chunk(self, pool: multiprocessing.pool.Pool) -> None:
        function = Counting("function")
        expected = [value * 2 for value in range(1000)]

        PICKLES.clear()
        assert pool.map(function, range(1000), chunksize=1) == expected
        assert PICKLES.count("function") == 1000

        PICKLES.clear()
        assert pool.map(function, range(1000)) == expected
        default_chunks = math.ceil(1000 / math.ceil(1000 / (4 * 2)))
        assert PICKLES.count("function") == default_chunks == 8

        PICKLES.clear()
        assert pool.map(function, range(1000), chunksize=1000) == expected
        assert PICKLES.count("function") == 1

        PICKLES.clear()
        assert pool.apply(function, (21,)) == 42
        assert PICKLES.count("function") == 1

    def test_imap_pickles_the_function_per_item_unless_chunked(
        self, pool: multiprocessing.pool.Pool
    ) -> None:
        function = Counting("function")

        PICKLES.clear()
        assert list(pool.imap(function, range(100))) == [value * 2 for value in range(100)]
        assert PICKLES.count("function") == 100

        PICKLES.clear()
        assert sorted(pool.imap_unordered(function, range(100), chunksize=10)) == [
            value * 2 for value in range(100)
        ]
        assert PICKLES.count("function") == 10

    def test_map_async_returns_before_the_work_is_done(
        self, pool: multiprocessing.pool.Pool, tmp_path: pathlib.Path
    ) -> None:
        gate_path = tmp_path / "open"

        result = pool.map_async(gated_return, [str(gate_path)] * 2)

        assert not result.ready()
        result.wait(SHORT)
        assert not result.ready()
        gate_path.write_text("", encoding="utf-8")
        assert result.get(WAIT) == [0, 0]
        assert result.ready() and result.successful()

    def test_imap_returns_while_its_input_is_still_being_produced(
        self, pool: multiprocessing.pool.Pool
    ) -> None:
        release = threading.Event()

        def items() -> Iterator[int]:
            yield 1
            release.wait(WAIT)
            yield 2

        try:
            start = time.perf_counter()
            iterator = pool.imap(double, items())
            first = next(iterator)
            assert time.perf_counter() - start < WAIT / 2, "the input was listed before returning"
            assert not release.is_set()
        finally:
            release.set()
        assert first == 2
        assert list(iterator) == [4]

    def test_imap_buffers_results_the_consumer_has_not_asked_for(
        self, pool: multiprocessing.pool.Pool
    ) -> None:
        iterator = pool.imap(identity, range(6))

        assert wait_until(lambda: len(cast("Any", iterator)._items) == 6)
        assert list(iterator) == list(range(6))

    def test_imap_reads_the_whole_input_without_being_iterated(
        self, pool: multiprocessing.pool.Pool
    ) -> None:
        consumed: list[int] = []

        def numbers() -> Iterator[int]:
            for number in range(100):
                consumed.append(number)
                yield number

        iterator = pool.imap(identity, numbers())

        assert wait_until(lambda: len(consumed) == 100), f"read {len(consumed)} of 100"
        assert list(iterator) == list(range(100))

    def test_imap_results_are_unpickled_before_next_asks_for_them(
        self, pool: multiprocessing.pool.Pool
    ) -> None:
        UNPICKLES.clear()
        iterator = pool.imap(make_reconstructed, ["a", "b"])

        assert wait_until(lambda: len(cast("Any", iterator)._items) == 2)
        assert len(UNPICKLES) == 2
        assert threading.main_thread() not in UNPICKLES
        assert [item.tag for item in iterator] == ["a", "b"]
        assert len(UNPICKLES) == 2, "next() unpickled a result again"

    def test_a_slow_callback_holds_up_every_later_result(
        self, pool: multiprocessing.pool.Pool
    ) -> None:
        entered = threading.Event()
        release = threading.Event()

        def slow(_: int) -> None:
            entered.set()
            release.wait(WAIT)

        first = pool.apply_async(identity, (1,), callback=slow)
        assert entered.wait(WAIT)
        second = pool.apply_async(identity, (2,))
        try:
            second.wait(SHORT * 6)
            assert not second.ready(), "a result was delivered while a callback ran"
        finally:
            release.set()
        assert second.get(WAIT) == 2
        assert first.get(WAIT) == 1

    def test_a_thread_pool_passes_tasks_and_results_by_reference(self) -> None:
        function = Counting("threaded")
        payload = [object()]
        children = len(multiprocessing.active_children())
        PICKLES.clear()

        with multiprocessing.pool.ThreadPool(2) as pool:
            assert len(multiprocessing.active_children()) == children
            assert pool.map(function, range(10)) == [value * 2 for value in range(10)]
            assert pool.map(identity, payload)[0] is payload[0]
            assert next(pool.imap(identity, payload)) is payload[0]

        assert PICKLES == []

    def test_a_thread_pool_terminate_leaves_a_running_task_running(self) -> None:
        entered = threading.Event()
        release = threading.Event()
        finished: list[int] = []

        def task() -> None:
            entered.set()
            release.wait(WAIT)
            finished.append(1)

        pool = multiprocessing.pool.ThreadPool(1)
        pool.apply_async(task)
        assert entered.wait(WAIT)
        terminator = spawn_thread(pool.terminate)
        try:
            join_threads([terminator])
            assert finished == [], "terminate() waited for the task"
        finally:
            release.set()
        assert wait_until(lambda: finished == [1]), "the task was stopped"

    def test_imap_keeps_input_order_and_imap_unordered_yields_on_arrival(
        self, pool: multiprocessing.pool.Pool, tmp_path: pathlib.Path
    ) -> None:
        first_gate = tmp_path / "first"
        ordered = pool.imap(gated_task, [(str(first_gate), "gated"), (None, "free")])
        assert wait_until(lambda: 1 in cast("Any", ordered)._unsorted), "free never arrived"
        with pytest.raises(multiprocessing.TimeoutError):
            cast("Any", ordered).next(SHORT)
        first_gate.write_text("", encoding="utf-8")
        assert list(ordered) == ["gated", "free"]

        second_gate = tmp_path / "second"
        unordered = pool.imap_unordered(gated_task, [(str(second_gate), "gated"), (None, "free")])
        assert next(unordered) == "free"
        second_gate.write_text("", encoding="utf-8")
        assert list(unordered) == ["gated"]

    def test_get_with_a_timeout_raises_the_package_timeout_error(
        self, pool: multiprocessing.pool.Pool, tmp_path: pathlib.Path
    ) -> None:
        gate_path = tmp_path / "open"
        result = pool.apply_async(gated_return, (str(gate_path), 7))

        with pytest.raises(ValueError):
            result.successful()
        with pytest.raises(multiprocessing.TimeoutError):
            result.get(timeout=SHORT)
        assert not issubclass(multiprocessing.TimeoutError, builtins.TimeoutError)
        gate_path.write_text("", encoding="utf-8")
        assert result.get(WAIT) == 7
        assert result.successful()

    def test_the_result_is_unpickled_by_the_handler_thread_before_get(
        self, pool: multiprocessing.pool.Pool
    ) -> None:
        UNPICKLES.clear()

        result = pool.apply_async(make_reconstructed, ("value",))
        result.wait(WAIT)

        assert result.ready()
        assert len(UNPICKLES) == 1, "the result was not reconstructed before get()"
        assert UNPICKLES[0] is not threading.main_thread()
        assert result.get(WAIT).tag == "value"
        assert len(UNPICKLES) == 1, "get() reconstructed it again"

    def test_a_callback_runs_in_the_handler_thread_before_ready(
        self, pool: multiprocessing.pool.Pool
    ) -> None:
        seen: dict[str, object] = {}
        bound = threading.Event()

        def callback(value: int) -> None:
            bound.wait(WAIT)
            seen["thread"] = threading.current_thread()
            seen["ready"] = result.ready()
            seen["value"] = value

        result = pool.apply_async(identity, (5,), callback=callback)
        bound.set()

        assert result.get(WAIT) == 5
        assert seen["thread"] is cast("Any", pool)._result_handler
        assert seen["ready"] is False
        assert seen["value"] == 5

    def test_close_refuses_new_tasks_and_join_requires_it(self) -> None:
        pool = multiprocessing.Pool(1)
        try:
            with pytest.raises(ValueError):
                pool.join()
            pending = pool.apply_async(double, (4,))
            pool.close()
            with pytest.raises(ValueError):
                pool.apply_async(double, (5,))
            assert pending.get(WAIT) == 8
        finally:
            pool.terminate()
            pool.join()

    def test_the_context_manager_terminates_rather_than_waits(self, tmp_path: pathlib.Path) -> None:
        started = tmp_path / "started"
        gate_path = tmp_path / "never-opened"
        marker = tmp_path / "done"
        before = len(multiprocessing.active_children())

        with multiprocessing.Pool(1) as pool:
            assert len(multiprocessing.active_children()) == before + 1
            result = pool.apply_async(
                signal_then_wait_then_write, (str(started), str(gate_path), str(marker))
            )
            assert wait_until(started.exists)

        assert len(multiprocessing.active_children()) == before, "the worker was not killed"
        assert not result.ready()
        assert not marker.exists()


class TestQueueRows:
    """Queue(), JoinableQueue() and SimpleQueue()."""

    def test_put_returns_before_the_feeder_pickles_the_object(self) -> None:
        FEEDER_ENTERED.clear()
        FEEDER_GATE.clear()
        shared = multiprocessing.Queue()
        payload = Counting("payload")

        shared.put(Blocking())
        assert FEEDER_ENTERED.wait(WAIT)
        PICKLES.clear()
        shared.put(payload)
        assert PICKLES.count("payload") == 0
        payload.tag = "changed"
        FEEDER_GATE.set()

        assert isinstance(shared.get(timeout=WAIT), Blocking)
        received = shared.get(timeout=WAIT)
        assert received.tag == "changed"
        assert PICKLES.count("changed") == 1
        shared.close()
        shared.join_thread()

    def test_an_unpicklable_item_fails_in_the_feeder_after_put_returns(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        shared = multiprocessing.Queue()

        shared.put(lambda: None)

        with pytest.raises(queue.Empty):
            shared.get(timeout=SHORT * 4)
        if sys.platform != "darwin":
            assert wait_until(lambda: shared.qsize() == 0)
        collected: list[str] = []

        def traceback_printed() -> bool:
            collected.append(capsys.readouterr().err)
            return "local object" in "".join(collected)

        assert wait_until(traceback_printed)
        shared.close()
        shared.join_thread()

    def test_a_full_queue_refuses_a_put_at_once_or_after_its_timeout(self) -> None:
        shared = multiprocessing.Queue(maxsize=1)
        shared.put(1)

        with pytest.raises(queue.Full):
            shared.put_nowait(2)
        start = time.perf_counter()
        with pytest.raises(queue.Full):
            shared.put(2, timeout=SHORT)
        assert time.perf_counter() - start >= SHORT * 0.9

        assert shared.get(timeout=WAIT) == 1
        shared.put_nowait(2)
        assert shared.get(timeout=WAIT) == 2
        with pytest.raises(queue.Empty):
            shared.get_nowait()
        start = time.perf_counter()
        with pytest.raises(queue.Empty):
            shared.get(timeout=SHORT)
        assert time.perf_counter() - start >= SHORT * 0.9
        shared.close()
        shared.join_thread()

    def test_get_unpickles_after_releasing_the_reader_lock(self) -> None:
        shared = multiprocessing.Queue()
        LOCK_PROBE.clear()
        LOCK_PROBE["lock"] = cast("Any", shared)._rlock
        shared.put(LockProbing())

        assert isinstance(shared.get(timeout=WAIT), LockProbing)

        assert LOCK_PROBE.get("free") is True, "unpickling ran with the reader lock held"
        shared.close()
        shared.join_thread()

    def test_qsize_counts_puts_while_empty_follows_the_pipe(self) -> None:
        FEEDER_ENTERED.clear()
        FEEDER_GATE.clear()
        shared = multiprocessing.Queue()
        assert shared.empty()

        shared.put(Blocking())
        assert FEEDER_ENTERED.wait(WAIT)

        assert shared.empty(), "nothing has reached the pipe while the feeder is held"
        if sys.platform != "darwin":
            assert shared.qsize() == 1
            assert not shared.full()
        FEEDER_GATE.set()
        assert wait_until(lambda: not shared.empty())
        assert isinstance(shared.get(timeout=WAIT), Blocking)
        assert shared.empty()
        if sys.platform != "darwin":
            assert shared.qsize() == 0
        shared.close()
        shared.join_thread()

    def test_close_disables_the_queue_and_join_thread_flushes_it(self) -> None:
        FEEDER_ENTERED.clear()
        FEEDER_GATE.clear()
        shared = multiprocessing.Queue()
        parent_end, child_end = multiprocessing.Pipe()
        reader = multiprocessing.Process(target=drain_queue, args=(shared, 4, child_end))
        reader.start()
        child_end.close()
        shared.put(Blocking())
        assert FEEDER_ENTERED.wait(WAIT)
        for item in range(3):
            shared.put(item)

        shared.close()
        with pytest.raises(ValueError):
            shared.put(4)
        with pytest.raises(ValueError):
            shared.get_nowait()
        joiner = spawn_thread(shared.join_thread)
        joiner.join(SHORT * 4)
        assert joiner.is_alive(), "join_thread() returned with the feeder still held"
        FEEDER_GATE.set()
        join_threads([joiner])

        try:
            assert parent_end.poll(WAIT)
            received = parent_end.recv()
        finally:
            join_process(reader)
        assert received == ["Blocking", 0, 1, 2]

    def test_cancel_join_thread_is_accepted_before_and_after_the_feeder_starts(self) -> None:
        shared = multiprocessing.Queue()
        shared.cancel_join_thread()
        shared.put(1)
        shared.cancel_join_thread()
        assert shared.get(timeout=WAIT) == 1
        shared.close()

    def test_joinable_queue_join_waits_for_task_done_and_counts_them(self) -> None:
        shared = multiprocessing.JoinableQueue()
        shared.put(1)
        shared.put(2)
        joined = threading.Event()

        first_done = threading.Event()
        second_allowed = threading.Event()

        def consume() -> None:
            shared.get(timeout=WAIT)
            shared.task_done()
            first_done.set()
            second_allowed.wait(WAIT)
            shared.get(timeout=WAIT)
            shared.task_done()

        joiner = spawn_thread(lambda: (shared.join(), joined.set()))
        assert not joined.wait(SHORT), "join() returned with both items outstanding"
        consumer = spawn_thread(consume)
        assert first_done.wait(WAIT)
        assert not joined.wait(SHORT), "join() returned with one item outstanding"
        second_allowed.set()
        join_threads([consumer, joiner])
        assert joined.is_set()

        with pytest.raises(ValueError):
            shared.task_done()
        shared.close()
        shared.join_thread()

    @pytest.mark.skipif(sys.platform != "darwin", reason="qsize() is only unavailable on macOS")
    def test_qsize_is_unavailable_on_macos(self) -> None:
        shared = multiprocessing.Queue()
        with pytest.raises(NotImplementedError):
            shared.qsize()
        shared.close()

    def test_simple_queue_pickles_in_the_caller(self) -> None:
        shared = multiprocessing.SimpleQueue()
        payload = Counting("simple")
        assert shared.empty()

        PICKLES.clear()
        PICKLERS.clear()
        shared.put(payload)

        assert PICKLES.count("simple") == 1
        assert PICKLERS == [threading.current_thread()]
        assert wait_until(lambda: not shared.empty())
        assert shared.get().tag == "simple"
        assert shared.empty()
        shared.close()


class TestConnectionRows:
    """Pipe() and the Connection objects it returns."""

    def test_send_pickles_in_the_caller_and_recv_returns_an_equal_object(self) -> None:
        left, right = multiprocessing.Pipe()
        payload = Counting("pipe")

        PICKLES.clear()
        PICKLERS.clear()
        left.send(payload)

        assert PICKLES.count("pipe") == 1
        assert PICKLERS == [threading.current_thread()]
        assert right.recv().tag == "pipe"
        right.send([1, 2])
        assert left.recv() == [1, 2]
        left.close()
        right.close()

    def test_a_one_way_pipe_has_a_read_end_and_a_write_end(self) -> None:
        reader, writer = multiprocessing.Pipe(duplex=False)

        assert reader.readable and not reader.writable
        assert writer.writable and not writer.readable
        with pytest.raises(OSError):
            reader.send(1)
        with pytest.raises(OSError):
            writer.recv()
        writer.send_bytes(b"raw")
        assert reader.recv_bytes() == b"raw"
        reader.close()
        writer.close()

    def test_recv_bytes_enforces_maxlength_and_recv_bytes_into_reports_a_short_buffer(
        self,
    ) -> None:
        left, right = multiprocessing.Pipe()
        left.send_bytes(b"x" * 100)
        with pytest.raises(OSError):
            right.recv_bytes(maxlength=10)

        left, right = multiprocessing.Pipe()
        left.send_bytes(b"y" * 100)
        with pytest.raises(multiprocessing.BufferTooShort) as caught:
            right.recv_bytes_into(bytearray(10))
        assert caught.value.args[0] == b"y" * 100

        left.send_bytes(b"z" * 100)
        buffer = bytearray(200)
        assert right.recv_bytes_into(buffer) == 100
        assert buffer[:100] == b"z" * 100
        left.close()
        right.close()

    def test_poll_is_immediate_by_default_and_honours_a_timeout(self) -> None:
        left, right = multiprocessing.Pipe()

        start = time.perf_counter()
        assert not right.poll()
        assert time.perf_counter() - start < WAIT / 2
        start = time.perf_counter()
        assert not right.poll(SHORT)
        assert time.perf_counter() - start >= SHORT * 0.9

        left.send(1)
        assert right.poll(WAIT)
        assert right.recv() == 1
        left.close()
        right.close()

    def test_send_blocks_once_the_buffer_is_full_until_the_other_end_reads(self) -> None:
        left, right = multiprocessing.Pipe()
        sender = spawn_thread(left.send_bytes, b"x" * (4 << 20))

        sender.join(SHORT * 6)
        assert sender.is_alive(), "a 4 MiB send returned with nobody reading"

        assert len(right.recv_bytes()) == 4 << 20
        join_threads([sender])
        left.close()
        right.close()

    def test_close_marks_the_connection_and_disables_it(self) -> None:
        left, right = multiprocessing.Pipe()
        assert isinstance(left.fileno(), int)
        assert not left.closed

        left.close()

        assert left.closed
        with pytest.raises(OSError):
            left.recv()
        with pytest.raises(OSError):
            left.fileno()
        right.close()


class TestListenerRows:
    """Listener(), Client(), wait() and the two challenge functions."""

    def test_a_listener_hands_a_client_a_connection(self) -> None:
        results: list[int] = []

        def call(address: Any) -> None:
            with multiprocessing.connection.Client(address) as conn:
                conn.send([1, 2])
                results.append(conn.recv())

        with multiprocessing.connection.Listener() as listener:
            assert listener.last_accepted is None
            caller = spawn_thread(call, listener.address)
            with listener.accept() as conn:
                conn.send(sum(conn.recv()))
            join_threads([caller])
            if POSIX:  # a Windows named-pipe listener leaves it None
                assert listener.last_accepted is not None

        assert results == [3]
        with pytest.raises(OSError):
            listener.accept()

    def test_a_mismatched_authkey_is_refused_on_both_sides(self) -> None:
        errors: list[type] = []

        def call(address: Any) -> None:
            try:
                multiprocessing.connection.Client(address, authkey=b"wrong")
            except multiprocessing.AuthenticationError as error:
                errors.append(type(error))

        with multiprocessing.connection.Listener(authkey=b"right") as listener:
            caller = spawn_thread(call, listener.address)
            with pytest.raises(multiprocessing.AuthenticationError):
                listener.accept()
            join_threads([caller])

        assert errors == [multiprocessing.AuthenticationError]

    @staticmethod
    def _challenge_sizes(key: bytes) -> dict[str, list[int]]:
        """The length of every message each side sends during one exchange."""
        sizes: dict[str, list[int]] = {"deliver": [], "answer": []}
        left, right = multiprocessing.Pipe()
        for conn, side in ((left, "deliver"), (right, "answer")):
            original = conn.send_bytes

            def counting(buf: Any, *args: Any, _side: str = side, _send: Any = original) -> None:
                sizes[_side].append(len(buf))
                _send(buf, *args)

            cast("Any", conn).send_bytes = counting

        answerer = spawn_thread(multiprocessing.connection.answer_challenge, right, key)
        multiprocessing.connection.deliver_challenge(left, key)
        join_threads([answerer])
        left.close()
        right.close()
        return sizes

    def test_the_challenge_is_the_same_few_messages_for_any_key(self) -> None:
        short = self._challenge_sizes(b"k")
        long = self._challenge_sizes(b"k" * 100_000)

        assert short == long, (short, long)
        assert len(short["deliver"]) == 2 and len(short["answer"]) == 1, short

    def test_wait_registers_every_object_and_returns_the_ready_ones(self) -> None:
        pipes = [multiprocessing.Pipe(duplex=False) for _ in range(5)]
        readers: Any = [CountingFileno(reader) for reader, _ in pipes]

        start = time.perf_counter()
        assert multiprocessing.connection.wait(readers, SHORT) == []
        assert time.perf_counter() - start >= SHORT * 0.9
        assert all(reader.calls >= 1 for reader in readers)

        pipes[2][1].send(1)
        before = [reader.calls for reader in readers]
        first = multiprocessing.connection.wait(readers, WAIT)
        second = multiprocessing.connection.wait(readers, WAIT)

        assert first == second == [readers[2]] and first is not second
        assert all(reader.calls >= count + 2 for reader, count in zip(readers, before, strict=True))
        for reader, writer in pipes:
            reader.close()
            writer.close()


class TestSynchronizationRows:
    """Lock, RLock, Semaphore, BoundedSemaphore, Condition, Event and Barrier."""

    def test_lock_acquire_is_immediate_when_free_and_bounded_by_its_timeout(self) -> None:
        lock = multiprocessing.Lock()

        assert lock.acquire(False)
        assert not lock.acquire(False)
        start = time.perf_counter()
        assert not lock.acquire(timeout=SHORT)
        assert time.perf_counter() - start >= SHORT * 0.9
        lock.release()
        assert lock.acquire(False)
        lock.release()

    def test_releasing_an_unheld_lock_raises(self) -> None:
        with pytest.raises(ValueError):
            multiprocessing.Lock().release()
        with pytest.raises(AssertionError):
            multiprocessing.RLock().release()

    def test_an_rlock_is_immediate_for_its_owner_and_held_until_the_last_release(
        self,
    ) -> None:
        rlock = multiprocessing.RLock()
        attempts: list[bool] = []
        for _ in range(3):
            assert rlock.acquire(False)

        join_threads([spawn_thread(lambda: attempts.append(rlock.acquire(False)))])
        assert attempts == [False]
        rlock.release()
        rlock.release()
        join_threads([spawn_thread(lambda: attempts.append(rlock.acquire(False)))])
        assert attempts == [False, False]
        rlock.release()
        join_threads([spawn_thread(lambda: attempts.append(rlock.acquire(False)))])
        assert attempts == [False, False, True]

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="locked() was added in Python 3.14")
    def test_locked_reports_the_state(self) -> None:
        lock = multiprocessing.Lock()
        rlock = multiprocessing.RLock()

        probes = cast("Any", lock), cast("Any", rlock)
        assert not any(probe.locked() for probe in probes)
        with lock, rlock:
            assert all(probe.locked() for probe in probes)
        assert not any(probe.locked() for probe in probes)

    def test_a_semaphore_counts_and_a_bounded_one_refuses_over_release(self) -> None:
        semaphore = multiprocessing.Semaphore(2)
        if sys.platform != "darwin":
            assert semaphore.get_value() == 2

        assert semaphore.acquire(False)
        assert semaphore.acquire(False)
        assert not semaphore.acquire(False)
        semaphore.release()
        assert semaphore.acquire(False)
        semaphore.release()
        semaphore.release()

        bounded = multiprocessing.BoundedSemaphore(1)
        assert bounded.acquire(False)
        bounded.release()
        with pytest.raises(ValueError):
            bounded.release()

    def test_notify_wakes_n_sleepers_and_notify_all_the_rest(self) -> None:
        condition = multiprocessing.Condition()
        woken: list[tuple[int, bool]] = []
        waiting = threading.Semaphore(0)

        def wait(index: int) -> None:
            with condition:
                waiting.release()
                notified = condition.wait(WAIT)
                woken.append((index, notified))

        threads = [spawn_thread(wait, index) for index in range(6)]
        for _ in range(6):
            assert waiting.acquire(timeout=WAIT)
        with condition:
            condition.notify(2)
        assert wait_until(lambda: len(woken) == 2)
        time.sleep(SHORT)
        assert len(woken) == 2
        start = time.perf_counter()
        with condition:
            condition.notify_all()
        join_threads(threads)
        assert time.perf_counter() - start < WAIT / 2, "the rest woke only by timing out"
        assert sorted(woken) == [(index, True) for index in range(6)]

    @pytest.mark.skipif(sys.platform == "darwin", reason="get_value() is unavailable on macOS")
    def test_notify_clears_the_bookkeeping_of_timed_out_waits(self) -> None:
        condition = multiprocessing.Condition()
        woken_count = cast("Any", condition)._woken_count

        def timed_out_wait() -> None:
            with condition:
                assert not condition.wait(SHORT)

        join_threads([spawn_thread(timed_out_wait) for _ in range(3)])

        assert woken_count.get_value() == 3
        with condition:
            condition.notify()
        assert woken_count.get_value() == 0

    @pytest.mark.skipif(
        not POSIX or sys.platform == "darwin",
        reason="needs kill() by signal and get_value(), which macOS lacks",
    )
    def test_a_sleeper_killed_mid_wait_blocks_the_next_notify_for_good(self) -> None:
        """The blocked thread is a daemon and the event is never used again."""
        doomed = multiprocessing.Event()
        condition = cast("Any", doomed)._cond
        sleeper = multiprocessing.Process(target=wait_on, args=(doomed,))
        sleeper.start()
        try:
            assert wait_until(lambda: condition._sleeping_count.get_value() == 1)
            with condition:
                pass  # the sleeper has released the lock, so it is inside its semaphore wait
        finally:
            sleeper.kill()
            join_process(sleeper)
        assert sleeper.exitcode == -signal.SIGKILL

        setter = spawn_thread(doomed.set)

        setter.join(SHORT * 4)
        assert setter.is_alive(), "set() returned without the dead sleeper's acknowledgement"

    def test_wait_releases_a_recursively_held_lock(self) -> None:
        condition = multiprocessing.Condition()
        acquired = threading.Event()
        waiting = threading.Event()

        notified: list[tuple[bool, int]] = []
        exited: list[bool] = []

        def depth() -> int:
            return cast("Any", condition)._lock._semlock._count()

        def wait() -> None:
            with condition, condition:
                waiting.set()
                notified.append((condition.wait(WAIT), depth()))
            exited.append(True)

        waiter = spawn_thread(wait)
        assert waiting.wait(WAIT)

        def notify() -> None:
            with condition:
                acquired.set()
                condition.notify()

        start = time.perf_counter()
        join_threads([spawn_thread(notify)])
        assert time.perf_counter() - start < WAIT / 2, "the notifier waited for the timeout"
        assert acquired.is_set()
        join_threads([waiter])
        assert notified == [(True, 2)]
        assert exited == [True]

    def test_wait_for_calls_the_predicate_once_before_waiting_and_once_per_wakeup(
        self,
    ) -> None:
        condition = multiprocessing.Condition()
        calls: list[int] = []

        with condition:
            assert condition.wait_for(lambda: calls.append(1) or True)
        assert len(calls) == 1

        calls.clear()
        state = {"ready": False}

        def make_ready() -> None:
            time.sleep(SHORT)
            with condition:
                state["ready"] = True
                condition.notify()

        def predicate() -> bool:
            calls.append(1)
            return state["ready"]

        with condition:
            spawn_thread(make_ready)
            start = time.perf_counter()
            assert condition.wait_for(predicate, WAIT)
        assert time.perf_counter() - start < WAIT / 2, "the second look came from the timeout"
        assert len(calls) == 2

    def test_event_wait_is_immediate_once_set_and_set_wakes_every_waiter(self) -> None:
        event = multiprocessing.Event()
        assert not event.is_set()

        start = time.perf_counter()
        assert not event.wait(SHORT)
        assert time.perf_counter() - start >= SHORT * 0.9

        results: list[bool] = []
        threads = [spawn_thread(lambda: results.append(event.wait(WAIT))) for _ in range(5)]
        if sys.platform == "darwin":
            time.sleep(SHORT)
        else:
            condition = cast("Any", event)._cond
            assert wait_until(
                lambda: (
                    condition._sleeping_count.get_value() - condition._woken_count.get_value() == 5
                )
            ), "not every waiter was asleep"
        start = time.perf_counter()
        event.set()
        join_threads(threads)
        assert time.perf_counter() - start < WAIT / 2, "the waiters woke only by timing out"
        assert results == [True] * 5
        start = time.perf_counter()
        assert event.wait(WAIT)
        assert time.perf_counter() - start < WAIT / 2
        event.clear()
        assert not event.is_set()

    def test_the_last_party_releases_the_barrier_and_runs_the_action_once(self) -> None:
        actions: list[int] = []
        barrier = multiprocessing.Barrier(3, action=lambda: actions.append(1))
        indices: list[int] = []
        threads = [spawn_thread(lambda: indices.append(barrier.wait(WAIT))) for _ in range(2)]

        assert wait_until(lambda: barrier.n_waiting == 2)
        assert indices == []
        assert barrier.parties == 3
        indices.append(barrier.wait(WAIT))
        join_threads(threads)

        assert sorted(indices) == [0, 1, 2]
        assert actions == [1]
        assert not barrier.broken

    @pytest.mark.parametrize(("method", "left_broken"), [("abort", True), ("reset", False)])
    def test_abort_and_reset_wake_every_waiter_with_broken_barrier_error(
        self, method: str, left_broken: bool
    ) -> None:
        barrier = multiprocessing.Barrier(3)
        errors: list[type] = []

        def wait() -> None:
            try:
                barrier.wait(WAIT)
            except threading.BrokenBarrierError as error:
                errors.append(type(error))

        threads = [spawn_thread(wait) for _ in range(2)]
        assert wait_until(lambda: barrier.n_waiting == 2)
        start = time.perf_counter()
        getattr(barrier, method)()
        join_threads(threads)

        assert time.perf_counter() - start < WAIT / 2, "the waiters left only by timing out"
        assert errors == [threading.BrokenBarrierError] * 2
        assert barrier.broken is left_broken
        assert barrier.n_waiting == 0

    def test_an_expired_timeout_breaks_the_barrier(self) -> None:
        barrier = multiprocessing.Barrier(3)

        with pytest.raises(threading.BrokenBarrierError):
            barrier.wait(SHORT)

        assert barrier.broken
        barrier.reset()
        assert not barrier.broken

    @pytest.mark.skipif(not POSIX, reason="Windows has no resource tracker")
    @pytest.mark.parametrize("method", ["fork", "spawn", "forkserver"])
    @pytest.mark.parametrize("factory", ["Lock", "Queue"])
    def test_the_first_primitive_starts_the_resource_tracker_except_under_fork(
        self, method: str, factory: str
    ) -> None:
        if method not in multiprocessing.get_all_start_methods():
            pytest.skip(f"the {method} start method is not available here")
        source = f"""
            import multiprocessing
            from multiprocessing import resource_tracker

            context = multiprocessing.get_context({method!r})
            before = resource_tracker._resource_tracker._pid
            primitive = context.{factory}()
            after = resource_tracker._resource_tracker._pid
            print(before is None, after is not None)
            """

        result = subprocess.run(
            [sys.executable, "-c", textwrap.dedent(source)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.split() == ["True", str(method != "fork")]


class TestSharedCtypesRows:
    """RawValue(), RawArray(), Value(), Array() and synchronized()."""

    def test_value_without_a_lock_is_the_raw_object(self) -> None:
        raw = multiprocessing.Value("i", 5, lock=False)
        wrapped = multiprocessing.Value("i", 5)

        assert isinstance(raw, ctypes.c_int)
        assert not hasattr(raw, "get_lock")
        assert isinstance(wrapped.get_obj(), ctypes.c_int)
        assert type(wrapped.get_lock()).__name__ == "RLock"
        assert wrapped.value == 5
        assert multiprocessing.RawValue("d", 1.5).value == 1.5

        class Point(ctypes.Structure):
            _fields_ = [("x", ctypes.c_int), ("y", ctypes.c_int)]

        point = multiprocessing.RawValue(Point)
        assert (point.x, point.y) == (0, 0)
        text: Any = multiprocessing.Value(ctypes.c_char * 4)
        text.value = b"ab"
        assert text.value == b"ab" and text.value is not text.value

    def test_the_wrappers_take_the_lock_per_access_and_never_for_len(self) -> None:
        lock = CountingLock()
        value: Any = multiprocessing.Value("i", 0, lock=cast("Any", lock))
        array: Any = multiprocessing.Array("i", 5, lock=cast("Any", lock))

        assert value.value == 0
        assert (lock.acquires, lock.releases) == (1, 1)
        value.value = 3
        assert (lock.acquires, lock.releases) == (2, 2)
        assert len(array) == 5
        assert (lock.acquires, lock.releases) == (2, 2)
        assert array[0] == 0
        assert (lock.acquires, lock.releases) == (3, 3)
        assert array[1:4] == [0, 0, 0]
        assert (lock.acquires, lock.releases) == (4, 4)
        array[2] = 7
        assert (lock.acquires, lock.releases) == (5, 5)
        with value:
            pass
        assert (lock.acquires, lock.releases) == (6, 6)
        assert value.acquire() and lock.acquires == 7
        value.release()
        assert lock.releases == 7
        assert array.get_lock() is lock

    def test_arrays_are_zeroed_or_copied_and_slices_are_new_lists(self) -> None:
        source = [1, 2, 3]
        copied = multiprocessing.Array("i", source)
        raw = multiprocessing.RawArray("i", source)
        source.append(4)

        assert multiprocessing.Array("i", 4)[:] == [0, 0, 0, 0]
        assert multiprocessing.RawArray("i", 3)[:] == [0, 0, 0]
        assert copied[:] == raw[:] == [1, 2, 3]
        first, second = copied[:], copied[:]
        assert first == second and first is not second
        first[0] = 99
        assert copied[0] == 1
        assert multiprocessing.Array("c", b"ab")[:] == b"ab"
        assert multiprocessing.Array("u", "ab")[:] == "ab"

    def test_a_child_writes_into_the_same_memory(self) -> None:
        value = multiprocessing.Value("i", 0)
        array = multiprocessing.Array("i", 3)
        raw = multiprocessing.RawArray("i", 3)

        child = multiprocessing.Process(target=write_shared, args=(value, array, raw))
        child.start()
        join_process(child)

        assert child.exitcode == 0
        assert value.value == 42
        assert array[:] == [0, 10, 20]
        assert raw[:] == [1, 2, 3]

    def test_an_augmented_assignment_takes_the_lock_twice(self) -> None:
        lock = CountingLock()
        value: Any = multiprocessing.Value("i", 0, lock=cast("Any", lock))

        value.value += 1

        assert (lock.acquires, lock.releases) == (2, 2), "one for the read, one for the write"
        assert value.value == 1

    def test_a_pool_task_argument_cannot_be_a_shared_ctypes_object(
        self, pool: multiprocessing.pool.Pool
    ) -> None:
        for shared in (
            multiprocessing.Value("i", 1),
            multiprocessing.Array("i", 3),
            multiprocessing.RawValue("i", 1),
            multiprocessing.RawArray("i", 3),
        ):
            with pytest.raises(RuntimeError, match="through inheritance"):
                pool.apply(identity, (shared,))

    def test_synchronized_wraps_the_object_in_place(self) -> None:
        raw = multiprocessing.RawValue("i", 3)
        cells = multiprocessing.RawArray("i", 3)

        wrapped: Any = multiprocessing.sharedctypes.synchronized(raw)
        wrapped_cells: Any = multiprocessing.sharedctypes.synchronized(cells)

        assert wrapped.get_obj() is raw
        assert wrapped_cells.get_obj() is cells
        raw.value = 4
        cells[1] = 7
        assert wrapped.value == 4
        assert wrapped_cells[:] == [0, 7, 0]

        class Pair(ctypes.Structure):
            _fields_ = [("x", ctypes.c_int), ("y", ctypes.c_int)]

        first: Any = multiprocessing.sharedctypes.synchronized(multiprocessing.RawValue(Pair))
        second: Any = multiprocessing.sharedctypes.synchronized(multiprocessing.RawValue(Pair))
        assert type(first) is type(second), "the wrapper class was built twice"
        assert all(isinstance(vars(type(first))[name], property) for name in ("x", "y"))
        first.x = 5
        assert first.get_obj().x == 5


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="looks blocks up in /dev/shm")
class TestSharedMemoryRows:
    """SharedMemory() and its members.

    Existence is checked in /dev/shm rather than by attaching, since attaching
    registers the block with this process's resource tracker.
    """

    @pytest.mark.timing
    def test_creating_a_block_costs_the_same_at_any_size(self) -> None:
        def fastest(size: int) -> float:
            best = float("inf")
            for _ in range(7):
                start = time.perf_counter()
                block = multiprocessing.shared_memory.SharedMemory(create=True, size=size)
                best = min(best, time.perf_counter() - start)
                block.close()
                block.unlink()
            return best

        small, large = fastest(4 << 10), fastest(16 << 20)

        assert large / small < 50, f"4 KiB {small * 1e6:.1f} us, 16 MiB {large * 1e6:.1f} us"

    def test_buf_is_one_view_whose_slices_share_the_block(self) -> None:
        block: Any = multiprocessing.shared_memory.SharedMemory(create=True, size=16)
        try:
            assert block.buf is block.buf
            assert block.size >= 16
            window = block.buf[4:8]
            window[0] = 7
            assert block.buf[4] == 7
            with pytest.raises(BufferError):
                block.close()
            window.release()
            attached: Any = multiprocessing.shared_memory.SharedMemory(name=block.name)
            assert attached.buf[4] == 7
            attached.close()
        finally:
            block.close()
            block.unlink()
        assert not shm_exists(block.name)

    def test_a_block_pickles_as_its_name_whatever_its_size(self) -> None:
        sizes = []
        for size in (64, 16 << 20):
            block = multiprocessing.shared_memory.SharedMemory(create=True, size=size)
            try:
                sizes.append(len(pickle.dumps(block)))
            finally:
                block.close()
                block.unlink()

        assert max(sizes) < 200, sizes

    def test_the_resource_tracker_unlinks_a_block_left_behind(self) -> None:
        result = run_python(
            """
            from multiprocessing import shared_memory
            block = shared_memory.SharedMemory(create=True, size=64)
            print(block.name)
            block.close()
            """
        )

        assert result.returncode == 0, result.stderr
        name = result.stdout.strip()
        assert wait_until(lambda: not shm_exists(name)), f"{name} outlived its creator"

    def test_attaching_registers_the_block_too(self) -> None:
        from multiprocessing import resource_tracker

        block = multiprocessing.shared_memory.SharedMemory(create=True, size=64)
        resource_tracker.unregister(cast("Any", block)._name, "shared_memory")
        try:
            result = run_python(
                f"""
                from multiprocessing import shared_memory
                shared_memory.SharedMemory(name={block.name!r}).close()
                """
            )
            assert result.returncode == 0, result.stderr
            assert wait_until(lambda: not shm_exists(block.name)), "the attacher left it"
        finally:
            block.close()
            if shm_exists(block.name):
                block.unlink()

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="track= was added in Python 3.13")
    def test_track_false_leaves_the_block_for_the_caller(self) -> None:
        result = run_python(
            """
            from multiprocessing import shared_memory
            block = shared_memory.SharedMemory(create=True, size=64, track=False)
            print(block.name)
            block.close()
            """
        )

        assert result.returncode == 0, result.stderr
        name = result.stdout.strip()
        try:
            time.sleep(SHORT * 4)
            assert shm_exists(name)
        finally:
            leftover = cast("Any", multiprocessing.shared_memory.SharedMemory)(name, track=False)
            leftover.close()
            leftover.unlink()

    @pytest.mark.parametrize("method", ["fork", "spawn", "forkserver"])
    @pytest.mark.parametrize("factory", ["SharedMemory", "SharedMemoryManager"])
    def test_the_first_block_or_manager_starts_the_resource_tracker(
        self, method: str, factory: str
    ) -> None:
        if method not in multiprocessing.get_all_start_methods():
            pytest.skip(f"the {method} start method is not available here")
        create = {
            "SharedMemory": "shared_memory.SharedMemory(create=True, size=64).unlink()",
            "SharedMemoryManager": "managers.SharedMemoryManager()",
        }[factory]
        result = run_python(
            f"""
            import multiprocessing
            multiprocessing.set_start_method({method!r})
            from multiprocessing import managers, resource_tracker, shared_memory
            before = resource_tracker._resource_tracker._pid
            {create}
            after = resource_tracker._resource_tracker._pid
            print(before is None, after is not None)
            """
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.split() == ["True", "True"]


class CountingList(multiprocessing.shared_memory.ShareableList):
    """Counts item reads, to see how far count() and index() walk."""

    reads = 0

    def __getitem__(self, position: int) -> Any:
        CountingList.reads += 1
        return super().__getitem__(position)


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="looks blocks up in /dev/shm")
class TestShareableListRows:
    """ShareableList() and its members."""

    def test_items_are_fixed_in_number_and_in_str_capacity(self) -> None:
        items: Any = cast("Any", multiprocessing.shared_memory.ShareableList)(
            [1, 2.5, "text", b"raw", None]
        )
        try:
            assert len(items) == 5
            assert list(items) == [1, 2.5, "text", b"raw", None]
            items[0] = 42
            items[2] = "textabc"
            assert items[0] == 42 and items[2] == "textabc"
            with pytest.raises(ValueError, match="exceeds available storage"):
                items[2] = "textabcde"
            eight = cast("Any", multiprocessing.shared_memory.ShareableList)([b"12345678"])
            try:
                eight[0] = b"x" * 16
                with pytest.raises(ValueError, match="exceeds available storage"):
                    eight[0] = b"x" * 17
            finally:
                eight.shm.close()
                eight.shm.unlink()
            with pytest.raises(ValueError, match="exceeds available storage"):
                items[2] = "x" * 100
            assert not hasattr(items, "append")
            assert isinstance(items.shm, multiprocessing.shared_memory.SharedMemory)
            attached: Any = multiprocessing.shared_memory.ShareableList(name=items.shm.name)
            assert list(attached) == [42, 2.5, "textabc", b"raw", None]
            attached[1] = 7.5
            assert items[1] == 7.5
            attached.shm.close()
        finally:
            items.shm.close()
            items.shm.unlink()

    def test_the_block_grows_with_the_str_lengths(self) -> None:
        short = multiprocessing.shared_memory.ShareableList(["x"])
        long = multiprocessing.shared_memory.ShareableList(["x" * 10_000])
        try:
            assert long.shm.size - short.shm.size >= 9_000
        finally:
            for items in (short, long):
                items.shm.close()
                items.shm.unlink()

    def test_count_reads_every_item_and_index_stops_at_the_first_match(self) -> None:
        items = CountingList(list(range(100)))
        try:
            CountingList.reads = 0
            assert items.count(5) == 1
            assert CountingList.reads >= 100

            CountingList.reads = 0
            assert items.index(5) == 5
            assert CountingList.reads <= 7

            formats = items.format
            assert formats == "q" * 100 and formats is not items.format
        finally:
            items.shm.close()
            items.shm.unlink()


class TestManagerRows:
    """Manager(), its factories, proxies, connect(), shutdown() and register()."""

    def test_a_manager_is_one_child_that_the_context_manager_shuts_down(self) -> None:
        before = len(multiprocessing.active_children())

        with multiprocessing.Manager() as manager:
            assert len(multiprocessing.active_children()) == before + 1
            assert manager.list([1])[:] == [1]

        assert wait_until(lambda: len(multiprocessing.active_children()) == before)

    def test_every_proxy_operation_is_a_round_trip(self) -> None:
        """Counts messages sent on the thread's server connection, not proxy method calls."""
        calls: list[object] = []

        with multiprocessing.Manager() as manager:
            items = manager.list(range(5))
            mapping = manager.dict({index: index for index in range(5)})
            assert len(items) == 5  # the first call opens this thread's connection
            connection = cast("Any", items)._tls.connection
            original_send = connection.send

            def counting_send(message: object) -> None:
                calls.append(message)
                original_send(message)

            connection.send = counting_send
            observed: dict[str, int] = {}
            probes: list[tuple[str, Callable[[], object]]] = [
                ("list slice", lambda: items[:]),
                ("list iteration", lambda: drain(items)),
                ("list()", lambda: list(items)),
                ("list append", lambda: items.append(5)),
                ("dict copy", mapping.copy),
                ("dict keys", mapping.keys),
                ("dict values", mapping.values),
                ("dict items", mapping.items),
                ("dict()", lambda: dict(mapping)),
                ("dict iteration", lambda: drain(mapping)),
            ]
            for label, probe in probes:
                calls.clear()
                probe()
                observed[label] = len(calls)

        assert observed == {
            "list append": 1,
            "list slice": 1,
            "list iteration": 6,
            "list()": 7,
            "dict copy": 1,
            "dict keys": 1,
            "dict values": 1,
            "dict items": 1,
            "dict()": 6,
            "dict iteration": 7,
        }

    def test_connect_reaches_a_server_another_manager_started(self) -> None:
        with multiprocessing.Manager() as manager:
            shared = manager.list([1, 2])
            with pytest.raises(multiprocessing.ProcessError):
                manager.get_server()

            children = len(multiprocessing.active_children())
            objects = cast("Any", manager)._number_of_objects()
            other = multiprocessing.managers.SyncManager(address=manager.address)
            other.connect()

            assert len(multiprocessing.active_children()) == children, "connect() spawned"
            created = other.list([3])
            assert created[:] == [3]
            assert cast("Any", manager)._number_of_objects() == objects + 1, "another server"
            assert shared[:] == [1, 2]
            assert isinstance(manager.address, (str, bytes, tuple))
        manager.join(WAIT)

    def test_register_adds_a_factory_to_the_class_it_is_called_on(self) -> None:
        class Custom(multiprocessing.managers.BaseManager):
            pass

        Custom.register("counter", list)

        assert callable(cast("Any", Custom).counter)
        assert not hasattr(multiprocessing.managers.BaseManager, "counter")
        assert not hasattr(multiprocessing.managers.SyncManager, "counter")

        class Derived(multiprocessing.managers.SyncManager):
            pass

        inherited = cast("Any", multiprocessing.managers.SyncManager)._registry
        Derived.register("counter", list)
        registry = cast("Any", Derived)._registry
        assert registry is not inherited
        assert len(registry) == len(inherited) + 1
        assert "counter" not in inherited
        Derived.register("another", list)
        assert cast("Any", Derived)._registry is registry, "a later call copied again"

    def test_a_base_manager_starts_nothing_until_start(self) -> None:
        children = len(multiprocessing.active_children())
        manager = multiprocessing.managers.SyncManager()

        assert len(multiprocessing.active_children()) == children
        assert not hasattr(manager, "shutdown")
        manager.start()
        try:
            assert len(multiprocessing.active_children()) == children + 1
            with pytest.raises(multiprocessing.ProcessError):
                manager.start()
        finally:
            manager.shutdown()
        manager.join(WAIT)

    def test_callmethod_and_getvalue_are_one_round_trip(self) -> None:
        calls: list[object] = []

        with multiprocessing.Manager() as manager:
            items: Any = manager.list(range(5))
            assert len(items) == 5  # opens this thread's connection
            connection = items._tls.connection
            original_send = connection.send

            def counting_send(message: object) -> None:
                calls.append(message)
                original_send(message)

            connection.send = counting_send
            copied = items._getvalue()
            assert len(calls) == 1
            length = items._callmethod("__len__")
            assert len(calls) == 2

        assert type(copied) is list and copied == [0, 1, 2, 3, 4]
        assert length == 5

    @pytest.mark.skipif(not sys.platform.startswith("linux"), reason="looks blocks up in /dev/shm")
    def test_a_shared_memory_manager_registers_and_then_unlinks_its_blocks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        methods: list[str] = []
        original = cast("Any", multiprocessing.managers).dispatch

        def counting(conn: Any, ident: Any, methodname: str, *args: Any, **kwargs: Any) -> Any:
            methods.append(methodname)
            return original(conn, ident, methodname, *args, **kwargs)

        monkeypatch.setattr(multiprocessing.managers, "dispatch", counting)
        with multiprocessing.managers.SharedMemoryManager() as manager:
            methods.clear()
            block = manager.SharedMemory(64)
            assert methods == ["track_segment"]
            items = manager.ShareableList([1, 2])
            assert methods == ["track_segment"] * 2
            names = [block.name, items.shm.name]
            assert all(shm_exists(name) for name in names)
            block.close()
            items.shm.close()

        assert not any(shm_exists(name) for name in names)


class TestDummyRows:
    """multiprocessing.dummy: the same API on threads."""

    def test_the_dummy_module_passes_objects_by_reference(self) -> None:
        dummy: Any = multiprocessing.dummy
        payload = Counting("dummy")
        PICKLES.clear()

        left, right = dummy.Pipe()
        left.send(payload)

        assert right.recv() is payload
        assert PICKLES == []
        assert issubclass(dummy.Process, threading.Thread)
        assert dummy.Queue is queue.Queue
        assert dummy.Manager() is dummy
        with dummy.Pool(2) as pool:
            assert isinstance(pool, multiprocessing.pool.ThreadPool)


class TestModuleFunctionRows:
    """cpu_count(), the start-method functions, logging, settings and the constants."""

    def test_cpu_count_is_the_os_count(self) -> None:
        assert multiprocessing.cpu_count() == os.cpu_count()

    def test_the_start_method_functions(self) -> None:
        methods = multiprocessing.get_all_start_methods()

        assert methods is not multiprocessing.get_all_start_methods()
        assert methods == multiprocessing.get_all_start_methods()
        assert multiprocessing.get_start_method() in methods
        for method in methods:
            assert multiprocessing.get_context(method).get_start_method() == method
        assert multiprocessing.get_context() is multiprocessing.get_context()
        with pytest.raises(ValueError):
            multiprocessing.get_context("nonsense")

    def test_set_start_method_refuses_a_second_call_unless_forced(self) -> None:
        source = """
            import multiprocessing

            methods = multiprocessing.get_all_start_methods()
            multiprocessing.set_start_method(methods[0])
            try:
                multiprocessing.set_start_method(methods[-1])
            except RuntimeError:
                print("refused")
            multiprocessing.set_start_method(methods[-1], force=True)
            print(multiprocessing.get_start_method() == methods[-1])
            """

        result = subprocess.run(
            [sys.executable, "-c", textwrap.dedent(source)],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.split() == ["refused", "True"]

    def test_fork_warns_when_the_parent_has_threads_from_3_12(self) -> None:
        if "fork" not in multiprocessing.get_all_start_methods():
            pytest.skip("the fork start method is not available here")
        release = threading.Event()
        helper = spawn_thread(release.wait, WAIT)
        try:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                process: Any = multiprocessing.get_context("fork").Process(
                    target=identity, args=(1,)
                )
                process.start()
            join_process(process)
        finally:
            release.set()
            join_threads([helper])

        warned = any(issubclass(item.category, DeprecationWarning) for item in caught)
        assert warned is (sys.version_info >= (3, 12)), [str(item.message) for item in caught]

    def test_the_first_forkserver_start_launches_the_server_once(self) -> None:
        if "forkserver" not in multiprocessing.get_all_start_methods():
            pytest.skip("the forkserver start method is not available here")
        result = run_python(
            """
            import multiprocessing
            from multiprocessing import forkserver

            context = multiprocessing.get_context("forkserver")
            before = forkserver._forkserver._forkserver_pid
            pids = []
            for _ in range(2):
                process = context.Process(target=int)
                process.start()
                process.join()
                pids.append(forkserver._forkserver._forkserver_pid)
            print(before is None, pids[0] is not None, pids[0] == pids[1])
            """
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.split() == ["True", "True", "True"]

    def test_get_logger_is_one_object_and_log_to_stderr_adds_a_handler_per_call(
        self,
    ) -> None:
        logger = multiprocessing.get_logger()
        before = list(logger.handlers)
        try:
            assert multiprocessing.log_to_stderr() is logger
            assert multiprocessing.log_to_stderr() is logger
            assert multiprocessing.get_logger() is logger
            assert len(logger.handlers) == len(before) + 2
        finally:
            logger.handlers[:] = before

    def test_the_settings_functions_store_or_do_nothing(self) -> None:
        from multiprocessing import forkserver, spawn

        assert multiprocessing.freeze_support() is None
        assert multiprocessing.allow_connection_pickling() is None
        previous = spawn.get_executable()
        try:
            multiprocessing.set_executable(sys.executable)
            assert os.fsdecode(spawn.get_executable()) == sys.executable
        finally:
            multiprocessing.set_executable(previous)
        server = cast("Any", forkserver)._forkserver
        original = server._preload_modules
        try:
            multiprocessing.set_forkserver_preload(["json"])
            assert server._preload_modules == ["json"]
        finally:
            server._preload_modules = original

    def test_the_exceptions_constants_and_reducer(self) -> None:
        module = cast("Any", multiprocessing)
        for error in (
            multiprocessing.BufferTooShort,
            multiprocessing.TimeoutError,
            multiprocessing.AuthenticationError,
        ):
            assert issubclass(error, multiprocessing.ProcessError)
        assert issubclass(multiprocessing.ProcessError, Exception)
        assert module.SUBDEBUG == 5
        assert module.SUBWARNING == 25
        assert module.reducer is module.reduction
        assert hasattr(module.reducer, "ForkingPickler")


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


class TestDocumentedExamples:
    """Every block runs in its own interpreter and directory, and asserts its own results.

    The blocks start processes, pools, managers and a listener, so each runs as
    a script under the default start method, which is how its
    ``if __name__ == "__main__":`` guard is meant to be exercised.
    """

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []

        for line, source in _blocks():
            cwd = tmp_path / f"line{line}"
            cwd.mkdir()
            result = _run(source, cwd)
            if result.returncode != 0 or result.stderr.strip():
                failures.append(f"{PAGE.name}:{line}: {result.stderr.strip()}")

        assert not failures, "\n".join(failures)

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        source = _block_containing("cells = Array(")
        broken = source.replace("assert counter.value == 1", "assert counter.value == 2", 1)
        assert broken != source, "the mutation did not change the assertion"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "AssertionError" in result.stderr
