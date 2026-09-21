"""Tests for docs/stdlib/sys.md.

Most of `sys` reads or writes one interpreter field, so most of the page is a
wall of O(1) with nothing to vary. The rows that are not constant are mostly
observable rather than timed: a frame walk is a chain of known length,
`_current_frames()` and `_current_exceptions()` return one entry per thread,
audit hooks fire in order until one raises, a tracer is called once per event,
an import miss calls every `sys.meta_path` finder, and the `sys.path_hooks`
scan happens once per path entry. Where only a stopwatch separates two growth
classes - the frame walk, the first intern, installing a tracer, the
`sys.monitoring` instrumentation, the insert loop - the test measures the same
operation at two input sizes and asserts on the ratio. The one stopwatch test
that does not vary a size is the module-name comparison, which times two
different collection types instead; its scope is below.

Measurement scope:

* `sys._getframe(d)`: depth 100 against depth 1,000, 20,000 calls each,
  asserting the deeper walk costs more than four times the shallower one.
* `sys.setrecursionlimit(n)` is O(t) in the thread count from 3.11, where it
  writes through to every thread state (`Py_SetRecursionLimit` in
  Python/ceval.c): flat on 3.10 at 5.0e-08s from 1 thread to 400, and
  3.4e-08s to 4.9e-07s across the same range on 3.14.
* `sys.intern(s)`: 2,000 fresh strings of 1,000 characters against 2,000 of
  100,000, in a subprocess, asserting a factor of ten. Re-interning the same
  two lengths is asserted flat within a factor of two, and `sys._is_interned`
  is flat over the same lengths - 5.7e-03s against 5.8e-03s for 200,000 calls.
* `sys.monitoring.set_local_events`: 100 bytes of bytecode against 98,988,
  6.6e-07s against 6.3e-04s, a factor of 956 for a factor of 990 in code.
* `sys.monitoring.set_events`: the same two code objects, this time on the
  stack while the call is made, 6.1e-06s against 6.1e-04s. The fixed
  stop-the-world cost is what keeps the ratio at 100 rather than 990.
* `name in sys.builtin_module_names` against `name in sys.stdlib_module_names`
  for a name at the end of the tuple: 0.068s against 0.0027s for 100,000
  lookups over 100 and 297 entries, a factor of 25. This one contrasts two
  fixed collections rather than two sizes of one, so it separates a scan from
  a hash lookup without establishing either growth curve; the types it asserts
  alongside are what carry the O(b) and O(1) in the rows.
* `sys.settrace(fn)`: installing and removing a tracer while a frame of 110
  bytes of bytecode is live against one of 98,998, 100 calls per sample and
  the best of five. Flat on 3.10 and 3.11 - 1.3e-07s against 1.3e-07s - and
  7.3e-06s against 7.3e-04s on 3.12, 6.6e-06s against 6.0e-04s on 3.13,
  7.0e-06s against 6.2e-04s on 3.14. `sys.setprofile` measures the same way,
  4.1e-06s against 3.0e-04s on 3.14, and is covered by the same row.
* k inserts at the front of an 8-element list: k of 2,000 against 4,000,
  asserting more than three times the cost, which a bound without the k**2
  term would put at two.
* `sys.getsizeof`: list, dict, set, str, bytes and int at two sizes three to
  four orders of magnitude apart, asserting the larger costs less than twice
  the smaller.
* `sys.intern` retention: 500 strings of 20,000 characters interned and
  dropped retains 10.0 MB on 3.12.5 and 3.12.6 and 0.0 MB on 3.10, 3.11,
  3.12.7, 3.12.14, 3.13 and 3.14. The immortal window is a patch range, not a
  minor release: gh-113993 landed in 3.12.7.
* The rest is counted rather than timed: hooks fired, `find_spec` calls,
  `__sizeof__` calls, traceback frames printed, `firstiter` calls, entries in
  a returned dict, and object identity before and after.

Untested axes, and why:

* Interpreter count. Every measurement here is from one process with one
  interpreter, so the `i` in `sys.getallocatedblocks()` and the walk over all
  interpreters in `sys._current_exceptions()` are source-only; only the
  per-thread term is measured.
* Interpreter state. `_current_frames`, `_current_exceptions` and
  `setrecursionlimit` walk per-interpreter thread lists, so a sub-interpreter
  would change which threads are counted, not how the count is reached.
* Audit hook cost. The dispatch is counted, not timed; a hook that does real
  work adds its own cost to each of the h calls, which is the caller's. The
  same goes for the `m` in the `excepthook` rows: a longer message is measured
  through the report it produces, not a `__str__` that does work to produce a
  short one.
* Argument count. `sys.audit(event, *args)` is measured at a fixed arity; the
  tuple the call packs is the caller's, as `h` is not.
* Callback cost under `sys.monitoring`. The instrumentation is measured; what
  a registered callback does on each event is the caller's.

Not settled by execution:

* Every O(1) row with no input dimension - `getrecursionlimit`, `getrefcount`,
  `exc_info`, the simple getters, the struct sequences and the data
  attributes. There is nothing to vary, so growth cannot be measured. They are
  single field reads in Python/sysmodule.c, and the tests below assert only
  that each name exists and answers.
* `sys.exit()`'s note that the shutdown after the raise is not part of its
  cost. The raise is tested; the interpreter teardown it triggers cannot be
  measured from inside the process it tears down.
* `sys.breakpointhook()`'s default. `PYTHONBREAKPOINT` steering it is tested;
  what `pdb.set_trace()` costs is an interactive session.
* `sys.getobjects()` exists only in a `Py_TRACE_REFS` debug build, which this
  project does not run.
* `sys.ps1` and `sys.ps2` are bound only in an interactive session, so their
  absence here is asserted and their O(1) read is not.
  `sys.__interactivehook__` is not in that group: `site` installs it in a
  plain script too, and it is interactive startup that *calls* it, which
  nothing here does. `sys.last_exc`, `sys.last_type`, `sys.last_value` and
  `sys.last_traceback` are not in that group: a plain script binds them too,
  and the tests below read them from a replacement `sys.excepthook`.
* The platform-only rows - `sys.getwindowsversion()`, `sys.dllhandle`,
  `sys.winver` and `sys._enablelegacywindowsfsencoding()` on Windows,
  `sys.getandroidapilevel()` on Android, `sys._emscripten_info` on Emscripten
  - each have a test guarded by `sys.platform`. Every one of those guards
  skips on Linux and on CI, so no run this project performs verifies those
  rows; the guard is there so a reader on that platform gets an answer rather
  than a red suite.
* `sys._debugmallocstats()`'s O(a) in the allocator's arenas, and
  `sys._clear_internal_caches()`'s O(x) in the tier-2 executors. Both calls are
  exercised. A program does influence both counts, but not in a way it can
  read back or hold steady, so neither supports a two-size measurement here.
* `sys.tracebacklimit` capping what is printed rather than what is walked.
  The printed frames are counted; that `tb_printinternal` in
  Python/traceback.c measures the whole chain before skipping to the limit is
  source-only.
* `sys.monitoring.restart_events()` and `clear_tool_id()` costing the same
  walk as `set_events`. Their effects are observed; that all three reach
  `instrument_all_executing_code_objects` in Python/instrumentation.c is
  source-only, and only `set_events` is timed.
* `sys.getallocatedblocks()` pausing every thread from 3.13. The sum is read;
  `_PyEval_StopTheWorldAll` around it in Objects/obmalloc.c is source-only.
* The `sys.stdin`, `sys.stdout` and `sys.stderr` member attributes the audit
  reports as unclassified - `encoding`, `errors`, `line_buffering`, `newlines`,
  `buffer`, `mode`, `name`, `closed`, `write_through` - belong to
  `io.TextIOWrapper` and are priced on the io page, not here.
"""

from __future__ import annotations

import gc
import io
import os
import pathlib
import re
import select
import subprocess
import sys
import textwrap
import threading
import time
import timeit
import tracemalloc
from collections.abc import AsyncIterator, Callable, Iterator
from types import FrameType
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).resolve().parent.parent / "docs" / "stdlib" / "sys.md"
EXPECTED_BLOCKS = 13

# gh-113993 made interned strings mortal again, and it was backported: the
# immortal table covers 3.12.0 to 3.12.6 and nothing else in the supported
# range. Interning 500 strings of 20,000 characters and dropping every
# reference retains 10.0 MB on 3.12.5 and 3.12.6, and 0.0 MB on 3.12.7.
IMMORTAL_INTERNING = (3, 12) <= sys.version_info[:3] < (3, 12, 7)


def sys_attr(name: str) -> Any:
    """Reach a `sys` name typeshed does not carry at the floor of the range."""
    return getattr(sys, name)


def per_call(operation: Callable[[], Any], number: int = 1000, repeat: int = 5) -> float:
    """Seconds per call, taking the best of several runs."""
    return min(timeit.repeat(operation, number=number, repeat=repeat)) / number


