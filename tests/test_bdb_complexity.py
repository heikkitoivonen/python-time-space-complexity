"""Tests for docs/stdlib/bdb.md.

The page prices a debugger per trace event: each event costs O(p) to match
skip patterns and O(b) to find the frame's line among the file's breakpoint
lines, and which events arrive decides the rest. Almost every claim is
settled by observation. An `int` subclass that counts its comparisons shows
how many breakpoint lines an operation looks at, a counting `fnmatch` shows
how many skip patterns, list subclasses record the lengths `remove()` works
on and the entries `clear_all_breaks()` walks, and identity shows what is
returned without a copy. Everything that installs a trace function runs in a
subprocess, because tracing in the pytest process changes later allocation
tests; there a `dispatch_line` override counts the line events delivered.

Measurement scope:

* `Bdb()` calls `_add_to_breaks` once per registered location, 10 and 1,000
  of them, and with all of them in one file compares each with the lines
  added before it, L(L - 1)/2 comparisons in all. It keeps its skip patterns
  as a set. `reset()` calls
  `linecache.checkcache()` with no file name, and that call stats all 50
  entries of a 50-entry cache; `run()`, `runcall()` and `set_trace()` each
  call it once.
  `canonic()` returns the same object on a second call and leaves `<string>`
  unchanged and uncached.
* `stop_here()`, `dispatch_return()` and `dispatch_exception()` call
  `fnmatch` once per skip pattern, 5 and 50 of them, for a module that
  matches none. `dispatch_line()` on a line holding no breakpoint compares at
  least b and at most 3b breakpoint lines, for b of 10 and 1,000;
  `get_break()` compares exactly b. `is_skipped_module()` stops at the first
  of 51 patterns when that one matches. On 3.14+ `dispatch_call()` compares each
  of the b lines once, through `break_anywhere()`, and returns `None`; before
  3.14 it compares none and traces the frame. On 3.14+ a second `break_anywhere()` on the same
  code reuses the cached line set by identity.
* Line events, counted in a subprocess on loops of 100 and 10,000
  iterations: with no breakpoint, `set_continue()` leaves one; with a
  breakpoint in another file, a function called after the first stop raises
  none, and the frame the stop happened in raises between 2n and 2n + 10 for
  n iterations of a two-line loop. With the breakpoint in another function of the loop's own file,
  3.14+ delivers one line event and 3.10-3.13 more than the iteration count.
  On 3.14 `backend='monitoring'` delivers the same small number, under 50,
  for both loop lengths.
* `set_trace()` at recursion depths 10 and 100 sets `f_trace` on every frame
  of the stack, and 3.13+ records one saved flag pair per frame; the first
  stop is an opcode stop on 3.13+ and a line stop before. On 3.13+ a
  `set_step()` at that stop clears `f_trace_opcodes` on every frame that had
  it, reading `botframe` 90 more times at depth 100 than at depth 10, and the
  next two `set_step()` calls read it not at all. `bdb.set_trace()` stops once, inside itself on 3.13+ and in its caller
  before, and leaves no trace function after `set_continue()`. Stepping is asserted by the stops a scripted
  debugger records: `set_next()` passes over a call, `set_step()` enters it,
  `set_until()` stops at the given line, `set_return()` stops at the return,
  and `set_quit()` ends the run before the next line, with `runcall()`
  returning `None`. On 3.14 `start_trace()` and `stop_trace()` install and
  remove `trace_dispatch`.
* `set_break()` compares the new line with each of b lines already set, for
  b of 10 and 1,000, returns an error string for a line past the end, and
  leaves the whole file in `linecache`. On 3.12+, with `enterframe` set, it
  calls `break_anywhere()` once per frame, 90 more times at depth 100 than at
  depth 10; before 3.12 it calls it for none.
* `clear_break()` over k breakpoints at one line removes them from lists of
  length k, k - 1, ... 1, for k of 5 and 50. `deleteMe()` calls `remove()`
  once and leaves `None` at its number. `clear_all_file_breaks()` leaves the
  even-numbered breakpoints of k at a line, for k of 4 and 5, and a later `Bdb`
  sees them.
  `clear_all_breaks()` walks all 1,001 numbers after 999 of 1,000
  breakpoints were deleted. `get_breaks()`, `get_file_breaks()` and
  `get_all_breaks()` return the registry's list, the instance's list and the
  instance's dict by identity. `get_bpbynumber()` raises `ValueError` for an
  empty, non-numeric, out-of-range and deleted number.
* `effective()` evaluates the condition of each of k enabled breakpoints,
  5 and 50, when none holds, passes over a disabled one without a hit, spends
  an ignore count before stopping, and returns `(bp, False)` for a condition
  that raises, leaving its ignore count alone. `break_here()` calls
  `do_clear()` for a temporary breakpoint when the flag is `True` and not when
  its condition raised. `checkfuncname()` and `break_here()` are asserted on a
  function-name breakpoint, which counts only on the function's first line.
* `get_stack()` returns 90 more entries at depth 100 than at depth 10, and a
  traceback adds its entries. `format_stack_entry()` renders a return value
  of 10 and 100,000 list items to the same length, calling `repr()` on the
  same number of items, under 10, for both, and compares the keys of a
  1,000-key dict or set return value while comparing no list items.
* The `Breakpoint` rows are asserted by numbering, registry membership,
  `bpformat()` text, `bpprint()` output, `enable()`/`disable()` and the
  attributes `effective()` updates. `do_clear()` raises
  `NotImplementedError`, the `user_*` methods return `None`, and on 3.14
  `disable_current_event()` and `restart_events()` return `None` under the
  default backend. `runeval()` returns the expression's value.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The O(k²) of `clear_break()` and the O(k) of `deleteMe()` are the list
  lengths `remove()` is observed to work on, priced by `list.remove()` being
  linear. The O(B·k) and O(b·k²) of `clear_all_breaks()` and
  `clear_all_file_breaks()` are upper bounds read from Lib/bdb.py; only the
  walk over B is observed.
* Pricing file names, module names, source lines and conditions at O(1) is
  the page's cost model; `canonic()` runs `os.path.abspath()` once per name,
  and `fnmatch` matches each pattern against the module name.
* One-time cache fills are left out of the bounds by the page's cost model:
  `linecache` reading a whole file, `canonic()` resolving a new name, and on
  3.14 `break_anywhere()` building a code object's line set from
  `co_lines()`. Only that `set_break()` fills `linecache` and that the line
  set is reused are observed.
* The O(c) space of `reset()`, and so of the `run*` methods and
  `set_trace()`, is the list of cache keys `linecache.checkcache()` takes
  before checking them, read from Lib/linecache.py.
* The `'monitoring'` backend is observed only for the line events it
  delivers. Its own bounds, including the stack walk its tracer makes to set
  local events, are not priced on the page.
* Generator and coroutine frames, which the dispatch methods treat apart
  while stepping, threads, and `user_*` methods that do work are not
  exercised; every traced function here is a plain function in one thread.
* Undocumented names are not on the page: `set_stepinstr()`,
  `dispatch_opcode()`, `user_opcode()` and `set_enterframe()` (3.12+/3.13+
  internals of `set_trace()`), `Breakpoint.next`, the demonstration `Tdb`,
  `foo()`, `bar()` and `test()`, and `E`, an alias of
  `sys.monitoring.events` on 3.14. The page's examples call the undocumented
  `Breakpoint.clearBreakpoints()` to start from an empty registry.
"""

