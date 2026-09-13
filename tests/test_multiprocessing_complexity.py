"""Tests for docs/stdlib/multiprocessing.md.

Lib/multiprocessing/process.py: ``Process.__init__`` copies its args and
kwargs and stores the target; ``start()`` calls ``_cleanup()``, which polls
every child in the module's ``_children`` set, then builds the context's
Popen - ``popen_fork`` forks and sends nothing through Python,
``popen_spawn_posix`` and ``popen_forkserver`` pickle the process object
with ``reduction.dump`` and write it to the child; ``join()`` waits on the
Popen and discards a finished child from ``_children``; ``is_alive()`` is
one ``poll()``; ``terminate()``, ``kill()`` and ``interrupt()`` (3.14+)
send a signal and return; ``close()`` raises ValueError while ``poll()`` is
None and afterwards ``_check_closed`` raises in the methods and the
``exitcode``, ``pid`` and ``sentinel`` properties; ``active_children()`` is
``_cleanup()`` plus ``list(_children)``. Lib/multiprocessing/pool.py:
``Pool.__init__`` starts ``processes`` workers (``os.process_cpu_count()``
from 3.13, ``os.cpu_count()`` before) and three daemon threads; ``map()``
is ``_map_async(...).get()``, and ``_map_async`` lists an unsized iterable,
computes ``chunksize`` as ``ceil(len / (4 * workers))`` and builds a
MapResult holding ``[None] * len``; the task-handler thread iterates the
chunk generator and pickles each ``(mapstar, (func, chunk))`` task with
``inqueue._writer.send``, so the function is pickled once per chunk;
``imap()`` and ``imap_unordered()`` queue a generator over the input with
chunksize 1 and return an iterator whose ``_set`` appends every arriving
result to a deque, ``IMapIterator`` parking out-of-order ones in
``_unsorted``; ``ApplyResult._set`` unpickled nothing itself - the result
handler thread did, on ``recv`` - runs the callback and only then sets the
event ``ready()`` reads; ``get(timeout)`` raises the package's
``TimeoutError``; ``__exit__`` is ``terminate()``, whose ``_terminate_pool``
drains the inqueue, terminates each worker and joins it, and ``join()``
raises ValueError in the RUN state. Lib/multiprocessing/queues.py:
``Queue.put`` acquires the bounded semaphore, appends to a deque and
notifies; the feeder thread started on the first ``put`` pops, pickles with
``ForkingPickler.dumps``, and ``send_bytes`` under the writer lock, printing
a traceback and releasing the semaphore when pickling fails; ``get``
``recv_bytes`` under the reader lock, releases the semaphore and lock, and
then ``loads``; ``qsize`` is ``maxsize - sem.get_value()``, ``empty`` is
``not reader.poll()``; ``close`` marks the queue closed and queues the
feeder's sentinel; ``join_thread`` joins the feeder; ``SimpleQueue.put``
pickles in the caller, then ``send_bytes`` under the writer lock.
Lib/multiprocessing/connection.py: ``send`` is ``_send_bytes(dumps(obj))``,
``recv`` is ``loads(_recv_bytes())``, ``recv_bytes(maxlength)`` returns
None from ``_recv_bytes`` past the limit, which ``_bad_message_length``
turns into OSError, ``recv_bytes_into`` raises BufferTooShort carrying the
message, ``_send`` loops on ``os.write`` and blocks when the socket buffer
is full, ``poll`` is ``wait([self], timeout)``. Lib/multiprocessing/
synchronize.py: every primitive is a named ``_multiprocessing.SemLock``,
registered with the resource tracker unless the fork context unlinked it at
once; ``Condition.wait`` releases the lock ``_count()`` times and acquires
a semaphore, ``notify(n)`` releases the wait semaphore up to n times and
acquires the woken counter once per sleeper, ``notify_all`` is
``notify(sys.maxsize)``, ``Event.set`` is ``notify_all``, and Barrier is
``threading.Barrier`` with its state in a two-int shared buffer.
Lib/multiprocessing/sharedctypes.py: ``RawValue`` and ``RawArray`` take a
heap block, ``memset`` it, and ``__init__`` it from the arguments; ``Value``
and ``Array`` wrap the raw object with an ``RLock`` unless ``lock=False``,
the wrapper's ``value``, ``__getitem__``, ``__setitem__`` and slices
acquiring the lock and ``__len__`` not. Lib/multiprocessing/managers.py:
``Manager()`` is ``SyncManager(...).start()``, which starts a server
process and ``recv``s its address; each registered factory dispatches a
``create`` on a fresh connection and returns a proxy whose ``_incref`` is
another; ``BaseProxy._callmethod`` sends ``(id, methodname, args, kwds)``
on the thread's connection and receives ``(kind, result)``; list proxies
expose ``__getitem__`` but not ``__iter__``, so iteration is Python's
index-until-IndexError fallback, and dict proxies expose ``__iter__`` as an
Iterator proxy whose every ``__next__`` is a round trip; ``__exit__`` is
``shutdown()``. ``log_to_stderr`` adds a StreamHandler on every call;
``get_all_start_methods`` builds a new list; ``set_start_method`` raises
RuntimeError once a context is set unless forced.

Observation settles every row that has something to observe:

* an unstarted Process has no pid, ident or exitcode, is not alive, raises
  ValueError for ``sentinel`` and is absent from ``active_children()``; a
  list passed as ``args`` is copied, so an item appended afterwards is not
  seen; the target runs once, in a process whose ``os.getpid()`` is the
  Process's ``pid`` and whose ``parent_process().pid`` is the parent's,
  with its args and kwargs, where a direct ``run()`` runs it in the caller
  and a Process without a target runs nothing; ``join()`` on a finished
  child returns in under 5 seconds with a ten-second timeout and on a
  blocked one returns after its 50 ms timeout with the child alive;
  ``terminate()`` and ``kill()`` leave exit codes of -SIGTERM and -SIGKILL,
  and ``terminate()`` returns well inside five seconds from a child that
  ignores SIGTERM and stays alive until killed,
  and on 3.14 ``interrupt()`` reaches a SIGINT handler the child installed;
  ``close()`` raises ValueError on a live child, and afterwards
  ``is_alive()``, ``join()``, ``exitcode`` and ``pid`` raise it;
  ``active_children()`` with three live children returns a new
  three-element list, polls each child once, and ``start()`` polls all
  three; under ``spawn`` and ``forkserver`` an argument's ``__getstate__``
  runs once in the parent during ``start()``, under ``fork`` never;
* ``Pool(2)`` adds two to ``active_children()`` and ``close()`` +
  ``join()`` removes them, a default ``Pool()`` adds the CPU count;
  ``map()`` returns results in input order and exhausts a generator input,
  and ``map_async()`` has exhausted one, in the calling thread, by the
  time it returns, its tasks still gated;
  on 1000 items the function's ``__getstate__`` runs 1000 times with
  ``chunksize=1``, 8 times with the default on two workers, once with
  ``chunksize=1000``, 100 times for ``imap`` over 100 items and 10 with
  ``chunksize=10``; ``map_async`` returns with ``ready()`` false while its
  tasks are held behind a file gate; ``imap()`` yields its first item
  within five seconds while the input generator is still gated; six
  results reach the iterator's deque with none consumed; over a gated first task and a free second, ``imap`` parks the free
  result and times out where ``imap_unordered`` yields it at once; ``get(timeout=0.05)`` on a gated task
  raises ``multiprocessing.TimeoutError``, which is not a subclass of the
  builtin; ``successful()`` before ready raises ValueError; a result's ``__setstate__``
  has run once, in a thread other than the main one, once ``wait()``
  returns and before ``get()``, which does not run it again;
  a callback runs in a thread that is not the main thread and sees
  ``ready()`` false; ``apply_async`` after ``close()`` and ``join()``
  before it raise ValueError; a task that has signalled it started and is
  held behind a gate when a ``with`` block ends never writes its file, and
  its worker has left ``active_children()`` by then;
* a Queue's feeder, held inside one object's ``__getstate__``, has not
  pickled the object put after it, and the value received reflects a
  mutation made after ``put()`` returned; putting a lambda prints a
  traceback in the feeder, leaves ``qsize()`` at 0 and ``get(timeout)``
  raising Empty; ``Queue(maxsize=1)`` raises Full on the second
  ``put_nowait`` and after a 50 ms timed put; ``get_nowait`` on an empty queue raises Empty; a payload's ``__setstate__``
  finds the reader lock free while ``get()`` unpickles it; with the feeder held ``qsize()`` is 1 and
  ``empty()`` still true, and it turns false once the feeder is released;
  ``put`` and ``get`` after ``close()`` raise ValueError, ``join_thread()`` does not return while the feeder is held, and the
  three items buffered behind it at ``close()`` still reach a child reader;
  JoinableQueue's third ``task_done()`` for two puts raises ValueError and
  ``join()`` stays blocked with one item outstanding and returns once both
  are done; ``SimpleQueue.put`` runs ``__getstate__`` once, in the calling thread,
  before returning;
* ``Connection.send`` runs ``__getstate__`` once, in the calling thread,
  before returning and ``recv`` returns an equal object; the read end of a one-way pipe refuses
  ``send``; ``recv_bytes(maxlength)`` raises OSError for a longer message;
  ``recv_bytes_into`` a short buffer raises BufferTooShort carrying the
  message and a long one returns the length; ``poll()`` is false in under five seconds,
  false after its 50 ms timeout, true after a send; a 4 MiB ``send_bytes``
  is still blocked after 300 ms with no reader and finishes once one
  reads; a closed connection reports ``closed`` and refuses ``recv``;
* a free Lock is taken by a non-blocking acquire, a held one refuses it
  and gives up a 50 ms timed acquire after at least 50 ms; releasing an
  unheld Lock raises ValueError and an unheld RLock AssertionError; an
  RLock held three times refuses another thread until the third release;
  on 3.14 ``locked()`` follows the state; Semaphore(2) grants two and
  refuses the third, ``get_value()`` says 2, and BoundedSemaphore raises
  ValueError on the release past its initial value; ``notify(2)`` on six waiting threads wakes exactly two and
  ``notify_all()`` the rest, every wait returning True well inside its
  timeout; ``Event.set()`` is still blocked 200 ms after a child counted asleep on
  the event, and past releasing its lock, was killed; three
  timed-out waits leave three acknowledgements that the next ``notify()``
  clears; a waiter releases a doubly-held RLock for the notifier, who gets it
  well inside the wait's timeout, and the wait returns True with the lock
  held twice again;
  ``wait_for`` calls a true predicate once, and one made true by the
  notifier twice, the second look coming from that notify well inside the
  timeout;
  ``Event.wait()`` on a set event returns True at once, on a clear one
  returns False after its timeout, and ``set()`` wakes all five waiters, counted asleep first, well inside
  their ten-second timeout;
  the third of three barrier parties releases the other two and runs the
  action once, ``abort()`` and ``reset()`` each raise BrokenBarrierError in both waiters
  well inside their timeout, ``abort()`` leaving the barrier broken and
  ``reset()`` not, and a 50 ms timeout that expires leaves it broken until
  ``reset()``; in a fresh
  interpreter the resource tracker has no pid before the first ``Lock()``
  or ``Queue()`` and one afterwards under ``spawn`` and ``forkserver``,
  and none afterwards under ``fork``;
* ``Value(lock=False)`` is the bare ctypes object; a counting lock passed
  to ``Value`` is acquired once per read of ``value``, to ``Array`` once
  per item read and once per slice and never for ``len()``; ``Array`` from
  a sequence is a copy, its slice a new list each time, bytes for a ``c``
  array and str for a ``u`` array; a RawValue of a two-int Structure is zeroed and a four-char ``Value``
  returns a fresh bytes copy; a child's writes
  to a Value, an Array and a RawArray are visible in the parent;
* ``Manager()`` adds one child and the ``with`` block's exit removes it;
  ``append`` and ``[:]`` on a five-item list proxy each send one message on
  the thread's server connection, iteration six, ``list()`` seven; ``copy()``, ``keys()``,
  ``values()`` and ``items()`` on a dict proxy are one each, ``dict()`` six
  and iteration seven; ``connect()`` from a second manager adds no child, and a list it creates
  raises the first manager's server object count by one; ``get_server()`` on a started manager raises ProcessError;
  ``register()`` on a subclass adds the factory there and not to the base,
  a first registration on a SyncManager subclass copying the inherited
  registry plus one;
* ``cpu_count()`` is ``os.cpu_count()``; ``get_all_start_methods()`` is a
  new list each call containing the current method; an unknown method
  raises ValueError; a second ``set_start_method()`` in a fresh interpreter
  raises RuntimeError and ``force=True`` does not; ``get_logger()`` is one
  object and two ``log_to_stderr()`` calls add two handlers; the four
  exceptions subclass ProcessError; ``SUBDEBUG`` and ``SUBWARNING`` are 5
  and 25; ``reducer`` is the ``reduction`` module.

Not settled by running code: s, w and b themselves - how long a process
takes to start, how long a wait blocks and how many bytes an object pickles
to are the platform's and pickle's; the O(e) zeroing of a RawArray, which
is a memset the tests only observe the result of; ``Semaphore.get_value()``
on macOS, where the tests skip it; ``freeze_support()`` inside a frozen
executable; ``set_executable()`` and ``set_forkserver_preload()``, which
only store a value the next child start reads; the deadlock of two peers
that both send before receiving, which the tests infer from the one-way
block; and Windows, where ``Pipe()`` returns a PipeConnection and the
signals are TerminateProcess.
Not varied: pool workers beyond two except for the default count, pickled
sizes beyond a few kilobytes except for the 4 MiB blocking send, manager
serializers other than pickle, ``initializer`` and ``maxtasksperchild``,
and contention between more than one child process on a primitive.

Every helper thread here is a daemon and every child is joined or
terminated, so a failing assertion cannot hang the interpreter at exit. A
child is never killed while it is inside a wait on a primitive the test
uses again, since the killed-sleeper test shows what that does to the next
``set()``.
"""