def run_isolated(
    source: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run a snippet in a fresh interpreter.

    Audit hooks cannot be removed once installed, a tracer slows everything
    that follows, and `sys.monitoring` leaves instrumentation on whatever was
    executing, so the tests for those run out of process rather than leaving
    the suite in a changed state. So does the intern timing test: on 3.12.0 to
    3.12.6 an interned string is immortal, and it interns some 200 MB of them
    that would otherwise stay resident for the rest of the run.
    """
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        env=None if env is None else {**os.environ, **env},
        check=False,
    )


class ParkedThreads:
    """A context manager holding a fixed number of threads alive and idle."""

    def __init__(self, count: int) -> None:
        self.count = count
        self._release = threading.Event()
        self._running = threading.Barrier(count + 1)
        self._threads: list[threading.Thread] = []

    def _park(self) -> None:
        self._running.wait()
        self._release.wait()

    def __enter__(self) -> ParkedThreads:
        self._threads = [
            threading.Thread(target=self._park, daemon=True) for _ in range(self.count)
        ]
        for thread in self._threads:
            thread.start()
        self._running.wait()  # every thread is live before anything is measured
        return self

    def __exit__(self, *exc: object) -> None:
        self._release.set()
        for thread in self._threads:
            thread.join()


class TestExceptionState:
    """`exc_info()`, `exception()`, `exit()` and the `last_*` attributes."""

    def test_exc_info_reports_the_exception_being_handled(self) -> None:
        try:
            raise ValueError("boom")
        except ValueError as caught:
            exc_type, exc_value, exc_traceback = sys.exc_info()

            assert exc_type is ValueError
            assert exc_value is caught
            assert exc_traceback is caught.__traceback__

    def test_exc_info_builds_a_fresh_tuple_each_call(self) -> None:
        """O(1), but it is a construction rather than a cached read."""
        try:
            raise ValueError("boom")
        except ValueError:
            first, second = sys.exc_info(), sys.exc_info()

            assert first == second
            assert first is not second

    def test_outside_a_handler_there_is_nothing_to_report(self) -> None:
        assert sys.exc_info() == (None, None, None)

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="sys.exception() is Python 3.11+")
    def test_exception_returns_the_value_without_the_tuple(self) -> None:
        try:
            raise ValueError("boom")
        except ValueError:
            assert sys_attr("exception")() is sys.exc_info()[1]

    def test_exit_raises_rather_than_terminating(self) -> None:
        """Why the row prices the raise and not the shutdown: it is catchable."""
        with pytest.raises(SystemExit) as raised:
            sys.exit(3)

        assert raised.value.code == 3

    @pytest.mark.parametrize("name", ["last_exc", "last_type", "last_value", "last_traceback"])
    def test_the_last_attributes_are_unbound_while_code_runs(self, name: str) -> None:
        """The row's "before that, reading one raises `AttributeError`".

        A batch run raises and handles plenty of exceptions - this suite does
        nothing else - and none of them binds these names, because none of
        them reaches the default `excepthook`.
        """
        assert not hasattr(sys, name)

    def test_the_interpreter_binds_them_before_it_calls_the_hook(self) -> None:
        """Reading the rows as "interactive only" would be wrong: a script
        binds them too, just at the point where it is already stopping.

        A replacement hook is the observation point that also settles *when*:
        it runs while the interpreter reports the exception, and the names are
        already bound by the time it is entered. The companion test below is
        what places the binding on that path rather than on the hook itself.
        """
        result = run_isolated(
            """
            import sys

            def hook(exc_type, exc, traceback):
                latest = sys.last_exc if sys.version_info >= (3, 12) else exc
                print(type(sys.last_value).__name__,
                      sys.last_value is exc,
                      latest is exc,
                      sys.last_type is exc_type,
                      sys.last_traceback is traceback)

            sys.excepthook = hook
            raise ValueError("uncaught")
            """
        )

        assert result.returncode == 1, result.stderr
        assert result.stdout.split() == ["ValueError", "True", "True", "True", "True"]

    def test_calling_the_hook_yourself_binds_nothing(self) -> None:
        """The row's "calling the hook yourself does not bind them", which is
        why the tests above are about where the exception ends up rather than
        about the hook. Several tests in this file call `sys.excepthook`
        directly, and the unbound assertions above hold anyway.
        """
        report = io.StringIO()
        original_stderr = sys.stderr
        sys.stderr = report
        try:
            try:
                raise ValueError("boom")
            except ValueError as caught:
                sys.excepthook(type(caught), caught, caught.__traceback__)
        finally:
            sys.stderr = original_stderr

        assert "ValueError: boom" in report.getvalue()
        for name in ("last_exc", "last_type", "last_value", "last_traceback"):
            assert not hasattr(sys, name), name

    def test_calling_the_hook_yourself_disturbs_nothing_already_bound(self) -> None:
        """The other side of it: the hook neither writes the names nor clears
        them, so a value already there survives the call unchanged.
        """
        result = run_isolated(
            """
            import io
            import sys

            sys.last_value = "value"
            sys.last_type = "type"
            sys.last_traceback = "traceback"
            if sys.version_info >= (3, 12):
                sys.last_exc = "exc"
            report = io.StringIO()
            original = sys.stderr
            sys.stderr = report
            try:
                try:
                    raise ValueError("boom")
                except ValueError as caught:
                    sys.excepthook(type(caught), caught, caught.__traceback__)
            finally:
                sys.stderr = original
            print(sys.last_value, sys.last_type, sys.last_traceback,
                  getattr(sys, "last_exc", "exc"),
                  "ValueError: boom" in report.getvalue())
            """
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.split() == ["value", "type", "traceback", "exc", "True"]


def _raising_chain(depth: int) -> Callable[[], None]:
    """A chain of `depth` distinct code objects ending in a raise.

    Distinct names and distinct code objects: the traceback machinery collapses
    consecutive identical frames into "Previous line repeated", so a chain built
    from one recursive function would print a fixed number of lines whatever
    the depth.
    """
    lines = [f"def level_{index}():\n    return level_{index + 1}()" for index in range(depth)]
    lines.append(f"def level_{depth}():\n    raise ValueError('boom')")
    namespace: dict[str, Any] = {}
    exec("\n".join(lines), namespace)  # noqa: S102 - generated, not caller-supplied
    return namespace["level_0"]


def _printed_frames(depth: int, limit: int | None = None) -> int:
    """`File` lines `sys.excepthook` writes for a chain of the given depth."""
    report = io.StringIO()
    original_stderr = sys.stderr
    had_limit = hasattr(sys, "tracebacklimit")
    previous_limit = getattr(sys, "tracebacklimit", None)
    sys.stderr = report
    if limit is not None:
        sys.tracebacklimit = limit
    try:
        try:
            _raising_chain(depth)()
        except ValueError as caught:
            sys.excepthook(type(caught), caught, caught.__traceback__)
    finally:
        sys.stderr = original_stderr
        if limit is not None:
            if had_limit:
                sys.tracebacklimit = previous_limit
            else:
                del sys.tracebacklimit
    return report.getvalue().count('  File "')


class TestExceptionReporting:
    """`excepthook` | O(d + s) |, `unraisablehook`, and `sys.tracebacklimit`."""

    def test_the_hook_prints_one_entry_per_traceback_frame(self) -> None:
        """The d in the row, counted: three more frames, three more entries."""
        shallow, deep = _printed_frames(3), _printed_frames(6)

        assert deep - shallow == 3, f"3-deep printed {shallow}, 6-deep printed {deep}"

    def test_the_source_line_is_read_for_every_frame_that_has_one(self) -> None:
        """The s in the row: each printed frame carries its source line, which
        the hook has to go to the file for.

        The generated levels are compiled from a string and have no file, so
        they print a `File` line and nothing under it - which is the contrast
        that shows the source is read rather than carried by the traceback.
        """
        report = io.StringIO()
        original_stderr = sys.stderr
        sys.stderr = report
        try:
            try:
                _raising_chain(2)()
            except ValueError as caught:
                sys.excepthook(type(caught), caught, caught.__traceback__)
        finally:
            sys.stderr = original_stderr

        text = report.getvalue()
        assert text.count('  File "') == 4, text
        assert "_raising_chain(2)()" in text, "this frame has a file, so its line is read"
        assert "raise ValueError" not in text, "the generated frames have no file to read"

    def test_a_repeated_frame_prints_three_times_and_then_a_count(self) -> None:
        """Why the row does not say "one line per frame": `tb_printinternal`
        prints a repeated frame up to `TB_RECURSIVE_CUTOFF` times and then a
        count, so the printed lines stop following d while the walk over d
        does not.
        """

        def recurse(remaining: int) -> None:
            if remaining == 0:
                raise ValueError("boom")
            recurse(remaining - 1)

        report = io.StringIO()
        original_stderr = sys.stderr
        sys.stderr = report
        try:
            try:
                recurse(40)
            except ValueError as caught:
                sys.excepthook(type(caught), caught, caught.__traceback__)
        finally:
            sys.stderr = original_stderr

        text = report.getvalue()
        recursed = [line for line in text.splitlines() if "in recurse" in line]

        assert len(recursed) == 4, f"three of the repeat, plus the raising line:\n{text}"
        assert "[Previous line repeated 37 more times]" in text, text

    def test_the_message_is_rendered_into_the_report(self) -> None:
        """The m in the row: a longer `str()` is a longer report, with the
        same traceback and the same source behind it.
        """

        def report_for(message: str) -> str:
            captured = io.StringIO()
            original_stderr = sys.stderr
            sys.stderr = captured
            try:
                try:
                    raise ValueError(message)
                except ValueError as caught:
                    sys.excepthook(type(caught), caught, caught.__traceback__)
            finally:
                sys.stderr = original_stderr
            return captured.getvalue()

        short, long = report_for("x" * 10), report_for("x" * 10_000)

        assert len(long) - len(short) == 9_990, "the message is copied through verbatim"

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="__notes__ are Python 3.11+")
    def test_notes_are_part_of_the_same_term(self) -> None:
        """The m in the row is what the exception renders to, not only its
        `str()`: a note is printed too, with the traceback unchanged.
        """

        def report_for(note: str | None) -> str:
            error: Any = ValueError("boom")  # add_note() is not in typeshed's 3.10
            if note is not None:
                error.add_note(note)
            captured = io.StringIO()
            original_stderr = sys.stderr
            sys.stderr = captured
            try:
                try:
                    raise error
                except ValueError as caught:
                    sys.excepthook(type(caught), caught, caught.__traceback__)
            finally:
                sys.stderr = original_stderr
            return captured.getvalue()

        plain, noted = report_for(None), report_for("y" * 5_000)

        assert len(noted) - len(plain) == 5_001, "the note and its newline"

    def test_tracebacklimit_caps_the_frames(self) -> None:
        """Why the row says the limit caps d rather than changing the walk."""
        assert not hasattr(sys, "tracebacklimit"), "unbound by default, so there is no cap"

        assert _printed_frames(6, limit=2) == 2

    def test_tracebacklimit_caps_the_unraisable_hook_too(self) -> None:
        """The row says "the two rows above", so the second one is checked."""
        report = io.StringIO()
        original_stderr = sys.stderr
        original_hook = sys.unraisablehook  # pytest installs one that captures
        sys.stderr = report
        sys.unraisablehook = sys.__unraisablehook__
        sys.tracebacklimit = 2
        try:

            class Failing:
                def __del__(self) -> None:
                    _raising_chain(5)()

            Failing()
            gc.collect()
        finally:
            del sys.tracebacklimit
            sys.unraisablehook = original_hook
            sys.stderr = original_stderr

        assert report.getvalue().count('  File "') == 2

    def test_the_unraisable_hook_sees_what_cannot_propagate(self) -> None:
        """The row's "an exception that had nowhere to propagate"."""
        caught: list[Any] = []
        original = sys.unraisablehook
        sys.unraisablehook = caught.append
        try:

            class Failing:
                def __del__(self) -> None:
                    raise ValueError("boom")

            Failing()
            gc.collect()
        finally:
            sys.unraisablehook = original

        assert len(caught) == 1
        assert caught[0].exc_type is ValueError

    def test_the_originals_are_kept(self) -> None:
        assert sys.__excepthook__ is not None
        assert sys.__unraisablehook__ is not None


class TestFrames:
    """`sys._getframe(d)` | O(d) | and `sys._current_frames()` | O(t) |."""

    @staticmethod
    def _nest(depth: int, action: Callable[[], Any]) -> Any:
        """Call `action` with exactly `depth` frames of `_nest` beneath it."""
        if depth <= 1:
            return action()
        return TestFrames._nest(depth - 1, action)

    @staticmethod
    def _names_up_to(target: str) -> list[str]:
        """Every frame name from here outwards, stopping at `target`."""
        names: list[str] = []
        level = 0
        while True:
            name = sys._getframe(level).f_code.co_name
            names.append(name)
            if name == target:
                return names
            level += 1

    def test_getframe_walks_one_link_per_level(self) -> None:
        """Observable rather than timed: each level is one more frame.

        `_nest` calls itself, so at depth d the chain between here and this
        test holds exactly d frames of `_nest` - which is what the walk has to
        traverse. Counting them rather than indexing them keeps the assertion
        clear of the comprehension frame 3.11 adds and 3.12 inlines away.
        """
        own_name = "test_getframe_walks_one_link_per_level"

        for depth in (5, 25):
            names = self._nest(depth, lambda: self._names_up_to(own_name))

            assert names.count("_nest") == depth, (
                f"depth {depth} should put {depth} _nest frames on the chain: {names}"
            )
            assert names[-1] == own_name

    def test_asking_past_the_bottom_of_the_stack_raises(self) -> None:
        """The walk counts links, so it can run out of them."""
        with pytest.raises(ValueError, match="call stack is not deep enough"):
            sys._getframe(1_000_000)

    @pytest.mark.skipif(
        sys.version_info < (3, 12), reason="sys._getframemodulename() is Python 3.12+"
    )
    def test_getframemodulename_walks_the_same_chain(self) -> None:
        """The row's "the same walk": each level names one module further out."""
        module_name = sys_attr("_getframemodulename")

        assert module_name(0) == __name__

        def one_level_in() -> Any:
            return module_name(1)

        assert one_level_in() == __name__
        assert module_name(1_000_000) is None, "past the bottom it answers None, not a name"

    @pytest.mark.timing
    def test_getframe_cost_follows_the_depth(self) -> None:
        original = sys.getrecursionlimit()
        sys.setrecursionlimit(20_000)  # the 1,000-deep nest needs headroom
        try:
            shallow = self._nest(100, lambda: per_call(lambda: sys._getframe(100), 20_000))
            deep = self._nest(1_000, lambda: per_call(lambda: sys._getframe(1_000), 20_000))
        finally:
            sys.setrecursionlimit(original)

        assert deep > shallow * 4, (
            f"ten times the depth is ten times the walk: depth 100 {shallow:.2e}s, "
            f"depth 1,000 {deep:.2e}s"
        )

    def test_current_frames_returns_one_entry_per_thread(self) -> None:
        """The O(t) row, observed directly in the size of the result."""
        alone = len(sys._current_frames())

        with ParkedThreads(12):
            crowded = len(sys._current_frames())

        assert crowded == alone + 12, (
            f"expected one frame per live thread: {alone} alone, {crowded} with 12 more"
        )

    def test_current_exceptions_covers_the_same_threads(self) -> None:
        """The row's "a thread handling nothing maps to `None`".

        Reading the dict as "threads with an exception" would make its size a
        property of what the program is doing rather than of the thread count.
        It is not: every live thread has an entry, whether or not it is in a
        handler.
        """
        with ParkedThreads(8):
            frames = sys._current_frames()
            exceptions = sys._current_exceptions()

        assert set(exceptions) == set(frames)
        idle = [value for key, value in exceptions.items() if key != threading.get_ident()]
        empty = None if sys.version_info >= (3, 12) else (None, None, None)
        assert idle and all(value == empty for value in idle)


class TestRecursionLimit:
    """`getrecursionlimit()` | O(1) | and `setrecursionlimit(n)` | O(t) |."""

    @pytest.fixture(autouse=True)
    def _restore_limit(self) -> Iterator[None]:
        original = sys.getrecursionlimit()
        yield
        sys.setrecursionlimit(original)

    def test_the_limit_round_trips(self) -> None:
        sys.setrecursionlimit(2_500)

        assert sys.getrecursionlimit() == 2_500

    def test_a_limit_below_the_current_depth_is_refused(self) -> None:
        with pytest.raises(RecursionError, match="limit is too low"):
            sys.setrecursionlimit(1)

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 11), reason="3.10 sets one interpreter-wide value")
    def test_setting_the_limit_costs_one_pass_over_the_threads(self) -> None:
        """`Py_SetRecursionLimit` loops over thread states.

        On 3.10 this is flat, which is why the test does not run there: the
        loop was introduced with the per-thread limit in 3.11.
        """
        limit = sys.getrecursionlimit()
        alone = per_call(lambda: sys.setrecursionlimit(limit), 20_000)

        with ParkedThreads(300):
            crowded = per_call(lambda: sys.setrecursionlimit(limit), 20_000)

        assert crowded > alone * 3, (
            f"300 more thread states should cost more to write through: "
            f"alone {alone:.2e}s, crowded {crowded:.2e}s"
        )

    @pytest.mark.timing
    @pytest.mark.skipif(
        sys.version_info >= (3, 11), reason="3.11 and later write through to each thread"
    )
    def test_before_3_11_the_limit_was_one_field(self) -> None:
        limit = sys.getrecursionlimit()
        alone = per_call(lambda: sys.setrecursionlimit(limit), 20_000)

        with ParkedThreads(300):
            crowded = per_call(lambda: sys.setrecursionlimit(limit), 20_000)

        assert crowded < alone * 3, (
            f"3.10 writes one interpreter field, so threads should not matter: "
            f"alone {alone:.2e}s, crowded {crowded:.2e}s"
        )

    def test_the_switch_interval_round_trips(self) -> None:
        original = sys.getswitchinterval()
        try:
            sys.setswitchinterval(0.01)
            assert sys.getswitchinterval() == pytest.approx(0.01)
        finally:
            sys.setswitchinterval(original)