from __future__ import annotations

import bdb
import fnmatch
import io
import json
import linecache
import os
import pathlib
import re
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from types import FrameType
from typing import Any, ClassVar

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "bdb.md"
EXPECTED_BLOCKS = 8
FAKE_FILE = "/nonexistent/bdb_complexity_target.py"


@pytest.fixture(autouse=True)
def _fresh_registry() -> Iterator[None]:
    """Give each test an empty breakpoint registry and restore the original."""
    saved = (bdb.Breakpoint.next, bdb.Breakpoint.bplist, bdb.Breakpoint.bpbynumber)
    bdb.Breakpoint.next = 1
    bdb.Breakpoint.bplist = {}
    bdb.Breakpoint.bpbynumber = [None]
    yield
    bdb.Breakpoint.next, bdb.Breakpoint.bplist, bdb.Breakpoint.bpbynumber = saved


class CountingLine(int):
    """A line number that counts the comparisons made against it."""

    compared: ClassVar[list[int]] = [0]

    def __eq__(self, other: object) -> bool:
        CountingLine.compared[0] += 1
        # Compare plain ints, so two counting lines count one comparison, not two
        return isinstance(other, int) and int(self) == int(other)

    def __lt__(self, other: int) -> bool:  # type: ignore[override]
        CountingLine.compared[0] += 1
        return int(self) < int(other)

    __hash__ = int.__hash__


def counting_lines(count: int) -> list[int]:
    """`count` breakpoint lines no test frame is on, with the counter reset."""
    CountingLine.compared[0] = 0
    return [CountingLine(1_000_000 + index) for index in range(count)]


class RecordingList(list):  # type: ignore[type-arg]
    """A list that records its length each time `remove()` is called."""

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.lengths: list[int] = []

    def remove(self, value: Any) -> None:
        self.lengths.append(len(self))
        super().remove(value)


class IterationCountingList(list):  # type: ignore[type-arg]
    """A list that counts the entries handed out by iteration."""

    def __init__(self, *args: Any) -> None:
        super().__init__(*args)
        self.yielded = 0

    def __iter__(self) -> Iterator[Any]:
        for item in super().__iter__():
            self.yielded += 1
            yield item


def continuing_debugger(**kwargs: Any) -> Any:
    """A `Bdb` in continue mode at the caller's caller, with nothing traced."""
    debugger: Any = bdb.Bdb(**kwargs)
    debugger.reset()
    debugger.botframe = sys._getframe(2)
    debugger.stopframe = debugger.botframe
    debugger.stoplineno = -1
    return debugger


def nested(depth: int, func: Any) -> Any:
    """Call `func(frame)` from `depth` frames down."""
    if depth:
        return nested(depth - 1, func)
    return func(sys._getframe())


def finished_frame() -> FrameType:
    """A frame whose line number no longer moves."""
    return sys._getframe()


def run_script(source: str, cwd: pathlib.Path) -> Any:
    """Run `source` in a fresh interpreter and return the JSON on its last line."""
    script = cwd / "script.py"
    script.write_text(textwrap.dedent(source), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


class TestConstructionCopiesTheRegistry:
    """`bdb.Bdb(skip=None, backend='settrace')` | O(p + L) | O(p + L): every
    location already registered, by any instance, is copied in."""

    @pytest.mark.parametrize("locations", [10, 1_000])
    def test_each_registered_location_is_added_once(self, locations: int) -> None:
        for line in range(1, locations + 1):
            bdb.Breakpoint(FAKE_FILE, line)
        added: list[tuple[str, int]] = []

        class Recording(bdb.Bdb):
            def _add_to_breaks(self, filename: str, lineno: int) -> None:
                added.append((filename, lineno))
                super()._add_to_breaks(filename, lineno)  # type: ignore[misc]

        debugger = Recording()

        assert len(added) == locations
        assert debugger.get_file_breaks(FAKE_FILE) == list(range(1, locations + 1))

    @pytest.mark.parametrize("locations", [10, 1_000])
    def test_each_location_is_checked_against_its_files_lines_so_far(self, locations: int) -> None:
        """All L locations in one file: the lines added before each are compared."""
        for line in range(1, locations + 1):
            bdb.Breakpoint(FAKE_FILE, CountingLine(line))
        CountingLine.compared[0] = 0

        bdb.Bdb()

        assert CountingLine.compared[0] == locations * (locations - 1) // 2

    def test_skip_patterns_are_kept_as_a_set(self) -> None:
        assert bdb.Bdb(skip=["a.*", "b", "a.*"]).skip == {"a.*", "b"}
        assert bdb.Bdb().skip is None

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="backend is 3.14+")
    def test_backend_is_checked(self) -> None:
        assert bdb.Bdb(backend="monitoring").backend == "monitoring"  # type: ignore[call-arg,attr-defined]
        with pytest.raises(ValueError, match="Invalid backend"):
            bdb.Bdb(backend="bogus")  # type: ignore[call-arg]