from __future__ import annotations

import builtins
import ctypes
import math
import multiprocessing
import multiprocessing.connection
import multiprocessing.managers
import multiprocessing.pool
import multiprocessing.queues
import multiprocessing.sharedctypes
import multiprocessing.synchronize
import os
import pathlib
import queue
import re
import signal
import subprocess
import sys
import textwrap
import threading
import time
import types
import warnings
from collections.abc import Callable, Iterator
from typing import Any, cast

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "multiprocessing.md"
EXPECTED_BLOCKS = 6
WAIT = 10.0
SHORT = 0.05
POSIX = sys.platform != "win32"

_CONNECTION_TYPE = type(multiprocessing.Pipe()[0])

CLASSES: dict[str, type] = {
    "Process": multiprocessing.Process,
    "Pool": multiprocessing.pool.Pool,
    "AsyncResult": multiprocessing.pool.AsyncResult,
    "Queue": multiprocessing.queues.Queue,
    "JoinableQueue": multiprocessing.queues.JoinableQueue,
    "SimpleQueue": multiprocessing.queues.SimpleQueue,
    "Connection": _CONNECTION_TYPE,
    "Lock": multiprocessing.synchronize.Lock,
    "RLock": multiprocessing.synchronize.RLock,
    "Semaphore": multiprocessing.synchronize.Semaphore,
    "BoundedSemaphore": multiprocessing.synchronize.BoundedSemaphore,
    "Condition": multiprocessing.synchronize.Condition,
    "Event": multiprocessing.synchronize.Event,
    "Barrier": multiprocessing.synchronize.Barrier,
    # The lock methods live on the base both wrappers share, so a row on Value
    # covers Array too.
    "Value": multiprocessing.sharedctypes.SynchronizedBase,
    "Array": multiprocessing.sharedctypes.SynchronizedArray,
    "Manager": multiprocessing.managers.SyncManager,
}
# Classes whose __init__ installs public methods on the instance, and how to
# build one so those names count as members too.
INSTANCES: dict[str, Callable[[], object]] = {
    "Lock": multiprocessing.Lock,
    "RLock": multiprocessing.RLock,
    "Semaphore": multiprocessing.Semaphore,
    "BoundedSemaphore": multiprocessing.BoundedSemaphore,
    "Condition": multiprocessing.Condition,
    "Value": lambda: multiprocessing.Value("i", 0),
    "Array": lambda: multiprocessing.Array("i", 1),
}
# Members that exist only on a started instance, which the coverage check
# does not build.
INSTANCE_ONLY_MEMBERS = {("Manager", "shutdown")}
# Table names that are the types the module's factories return rather than
# attributes of the module itself.
RETURNED_TYPES = {"AsyncResult", "Connection"}
# `reducer` is a module object too, and is the one that is API.
LEAKED_IMPORTS = {"sys"}
# Pool.Process is the hook the pool builds its workers with, not user API.
UNDOCUMENTED_MEMBERS = {("Pool", "Process")}
VERSION_GATED_MEMBERS: dict[tuple[str, str], tuple[tuple[int, int], str]] = {
    ("Process", "interrupt"): ((3, 14), "Python 3.14+"),
    ("Lock", "locked"): ((3, 14), "Python 3.14+"),
    ("RLock", "locked"): ((3, 14), "Python 3.14+"),
    ("Semaphore", "locked"): ((3, 14), "Python 3.14+"),
    ("Manager", "set"): ((3, 14), "Python 3.14+"),
}