class CountingSizeof:
    """An object that records how often its `__sizeof__` is consulted."""

    calls = 0

    @classmethod
    def reset(cls) -> None:
        cls.calls = 0

    def __sizeof__(self) -> int:
        CountingSizeof.calls += 1
        return 42


class TestGetsizeof:
    """`sys.getsizeof(obj)` | O(1) | it asks the object, and asks only it."""

    def test_getsizeof_calls_dunder_sizeof_once(self) -> None:
        CountingSizeof.reset()

        size = sys.getsizeof(CountingSizeof())

        assert CountingSizeof.calls == 1
        assert size >= 42, "the GC header is added to what __sizeof__ returned"

    def test_getsizeof_does_not_look_inside_a_container(self) -> None:
        """The row's "never looks inside a container", counted.

        A hundred members whose `__sizeof__` would announce itself, and not
        one of them is asked.
        """
        CountingSizeof.reset()
        members = [CountingSizeof() for _ in range(100)]

        sys.getsizeof(members)

        assert CountingSizeof.calls == 0, "a recursive size would have called every member"

    def test_container_size_does_not_follow_its_contents(self) -> None:
        small = sys.getsizeof([b"x"])
        large = sys.getsizeof([b"x" * 1_000_000])

        assert small == large, "the list holds pointers, whatever they point at"

    # Built inside the test: a 100,000-digit int cannot be turned into a
    # pytest parameter id without tripping sys.set_int_max_str_digits.
    BUILDERS: dict[str, tuple[Callable[[], Any], Callable[[], Any]]] = {
        "list": (lambda: [0] * 100, lambda: [0] * 1_000_000),
        "dict": (lambda: dict.fromkeys(range(100)), lambda: dict.fromkeys(range(200_000))),
        "set": (lambda: set(range(100)), lambda: set(range(200_000))),
        "str": (lambda: "x" * 100, lambda: "x" * 1_000_000),
        "bytes": (lambda: b"x" * 100, lambda: b"x" * 1_000_000),
        "int": (lambda: 10**100, lambda: 10**100_000),
    }

    @pytest.mark.timing
    @pytest.mark.parametrize("name", sorted(BUILDERS))
    def test_getsizeof_is_constant_for_builtins(self, name: str) -> None:
        """Every builtin computes its size from a stored count."""
        build_small, build_large = self.BUILDERS[name]
        small, large = build_small(), build_large()

        quick = per_call(lambda: sys.getsizeof(small), 100_000)
        slow = per_call(lambda: sys.getsizeof(large), 100_000)

        assert slow < quick * 2, (
            f"{name} grew by a factor of thousands and getsizeof should not notice: "
            f"small {quick:.2e}s, large {slow:.2e}s"
        )

    def test_an_object_without_dunder_sizeof_needs_the_default(self) -> None:
        class Bare:
            __slots__ = ()
            __sizeof__ = None  # type: ignore[assignment]

        with pytest.raises(TypeError):
            sys.getsizeof(Bare())

        assert sys.getsizeof(Bare(), 99) == 99

    def test_getrefcount_reports_a_live_count(self) -> None:
        target: list[int] = []
        before = sys.getrefcount(target)
        alias = target

        assert sys.getrefcount(target) == before + 1
        del alias
        assert sys.getrefcount(target) == before