class TestResetRevalidatesLinecache:
    """`Bdb.reset()` | O(c): every file in `linecache` is checked again."""

    def test_reset_checks_the_whole_cache(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[tuple[Any, ...]] = []
        monkeypatch.setattr(linecache, "checkcache", lambda *args: calls.append(args))

        bdb.Bdb().reset()

        assert calls == [()]

    def test_checking_the_whole_cache_stats_every_entry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entries = 50
        cache = {
            f"/nonexistent/{index}.py": (1, 1.0, ["x\n"], f"/nonexistent/{index}.py")
            for index in range(entries)
        }
        monkeypatch.setattr(linecache, "cache", cache)
        stats: list[str] = []
        real_stat = os.stat

        def counting_stat(path: Any, *args: Any, **kwargs: Any) -> Any:
            stats.append(str(path))
            return real_stat(path, *args, **kwargs)

        monkeypatch.setattr(os, "stat", counting_stat)

        linecache.checkcache()

        assert len(stats) == entries

    def test_run_runcall_and_set_trace_reset_once(self, tmp_path: pathlib.Path) -> None:
        counts = run_script(
            """
            import bdb, json, linecache, sys
            calls = []
            linecache.checkcache = lambda *args: calls.append(args)
            bdb.Bdb().run("x = 1", {})
            after_run = len(calls)
            bdb.Bdb().runcall(len, [])
            after_runcall = len(calls)
            debugger = bdb.Bdb()
            debugger.set_trace()
            debugger.set_continue()
            assert sys.gettrace() is None
            print(json.dumps([after_run, after_runcall, len(calls)]))
            """,
            tmp_path,
        )

        assert counts == [1, 2, 3]


class TestCanonicIsCached:
    """`Bdb.canonic(filename)` | O(1): cached per name; angle-bracket names
    come back unchanged."""

    def test_a_second_call_returns_the_cached_object(self) -> None:
        debugger = bdb.Bdb()

        first = debugger.canonic("some/relative/file.py")

        assert debugger.canonic("some/relative/file.py") is first
        assert debugger.fncache == {"some/relative/file.py": first}
        assert os.path.isabs(first)

    def test_angle_bracket_names_are_returned_as_given(self) -> None:
        debugger = bdb.Bdb()

        assert debugger.canonic("<string>") == "<string>"
        assert debugger.fncache == {}


class TestEventCostFollowsSkipsAndBreakpointLines:
    """The dispatch rows: O(p) to match skip patterns, O(b) to look for the
    frame's line among the file's breakpoint lines."""

    @pytest.fixture
    def fnmatch_calls(self, monkeypatch: pytest.MonkeyPatch) -> list[str]:
        calls: list[str] = []
        real = fnmatch.fnmatch

        def counting(name: str, pattern: str) -> bool:
            calls.append(pattern)
            return real(name, pattern)

        monkeypatch.setattr(fnmatch, "fnmatch", counting)
        return calls

    @pytest.mark.parametrize("patterns", [5, 50])
    def test_stop_here_matches_every_pattern(self, patterns: int, fnmatch_calls: list[str]) -> None:
        debugger = continuing_debugger(skip=[f"nomatch{index}.*" for index in range(patterns)])

        assert debugger.stop_here(sys._getframe()) is False

        assert len(fnmatch_calls) == patterns

    @pytest.mark.parametrize("patterns", [5, 50])
    def test_return_and_exception_events_match_every_pattern(
        self, patterns: int, fnmatch_calls: list[str]
    ) -> None:
        debugger = continuing_debugger(skip=[f"nomatch{index}.*" for index in range(patterns)])
        frame = sys._getframe()

        debugger.dispatch_return(frame, None)
        debugger.dispatch_exception(frame, (ValueError, ValueError(), None))

        assert len(fnmatch_calls) == 2 * patterns

    def test_is_skipped_module_stops_at_the_first_match(self, fnmatch_calls: list[str]) -> None:
        debugger: Any = bdb.Bdb(skip=["json.*"])
        # A list, unlike the set Bdb builds, fixes the order the patterns are tried in
        debugger.skip = ["json.*", *(f"nomatch{index}.*" for index in range(50))]

        assert debugger.is_skipped_module("json.encoder") is True
        assert fnmatch_calls == ["json.*"]
        assert debugger.is_skipped_module("csv") is False
        assert debugger.is_skipped_module(None) is False  # type: ignore[arg-type]

    @pytest.mark.parametrize("lines", [10, 1_000])
    def test_a_line_event_compares_each_breakpoint_line(self, lines: int) -> None:
        debugger = continuing_debugger()
        frame = sys._getframe()
        debugger.breaks[debugger.canonic(frame.f_code.co_filename)] = counting_lines(lines)

        assert debugger.dispatch_line(frame) == debugger.trace_dispatch

        assert lines <= CountingLine.compared[0] <= 3 * lines

    @pytest.mark.parametrize("lines", [10, 1_000])
    def test_get_break_compares_each_breakpoint_line(self, lines: int) -> None:
        debugger = bdb.Bdb()
        debugger.breaks[debugger.canonic(FAKE_FILE)] = counting_lines(lines)

        assert debugger.get_break(FAKE_FILE, 1) is False

        assert CountingLine.compared[0] == lines

    @pytest.mark.parametrize("lines", [10, 1_000])
    def test_a_call_event_checks_the_frame_against_each_line(self, lines: int) -> None:
        debugger = continuing_debugger()
        frame = sys._getframe()
        debugger.breaks[debugger.canonic(frame.f_code.co_filename)] = counting_lines(lines)

        result = debugger.dispatch_call(frame, None)

        if sys.version_info >= (3, 14):
            assert result is None
            assert CountingLine.compared[0] == lines
        else:
            # Any breakpoint in the file is enough to trace the frame
            assert result == debugger.trace_dispatch
            assert CountingLine.compared[0] == 0

    def test_break_anywhere_before_314_counts_any_breakpoint_in_the_file(self) -> None:
        debugger = bdb.Bdb()
        frame = sys._getframe()
        debugger.breaks[debugger.canonic(frame.f_code.co_filename)] = [1_000_000]

        assert debugger.break_anywhere(frame) is (sys.version_info < (3, 14))

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="the line cache is 3.14+")
    def test_break_anywhere_caches_each_code_objects_lines(self) -> None:
        debugger: Any = bdb.Bdb()
        frame = sys._getframe()
        debugger.breaks[debugger.canonic(frame.f_code.co_filename)] = [frame.f_lineno]

        assert debugger.break_anywhere(frame) is True
        cached = debugger.code_linenos[frame.f_code]
        assert debugger.break_anywhere(frame) is True
        assert debugger.code_linenos[frame.f_code] is cached

    def test_break_here_finds_a_breakpoint_set_by_function_name(self) -> None:
        def target(second: bool) -> FrameType:
            if second:
                return sys._getframe()
            return sys._getframe()

        first_frame, second_frame = target(False), target(True)
        debugger = bdb.Bdb()
        filename = debugger.canonic(first_frame.f_code.co_filename)
        first_line = first_frame.f_code.co_firstlineno
        debugger.breaks[filename] = [first_line]
        breakpoint_ = bdb.Breakpoint(filename, first_line, funcname="target")

        # Neither frame is on the def line: the function's first line is looked up instead
        assert debugger.break_here(first_frame) is True
        assert breakpoint_.func_first_executable_line == first_frame.f_lineno
        assert bdb.checkfuncname(breakpoint_, second_frame) is False
        assert bdb.checkfuncname(breakpoint_, sys._getframe()) is False