def _gated_away(owner: str, member: str) -> bool:
    """A documented member this interpreter is allowed to lack: older than its gate."""
    gate = VERSION_GATED_MEMBERS.get((owner, member))
    return gate is not None and sys.version_info < gate[0]


def _module_names() -> set[str]:
    """Public names of the package that are not submodules, which importing adds."""
    return {
        name
        for name in dir(multiprocessing)
        if not name.startswith("_")
        and (name == "reducer" or not isinstance(getattr(multiprocessing, name), types.ModuleType))
    } - LEAKED_IMPORTS


def _table_rows() -> list[str]:
    text = PAGE.read_text(encoding="utf-8")
    start = text.index("| Operation | Time | Space | Notes |")
    end = text.index("\n\nSubmodules", start)
    return [line for line in text[start:end].splitlines() if line.startswith("| `")]


def _segments(span: str) -> Iterator[str]:
    """The names in one backticked span, ``Array[i]`` and ``len(Array)`` included."""
    for segment in span.split("/"):
        segment = segment.strip()
        segment = re.sub(r"\[.*\]", "", segment)
        if segment.startswith("len(") and segment.endswith(")"):
            segment = segment[4:-1]
        segment = segment.removesuffix("()").strip()
        if " " in segment:
            segment = segment.split(" ", 1)[0]
        yield segment