class TestIntern:
    """`sys.intern(s)` | O(len(s)) | O(1) when already interned."""

    def test_equal_strings_intern_to_one_object(self) -> None:
        first = sys.intern("".join(["inter", "ning", "-probe"]))
        second = sys.intern("".join(["inter", "ning", "-probe"]))

        assert first is second

    def test_interning_an_interned_string_returns_it_unchanged(self) -> None:
        once = sys.intern("x" * 5_000)

        assert sys.intern(once) is once

    def test_only_exact_strings_can_be_interned(self) -> None:
        """A str subclass is refused too, so the row's `len(s)` is the
        length of a real str and says nothing about a subclass.
        """

        class Subclass(str):
            pass

        with pytest.raises(TypeError, match="can't intern"):
            sys.intern(Subclass("text"))

        with pytest.raises(TypeError, match="must be str"):
            sys.intern(b"bytes")  # type: ignore[arg-type]

    @pytest.mark.skipif(
        sys.version_info < (3, 12), reason="sys.getunicodeinternedsize() is Python 3.12+"
    )
    def test_interning_adds_to_the_table(self) -> None:
        """Why the first intern costs O(len): it is a lookup and an insert."""
        interned_size = sys_attr("getunicodeinternedsize")
        before = interned_size()

        kept = sys.intern("".join(["a-string-nothing-else-would-hold", "-1"]))

        assert interned_size() == before + 1
        assert kept == "a-string-nothing-else-would-hold-1"

    @pytest.mark.skipif(
        sys.version_info < (3, 12), reason="sys.getunicodeinternedsize() is Python 3.12+"
    )
    def test_an_interned_string_nobody_keeps_does_not_stay(self) -> None:
        """The row's "the table holds no reference of its own", counted.

        `sys_intern_impl` calls `_PyUnicode_InternMortal`, so discarding the
        result discards the entry with it. Inside the immortal window the same
        call left the string alive and the count rose whether anyone kept it
        or not. This test can only see 3.12 onwards, since
        `getunicodeinternedsize()` does not exist before it - the retention
        test below covers the whole supported range.
        """
        interned_size = sys_attr("getunicodeinternedsize")
        before = interned_size()

        sys.intern("".join(["nothing-holds-this-string", "-2"]))

        if IMMORTAL_INTERNING:
            assert interned_size() == before + 1, "3.12.0 to 3.12.6 interning made it immortal"
        else:
            assert interned_size() == before, "a string nobody references is not kept interned"

    def test_only_the_immortal_window_keeps_an_interned_string_alive(self) -> None:
        """The retention, measured on every supported version.

        `getunicodeinternedsize()` arrived in 3.12, so the count test above
        cannot see 3.10 or 3.11. Traced allocation can: intern a payload,
        drop every reference to it, and see whether the memory comes back.
        """
        payload = 500 * 20_000  # bytes of ASCII, if every string is kept

        def intern_and_discard() -> None:
            """Nothing outlives this call, so its locals cannot hold them."""
            for index in range(500):
                sys.intern(str(index).rjust(20_000, "q"))

        tracemalloc.start()
        try:
            base, _ = tracemalloc.get_traced_memory()
            intern_and_discard()
            gc.collect()
            current, _ = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        retained = current - base
        if IMMORTAL_INTERNING:
            assert retained > payload * 0.5, (
                f"interning is immortal here, so the payload should still be held: "
                f"retained {retained:,} of {payload:,} bytes"
            )
        else:
            assert retained < payload * 0.1, (
                f"interned strings are freed with their last reference: "
                f"retained {retained:,} of {payload:,} bytes"
            )

    @pytest.mark.timing
    def test_the_first_intern_follows_the_string_length(self) -> None:
        """Run out of process: inside the immortal window an interned string
        is never freed, and this test interns about 200 MB of them, which
        would stay resident for the rest of the suite. The subprocess times both lengths and prints
        one figure per line; the assertion is unchanged.
        """
        result = run_isolated(
            """
            import sys
            import timeit

            def fresh(length, count=2_000):
                strings = [str(index).rjust(length, "q") for index in range(count)]
                start = timeit.default_timer()
                for text in strings:
                    sys.intern(text)
                return (timeit.default_timer() - start) / count

            print(min(fresh(1_000) for _ in range(3)))
            print(min(fresh(100_000) for _ in range(3)))
            """
        )

        assert result.returncode == 0, result.stderr
        short, long = (float(line) for line in result.stdout.split())

        assert long > short * 10, (
            f"a hundred times the characters is hashed and compared: "
            f"1,000 chars {short:.2e}s, 100,000 chars {long:.2e}s"
        )

    @pytest.mark.timing
    def test_re_interning_does_not_follow_the_length(self) -> None:
        short, long = sys.intern("q" * 1_000), sys.intern("q" * 100_000)

        short_time = per_call(lambda: sys.intern(short), 100_000)
        long_time = per_call(lambda: sys.intern(long), 100_000)

        assert long_time < short_time * 2, (
            f"an already-interned string is recognised without being read: "
            f"1,000 chars {short_time:.2e}s, 100,000 chars {long_time:.2e}s"
        )

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="sys._is_interned() is 3.13+")
    def test_is_interned_answers_from_the_object(self) -> None:
        is_interned = sys_attr("_is_interned")
        fresh = "".join(["never", "-interned", "-probe"])

        assert is_interned(fresh) is False
        assert is_interned(sys.intern(fresh)) is True

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 13), reason="sys._is_interned() is 3.13+")
    def test_is_interned_does_not_read_the_string(self) -> None:
        """The row's "does not pay the row above": a flag, not a table search."""
        is_interned = sys_attr("_is_interned")
        short, long = "q" * 1_000 + "-a", "q" * 100_000 + "-b"

        short_time = per_call(lambda: is_interned(short), 200_000)
        long_time = per_call(lambda: is_interned(long), 200_000)

        assert long_time < short_time * 2, (
            f"a hundred times the characters should not be read: "
            f"1,000 chars {short_time:.2e}s, 100,000 chars {long_time:.2e}s"
        )


class TestMemoryAccounting:
    """`getallocatedblocks()`, the cache clears, and the int digit limit."""

    def test_allocated_blocks_follows_what_is_alive(self) -> None:
        """The row prices the sum, not the counting: the counter is kept as
        objects are allocated, so the call only reads it.
        """
        before = sys.getallocatedblocks()
        held = [object() for _ in range(200_000)]
        during = sys.getallocatedblocks()
        del held
        gc.collect()
        after = sys.getallocatedblocks()

        assert during - before > 100_000
        assert after < during

    def test_clearing_the_type_cache_keeps_lookups_working(self) -> None:
        """The clear walks a fixed-size table, so there is no size to vary -
        what is checked is that it is a cache drop and not a semantic change.
        """

        class Example:
            def method(self) -> int:
                return 7

        instance = Example()
        assert instance.method() == 7

        with pytest.deprecated_call() if sys.version_info >= (3, 14) else _no_warning():
            sys._clear_type_cache()

        assert instance.method() == 7

    @pytest.mark.skipif(
        sys.version_info < (3, 13), reason="sys._clear_internal_caches() is Python 3.13+"
    )
    def test_the_general_clear_is_not_deprecated(self) -> None:
        """The 3.14 row: the warning is on the narrow call, not the wide one."""
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            sys_attr("_clear_internal_caches")()

    def test_the_digit_limit_round_trips_and_is_enforced(self) -> None:
        """The row's "what it caps is the quadratic work in int(str)"."""
        original = sys.get_int_max_str_digits()
        try:
            sys.set_int_max_str_digits(640)
            assert sys.get_int_max_str_digits() == 640

            with pytest.raises(ValueError, match="for integer string conversion"):
                str(10**700)

            assert len(str(10**600)) == 601, "under the limit, the conversion still happens"
        finally:
            sys.set_int_max_str_digits(original)

    def test_debug_malloc_stats_writes_to_stderr(self) -> None:
        """Exercised out of process: it writes straight to the C-level stderr,
        which a replaced `sys.stderr` does not capture.
        """
        result = run_isolated("import sys; sys._debugmallocstats()")

        assert result.returncode == 0, result.stderr
        assert result.stderr.strip(), "nothing was written"


def _no_warning() -> Any:
    """A stand-in context manager for versions that do not warn."""
    import warnings

    return warnings.catch_warnings()