class TestUserHooksAndStubs:
    """The `user_*` methods do nothing, `do_clear()` must be supplied, and on
    3.14 the event switches do nothing under the default backend."""

    def test_user_methods_do_nothing(self) -> None:
        debugger = bdb.Bdb()
        frame = sys._getframe()

        assert debugger.user_call(frame, None) is None
        assert debugger.user_line(frame) is None
        assert debugger.user_return(frame, 1) is None
        assert debugger.user_exception(frame, (ValueError, ValueError(), None)) is None  # type: ignore[arg-type]

    def test_do_clear_must_be_supplied(self) -> None:
        with pytest.raises(NotImplementedError):
            bdb.Bdb().do_clear("1")

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="3.14+")
    def test_event_switches_do_nothing_under_settrace(self) -> None:
        debugger: Any = bdb.Bdb()

        assert debugger.disable_current_event() is None
        assert debugger.restart_events() is None

    def test_bdbquit_is_an_exception(self) -> None:
        assert issubclass(bdb.BdbQuit, Exception)


LOOP_MODULE = """\
def loop(n):
    total = 0
    for i in range(n):
        total += i
    return total


def never_called():
    return 1
"""

COUNTING_DEBUGGER = """
import bdb, json, os, sys
sys.path.insert(0, os.getcwd())
import target

class Counting(bdb.Bdb):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.lines = 0

    def dispatch_line(self, frame):
        self.lines += 1
        return super().dispatch_line(frame)

    def user_line(self, frame):
        self.set_continue()

def caller(n):
    return target.loop(n)

def count(func, n, where, **kwargs):
    bdb.Breakpoint.clearBreakpoints()
    debugger = Counting(**kwargs)
    if where == "same file":
        line = target.never_called.__code__.co_firstlineno + 1
        assert debugger.set_break(target.__file__, line) is None
    elif where == "other file":
        line = bdb.effective.__code__.co_firstlineno + 1
        assert debugger.set_break(bdb.__file__, line) is None
    debugger.runcall(func, n)
    assert sys.gettrace() is None
    return debugger.lines
"""


class TestWhatGetsTraced:
    """Which line events reach `dispatch_line()`: none after `set_continue()`
    with no breakpoints, none in a frame that cannot stop, one per line in the
    frame a stop happened in."""

    SIZES = (100, 10_000)

    def counts(self, tmp_path: pathlib.Path, call: str) -> list[int]:
        (tmp_path / "target.py").write_text(LOOP_MODULE, encoding="utf-8")
        source = COUNTING_DEBUGGER + f"\nprint(json.dumps([{call} for n in {self.SIZES}]))\n"
        return run_script(source, tmp_path)

    def test_continuing_with_no_breakpoints_stops_tracing(self, tmp_path: pathlib.Path) -> None:
        assert self.counts(tmp_path, "count(target.loop, n, None)") == [1, 1]

    def test_a_frame_that_cannot_stop_raises_no_line_events(self, tmp_path: pathlib.Path) -> None:
        assert self.counts(tmp_path, "count(caller, n, 'other file')") == [1, 1]

    def test_the_stopped_frame_raises_one_per_line(self, tmp_path: pathlib.Path) -> None:
        """Each iteration of `loop()` executes two lines: the `for` and its body."""
        counts = self.counts(tmp_path, "count(target.loop, n, 'other file')")

        for size, lines in zip(self.SIZES, counts, strict=True):
            assert 2 * size <= lines <= 2 * size + 10, (size, lines)

    def test_a_breakpoint_in_the_same_file(self, tmp_path: pathlib.Path) -> None:
        """3.14+ traces only a function whose code holds the breakpoint;
        before, any breakpoint in the file traces every function in it."""
        small, large = self.counts(tmp_path, "count(caller, n, 'same file')")

        if sys.version_info >= (3, 14):
            assert (small, large) == (1, 1)
        else:
            assert small > self.SIZES[0]
            assert large > self.SIZES[1]

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="backend is 3.14+")
    def test_the_monitoring_backend_switches_off_lines_that_cannot_stop(
        self, tmp_path: pathlib.Path
    ) -> None:
        small, large = self.counts(
            tmp_path, "count(target.loop, n, 'other file', backend='monitoring')"
        )

        assert small == large < 50