def _documented_in(row: str) -> tuple[set[str], set[tuple[str, str]]]:
    """Module-level names and (class, member) pairs one row names.

    A backticked span is split on ``/``; a segment after the first inherits
    the class of the segment before it, so ``Process.name/daemon`` names two
    attributes of Process and ``Lock()`` / ``RLock()`` two module names.
    """
    names: set[str] = set()
    members: set[tuple[str, str]] = set()
    operation = row.split("|")[1]
    for span in re.findall(r"`([^`]+)`", operation):
        owner: str | None = None
        for segment in _segments(span):
            if "." in segment:
                class_name, member = segment.split(".", 1)
                owner = class_name
                names.add(class_name)
                members.add((class_name, member))
            elif owner is not None:
                members.add((owner, segment))
            else:
                names.add(segment)
    return names, members


def _documented() -> tuple[set[str], set[tuple[str, str]]]:
    """Module-level names and (class, member) pairs the whole table names."""
    names: set[str] = set()
    members: set[tuple[str, str]] = set()
    for row in _table_rows():
        row_names, row_members = _documented_in(row)
        names |= row_names
        members |= row_members
    return names, members


def _public_members(owner: str) -> set[str]:
    """Public names on the class or its bases, plus any its __init__ installs."""
    members = {name for name in dir(CLASSES[owner]) if not name.startswith("_")}
    if owner in INSTANCES:
        members |= {name for name in dir(INSTANCES[owner]()) if not name.startswith("_")}
    return members - {member for cls, member in UNDOCUMENTED_MEMBERS if cls == owner}


