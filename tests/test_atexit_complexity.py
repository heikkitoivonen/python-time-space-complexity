"""Tests for docs/stdlib/atexit.md.

The page prices the module by the size of its one registry: `register()` adds
an entry, `unregister()` scans every entry, and shutdown calls each one. Every
measurement runs in a fresh child interpreter, where the private
`atexit._clear()`, `atexit._ncallbacks()` and `atexit._run_exitfuncs()` can
empty, count and run the registry without touching the test process's own
handlers. Growth is settled by holding the work fixed while the registry grows
a hundredfold, space by traced allocation, and behaviour by what a child
interpreter prints and returns.

Measurement scope:

* `register()` is timed as 1,000 calls on top of 1,000 and of 100,000
  registered handlers, fastest of three, with the registry rebuilt before
  each trial. On Python 3.14+ the larger registry costs more than 10x as
  much per call; on 3.13 and earlier less than 5x. Its space is the traced
  growth of current memory over 10,000 and 100,000 registrations: under 200
  bytes per handler at both sizes, and less than 2x apart.
* `unregister()` is a counting `__eq__` called once per registered handler,
  for 50 and 5,000 handlers, with no match. The removal term is timed with
  20,000 older handlers fixed and 200 and then 2,000 matches registered after
  them, fastest of three: on 3.14+ 10x the matches costs more than 4x, on
  3.13 and earlier less than 2.5x, where the scan of the older handlers
  dominates. Its space is a traced peak under 1 KB over 100,000 handlers,
  for an absent function, for one match and for 50,000 matches.
* Slots on 3.13 and earlier: after 10,000 register/unregister cycles of one
  function `_ncallbacks()` reports 10,000 and an `unregister()` of an absent
  function costs more than 20x what it does on a registry of one handler; on
  3.14+ `_ncallbacks()` reports 0.
* Running the handlers is a traced peak around `_run_exitfuncs()` over 10,000
  and 100,000 handlers of one function with no arguments: on 3.14+ it is at
  least one pointer per handler, on 3.13 and earlier under 1 KB at both
  sizes. Its time is the same two sizes, fastest of three: 10x the handlers
  costs between 4x and 30x.
  That the handlers run newest first, that a raising handler is reported on
  stderr while the others run and the exit status stays 0, and which ways of
  ending a child run them, are asserted on the child's output and exit
  status: normal end (status 0), `sys.exit(3)` (status 3), an uncaught
  exception and `SIGINT` (a non-zero status and the exception on stderr) do;
  `os._exit()` and `SIGKILL` do not; a `SIGTERM` handler that calls
  `sys.exit()` does.
* `register()` returning `func`, its `TypeError` for a non-callable, and
  equality-based removal of every match are asserted directly. That the
  registry keeps a bound method's object alive, and that `unregister()`
  releases it, are asserted with a weak reference in a child; that
  `weakref.finalize()` does not keep its object alive is asserted by the
  page's example, and that it runs at exit is covered by
  tests/test_weakref_complexity.py.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* On 3.13 and earlier the registry is a C array that grows 16 slots at a
  time, so `register()` is O(1) only where the allocator's `realloc()`
  extends the block in place, which is the condition the page states. Only
  glibc on Linux is measured; a `realloc()` that copies makes it O(n) every
  16 calls.
* The O(1) set operations in the page's Common Patterns example are the
  bounds of docs/builtins/set.md, not measured here.
* That handlers do not run after a Python fatal error is the official
  documentation's statement; no test provokes one.
* `SIGKILL` and the `SIGTERM` handler are POSIX tests: on Windows `os.kill()`
  ends the process with `TerminateProcess()`, which no Python code observes.
* The cost of the arguments stored with a handler, and of `__eq__`, are held
  at O(1) by the cost model; neither is varied. Registering or unregistering
  from inside a running handler is left undefined by the official
  documentation and is not tested. The 50,000-match removal leaves two thirds
  of the registry, so it does not reach the size at which a 3.14+ list
  shrinks its storage.
"""

from __future__ import annotations

import atexit
import json
import pathlib
import re
import signal
import struct
import subprocess
import sys
import textwrap
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "atexit.md"
EXPECTED_BLOCKS = 5

FROM_314 = sys.version_info >= (3, 14)

MEASURE_PRELUDE = """
import atexit
import json
import time
import tracemalloc

def handler():
    pass

def best_ns(func, repeats=3):
    best = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        elapsed = time.perf_counter_ns() - start
        best = elapsed if best is None else min(best, elapsed)
    return best
"""