class TestSetTraceHooksEveryFrame:
    """`Bdb.set_trace(frame=None)` | O(c + d) | O(d), and the O(d) walk of the
    first stepping call after it on 3.13+."""

    def test_every_frame_on_the_stack_is_hooked(self, tmp_path: pathlib.Path) -> None:
        results = run_script(
            """
            import bdb, json, sys

            class Quiet(bdb.Bdb):
                first = None
                def user_line(self, frame):
                    self.first = self.first or "line"
                def user_opcode(self, frame):
                    self.first = self.first or "opcode"

            def nest(n, debugger):
                if n:
                    return nest(n - 1, debugger)
                debugger.set_trace()
                hooked, frame = 0, sys._getframe()
                while frame:
                    hooked += frame.f_trace == debugger.trace_dispatch
                    frame = frame.f_back
                saved = len(getattr(debugger, "frame_trace_lines_opcodes", {}))
                debugger.set_continue()
                return hooked, saved

            results = []
            for depth in (10, 100):
                debugger = Quiet()
                hooked, saved = nest(depth, debugger)
                results.append([hooked, saved, debugger.first, sys.gettrace() is None])
            print(json.dumps(results))
            """,
            tmp_path,
        )

        (hooked_10, saved_10, first, untraced), (hooked_100, saved_100, _, _) = results
        assert hooked_100 - hooked_10 == 90
        assert hooked_10 >= 11
        assert untraced
        if sys.version_info >= (3, 13):
            assert (saved_10, saved_100) == (hooked_10, hooked_100)
            assert first == "opcode"
        else:
            assert (saved_10, saved_100) == (0, 0)
            assert first == "line"

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="instruction stepping is 3.13+")
    def test_the_first_step_after_set_trace_walks_the_stack(self, tmp_path: pathlib.Path) -> None:
        results = run_script(
            """
            import bdb, json, sys

            def marked():
                frame, count = sys._getframe(2), 0
                while frame:
                    count += bool(frame.f_trace_opcodes)
                    frame = frame.f_back
                return count

            class Stepper(bdb.Bdb):
                result = None
                def user_opcode(self, frame):
                    before = marked()
                    self.set_step()
                    self.result = [before, marked()]
                    self.set_continue()

            def nest(n, debugger):
                if n:
                    return nest(n - 1, debugger)
                debugger.set_trace()

            results = []
            for depth in (10, 100):
                debugger = Stepper()
                nest(depth, debugger)
                results.append(debugger.result)
            print(json.dumps(results))
            """,
            tmp_path,
        )

        (before_10, after_10), (before_100, after_100) = results
        assert before_100 - before_10 == 90
        assert after_10 == after_100 == 0

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="instruction stepping is 3.13+")
    def test_later_steps_do_not_walk_the_stack(self, tmp_path: pathlib.Path) -> None:
        """The walk compares each frame with `botframe`, so counting reads of
        `botframe` during a `set_step()` counts the frames it visits."""
        results = run_script(
            """
            import bdb, json

            class Stepper(bdb.Bdb):
                counting = False
                reads = 0

                @property
                def botframe(self):
                    if self.counting:
                        self.reads += 1
                    return self._botframe

                @botframe.setter
                def botframe(self, frame):
                    self._botframe = frame

                def step_counting(self):
                    self.reads, self.counting = 0, True
                    self.set_step()
                    self.counting = False
                    self.visits.append(self.reads)

                def user_opcode(self, frame):
                    self.step_counting()

                def user_line(self, frame):
                    self.step_counting()
                    if len(self.visits) == 3:
                        self.set_continue()

            def nest(n, debugger):
                if n:
                    return nest(n - 1, debugger)
                debugger.set_trace()
                a = 1
                b = 2
                return a + b

            results = []
            for depth in (10, 100):
                debugger = Stepper()
                debugger.visits = []
                nest(depth, debugger)
                results.append(debugger.visits)
            print(json.dumps(results))
            """,
            tmp_path,
        )

        (first_10, *later_10), (first_100, *later_100) = results
        assert first_100 - first_10 == 90
        assert later_10 == later_100 == [0, 0]

    def test_the_module_function_stops_once_and_can_continue(self, tmp_path: pathlib.Path) -> None:
        result = run_script(
            """
            import bdb, json, sys
            stops = []

            def record(self, frame):
                stops.append(frame.f_code.co_name)
                self.set_continue()

            bdb.Bdb.user_line = record
            bdb.Bdb.user_opcode = record

            def caller():
                bdb.set_trace()
                return 1

            caller()
            print(json.dumps([stops, sys.gettrace() is None]))
            """,
            tmp_path,
        )

        # 3.13+ stops at the next instruction, still inside bdb.set_trace()
        first_stop = "set_trace" if sys.version_info >= (3, 13) else "caller"
        assert result == [[first_stop], True]

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="3.14+")
    def test_start_and_stop_trace(self, tmp_path: pathlib.Path) -> None:
        result = run_script(
            """
            import bdb, json, sys
            debugger = bdb.Bdb()
            debugger.reset()
            debugger.start_trace()
            installed = sys.gettrace() == debugger.trace_dispatch
            debugger.stop_trace()
            print(json.dumps([installed, sys.gettrace() is None]))
            """,
            tmp_path,
        )

        assert result == [True, True]