class TestAuditHooks:
    """`sys.audit(event, *args)` | O(h) | every hook is called."""

    def test_every_installed_hook_sees_every_event(self) -> None:
        """Run out of process: an audit hook cannot be uninstalled."""
        result = run_isolated(
            """
            import sys

            fired = []
            for index in range(8):
                sys.addaudithook(lambda event, args, i=index: fired.append((i, event)))

            sys.audit("probe.one")
            sys.audit("probe.two")
            print(sorted(i for i, event in fired if event == "probe.one"))
            print(len([1 for _, event in fired if event.startswith("probe.")]))
            """
        )

        assert result.returncode == 0, result.stderr
        hooks, total = result.stdout.strip().splitlines()
        assert hooks == str(list(range(8))), "each of the eight hooks should see the event"
        assert total == "16", "eight hooks times two events"

    def test_hooks_run_in_the_order_they_were_added(self) -> None:
        """The row says "in the order they were added", which is what decides
        which hook sees an event first when one of them raises.
        """
        result = run_isolated(
            """
            import sys

            order = []
            for index in range(4):
                sys.addaudithook(lambda event, args, i=index: order.append(i))
            sys.audit("probe.order")
            print(order[-4:])
            """
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "[0, 1, 2, 3]"

    def test_adding_a_hook_runs_the_hooks_already_installed(self) -> None:
        """Why the `addaudithook` row is O(h) and not an amortized append: the
        call raises the `sys.addaudithook` event before it appends.
        """
        result = run_isolated(
            """
            import sys

            seen = []
            for index in range(5):
                sys.addaudithook(lambda event, args, i=index: seen.append((i, event)))

            before = len(seen)
            sys.addaudithook(lambda event, args: None)
            print(len(seen) - before, sorted({event for _, event in seen[before:]}))
            """
        )

        assert result.returncode == 0, result.stderr
        count, events = result.stdout.strip().split(" ", 1)
        assert count == "5", "all five hooks already installed should have run"
        assert events == "['sys.addaudithook']"

    def test_dispatch_stops_at_the_first_hook_that_raises(self) -> None:
        """The row's "until one of them raises". Reading it as "every hook is
        called" would make a hook that vetoes an event look like a no-op.
        """
        result = run_isolated(
            """
            import sys

            ran = []

            def first(event, args):
                if event == "probe":
                    ran.append("first")
                    raise RuntimeError("vetoed")

            def second(event, args):
                if event == "probe":
                    ran.append("second")

            sys.addaudithook(first)
            sys.addaudithook(second)
            try:
                sys.audit("probe")
            except RuntimeError as error:
                print(error)
            print(ran)
            """
        )

        assert result.returncode == 0, result.stderr
        raised, ran = result.stdout.strip().splitlines()
        assert raised == "vetoed", "the hook's exception reaches the caller"
        assert ran == "['first']", "the hook behind it never ran"

    def test_hooks_cannot_be_removed(self) -> None:
        assert not hasattr(sys, "removeaudithook")


class TestTracing:
    """`settrace(fn)` | O(f + C) | to install from 3.12; then one call per event."""

    def test_installing_and_reading_back_the_tracer(self) -> None:
        original = sys.gettrace()

        def tracer(frame: FrameType, event: str, arg: Any) -> Any:
            return None

        try:
            sys.settrace(tracer)
            assert sys.gettrace() is tracer
        finally:
            sys.settrace(original)

        assert sys.gettrace() is original

    def test_the_profiler_slot_is_separate_from_the_tracer(self) -> None:
        original = sys.getprofile()

        def profiler(frame: FrameType, event: str, arg: Any) -> Any:
            return None

        try:
            sys.setprofile(profiler)
            assert sys.getprofile() is profiler
            assert sys.gettrace() is not profiler
        finally:
            sys.setprofile(original)

    def test_the_tracer_is_called_once_per_line(self) -> None:
        """Why what installing costs is not the cost that matters: the
        events are per line, so the dispatch count follows the work done
        under the tracer and not the frame it was installed from.

        Counted rather than timed, and the two loop sizes differ by a factor
        of ten in traced lines, which is what a per-event dispatch means.
        """

        def count_line_events(iterations: int) -> int:
            events = 0

            def tracer(frame: FrameType, event: str, arg: Any) -> Any:
                nonlocal events
                if event == "line":
                    events += 1
                return tracer

            def work() -> int:
                total = 0
                for index in range(iterations):
                    total += index
                return total

            original = sys.gettrace()
            try:
                sys.settrace(tracer)
                work()
            finally:
                sys.settrace(original)
            return events

        few, many = count_line_events(10), count_line_events(100)

        assert many > few * 5, (
            f"a tracer pays per line executed, not per call: 10 iterations {few} events, "
            f"100 iterations {many}"
        )

    INSTALL_COST = """
        import sys
        import timeit

        def tracer(frame, event, arg):
            return None

        def toggle():
            sys.settrace(tracer)
            sys.settrace(None)

        def cost(count):
            lines = ['def frame(measure):', '    total = 0']
            lines += ['    total += %d' % index for index in range(count)]
            lines.append('    return measure()')
            namespace = {}
            exec(compile('\\n'.join(lines), '<generated>', 'exec'), namespace)
            measured = min(
                namespace['frame'](lambda: timeit.timeit(toggle, number=100))
                for _ in range(5)
            ) / 100
            return len(namespace['frame'].__code__.co_code), measured

        short_code, quick = cost(5)
        long_code, slow = cost(5_000)
        print(short_code, long_code)
        print(quick)
        print(slow)
        """

    def _install_cost(self) -> tuple[int, int, float, float]:
        """Bytecode and seconds for installing a tracer under a small frame
        and under a large one. Run out of process: the measurement leaves the
        frames it built instrumented.
        """
        result = run_isolated(self.INSTALL_COST)

        assert result.returncode == 0, result.stderr
        sizes, small, large = result.stdout.strip().splitlines()
        short_code, long_code = (int(value) for value in sizes.split())
        assert long_code > short_code * 100, f"the two frames are {short_code}, {long_code}"
        return short_code, long_code, float(small), float(large)

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 12), reason="3.10 and 3.11 just store a function")
    def test_installing_a_tracer_instruments_the_stack_from_3_12(self) -> None:
        """The corrected row. `_PyEval_SetTrace` in Python/legacy_tracing.c
        calls `set_monitoring_trace_events`, which instruments the code
        objects on every thread's stack - so what installing costs follows
        the frame you install from, not the tracer.
        """
        short_code, long_code, quick, slow = self._install_cost()

        assert slow > quick * 10, (
            f"installing under a large frame should cost more: {short_code} bytes "
            f"{quick:.2e}s, {long_code} bytes {slow:.2e}s"
        )

    @pytest.mark.timing
    @pytest.mark.skipif(
        sys.version_info >= (3, 12), reason="3.12 moved settrace onto sys.monitoring"
    )
    def test_before_3_12_installing_a_tracer_was_one_field(self) -> None:
        short_code, long_code, quick, slow = self._install_cost()

        assert slow < quick * 3, (
            f"3.10 and 3.11 store one function, so the stack should not matter: "
            f"{short_code} bytes {quick:.2e}s, {long_code} bytes {slow:.2e}s"
        )

    def test_call_tracing_re_enters_tracing_from_inside_the_tracer(self) -> None:
        """The row's "so a trace function can re-enter itself", and its one
        exception.

        Tracing is suspended while a trace function runs, so a plain call made
        from inside one is not traced. The control below is that plain call:
        it produces no events, and the `call_tracing()` call beside it does -
        on 3.10, 3.12, 3.13 and 3.14. The whole 3.11 line, 3.11.0 to 3.11.16,
        leaves it untraced, so the two ends of the supported range agree with
        each other and not with the middle.
        """
        plain: list[str] = []
        through_call_tracing: list[str] = []
        after: list[str] = []
        target: list[str] = plain

        def watched() -> int:
            return 1 + 1

        def tracer(frame: FrameType, event: str, arg: Any) -> Any:
            if frame.f_code is watched.__code__:
                target.append(event)
            return tracer

        def driver() -> None:
            pass

        def outer_tracer(frame: FrameType, event: str, arg: Any) -> Any:
            if frame.f_code is driver.__code__ and event == "call":
                nonlocal target
                target = plain
                watched()
                target = through_call_tracing
                sys.call_tracing(watched, ())
                target = after
                watched()  # suspension must be back, without anyone restoring it
            return tracer(frame, event, arg)

        original = sys.gettrace()
        try:
            sys.settrace(outer_tracer)
            driver()
        finally:
            sys.settrace(original)

        assert plain == [], "a plain call from inside a tracer is not traced"
        assert after == [], "and it is still not traced once call_tracing has returned"
        if sys.version_info[:2] == (3, 11):
            assert through_call_tracing == [], (
                f"3.11 runs it untraced, which is what the row's exception says: "
                f"{through_call_tracing}"
            )
        else:
            assert "call" in through_call_tracing, (
                f"call_tracing should have re-enabled tracing: {through_call_tracing}"
            )
        assert sys.gettrace() is original

    @pytest.mark.skipif(
        sys.version_info < (3, 12), reason="the stack trampoline calls are Python 3.12+"
    )
    @pytest.mark.skipif(not sys.platform.startswith("linux"), reason="perf backend is Linux-only")
    def test_the_stack_trampoline_is_a_flag(self) -> None:
        """Run out of process: activating it writes a perf map for the process."""
        result = run_isolated(
            """
            import sys

            print(sys.is_stack_trampoline_active())
            sys.activate_stack_trampoline("perf")
            print(sys.is_stack_trampoline_active())
            sys.deactivate_stack_trampoline()
            print(sys.is_stack_trampoline_active())
            try:
                sys.activate_stack_trampoline("nonesuch")
            except ValueError:
                print("rejected")
            """
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.split() == ["False", "True", "False", "rejected"]


@pytest.mark.skipif(sys.version_info < (3, 12), reason="sys.monitoring is Python 3.12+")
class TestMonitoring:
    """`sys.monitoring` | O(c) | the cost is the bytecode it instruments."""

    def test_a_tool_id_is_claimed_and_released(self) -> None:
        result = run_isolated(
            """
            import sys

            monitoring = sys.monitoring
            monitoring.use_tool_id(2, "probe")
            print(monitoring.get_tool(2))
            try:
                monitoring.use_tool_id(2, "other")
            except ValueError:
                print("taken")
            monitoring.free_tool_id(2)
            print(monitoring.get_tool(2))
            """
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.split() == ["probe", "taken", "None"]

    def test_local_events_reach_only_the_code_object_named(self) -> None:
        """Why `set_local_events` is O(c) for one c and `set_events` is not:
        it instruments the code object it is handed and nothing else.
        """
        result = run_isolated(
            """
            import sys

            monitoring = sys.monitoring
            monitoring.use_tool_id(2, "probe")
            seen = []
            monitoring.register_callback(
                2, monitoring.events.LINE, lambda code, lineno: seen.append(code.co_name)
            )

            def watched():
                return 1 + 1

            def unwatched():
                return 2 + 2

            monitoring.set_local_events(2, watched.__code__, monitoring.events.LINE)
            watched()
            unwatched()
            monitoring.set_local_events(2, watched.__code__, 0)
            monitoring.free_tool_id(2)
            print(sorted(set(seen)))
            """
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "['watched']"

    def test_freeing_a_tool_id_clears_its_events_only_from_3_14(self) -> None:
        """The `free_tool_id` row's version split. Reading the 3.14 behaviour
        back onto 3.12 would tell a caller its callbacks had stopped when
        instrumented code is still calling them.
        """
        result = run_isolated(
            """
            import sys

            monitoring = sys.monitoring
            monitoring.use_tool_id(2, "probe")
            seen = []
            monitoring.register_callback(
                2, monitoring.events.LINE, lambda code, lineno: seen.append(lineno)
            )

            def work():
                total = 0
                return total

            monitoring.set_local_events(2, work.__code__, monitoring.events.LINE)
            work()
            before = len(seen)
            monitoring.free_tool_id(2)
            work()
            print(before, len(seen) - before)
            """
        )

        assert result.returncode == 0, result.stderr
        before, after = (int(value) for value in result.stdout.split())
        assert before > 0, "the callback fired while the tool held the id"
        if sys.version_info >= (3, 14):
            assert after == 0, "3.14 clears the events with the id"
        else:
            assert after == before, "3.12 and 3.13 release the name and nothing else"

    def test_clear_tool_id_arrived_in_3_14(self) -> None:
        """The row's qualifier, which the name's absence is the evidence for."""
        monitoring = sys_attr("monitoring")

        assert hasattr(monitoring, "clear_tool_id") == (sys.version_info >= (3, 14))

    def test_a_callback_replaces_the_one_before_it(self) -> None:
        """The `register_callback` row's "hands back the previous callback"."""
        result = run_isolated(
            """
            import sys

            monitoring = sys.monitoring
            monitoring.use_tool_id(2, "probe")

            def first(code, lineno):
                return monitoring.DISABLE

            def second(code, lineno):
                return monitoring.DISABLE

            print(monitoring.register_callback(2, monitoring.events.LINE, first))
            print(monitoring.register_callback(2, monitoring.events.LINE, second) is first)
            print(monitoring.register_callback(2, monitoring.events.LINE, None) is second)
            print(monitoring.register_callback(2, monitoring.events.LINE, None))
            monitoring.free_tool_id(2)
            """
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.split() == ["None", "True", "True", "None"], (
            "the slot starts empty, hands back each callback it replaces, and "
            "empties again when the replacement is None"
        )

    def test_restart_events_turns_a_disabled_location_back_on(self) -> None:
        """The `restart_events` row's behaviour: a callback that returns
        `DISABLE` stops its location firing, and this is the state
        `restart_events` undoes.

        The row's O(f + C) is not what this establishes. That comes from
        `instrument_all_executing_code_objects`, which `restart_events` reaches
        the same way `set_events` does - source, not a measurement here.
        """
        result = run_isolated(
            """
            import sys

            monitoring = sys.monitoring
            monitoring.use_tool_id(2, "probe")
            seen = []

            def once(code, lineno):
                seen.append(lineno)
                return monitoring.DISABLE

            monitoring.register_callback(2, monitoring.events.LINE, once)

            def work():
                total = 0
                return total

            monitoring.set_local_events(2, work.__code__, monitoring.events.LINE)
            work()
            first = len(seen)
            work()
            while_disabled = len(seen) - first
            monitoring.restart_events()
            work()
            after_restart = len(seen) - first - while_disabled
            monitoring.free_tool_id(2)
            print(first, while_disabled, after_restart)
            """
        )

        assert result.returncode == 0, result.stderr
        first, while_disabled, after_restart = (int(v) for v in result.stdout.split())
        assert first > 0
        assert while_disabled == 0, "DISABLE turned the locations off"
        assert after_restart == first, "and restart_events turned them back on"

    @pytest.mark.skipif(
        sys.version_info < (3, 14), reason="sys.monitoring.clear_tool_id() is Python 3.14+"
    )
    def test_clearing_a_tool_id_keeps_the_slot(self) -> None:
        """The `clear_tool_id` row's "keeping the slot", against `free_tool_id`
        beside it, which gives the name back.
        """
        result = run_isolated(
            """
            import sys

            monitoring = sys.monitoring
            monitoring.use_tool_id(2, "probe")
            seen = []
            monitoring.register_callback(
                2, monitoring.events.LINE, lambda code, lineno: seen.append(lineno)
            )

            def work():
                total = 0
                return total

            monitoring.set_local_events(2, work.__code__, monitoring.events.LINE)
            monitoring.set_events(2, monitoring.events.PY_START)
            assert monitoring.get_events(2) != 0
            work()
            before = len(seen)
            monitoring.clear_tool_id(2)
            work()
            print(before, len(seen) - before, monitoring.get_tool(2))
            print(monitoring.get_events(2),
                  monitoring.get_local_events(2, work.__code__),
                  monitoring.register_callback(2, monitoring.events.LINE, None))
            monitoring.free_tool_id(2)
            print(monitoring.get_tool(2))
            """
        )

        assert result.returncode == 0, result.stderr
        counts, state, released = result.stdout.strip().splitlines()
        before, after, name = counts.split()
        assert int(before) > 0
        assert after == "0", "the callbacks and events went with the clear"
        assert name == "probe", "but the slot kept its name"
        assert state == "0 0 None", (
            f"both event masks empty and no callback left to hand back: {state}"
        )
        assert released == "None", "and free_tool_id then gives the name back"

    @pytest.mark.timing
    def test_instrumenting_one_code_object_follows_its_bytecode(self) -> None:
        """The O(c) row. Two code objects three orders of magnitude apart in
        bytecode, instrumented and cleared the same number of times.
        """
        result = run_isolated(
            """
            import sys
            import timeit

            monitoring = sys.monitoring
            monitoring.use_tool_id(2, "probe")
            monitoring.register_callback(
                2, monitoring.events.LINE, lambda code, lineno: monitoring.DISABLE
            )

            def cost(code):
                def toggle():
                    monitoring.set_local_events(2, code, monitoring.events.LINE)
                    monitoring.set_local_events(2, code, 0)

                return min(timeit.repeat(toggle, number=200, repeat=5)) / 200

            def build(count):
                lines = ['def target():', '    total = 0']
                lines += ['    total += %d' % index for index in range(count)]
                lines.append('    return total')
                namespace = {}
                exec(compile('\\n'.join(lines), '<generated>', 'exec'), namespace)
                return namespace['target'].__code__

            small, large = build(5), build(5_000)
            print(len(small.co_code), len(large.co_code))
            print(cost(small))
            print(cost(large))
            """
        )

        assert result.returncode == 0, result.stderr
        sizes, small, large = result.stdout.strip().splitlines()
        short_code, long_code = (int(value) for value in sizes.split())
        quick, slow = float(small), float(large)

        assert long_code > short_code * 100, f"the two code objects are {short_code}, {long_code}"
        assert slow > quick * 50, (
            f"instrumenting follows the bytecode: {short_code} bytes {quick:.2e}s, "
            f"{long_code} bytes {slow:.2e}s"
        )

    @pytest.mark.timing
    def test_global_events_instrument_what_is_on_the_stack(self) -> None:
        """The O(f + c) row: the same two code objects, this time executing
        while `set_events` runs, so the walk finds them on the stack.
        """
        result = run_isolated(
            """
            import sys
            import timeit

            monitoring = sys.monitoring
            monitoring.use_tool_id(2, "probe")
            monitoring.register_callback(
                2, monitoring.events.LINE, lambda code, lineno: monitoring.DISABLE
            )

            def toggle():
                monitoring.set_events(2, monitoring.events.LINE)
                monitoring.set_events(2, 0)

            def cost(count):
                lines = ['def frame(measure):', '    total = 0']
                lines += ['    total += %d' % index for index in range(count)]
                lines.append('    return measure()')
                namespace = {}
                exec(compile('\\n'.join(lines), '<generated>', 'exec'), namespace)
                measured = min(
                    namespace['frame'](lambda: timeit.timeit(toggle, number=100))
                    for _ in range(5)
                ) / 100
                return len(namespace['frame'].__code__.co_code), measured

            short_code, quick = cost(5)
            long_code, slow = cost(5_000)
            print(short_code, long_code)
            print(quick)
            print(slow)
            """
        )

        assert result.returncode == 0, result.stderr
        sizes, small, large = result.stdout.strip().splitlines()
        short_code, long_code = (int(value) for value in sizes.split())
        quick, slow = float(small), float(large)

        assert long_code > short_code * 100, f"the two frames are {short_code}, {long_code}"
        assert slow > quick * 10, (
            f"the frame on the stack is what gets instrumented: {short_code} bytes "
            f"{quick:.2e}s, {long_code} bytes {slow:.2e}s"
        )


class TestModulesAndPath:
    """The rows for `sys.modules` and `sys.path` are the rows for dict and list."""

    def test_modules_is_a_plain_dict(self) -> None:
        """What makes the lookup row true, rather than a claim of its own."""
        assert type(sys.modules) is dict
        assert sys.modules["sys"] is sys

    def test_path_is_a_plain_list(self) -> None:
        assert type(sys.path) is list

    def test_iterating_modules_visits_every_entry(self) -> None:
        assert len(list(sys.modules)) == len(sys.modules)

    def test_slice_assignment_prepends_without_replacing_the_list(self) -> None:
        """The page's fix for the repeated-insert loop, on a stand-in list."""
        path = ["/existing", "/entries"]
        identity = id(path)
        additions = ["/one", "/two", "/three"]

        path[:0] = additions

        assert id(path) == identity, "the interpreter keeps using the list it was given"
        assert path == ["/one", "/two", "/three", "/existing", "/entries"]

    @pytest.mark.timing
    def test_repeated_front_inserts_cost_more_than_one_splice(self) -> None:
        """k inserts shift e entries each, however they are ordered."""
        entries, additions = 4_000, 400
        base = [f"/entry/{index}" for index in range(entries)]
        extra = [f"/new/{index}" for index in range(additions)]

        def one_at_a_time() -> None:
            path = base.copy()
            for entry in reversed(extra):
                path.insert(0, entry)

        def one_splice() -> None:
            path = base.copy()
            path[:0] = extra

        looped = per_call(one_at_a_time, 200)
        spliced = per_call(one_splice, 200)

        assert looped > spliced * 5, (
            f"k inserts shift e entries each, however they are ordered: "
            f"loop {looped:.2e}s, splice {spliced:.2e}s"
        )

    @pytest.mark.timing
    def test_the_insert_loop_grows_with_the_square_of_the_additions(self) -> None:
        """The page's O(k*e + k**2). Holding e small and doubling k isolates
        the second term: a plain O(k*e) would double, and this does not.
        """
        base = ["/entry"] * 8

        def prepend(count: int) -> Callable[[], None]:
            extra = [f"/new/{index}" for index in range(count)]

            def run() -> None:
                path = base.copy()
                for entry in extra:
                    path.insert(0, entry)

            return run

        small = per_call(prepend(2_000), 20)
        large = per_call(prepend(4_000), 20)

        assert large > small * 3, (
            f"twice the additions into a short list is four times the shifting: "
            f"k=2,000 {small:.2e}s, k=4,000 {large:.2e}s"
        )

    def test_a_miss_calls_every_meta_path_finder(self) -> None:
        """The row's "one `find_spec()` per finder"."""
        import importlib

        class Counting:
            def __init__(self) -> None:
                self.calls = 0

            def find_spec(self, name: str, path: Any, target: Any = None) -> None:
                self.calls += 1
                return None

        finders = [Counting() for _ in range(4)]
        sys.meta_path[:0] = finders
        try:
            with pytest.raises(ImportError):
                importlib.import_module("no_such_module_for_the_sys_page")
        finally:
            del sys.meta_path[: len(finders)]

        assert [finder.calls for finder in finders] == [1, 1, 1, 1]

    def test_the_path_hook_scan_is_paid_once_per_entry(self, tmp_path: pathlib.Path) -> None:
        """What `sys.path_importer_cache` buys: three misses, one scan."""
        import importlib

        entry = str(tmp_path)
        seen: list[str] = []

        def hook(path: str) -> Any:
            seen.append(path)
            raise ImportError("not this hook")

        sys.path.append(entry)
        sys.path_hooks.insert(0, hook)
        try:
            for name in ("no_such_aaa", "no_such_bbb", "no_such_ccc"):
                with pytest.raises(ImportError):
                    importlib.import_module(name)
            cached = sys.path_importer_cache.get(entry)
        finally:
            sys.path_hooks.remove(hook)
            sys.path.remove(entry)
            sys.path_importer_cache.pop(entry, None)

        assert seen.count(entry) == 1, f"the hook saw the entry {seen.count(entry)} times"
        assert cached is not None, "a later hook handled the entry after this one declined"

    def test_the_two_module_name_collections_are_different_types(self) -> None:
        assert type(sys.builtin_module_names) is tuple
        assert type(sys.stdlib_module_names) is frozenset
        assert "sys" in sys.builtin_module_names
        assert "json" in sys.stdlib_module_names

    @pytest.mark.timing
    def test_the_tuple_is_scanned_and_the_frozenset_is_not(self) -> None:
        """The O(b) note on `sys.builtin_module_names`, against the frozenset
        beside it. The worst case for the scan is the last entry, which is the
        one the tuple has to walk to.
        """
        names = sys.builtin_module_names
        target = names[-1]

        scanned = per_call(lambda: target in names, 100_000)
        hashed = per_call(lambda: target in sys.stdlib_module_names, 100_000)

        assert scanned > hashed * 5, (
            f"{len(names)} entries scanned {scanned:.2e}s against a frozenset {hashed:.2e}s"
        )


class TestStreamsAndHooks:
    """The stream rows, `displayhook`, and what steers `breakpointhook`."""

    def test_the_originals_are_kept_alongside_the_current_streams(self) -> None:
        assert sys.__stdout__ is not None
        assert sys.__stderr__ is not None

    def test_displayhook_output_follows_the_repr(self) -> None:
        """The O(r) row, observed rather than timed: what it writes is the
        repr, so the characters written are the characters of the repr.
        """
        import builtins

        def shown(value: Any) -> str:
            buffer = io.StringIO()
            original = sys.stdout
            sys.stdout = buffer
            try:
                sys.displayhook(value)
            finally:
                sys.stdout = original
            return buffer.getvalue()

        small, large = list(range(10)), list(range(1_000))

        assert shown(small) == repr(small) + "\n"
        assert shown(large) == repr(large) + "\n"
        assert builtins._ == large  # type: ignore[attr-defined]

    def test_displayhook_pays_whatever_repr_charges(self) -> None:
        """The row's "producing it costs whatever the object charges": one
        character of output can be any amount of work, so r bounds the write
        and not the `__repr__`.
        """
        work = 0

        class Expensive:
            def __repr__(self) -> str:
                nonlocal work
                work += 1
                return "".join("x" for _ in range(100_000))[:1]

        buffer = io.StringIO()
        original = sys.stdout
        sys.stdout = buffer
        try:
            sys.displayhook(Expensive())
        finally:
            sys.stdout = original

        assert buffer.getvalue() == "x\n", "one character reached the stream"
        assert work == 1, "and the object was asked exactly once to produce it"

    def test_displayhook_returns_early_for_none(self) -> None:
        """The row's `None` clause. It is an early return, not a short repr:
        `repr(None)` is four characters, and none of them are written, and
        `builtins._` keeps whatever it already held.
        """
        import builtins

        # typeshed does not carry `builtins._`, which only the prompt binds
        namespace: Any = builtins
        had = hasattr(builtins, "_")
        previous = getattr(builtins, "_", None)
        buffer = io.StringIO()
        original = sys.stdout
        namespace._ = "kept"
        sys.stdout = buffer
        try:
            sys.displayhook(None)
            written, still = buffer.getvalue(), namespace._
        finally:
            sys.stdout = original
            if had:
                namespace._ = previous
            else:
                del namespace._

        assert written == ""
        assert still == "kept"

    def test_displayhook_does_not_invent_an_underscore_for_none(self) -> None:
        """The other half of the `None` clause: with nothing bound, the early
        return leaves nothing bound, rather than binding `None`.
        """
        result = run_isolated(
            """
            import builtins
            import sys

            assert not hasattr(builtins, "_")
            sys.displayhook(None)
            print(hasattr(builtins, "_"))
            sys.displayhook(7)
            print(builtins._)
            """
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.split() == ["False", "7", "7"]

    def test_pythonbreakpoint_names_what_the_hook_runs(self, tmp_path: pathlib.Path) -> None:
        """The row's "`PYTHONBREAKPOINT` names what runs instead": any
        importable callable, reached with the arguments `breakpoint()` was
        given, and `pdb` never imported.
        """
        (tmp_path / "page_probe.py").write_text(
            "def land(*args, **kwargs):\n    print('landed', args, sorted(kwargs.items()))\n",
            encoding="utf-8",
        )
        result = run_isolated(
            """
            import sys

            breakpoint(1, 2, where="here")
            print("pdb" in sys.modules)
            """,
            env={"PYTHONBREAKPOINT": "page_probe.land", "PYTHONPATH": str(tmp_path)},
        )

        assert result.returncode == 0, result.stderr
        landed, imported = result.stdout.strip().splitlines()
        assert landed == "landed (1, 2) [('where', 'here')]", (
            "the arguments reach the named callable unchanged"
        )
        assert imported == "False", "the default would have imported pdb"

    def test_pythonbreakpoint_zero_turns_the_hook_off(self) -> None:
        result = run_isolated(
            """
            import sys

            breakpoint()
            print("pdb" in sys.modules)
            """,
            env={"PYTHONBREAKPOINT": "0"},
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "False"

    @pytest.mark.parametrize("name", ["ps1", "ps2", "last_exc", "last_value"])
    def test_the_interactive_only_names_are_absent_in_a_script(self, name: str) -> None:
        assert not hasattr(sys, name)


class TestAsyncHooks:
    """`set_asyncgen_hooks()` and the coroutine origin depth."""

    @staticmethod
    def _step(awaitable: Any) -> Any:
        try:
            awaitable.send(None)
        except StopIteration as stop:
            return stop.value
        raise AssertionError("the step did not finish")

    def test_firstiter_runs_once_per_generator(self) -> None:
        """The row's "once per asynchronous generator, not once per step"."""
        started: list[Any] = []
        original = sys.get_asyncgen_hooks()
        sys.set_asyncgen_hooks(firstiter=started.append)
        try:

            async def numbers() -> AsyncIterator[int]:
                yield 1
                yield 2
                yield 3

            generator = numbers()
            values = [self._step(generator.__anext__()) for _ in range(3)]
        finally:
            sys.set_asyncgen_hooks(*original)

        assert values == [1, 2, 3]
        assert len(started) == 1, f"one generator, three steps, {len(started)} hook calls"

    def test_the_hooks_belong_to_one_thread(self) -> None:
        """The row's "per thread": a hook set in one thread is not the other's."""
        seen: list[Any] = []

        def in_thread() -> None:
            sys.set_asyncgen_hooks(firstiter=lambda generator: None)
            seen.append(sys.get_asyncgen_hooks().firstiter)

        original = sys.get_asyncgen_hooks()
        worker = threading.Thread(target=in_thread)
        worker.start()
        worker.join()

        assert seen[0] is not None, "the worker installed its own hook"
        assert sys.get_asyncgen_hooks() == original, "and it did not reach this thread"

    def test_the_hooks_round_trip(self) -> None:
        original = sys.get_asyncgen_hooks()
        try:
            sys.set_asyncgen_hooks(None, None)
            assert sys.get_asyncgen_hooks() == (None, None)
        finally:
            sys.set_asyncgen_hooks(*original)

    def test_origin_tracking_walks_at_most_the_depth_asked_for(self) -> None:
        """The row's "every coroutine created walks up to `depth` frames"."""
        original = sys.get_coroutine_origin_tracking_depth()
        try:

            async def work() -> None:
                pass

            sys.set_coroutine_origin_tracking_depth(0)
            plain = work()
            assert plain.cr_origin is None
            plain.close()

            sys.set_coroutine_origin_tracking_depth(2)

            def one_level_in() -> Any:
                return work()

            tracked = one_level_in()
            assert tracked.cr_origin is not None
            assert 0 < len(tracked.cr_origin) <= 2
            tracked.close()
        finally:
            sys.set_coroutine_origin_tracking_depth(original)


@pytest.mark.skipif(sys.version_info < (3, 14), reason="sys.remote_exec() is Python 3.14+")
class TestRemoteExec:
    """`sys.remote_exec(pid, script)` | O(1) | the script's cost is the target's."""

    def test_an_unreadable_script_is_refused_before_anything_is_sent(self) -> None:
        """The row's "checks the script is readable": the caller raises, and
        the target - this process - never runs anything.
        """
        with pytest.raises(FileNotFoundError):
            sys_attr("remote_exec")(os.getpid(), "/nonexistent/sys-page-probe.py")

    @pytest.mark.skipif(
        not sys.platform.startswith("linux"), reason="attaching needs the platform's permissions"
    )
    def test_the_target_runs_the_script(self, tmp_path: pathlib.Path) -> None:
        """The round trip, so "the target compiles and runs it" is observed
        rather than assumed. A sleeping child reaches a safe point between
        sleeps, which is where the script is picked up.

        The child announces itself on stdout rather than being given a fixed
        head start, so a slow machine cannot turn this into a flake.
        """
        if not sys_attr("is_remote_debug_enabled")():
            pytest.skip("remote debugging is disabled in this interpreter")

        marker = tmp_path / "marker.txt"
        script = tmp_path / "payload.py"
        script.write_text(
            f"import pathlib\npathlib.Path({str(marker)!r}).write_text('ran')\n",
            encoding="utf-8",
        )

        child = subprocess.Popen(
            [
                sys.executable,
                "-c",
                "import sys, time\n"
                "print('up', flush=True)\n"
                "for _ in range(600):\n"
                "    time.sleep(0.05)\n",
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
        )
        try:
            assert child.stdout is not None
            # Read the raw pipe rather than a buffered reader: a `readline()`
            # that blocks on a child which stalled mid-line would hang the
            # suite, and `select()` cannot see bytes already buffered above it.
            descriptor = child.stdout.fileno()
            announcement = b""
            handshake = time.monotonic() + 30
            while not announcement.endswith(b"\n") and time.monotonic() < handshake:
                ready, _, _ = select.select([descriptor], [], [], 1)
                if ready:
                    chunk = os.read(descriptor, 64)
                    if not chunk:
                        break  # the child closed the pipe without announcing
                    announcement += chunk
            assert announcement == b"up\n", f"the child never started: {announcement!r}"
            try:
                sys_attr("remote_exec")(child.pid, str(script))
            except PermissionError:  # pragma: no cover - depends on the sandbox
                pytest.skip("this process may not attach to another one here")
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline and not marker.exists():
                time.sleep(0.05)
        finally:
            child.terminate()
            child.wait(timeout=30)
            if child.stdout is not None:
                child.stdout.close()

        assert marker.exists(), "the target never ran the script"
        assert marker.read_text(encoding="utf-8") == "ran"


class TestConstantTimeSurface:
    """The grouped rows: names that exist and answer in one field read.

    There is no size to vary here, so this is coverage rather than a growth
    measurement - it fails if the page names something the module does not
    have, or if one of them starts raising.
    """

    GETTERS = [
        "getdefaultencoding",
        "getfilesystemencoding",
        "getfilesystemencodeerrors",
        "getrecursionlimit",
        "getswitchinterval",
        "getallocatedblocks",
        "get_asyncgen_hooks",
        "get_coroutine_origin_tracking_depth",
        "get_int_max_str_digits",
        "is_finalizing",
        "gettrace",
        "getprofile",
    ]

    ATTRIBUTES = [
        "platform",
        "version",
        "version_info",
        "implementation",
        "maxsize",
        "maxunicode",
        "executable",
        "argv",
        "orig_argv",
        "byteorder",
        "hexversion",
        "api_version",
        "copyright",
        "float_repr_style",
        "abiflags",
        "prefix",
        "exec_prefix",
        "base_prefix",
        "base_exec_prefix",
        "platlibdir",
        "pycache_prefix",
        "dont_write_bytecode",
        "warnoptions",
        "_xoptions",
        "meta_path",
        "path_hooks",
        "path_importer_cache",
        "flags",
        "float_info",
        "int_info",
        "hash_info",
        "thread_info",
    ]

    STRUCT_FIELDS: dict[str, list[str]] = {
        "version_info": ["major", "minor", "micro", "releaselevel", "serial"],
        "implementation": ["name", "version", "hexversion", "cache_tag"],
        "flags": [
            "debug",
            "inspect",
            "interactive",
            "optimize",
            "dont_write_bytecode",
            "no_user_site",
            "no_site",
            "ignore_environment",
            "verbose",
            "bytes_warning",
            "quiet",
            "hash_randomization",
            "isolated",
            "dev_mode",
            "utf8_mode",
            "warn_default_encoding",
            "int_max_str_digits",
        ],
        "float_info": [
            "max",
            "max_exp",
            "max_10_exp",
            "min",
            "min_exp",
            "min_10_exp",
            "dig",
            "mant_dig",
            "epsilon",
            "radix",
            "rounds",
        ],
        "int_info": [
            "bits_per_digit",
            "sizeof_digit",
            "default_max_str_digits",
            "str_digits_check_threshold",
        ],
        "hash_info": [
            "width",
            "modulus",
            "inf",
            "nan",
            "imag",
            "algorithm",
            "hash_bits",
            "seed_bits",
            "cutoff",
        ],
        "thread_info": ["name", "lock", "version"],
    }

    # Fields the page prices with a version on the row, and the release that
    # adds each. The assertion is two-sided, so it fails both if a field
    # arrives earlier than the row says and if it is missing where the row
    # promises it - which is what makes the row's qualifier checkable.
    VERSION_GATED_FIELDS: dict[tuple[str, str], tuple[int, int]] = {
        ("flags", "safe_path"): (3, 11),
        ("flags", "gil"): (3, 13),
        ("flags", "thread_inherit_context"): (3, 14),
        ("flags", "context_aware_warnings"): (3, 14),
        ("implementation", "supports_isolated_interpreters"): (3, 14),
    }

    @pytest.mark.parametrize("name", GETTERS)
    def test_a_named_getter_answers(self, name: str) -> None:
        getter = getattr(sys, name)

        assert callable(getter)
        getter()

    @pytest.mark.parametrize("name", ATTRIBUTES)
    def test_a_named_attribute_is_present(self, name: str) -> None:
        assert hasattr(sys, name)

    @pytest.mark.parametrize("owner", sorted(STRUCT_FIELDS))
    def test_the_struct_sequence_fields_are_present(self, owner: str) -> None:
        structure = getattr(sys, owner)

        for field in self.STRUCT_FIELDS[owner]:
            assert hasattr(structure, field), f"sys.{owner}.{field}"

    @pytest.mark.parametrize(
        ("owner", "field"), sorted(VERSION_GATED_FIELDS), ids=lambda value: str(value)
    )
    def test_a_version_gated_field_matches_its_qualifier(self, owner: str, field: str) -> None:
        introduced = self.VERSION_GATED_FIELDS[(owner, field)]
        structure = getattr(sys, owner)

        assert hasattr(structure, field) == (sys.version_info[:2] >= introduced), (
            f"sys.{owner}.{field} is documented as Python "
            f"{introduced[0]}.{introduced[1]}+, on {sys.version_info[:2]}"
        )

    def test_the_digit_flag_follows_its_setter_only_from_3_14(self) -> None:
        """The `sys.flags` row's one exception to "fixed at startup", and the
        version it starts at. Before 3.14 the flag keeps whatever the command
        line gave it while `get_int_max_str_digits()` moves, so a row without
        the qualifier would be wrong on four of the five supported releases.
        """
        original = sys.get_int_max_str_digits()
        startup = sys.flags.int_max_str_digits
        try:
            sys.set_int_max_str_digits(1_234)
            assert sys.get_int_max_str_digits() == 1_234

            if sys.version_info >= (3, 14):
                assert sys.flags.int_max_str_digits == 1_234
            else:
                assert sys.flags.int_max_str_digits == startup
        finally:
            sys.set_int_max_str_digits(original)

        if sys.version_info >= (3, 14):
            assert sys.flags.int_max_str_digits == sys.get_int_max_str_digits()
        else:
            assert sys.flags.int_max_str_digits == startup

    def test_orig_argv_keeps_what_argv_drops(self) -> None:
        """The row's "`orig_argv` keeps the interpreter's own options"."""
        result = run_isolated(
            """
            import sys
            print(sys.argv[0])
            print(sys.orig_argv[0] == sys.executable, "-c" in sys.orig_argv)
            """
        )

        assert result.returncode == 0, result.stderr
        argv_zero, orig = result.stdout.strip().splitlines()
        assert argv_zero == "-c"
        assert orig == "True True"

    @pytest.mark.skipif(sys.platform == "win32", reason="dlopen flags are a Unix interface")
    def test_the_dlopen_flags_round_trip(self) -> None:
        original = sys.getdlopenflags()
        try:
            sys.setdlopenflags(original)
            assert sys.getdlopenflags() == original
        finally:
            sys.setdlopenflags(original)

    @pytest.mark.skipif(sys.platform != "android", reason="Android-only API")
    def test_the_android_api_level_is_a_number(self) -> None:
        assert isinstance(sys_attr("getandroidapilevel")(), int)

    @pytest.mark.skipif(sys.platform != "emscripten", reason="Emscripten-only API")
    def test_the_emscripten_fields_are_present(self) -> None:
        info = sys_attr("_emscripten_info")

        for field in ("emscripten_version", "runtime", "pthreads", "shared_memory"):
            assert hasattr(info, field), field

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only API")
    def test_the_windows_names_are_present(self) -> None:
        assert isinstance(sys_attr("getwindowsversion")().major, int)
        assert hasattr(sys, "dllhandle")
        assert hasattr(sys, "winver")
        assert callable(sys_attr("_enablelegacywindowsfsencoding"))

    def test_the_gil_and_jit_flags_answer_where_they_exist(self) -> None:
        """Both rows are Python 3.13+ and 3.14+; on an older interpreter the
        names should be absent rather than answering something else.
        """
        assert hasattr(sys, "_is_gil_enabled") == (sys.version_info >= (3, 13))
        assert hasattr(sys, "_jit") == (sys.version_info >= (3, 14))

        if sys.version_info >= (3, 13):
            assert isinstance(sys_attr("_is_gil_enabled")(), bool)
        if sys.version_info >= (3, 14):
            jit = sys_attr("_jit")
            assert isinstance(jit.is_available(), bool)
            assert isinstance(jit.is_enabled(), bool)
            assert isinstance(jit.is_active(), bool)


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
    """Every block on the page runs.

    They are run out of process because several of them reassign `sys.stdout`,
    install an audit hook, mutate `sys.path` and raise the recursion limit -
    in-process that would leak into whatever ran next.
    """

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []

        for line, source in _blocks():
            result = _run(source, tmp_path)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()}")

        assert not failures, "\n".join(failures)

    def test_every_block_asserts_something(self) -> None:
        """The blocks carry their expected values as asserts, so running them
        checks the values and not only that nothing raised.
        """
        for line, source in _blocks():
            assert "assert " in source, f"{PAGE.name}:{line} asserts nothing"

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = _blocks()[0][1]
        broken = original.replace(
            "assert outermost() == 'outermost'", "assert outermost() == 'middle'", 1
        )
        assert broken != original, "the mutation did not change the assertion"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "AssertionError" in result.stderr