def run_child(source: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run `source` in a fresh interpreter and capture its output."""
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source), *args],
        capture_output=True,
        text=True,
        timeout=300,
        stdin=subprocess.DEVNULL,
        check=False,
    )


def measure(source: str) -> Any:
    """Run a measurement in a fresh interpreter and return what it printed as JSON."""
    result = run_child(MEASURE_PRELUDE + textwrap.dedent(source))
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


class TestRegisterReturnsItsFunction:
    """`register(func, *args, **kwargs)` returns `func` and rejects a
    non-callable before storing anything."""

    def test_it_returns_func_so_it_works_as_a_decorator(self) -> None:
        def handler() -> None:
            pass

        try:
            assert atexit.register(handler) is handler
        finally:
            atexit.unregister(handler)

    def test_a_non_callable_is_rejected_at_once(self) -> None:
        with pytest.raises(TypeError, match="callable"):
            atexit.register(42)  # type: ignore[arg-type]

    def test_arguments_are_stored_and_passed_at_exit(self) -> None:
        result = run_child(
            """
            import atexit
            atexit.register(print, "a", "b", sep="-")
            """
        )

        assert result.stdout == "a-b\n"


class TestRegisterCost:
    """`register()` | O(n) on Python 3.14+, O(1) before.

    The same 1,000 registrations are timed on a small and a hundredfold larger
    registry: an insert at the front of a list on 3.14+ scales with it, an
    append to the array before 3.14 does not.
    """

    SOURCE = """
    def added():
        pass

    def per_call(existing):
        best = None
        for _ in range(3):
            atexit._clear()
            for _ in range(existing):
                atexit.register(handler)
            start = time.perf_counter_ns()
            for _ in range(1_000):
                atexit.register(added)
            elapsed = time.perf_counter_ns() - start
            best = elapsed if best is None else min(best, elapsed)
        return best / 1_000

    print(json.dumps([per_call(1_000), per_call(100_000)]))
    """

    @pytest.mark.timing
    def test_registering_scales_with_the_registry_from_314_only(self) -> None:
        small, large = measure(self.SOURCE)
        ratio = large / small

        if FROM_314:
            assert ratio > 10, f"100x the registry: {small:.0f} -> {large:.0f} ns, x{ratio:.1f}"
        else:
            assert ratio < 5, f"100x the registry: {small:.0f} -> {large:.0f} ns, x{ratio:.1f}"

    SPACE = """
    def per_handler(count):
        atexit._clear()
        tracemalloc.start()
        before = tracemalloc.get_traced_memory()[0]
        for _ in range(count):
            atexit.register(handler)
        grown = tracemalloc.get_traced_memory()[0] - before
        tracemalloc.stop()
        return grown / count

    print(json.dumps([per_handler(10_000), per_handler(100_000)]))
    """

    def test_each_handler_adds_a_constant_amount(self) -> None:
        small, large = measure(self.SPACE)

        assert 0 < small < 200 and 0 < large < 200, f"bytes per handler: {small}, {large}"
        assert large < small * 2, f"bytes per handler grew with the registry: {small} -> {large}"


class TestUnregisterScansEveryHandler:
    """`unregister()` | O(n), plus O(n) per removed handler on Python 3.14+.

    The scan is counted with an `__eq__` that never matches; the removal term
    is timed by growing the matches in front of a fixed set of older handlers.
    """

    SCAN = """
    class Probe:
        calls = 0

        def __eq__(self, other):
            Probe.calls += 1
            return NotImplemented

        __hash__ = object.__hash__

        def __call__(self):
            pass

    counts = []
    for size in (50, 5_000):
        atexit._clear()
        for _ in range(size):
            atexit.register(handler)
        Probe.calls = 0
        atexit.unregister(Probe())
        counts.append(Probe.calls)
    print(json.dumps(counts))
    """

    def test_one_comparison_per_registered_handler(self) -> None:
        assert measure(self.SCAN) == [50, 5_000]

    REMOVAL = """
    def older():
        pass

    def removal(matches):
        def once():
            atexit._clear()
            for _ in range(20_000):
                atexit.register(older)
            for _ in range(matches):
                atexit.register(handler)
            start = time.perf_counter_ns()
            atexit.unregister(handler)
            return time.perf_counter_ns() - start

        return min(once() for _ in range(3))

    print(json.dumps([removal(200), removal(2_000)]))
    """

    @pytest.mark.timing
    def test_each_removal_shifts_the_older_handlers_from_314(self) -> None:
        few, many = measure(self.REMOVAL)
        ratio = many / few

        if FROM_314:
            assert ratio > 4, f"10x the matches before 20,000 handlers: {few} -> {many} ns"
        else:
            assert ratio < 2.5, f"10x the matches before 20,000 handlers: {few} -> {many} ns"

    UNREGISTER_SPACE = """
    def absent():
        pass

    def match():
        pass

    atexit._clear()
    for _ in range(100_000):
        atexit.register(handler)
    atexit.register(match)
    peaks = []
    for target, copies in ((absent, 0), (match, 0), (match, 50_000)):
        for _ in range(copies):
            atexit.register(target)
        tracemalloc.start()
        atexit.unregister(target)
        peaks.append(tracemalloc.get_traced_memory()[1])
        tracemalloc.stop()
    print(json.dumps(peaks))
    """

    def test_it_allocates_nothing_that_grows_with_the_registry(self) -> None:
        peaks = measure(self.UNREGISTER_SPACE)

        assert max(peaks) < 1_000, f"absent, one match, 50,000 matches: {peaks} bytes"

    def test_every_equal_handler_is_removed(self) -> None:
        result = run_child(
            """
            import atexit

            class Resource:
                def close(self):
                    print("closed")

            resource = Resource()
            atexit.register(resource.close)
            atexit.register(print, "kept")
            atexit.register(resource.close)
            assert resource.close is not resource.close
            atexit.unregister(resource.close)
            """
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout == "kept\n"


class TestUnregisteredSlots:
    """`n` counts handlers already unregistered on 3.13 and earlier: the slot
    stays until the handlers run. 3.14+ reclaims it."""

    SOURCE = """
    def absent():
        pass

    atexit._clear()
    atexit.register(handler)
    fresh = best_ns(lambda: atexit.unregister(absent), repeats=50)

    atexit._clear()
    for _ in range(10_000):
        atexit.register(handler)
        atexit.unregister(handler)
    slots = atexit._ncallbacks()
    cycled = best_ns(lambda: atexit.unregister(absent), repeats=50)
    print(json.dumps([slots, fresh, cycled]))
    """

    def test_the_slots_survive_before_314_and_not_after(self) -> None:
        slots, _, _ = measure(self.SOURCE)

        assert slots == (0 if FROM_314 else 10_000)

    @pytest.mark.timing
    @pytest.mark.skipif(FROM_314, reason="3.14+ reclaims an unregistered handler's slot")
    def test_the_scan_still_walks_them_before_314(self) -> None:
        _, fresh, cycled = measure(self.SOURCE)

        assert cycled > fresh * 20, f"10,000 freed slots: {fresh} -> {cycled} ns"


class TestRunningTheHandlers:
    """Running the handlers | O(n) | O(n) on Python 3.14+, O(1) before:
    newest first, and a raising handler is reported while the rest run."""

    SPACE = """
    peaks = []
    for size in (10_000, 100_000):
        atexit._clear()
        for _ in range(size):
            atexit.register(handler)
        tracemalloc.start()
        atexit._run_exitfuncs()
        peaks.append(tracemalloc.get_traced_memory()[1])
        tracemalloc.stop()
        assert atexit._ncallbacks() == 0
    print(json.dumps(peaks))
    """

    def test_the_copy_taken_before_running_from_314(self) -> None:
        small, large = measure(self.SPACE)

        pointer = struct.calcsize("P")
        if FROM_314:
            assert small >= pointer * 10_000, f"10,000 handlers peaked at {small} bytes"
            assert large >= pointer * 100_000, f"100,000 handlers peaked at {large} bytes"
        else:
            assert max(small, large) < 1_000, f"running peaked at {small} and {large} bytes"

    TIME = """
    def run(size):
        def once():
            atexit._clear()
            for _ in range(size):
                atexit.register(handler)
            start = time.perf_counter_ns()
            atexit._run_exitfuncs()
            return time.perf_counter_ns() - start

        return min(once() for _ in range(3))

    print(json.dumps([run(10_000), run(100_000)]))
    """

    @pytest.mark.timing
    def test_the_run_is_linear_in_the_handlers(self) -> None:
        small, large = measure(self.TIME)
        ratio = large / small

        assert 4 < ratio < 30, f"10x the handlers: {small} -> {large} ns, x{ratio:.1f}"

    def test_newest_first(self) -> None:
        result = run_child(
            """
            import atexit
            for name in ("a", "b", "c"):
                atexit.register(print, name)
            """
        )

        assert result.stdout.split() == ["c", "b", "a"]

    def test_a_raising_handler_does_not_stop_the_rest(self) -> None:
        result = run_child(
            """
            import atexit
            atexit.register(print, "older")
            atexit.register(lambda: 1 / 0)
            atexit.register(print, "newer")
            """
        )

        assert result.returncode == 0
        assert result.stdout.split() == ["newer", "older"]
        assert "atexit callback" in result.stderr
        assert "ZeroDivisionError" in result.stderr

    def test_the_exception_reaches_sys_unraisablehook(self) -> None:
        result = run_child(
            """
            import atexit, sys
            sys.unraisablehook = lambda unraisable: print(type(unraisable.exc_value).__name__)
            atexit.register(lambda: 1 / 0)
            """
        )

        assert result.returncode == 0
        assert result.stdout == "ZeroDivisionError\n"
        assert result.stderr == ""


class TestWhenHandlersRun:
    """The warning: normal shutdown runs the handlers; `os._exit()` and a
    signal Python does not handle skip them."""

    PROGRAM = """
    import atexit, os, signal, sys
    atexit.register(print, "ran", flush=True)
    how = sys.argv[1]
    if how == "exit":
        sys.exit(3)
    if how == "raise":
        raise KeyError("uncaught")
    if how == "_exit":
        os._exit(4)
    if how == "sigint":
        signal.signal(signal.SIGINT, signal.default_int_handler)
        signal.raise_signal(signal.SIGINT)
    if how == "sigkill":
        os.kill(os.getpid(), signal.SIGKILL)
    if how == "handled-sigterm":
        signal.signal(signal.SIGTERM, lambda signum, frame: sys.exit(143))
        os.kill(os.getpid(), signal.SIGTERM)
        signal.pause()
    """

    @pytest.mark.parametrize(
        ("how", "evidence"),
        [("end", None), ("exit", None), ("raise", "KeyError"), ("sigint", "KeyboardInterrupt")],
    )
    def test_normal_shutdown_runs_them(self, how: str, evidence: str | None) -> None:
        result = run_child(self.PROGRAM, how)

        assert result.stdout == "ran\n", result.stderr
        if how == "end":
            assert result.returncode == 0
        elif how == "exit":
            assert result.returncode == 3
        else:
            assert result.returncode != 0
            assert evidence is not None and evidence in result.stderr

    def test_os_exit_skips_them(self) -> None:
        result = run_child(self.PROGRAM, "_exit")

        assert result.returncode == 4
        assert result.stdout == ""

    @pytest.mark.skipif(
        sys.platform == "win32", reason="Windows has no SIGKILL; os.kill() calls TerminateProcess"
    )
    def test_an_unhandled_signal_skips_them(self) -> None:
        result = run_child(self.PROGRAM, "sigkill")

        assert result.returncode == -signal.SIGKILL
        assert result.stdout == ""

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="os.kill() on Windows calls TerminateProcess, which no signal handler sees",
    )
    def test_a_sigterm_handler_that_exits_runs_them(self) -> None:
        result = run_child(self.PROGRAM, "handled-sigterm")

        assert result.returncode == 143
        assert result.stdout == "ran\n"


class TestTheRegistryHoldsItsHandlers:
    """A registered bound method keeps its object alive until exit;
    `unregister()` releases it."""

    def test_a_bound_method_keeps_its_object_alive(self) -> None:
        result = run_child(
            """
            import atexit, gc, weakref

            class Resource:
                def close(self):
                    pass

            resource = Resource()
            alive = weakref.ref(resource)
            atexit.register(resource.close)
            del resource
            gc.collect()
            held = alive() is not None
            atexit.unregister(alive().close)
            gc.collect()
            print(held, alive() is None)
            """
        )

        assert result.stdout == "True True\n", result.stderr


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
    """Each block runs in its own subprocess, so the handlers one registers
    cannot reach another, and asserts its own result."""

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
        expected = '["registered last", "registered first"]'
        line, source = next((n, s) for n, s in _blocks() if expected in s)
        mutated = source.replace(expected, '["registered first", "registered last"]', 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