STEPPING_SCRIPT = """
import bdb, json

done = []

def inner():
    a = 1
    return a

def outer():
    x = inner()
    done.append(1)
    return x + 1

FIRST = outer.__code__.co_firstlineno

class Scripted(bdb.Bdb):
    def __init__(self, commands):
        super().__init__()
        self.commands = list(commands)
        self.stops = []

    def act(self, frame):
        command = self.commands.pop(0) if self.commands else "continue"
        if command == "step":
            self.set_step()
        elif command == "next":
            self.set_next(frame)
        elif command == "return":
            self.set_return(frame)
        elif command == "until":
            self.set_until(frame, FIRST + 3)
        elif command == "quit":
            self.set_quit()
        else:
            self.set_continue()

    def user_call(self, frame, argument_list):
        self.stops.append(["call", frame.f_code.co_name])
        self.act(frame)

    def user_line(self, frame):
        self.stops.append(["line", frame.f_code.co_name, frame.f_lineno - FIRST])
        self.act(frame)

    def user_return(self, frame, value):
        self.stops.append(["return", frame.f_code.co_name])
        self.act(frame)

def session(*commands):
    done.clear()
    debugger = Scripted(commands)
    result = debugger.runcall(outer)
    return [debugger.stops, result, len(done)]
"""


class TestStepping:
    """`set_step()`, `set_next()`, `set_return()`, `set_until()`,
    `set_continue()` and `set_quit()` decide the next stop, and nothing else."""

    def session(self, tmp_path: pathlib.Path, *commands: str) -> Any:
        return run_script(
            STEPPING_SCRIPT + f"\nprint(json.dumps(session(*{commands!r})))\n", tmp_path
        )

    def test_next_passes_over_a_call(self, tmp_path: pathlib.Path) -> None:
        stops, result, _ = self.session(tmp_path, "next", "continue")

        assert stops == [["line", "outer", 1], ["line", "outer", 2]]
        assert result == 2

    def test_step_enters_a_call(self, tmp_path: pathlib.Path) -> None:
        stops, _, _ = self.session(tmp_path, "step", "continue")

        assert stops == [["line", "outer", 1], ["call", "inner"]]

    def test_until_stops_at_the_given_line(self, tmp_path: pathlib.Path) -> None:
        stops, _, _ = self.session(tmp_path, "until", "continue")

        assert stops == [["line", "outer", 1], ["line", "outer", 3]]

    def test_return_stops_at_the_return(self, tmp_path: pathlib.Path) -> None:
        stops, _, _ = self.session(tmp_path, "return", "continue")

        assert stops == [["line", "outer", 1], ["return", "outer"]]

    def test_quit_ends_the_run_at_once(self, tmp_path: pathlib.Path) -> None:
        stops, result, done = self.session(tmp_path, "quit")

        assert stops == [["line", "outer", 1]]
        assert (result, done) == (None, 0)

    def test_run_and_runeval(self, tmp_path: pathlib.Path) -> None:
        result = run_script(
            """
            import bdb, json
            debugger = bdb.Bdb()
            debugger.user_line = lambda frame: debugger.set_continue()
            namespace = {}
            assert debugger.run("x = 6 * 7", namespace) is None
            value = debugger.runeval("x + 1", namespace)
            debugger.runctx("y = x", namespace, namespace)
            print(json.dumps([namespace["x"], value, namespace["y"]]))
            """,
            tmp_path,
        )

        assert result == [42, 43, 42]