def _documented_for(owner: str, members: set[tuple[str, str]]) -> set[str]:
    """Members documented on the class or on a documented base of it."""
    bases = {name for name, cls in CLASSES.items() if cls in CLASSES[owner].__mro__}
    return {member for documented_owner, member in members if documented_owner in bases}


def _has_member(owner: str, member: str) -> bool:
    if hasattr(CLASSES[owner], member):
        return True
    return owner in INSTANCES and hasattr(INSTANCES[owner](), member)


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


class TestEveryPublicNameIsDocumented:
    """The table has to name every public attribute of `multiprocessing` and of its classes."""

    def test_no_module_name_is_missing_from_the_table(self) -> None:
        missing = sorted(_module_names() - _documented()[0])

        assert not missing, f"{len(missing)} public names absent from the table: {missing}"

    def test_no_public_member_is_missing_from_the_table(self) -> None:
        """A member inherited from a documented base counts as documented."""
        members = _documented()[1]
        missing: list[str] = []
        for owner in CLASSES:
            documented = _documented_for(owner, members)
            missing.extend(
                f"{owner}.{name}" for name in sorted(_public_members(owner) - documented)
            )

        assert not missing, f"{len(missing)} members absent from the table: {missing}"

    def test_the_table_names_nothing_that_does_not_exist(self) -> None:
        """The other direction, so a typo cannot pass as coverage."""
        names, members = _documented()

        unknown_names = sorted(names - _module_names() - RETURNED_TYPES)
        unknown_members = sorted(
            f"{owner}.{member}"
            for owner, member in members
            if owner not in CLASSES
            or (
                not _has_member(owner, member)
                and not _gated_away(owner, member)
                and (owner, member) not in INSTANCE_ONLY_MEMBERS
            )
        )

        assert not unknown_names, f"the table names attributes the module lacks: {unknown_names}"
        assert not unknown_members, f"the table names members that do not exist: {unknown_members}"

    def test_the_version_gated_rows_say_so(self) -> None:
        rows = _table_rows()
        for (owner, member), (_, marker) in VERSION_GATED_MEMBERS.items():
            owning = [row for row in rows if (owner, member) in _documented_in(row)[1]]
            assert len(owning) == 1, f"expected one row naming {owner}.{member}, found {owning}"
            assert marker in owning[0], f"the {owner}.{member} row should say {marker}"

    def test_the_coverage_check_would_notice_a_gap(self) -> None:
        """A coverage test that cannot fail proves nothing about coverage."""
        names, members = _documented()

        assert {"Process", "Pool", "Pipe", "cpu_count", "SUBDEBUG", "reducer"} <= names
        assert {
            ("Process", "start"),
            ("Process", "sentinel"),
            ("Pool", "starmap_async"),
            ("Queue", "cancel_join_thread"),
            ("Connection", "recv_bytes_into"),
            ("Connection", "writable"),
            ("Value", "get_obj"),
            ("Manager", "Namespace"),
            ("Manager", "address"),
        } <= members
        assert _module_names() - (names - {"Barrier"}) == {"Barrier"}
        assert {"Process", "reducer"} <= _module_names() and "pool" not in _module_names()
        assert _public_members("JoinableQueue") - _documented_for(
            "JoinableQueue", members - {("JoinableQueue", "task_done")}
        ) == {"task_done"}
        assert "acquire" in _public_members("Lock")
        assert "value" in _public_members("Value")
        assert "put" in _documented_for("JoinableQueue", members)


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
            assert elapsed >= SHORT, elapsed
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
        assert seen["thread"] is not threading.main_thread()
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
        assert time.perf_counter() - start >= SHORT

        assert shared.get(timeout=WAIT) == 1
        shared.put_nowait(2)
        assert shared.get(timeout=WAIT) == 2
        with pytest.raises(queue.Empty):
            shared.get_nowait()
        start = time.perf_counter()
        with pytest.raises(queue.Empty):
            shared.get(timeout=SHORT)
        assert time.perf_counter() - start >= SHORT
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
        assert time.perf_counter() - start >= SHORT

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