class TestSetBreak:
    """`Bdb.set_break(...)` | O(b + d·b): the new line is compared with the
    file's b lines, and during a stop (3.12+) every frame is checked."""

    @pytest.mark.parametrize("lines", [10, 1_000])
    def test_the_new_line_is_compared_with_each_existing_one(self, lines: int) -> None:
        debugger = bdb.Bdb()
        filename = debugger.canonic(bdb.__file__)
        debugger.breaks[filename] = counting_lines(lines)

        assert debugger.set_break(filename, 1) is None

        assert CountingLine.compared[0] == lines
        assert len(debugger.breaks[filename]) == lines + 1

    def test_a_missing_line_is_an_error_string(self) -> None:
        debugger = bdb.Bdb()
        filename = debugger.canonic(bdb.__file__)

        assert debugger.set_break(filename, 10**6) == f"Line {filename}:1000000 does not exist"
        assert bdb.Breakpoint.bplist == {}

    def test_the_file_is_read_into_linecache(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "module.py"
        source.write_text("a = 1\nb = 2\nc = 3\n", encoding="utf-8")
        filename = bdb.Bdb().canonic(str(source))

        assert bdb.Bdb().set_break(filename, 2) is None

        cached: Any = linecache.cache[filename]
        assert cached[2] == ["a = 1\n", "b = 2\n", "c = 3\n"]
        linecache.clearcache()

    def test_during_a_stop_each_frame_is_checked(self) -> None:
        checked: list[FrameType] = []

        class Counting(bdb.Bdb):
            def break_anywhere(self, frame: FrameType) -> bool:
                checked.append(frame)
                return False

        def set_at(frame: FrameType) -> int:
            debugger: Any = Counting()
            debugger.enterframe = frame
            checked.clear()
            assert debugger.set_break(bdb.__file__, bdb.effective.__code__.co_firstlineno) is None
            return len(checked)

        shallow = nested(10, set_at)
        deep = nested(100, set_at)

        if sys.version_info >= (3, 12):
            assert deep - shallow == 90
        else:
            assert shallow == deep == 0


class TestClearingBreakpoints:
    """The clearing rows: `clear_break()` removes each of k from a shrinking
    list, `clear_all_file_breaks()` leaves every second one, and
    `clear_all_breaks()` walks every number ever assigned."""

    @staticmethod
    def set_k(debugger: bdb.Bdb, count: int) -> tuple[str, int]:
        filename = debugger.canonic(bdb.__file__)
        line = bdb.effective.__code__.co_firstlineno + 1
        for _ in range(count):
            assert debugger.set_break(filename, line) is None
        return filename, line

    @pytest.mark.parametrize("count", [5, 50])
    def test_clear_break_removes_from_a_shrinking_list(self, count: int) -> None:
        debugger = bdb.Bdb()
        location = self.set_k(debugger, count)
        recording = RecordingList(bdb.Breakpoint.bplist[location])
        bdb.Breakpoint.bplist[location] = recording

        assert debugger.clear_break(*location) is None

        assert recording.lengths == list(range(count, 0, -1))
        assert location not in bdb.Breakpoint.bplist
        assert debugger.get_all_breaks() == {}

    @pytest.mark.parametrize("count", [4, 5])
    def test_clear_all_file_breaks_leaves_every_second_one(self, count: int) -> None:
        debugger = bdb.Bdb()
        filename, line = self.set_k(debugger, count)

        assert debugger.clear_all_file_breaks(filename) is None

        assert debugger.get_file_breaks(filename) == []
        survivors = [each.number for each in bdb.Breakpoint.bplist[filename, line]]
        assert survivors == list(range(2, count + 1, 2))
        assert debugger.clear_all_breaks() == "There are no breakpoints"
        assert bdb.Bdb().get_break(filename, line)

    def test_clear_all_breaks_walks_every_number_ever_assigned(self) -> None:
        for line in range(1, 1_001):
            bdb.Breakpoint(FAKE_FILE, line)
        debugger: Any = bdb.Bdb()  # the stubs type arg as SupportsInt; bdb takes strings
        for number in range(1, 1_000):
            assert debugger.clear_bpbynumber(str(number)) is None
        counting = IterationCountingList(bdb.Breakpoint.bpbynumber)
        bdb.Breakpoint.bpbynumber = counting

        assert debugger.clear_all_breaks() is None

        assert counting.yielded == 1_001
        assert bdb.Breakpoint.bplist == {}

    def test_delete_me_leaves_none_at_its_number(self) -> None:
        first = bdb.Breakpoint(FAKE_FILE, 1)
        second = bdb.Breakpoint(FAKE_FILE, 1)
        recording = RecordingList(bdb.Breakpoint.bplist[FAKE_FILE, 1])
        bdb.Breakpoint.bplist[FAKE_FILE, 1] = recording

        first.deleteMe()

        assert recording.lengths == [2]
        assert bdb.Breakpoint.bpbynumber == [None, None, second]
        assert bdb.Breakpoint(FAKE_FILE, 2).number == 3

    def test_clear_bpbynumber_and_its_errors(self) -> None:
        debugger: Any = bdb.Bdb()
        filename, line = self.set_k(debugger, 2)

        assert debugger.clear_bpbynumber("1") is None
        assert debugger.get_breaks(filename, line) == [bdb.Breakpoint.bpbynumber[2]]
        assert debugger.clear_bpbynumber("1") == "Breakpoint 1 already deleted"
        for argument, message in [
            ("", "Breakpoint number expected"),
            ("x", "Non-numeric breakpoint number x"),
            ("99", "Breakpoint number 99 out of range"),
            ("1", "Breakpoint 1 already deleted"),
        ]:
            with pytest.raises(ValueError, match=message):
                debugger.get_bpbynumber(argument)


class TestQueriesReturnTheStoredObjects:
    """`get_breaks()`, `get_file_breaks()` and `get_all_breaks()` hand back
    what is stored, not a copy; `get_bpbynumber()` indexes a list."""

    def test_identity(self) -> None:
        debugger: Any = bdb.Bdb()
        filename = debugger.canonic(bdb.__file__)
        line = bdb.effective.__code__.co_firstlineno + 1
        assert debugger.set_break(filename, line) is None

        assert debugger.get_breaks(filename, line) is bdb.Breakpoint.bplist[filename, line]
        assert debugger.get_file_breaks(filename) is debugger.breaks[filename]
        assert debugger.get_all_breaks() is debugger.breaks
        assert debugger.get_bpbynumber("1") is bdb.Breakpoint.bpbynumber[1]

    def test_empty_answers(self) -> None:
        debugger = bdb.Bdb()

        assert debugger.get_breaks(FAKE_FILE, 1) == []
        assert debugger.get_file_breaks(FAKE_FILE) == []
        assert debugger.get_break(FAKE_FILE, 1) is False


class TestEffectiveWalksTheLine:
    """`bdb.effective(file, line, frame)` | O(k), plus each condition: the
    first enabled breakpoint whose condition holds and whose ignore count is
    spent."""

    @pytest.mark.parametrize("count", [5, 50])
    def test_every_condition_is_evaluated_when_none_holds(self, count: int) -> None:
        frame = finished_frame()
        evaluated: list[int] = []
        frame.f_globals["_bdb_test_probe"] = lambda: evaluated.append(1)
        try:
            breakpoints = [
                bdb.Breakpoint(FAKE_FILE, frame.f_lineno, cond="_bdb_test_probe()")
                for _ in range(count)
            ]

            assert bdb.effective(FAKE_FILE, frame.f_lineno, frame) == (None, None)
        finally:
            del frame.f_globals["_bdb_test_probe"]

        assert len(evaluated) == count
        assert all(each.hits == 1 for each in breakpoints)

    def test_disabled_ignored_and_active(self) -> None:
        frame = finished_frame()
        line = frame.f_lineno
        off = bdb.Breakpoint(FAKE_FILE, line)
        off.disable()
        ignored_once = bdb.Breakpoint(FAKE_FILE, line)
        ignored_once.ignore = 1

        assert bdb.effective(FAKE_FILE, line, frame) == (None, None)
        assert bdb.effective(FAKE_FILE, line, frame) == (ignored_once, True)
        assert (off.hits, ignored_once.hits, ignored_once.ignore) == (0, 2, 0)

        off.enable()
        assert bdb.effective(FAKE_FILE, line, frame) == (off, True)

    def test_a_condition_that_raises_stops_without_deleting(self) -> None:
        frame = finished_frame()
        broken = bdb.Breakpoint(FAKE_FILE, frame.f_lineno, cond="1 / 0")
        broken.ignore = 3

        assert bdb.effective(FAKE_FILE, frame.f_lineno, frame) == (broken, False)
        assert broken.ignore == 3

    @pytest.mark.parametrize(("cond", "cleared"), [(None, ["1"]), ("1 / 0", [])])
    def test_break_here_clears_a_temporary_breakpoint_only_when_told(
        self, cond: str | None, cleared: list[str]
    ) -> None:
        calls: list[str] = []

        class Clearing(bdb.Bdb):
            def do_clear(self, arg: str) -> None:
                calls.append(arg)

        frame = finished_frame()
        debugger = Clearing()
        filename = debugger.canonic(frame.f_code.co_filename)
        debugger.breaks[filename] = [frame.f_lineno]
        bdb.Breakpoint(filename, frame.f_lineno, temporary=True, cond=cond)

        assert debugger.break_here(frame) is True
        assert calls == cleared

    def test_checkfuncname_by_line(self) -> None:
        frame = finished_frame()

        assert bdb.checkfuncname(bdb.Breakpoint(FAKE_FILE, frame.f_lineno), frame) is True
        assert bdb.checkfuncname(bdb.Breakpoint(FAKE_FILE, frame.f_lineno + 1), frame) is False


class TestBreakpointObjects:
    """`bdb.Breakpoint(...)` | O(1): numbered in order and entered in both
    shared registries; `bpformat()` and `bpprint()` describe it."""

    def test_numbering_and_registries(self) -> None:
        first = bdb.Breakpoint(FAKE_FILE, 3)
        second = bdb.Breakpoint(FAKE_FILE, 3, temporary=True, cond="x", funcname="f")

        assert (first.number, second.number) == (1, 2)
        assert bdb.Breakpoint.bpbynumber == [None, first, second]
        assert bdb.Breakpoint.bplist == {(FAKE_FILE, 3): [first, second]}
        assert (second.file, second.line, second.temporary) == (FAKE_FILE, 3, True)
        assert (second.cond, second.funcname, second.enabled) == ("x", "f", True)
        assert (second.ignore, second.hits) == (0, 0)

    def test_bpformat_and_bpprint(self) -> None:
        breakpoint_ = bdb.Breakpoint(FAKE_FILE, 3, temporary=True, cond="x > 1")
        breakpoint_.disable()
        breakpoint_.ignore = 2
        breakpoint_.hits = 1
        out = io.StringIO()

        breakpoint_.bpprint(out)

        text = breakpoint_.bpformat()
        assert out.getvalue() == text + "\n"
        first_line = text.splitlines()[0]
        assert first_line.startswith("1   breakpoint   del  no ")
        assert first_line.endswith(f"at {FAKE_FILE}:3")
        assert "stop only if x > 1" in text
        assert "ignore next 2 hits" in text
        assert "already hit 1 time" in text


class TestStackInspection:
    """`get_stack(f, t)` | O(d + t), and `format_stack_entry()` | O(1) plus
    `reprlib.repr()` of a return value."""

    def test_get_stack_grows_with_depth(self) -> None:
        debugger = bdb.Bdb()
        debugger.reset()

        def stack_at(frame: FrameType) -> int:
            stack, index = debugger.get_stack(frame, None)
            assert stack[index][0] is frame
            return len(stack)

        assert nested(100, stack_at) - nested(10, stack_at) == 90

    def test_a_traceback_adds_its_entries(self) -> None:
        debugger = bdb.Bdb()
        debugger.reset()

        def fail(depth: int) -> None:
            if depth:
                fail(depth - 1)
            raise ValueError

        with pytest.raises(ValueError) as caught:
            fail(20)
        traceback = caught.value.__traceback__
        frame = sys._getframe()

        without, _ = debugger.get_stack(frame, None)
        with_tb, _ = debugger.get_stack(frame, traceback)

        assert len(with_tb) - len(without) == 21  # the traceback's frame is skipped

    @staticmethod
    def entry_for(value: Any) -> str:
        def returns() -> FrameType:
            __return__ = value  # noqa: F841
            return sys._getframe()

        frame = returns()
        return bdb.Bdb().format_stack_entry((frame, frame.f_lineno))

    def test_a_long_list_renders_no_longer_than_a_short_one(self) -> None:
        short = self.entry_for(list(range(10)))
        long = self.entry_for(list(range(100_000)))

        assert len(long) == len(short)
        assert "->[0, 1, 2, 3, 4, 5, ...]" in long

    def test_a_long_list_has_only_its_first_items_rendered(self) -> None:
        rendered = [0]

        class Item:
            def __repr__(self) -> str:
                rendered[0] += 1
                return "i"

        counts = []
        for size in (10, 100_000):
            rendered[0] = 0
            self.entry_for([Item() for _ in range(size)])
            counts.append(rendered[0])

        assert counts[0] == counts[1] < 10

    def test_a_dict_or_set_return_value_has_its_keys_sorted(self) -> None:
        compared = [0]

        class Key:
            def __init__(self, value: int) -> None:
                self.value = value

            def __lt__(self, other: Key) -> bool:
                compared[0] += 1
                return self.value < other.value

        self.entry_for([Key(index) for index in range(1_000)])
        assert compared[0] == 0

        self.entry_for({Key(index): None for index in range(1_000)})
        assert compared[0] >= 999

        compared[0] = 0
        self.entry_for({Key(index) for index in range(1_000)})
        assert compared[0] >= 999


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
    """Each block runs in its own subprocess, so the tracing it installs and
    the breakpoint registry cannot leak, and asserts its own result."""

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
        needle = "assert logger.seen == [0, 25, 50, 75]"
        line, source = next((n, s) for n, s in _blocks() if needle in s)
        mutated = source.replace(needle, "assert logger.seen == [0, 25, 50]", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