class TestSynchronizationRows:
    """Lock, RLock, Semaphore, BoundedSemaphore, Condition, Event and Barrier."""

    def test_lock_acquire_is_immediate_when_free_and_bounded_by_its_timeout(self) -> None:
        lock = multiprocessing.Lock()

        assert lock.acquire(False)
        assert not lock.acquire(False)
        start = time.perf_counter()
        assert not lock.acquire(timeout=SHORT)
        assert time.perf_counter() - start >= SHORT
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
        assert time.perf_counter() - start >= SHORT

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


class TestSharedMemoryRows:
    """RawValue(), RawArray(), Value() and Array()."""

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
        source = _block_containing("cells = Array(")
        broken = source.replace('Array("i", 5)', 'Array("i")', 1)
        assert broken != source, "the mutation did not change the constructor call"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "TypeError" in result.stderr

    @pytest.mark.parametrize(
        ("marker", "stdout"),
        [
            ('name="worker"', ["worker squares 7: 49", "0"]),
            ("pool.map(square", ["332833500 0"]),
            ("def produce(", ["[0, 1, 2, 3, 4]"]),
            ("def respond(", ["PING"]),
            ("cells = Array(", ["1 [0, 10, 20, 30, 40]"]),
            ("shared = manager.list(", ["[0, 1, 2, 3, 4, 5] [0, 2, 4, 6, 8, 10]"]),
        ],
        ids=["process", "pool", "queue", "pipe", "shared", "manager"],
    )
    def test_the_stated_output_is_what_the_block_produces(
        self, marker: str, stdout: list[str], tmp_path: pathlib.Path
    ) -> None:
        result = _run(_block_containing(marker), tmp_path)

        assert result.returncode == 0, result.stderr.strip()
        assert result.stdout.splitlines() == stdout
