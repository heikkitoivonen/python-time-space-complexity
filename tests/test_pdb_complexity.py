"""Tests for docs/stdlib/pdb.md.

The page prices a debugging session in three parts: entering the debugger,
which hooks every frame on the stack; each stop, which builds a list of the
frames and re-evaluates the frame's `display` expressions; and running between
stops, which costs the trace events the debugger receives. Almost every claim
is settled by observation. A `Pdb` subclass counts the events `trace_dispatch`
receives, or the calls a method makes; scripted `stdin` drives the session and
the text it writes to `stdout` is asserted on. Everything that installs a trace
function or `sys.monitoring` tool runs in a subprocess, because tracing in the
pytest process changes later allocation tests; so does everything that builds a
`Pdb`, with `HOME` and the working directory pointed at an empty temporary
directory so no real `.pdbrc` is read.

Measurement scope:

* `Pdb.set_trace()` at recursion depths 10 and 100 leaves `f_trace` set on
  every frame of the stack at the first stop, and `where` prints 90 more
  entries at depth 100. `continue` with no breakpoints then leaves
  `sys.gettrace()` as `None`. `set_trace()`, `run()`,
  `runcall()` and `post_mortem()` each call `linecache.checkcache()` once
  with no file name, which is the O(c) term priced on the bdb page.
* `Pdb()` keeps every line of a 7-line `~/.pdbrc` and a 5-line `./.pdbrc`
  in `rcLines`, and none with `readrc=False`; it copies 20 breakpoint
  locations already registered into its own `breaks`.
* Events are counted on `step()`, a two-line function called n times, for n
  of 100 and 1,000, after `continue`. With no breakpoints there are none.
  With a breakpoint in another function of the same file, the `'settrace'`
  backend delivers exactly n call events, and 2n line events before 3.14 and
  none from 3.14. With a breakpoint in another module, n call events and no
  line events. The frame the stop happened in, and its caller once it
  returns there, keep raising line events: more than n for an n-iteration
  loop in either. `next` over a call delivers n call events and no line
  events in the callee. On 3.14 the `'monitoring'` backend delivers one call
  event for the same n calls with a breakpoint elsewhere, and two when a
  breakpoint stops once midway. With a false-condition breakpoint inside
  `step()` it delivers all n call events; with one inside the loop, at least
  n line events at that line, as `'settrace'` does, against more than 2n
  line events in the loop on `'settrace'`.
* Three `step` commands from the `set_trace()` stop, before a line that
  calls a function, end in that function; three `next` commands never stop
  in it.
* Two `display` expressions are evaluated twice when set and twice more at
  each of four later stops; the counter is the expression itself.
* `list` prints 11 numbered lines, and `longlist` prints one per line of a
  30-line function. `up` moves one frame, observed by `p` of a local.
* `break` during a stop calls `break_anywhere()` once per frame, 90 more
  times at depth 100 than at depth 10, on 3.12.9+ and 3.13.1+; on earlier
  releases it calls it for none. The boundary tags were read from CPython's
  history; CI runs 3.12.14 and 3.13.14, so there the earlier side is exercised
  only on 3.10 and 3.11.
* A breakpoint condition is evaluated each time its line runs, 16 times for
  the 16 iterations up to the one where it first holds. `disable`, `enable`,
  `ignore`, `condition` and `clear` by number are observed through the stop
  they cause or prevent. `clear` with no arguments, answered `y`, calls
  `clear_all_breaks()` once.
* `interact` hands the console a namespace whose names are exactly the
  frame's globals and locals at that moment, and assignments made in it do not reach the frame's locals.
* `post_mortem()` prints 40 more entries under `where` for a traceback 50
  recursive calls deep than for one 10 deep. On 3.13+, an exception with 30
  chained causes lists 31 under `exceptions`, and a chain of 1,005 lists
  `Pdb.MAX_CHAINED_EXCEPTION_DEPTH`, 999. `pm()` on 3.12+ debugs
  `sys.last_exc` when `sys.last_traceback` points elsewhere, and before 3.12
  `sys.last_traceback`.
* On 3.14, `breakpoint()` builds one `Pdb`, on the `'monitoring'` backend,
  and a `pdb.set_trace()` after it reuses that one; it also reuses an
  instance whose own `set_trace()` ran last. Before 3.14 each of the two
  calls builds a new `Pdb`. `get_default_backend()` is `'settrace'`, and
  `set_default_backend('monitoring')` changes what a `Pdb` built without
  `backend` uses. `set_trace(commands=...)` runs the
  commands at the first stop, and `set_trace_async()` stops in a coroutine.
* `runeval()` and `runcall()` return the expression's and the call's value,
  and `run()` stops on line 1 of `<string>` before running anything.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The per-event cost is priced on the bdb page and its tests; here only which
  events arrive is counted. The O(L·b) of copying registered breakpoints is
  the `Bdb()` bound from that page.
* The O(d·b) of `break` is the product of the frames walked, observed, and the
  O(b) `break_anywhere()` priced on the bdb page. `clear` with no arguments is
  O(B·k) by `clear_all_breaks()`, also priced there, and its O(B) space is the
  list of live breakpoints `do_clear()` keeps to report; `clear bpnumber` is
  `clear_bpbynumber()`. `break function` for a name that does not evaluate in
  the current frame is resolved by `find_function()` scanning the source
  file; the page leaves that path out of the bound, and it is not exercised.
* `list`'s b factor is the `lineno in breaks` test `_print_lines()` makes
  against the file's list of breakpoint lines, and `display` with no argument
  listing the frame's x expressions is read from `do_display()`; only the n
  lines printed and the displays evaluated at stops are observed.
* `up` and `down` are O(1) and `p`, `pp` and `!` add only their expression by
  reading Lib/pdb.py: they index the stack list the stop built, and evaluate
  the expression once. That `exceptions number` rebuilds the stack for the
  chosen traceback, O(d), is read from `do_exceptions()`, which calls
  `setup()`.
* `python -m pdb` using the `'monitoring'` backend, and `Restart` ending a
  `restart`, are read from `main()` and `do_run()` in Lib/pdb.py; a script run
  under the command line is not exercised.
* Threads, generators and coroutines other than one `set_trace_async()` stop,
  `skip` patterns, signals and the remote `-p` attach of 3.14 are not
  exercised. Commands not on the page (`jump`, `alias`, `commands`,
  `source`, `whatis`, `args`, `retval`, `restart`, `quit`) are not priced,
  nor is `pdb.help()`, which hands the module's documentation to `pydoc`'s
  pager. `pdb.runctx()` is priced with `run()`, which it calls, and not run.
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess
import sys
import textwrap
from typing import Any, ClassVar

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "pdb.md"
EXPECTED_BLOCKS = 7

PRELUDE = '''
import io
import json
import pdb
import re
import sys
from collections import Counter


def scripted(commands, cls=pdb.Pdb, **kwargs):
    """A Pdb that reads `commands` and writes to a StringIO."""
    return cls(stdin=io.StringIO(commands), stdout=io.StringIO(), readrc=False,
               nosigint=True, **kwargs)


def emit(value):
    sys.settrace(None)
    print()
    print(json.dumps(value))
'''


def run_script(
    source: str, cwd: pathlib.Path, stdin: str | None = None, prelude: bool = True
) -> Any:
    """Run `source` in a fresh interpreter and return the JSON on its last line."""
    script = cwd / "script.py"
    body = textwrap.dedent(source)
    script.write_text((PRELUDE + body) if prelude else body, encoding="utf-8")
    env = {**os.environ, "HOME": str(cwd), "PYTHONBREAKPOINT": ""}
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        input=stdin,
        stdin=None if stdin is not None else subprocess.DEVNULL,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout.strip().splitlines()[-1])


class TestEnteringHooksEveryFrame:
    """`set_trace()` | O(c + d): every frame on the stack is hooked, the stop
    lists all of them, and `continue` with no breakpoints unhooks them all."""

    SOURCE = """
    class Recording(pdb.Pdb):
        def interaction(self, frame, tb):
            walk, traced, total = frame, 0, 0
            while walk is not None:
                total += 1
                traced += walk.f_trace is not None
                walk = walk.f_back
            first_stops.append([traced, total])
            super().interaction(frame, tb)

    def descend(depth, debugger):
        if depth:
            return descend(depth - 1, debugger)
        debugger.set_trace()
        return debugger.stdout.getvalue()

    first_stops = []
    transcript = descend({depth}, scripted('where\\ncontinue\\n', cls=Recording))
    emit({{'where': transcript.count('descend()'), 'gettrace': sys.gettrace() is None,
          'stops': first_stops}})
    """

    @pytest.fixture(scope="class")
    @classmethod
    def depths(cls, tmp_path_factory: pytest.TempPathFactory) -> dict[int, Any]:
        return {
            depth: run_script(cls.SOURCE.format(depth=depth), tmp_path_factory.mktemp("d"))
            for depth in (10, 100)
        }

    def test_every_frame_is_hooked_at_the_first_stop(self, depths: dict[int, Any]) -> None:
        for result in depths.values():
            [[traced, total]] = result["stops"]
            assert traced == total, result

        assert depths[100]["stops"][0][1] - depths[10]["stops"][0][1] == 90

    def test_where_lists_one_entry_per_frame(self, depths: dict[int, Any]) -> None:
        assert depths[100]["where"] - depths[10]["where"] == 90

    def test_continue_without_breakpoints_removes_the_hook(self, depths: dict[int, Any]) -> None:
        for result in depths.values():
            assert result["gettrace"] is True


class TestEntryPointsRevalidateLinecache:
    """The O(c) in every entry row: each one resets the debugger, which
    revalidates every file in `linecache` once."""

    SOURCE = """
    import linecache
    calls = Counter()
    original = linecache.checkcache

    def counting(filename=None):
        calls['all' if filename is None else 'one'] += 1
        return original(filename)

    linecache.checkcache = counting

    def work(value):
        return value + 1

    results = {}
    calls.clear()
    scripted('continue\\n').set_trace()
    results['set_trace'] = calls['all']
    calls.clear()
    scripted('continue\\n').run('x = 1', {})
    results['run'] = calls['all']
    calls.clear()
    scripted('continue\\n').runcall(work, 1)
    results['runcall'] = calls['all']
    try:
        work(None)
    except TypeError as error:
        traceback = error.__traceback__
    calls.clear()
    sys.stdin = io.StringIO('quit\\n')
    import contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        pdb.post_mortem(traceback)
    results['post_mortem'] = calls['all']
    emit(results)
    """

    def test_each_entry_point_checks_the_whole_cache_once(self, tmp_path: pathlib.Path) -> None:
        result = run_script(self.SOURCE, tmp_path)

        assert result == {"set_trace": 1, "run": 1, "runcall": 1, "post_mortem": 1}


class TestConstructionReadsTheRcFiles:
    """`Pdb()` | O(r + L·b) | O(r + L): both rc files are read whole, and the
    breakpoint locations already registered are copied."""

    SOURCE = """
    import bdb, pathlib, os
    for line in range(1, 21):
        bdb.Breakpoint(os.path.abspath('elsewhere.py'), line)
    with_rc = pdb.Pdb(nosigint=True)
    without_rc = pdb.Pdb(nosigint=True, readrc=False)
    emit({'rc': len(with_rc.rcLines), 'no_rc': len(without_rc.rcLines),
          'breaks': sum(len(lines) for lines in with_rc.breaks.values())})
    """

    def test_both_rc_files_are_read_and_breakpoints_copied(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / ".pdbrc").write_text(
            "".join(f"alias a{i} p {i}\n" for i in range(7)), encoding="utf-8"
        )
        work = tmp_path / "work"
        work.mkdir()
        (work / ".pdbrc").write_text(
            "".join(f"alias b{i} p {i}\n" for i in range(5)), encoding="utf-8"
        )

        script = work / "script.py"
        script.write_text(PRELUDE + textwrap.dedent(self.SOURCE), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(script)],
            cwd=work,
            capture_output=True,
            text=True,
            timeout=120,
            stdin=subprocess.DEVNULL,
            # `~` reads USERPROFILE on Windows.
            env={**os.environ, "HOME": str(tmp_path), "USERPROFILE": str(tmp_path)},
            check=False,
        )
        assert result.returncode == 0, result.stderr
        counts = json.loads(result.stdout.strip().splitlines()[-1])

        assert counts == {"rc": 12, "no_rc": 0, "breaks": 20}


TRACED = """
class CountingPdb(pdb.Pdb):
    def __init__(self, commands, **kwargs):
        super().__init__(stdin=io.StringIO(commands), stdout=io.StringIO(), readrc=False,
                         nosigint=True, **kwargs)
        self.events = Counter()

    def trace_dispatch(self, frame, event, arg):
        name = frame.f_code.co_name
        if name in ('step', 'loop', 'caller') and event in ('call', 'line'):
            self.events[name + ':' + event] += 1
            if event == 'line':
                self.events[f'{name}:line+{frame.f_lineno - frame.f_code.co_firstlineno}'] += 1
        return super().trace_dispatch(frame, event, arg)


def step(value):
    doubled = value * 2
    return doubled


def elsewhere():
    return 'never called'


def loop(count):
    total = 0
    for index in range(count):
        total += step(index)
    return total


def caller(count, commands, **kwargs):
    debugger = CountingPdb(commands, **kwargs)
    debugger.set_trace()
    loop(count)
    return dict(debugger.events)


ELSEWHERE = elsewhere.__code__.co_firstlineno + 1
IN_LOOP = loop.__code__.co_firstlineno + 3
IN_STEP = step.__code__.co_firstlineno + 1
"""


class TestWhatRunsTraced:
    """Running between stops: a Python call raises a call event, and lines
    raise events only in frames on the stack at the stop and in functions that
    could stop - from 3.14 those holding a breakpoint, before 3.14 every
    function in a file holding one. The monitoring backend raises each event
    once per location until the next stop, except that a function holding a
    breakpoint raises a call event on every call and its breakpoint line an
    event on every run."""

    CONFIGURATIONS: ClassVar[dict[str, tuple[str, str]]] = {
        "none": ("'continue\\n'", "{}"),
        "same-file": ("f'break {ELSEWHERE}\\ncontinue\\n'", "{}"),
        "other-module": ("f'break {json.__file__}:1\\ncontinue\\n'", "{}"),
        "next": ("'next\\nnext\\ncontinue\\n'", "{}"),
        "monitoring-same-file": (
            "f'break {ELSEWHERE}\\ncontinue\\n'",
            "{'backend': 'monitoring'}",
        ),
        "monitoring-in-loop": (
            "f'break {IN_LOOP}, index < 0\\ncontinue\\n'",
            "{'backend': 'monitoring'}",
        ),
        "settrace-in-loop": ("f'break {IN_LOOP}, index < 0\\ncontinue\\n'", "{}"),
        "monitoring-in-step": (
            "f'break {IN_STEP}, value < 0\\ncontinue\\n'",
            "{'backend': 'monitoring'}",
        ),
        "monitoring-stop-midway": (
            "f'break {IN_LOOP}, index == 50\\ncontinue\\ncontinue\\n'",
            "{'backend': 'monitoring'}",
        ),
    }

    @classmethod
    def events(cls, tmp_path: pathlib.Path, name: str, count: int) -> dict[str, int]:
        """Run one configuration in its own interpreter and return its counts."""
        commands, kwargs = cls.CONFIGURATIONS[name]
        source = TRACED + f"\nemit(caller({count}, {commands}, **{kwargs}))\n"
        return run_script(source, tmp_path)

    @pytest.mark.parametrize("count", [100, 1000])
    def test_no_breakpoints_means_no_events(self, tmp_path: pathlib.Path, count: int) -> None:
        events = self.events(tmp_path, "none", count)

        # Before 3.13 the first stop is itself a line event in caller()
        assert {name: n for name, n in events.items() if not name.startswith("caller:")} == {}

    @pytest.mark.parametrize("count", [100, 1000])
    def test_a_breakpoint_in_the_same_file(self, tmp_path: pathlib.Path, count: int) -> None:
        events = self.events(tmp_path, "same-file", count)

        assert events["step:call"] == count
        expected_lines = 0 if sys.version_info >= (3, 14) else 2 * count
        assert events.get("step:line", 0) == expected_lines, events

    @pytest.mark.parametrize("count", [100, 1000])
    def test_a_breakpoint_in_another_module(self, tmp_path: pathlib.Path, count: int) -> None:
        events = self.events(tmp_path, "other-module", count)

        assert events["step:call"] == count
        assert events.get("step:line", 0) == 0, events

    @pytest.mark.parametrize("count", [100, 1000])
    def test_next_over_a_call_raises_call_events_but_no_callee_lines(
        self, tmp_path: pathlib.Path, count: int
    ) -> None:
        events = self.events(tmp_path, "next", count)

        assert events["step:call"] == count
        assert events.get("step:line", 0) == 0
        assert events.get("loop:line", 0) == 0

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="the monitoring backend is 3.14+")
    @pytest.mark.parametrize("count", [100, 1000])
    def test_monitoring_raises_a_call_event_once_per_function(
        self, tmp_path: pathlib.Path, count: int
    ) -> None:
        events = self.events(tmp_path, "monitoring-same-file", count)

        assert events["step:call"] == 1, events

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="the monitoring backend is 3.14+")
    @pytest.mark.parametrize("count", [100, 1000])
    def test_monitoring_still_sees_a_breakpoint_line_every_time(
        self, tmp_path: pathlib.Path, count: int
    ) -> None:
        monitoring = self.events(tmp_path, "monitoring-in-loop", count)
        settrace = self.events(tmp_path, "settrace-in-loop", count)

        assert monitoring["loop:line+3"] >= count, monitoring
        assert settrace["loop:line+3"] >= count, settrace
        assert settrace["loop:line"] > 2 * count, settrace
        assert monitoring["step:call"] == 1
        assert settrace["step:call"] == count

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="the monitoring backend is 3.14+")
    @pytest.mark.parametrize("count", [100, 1000])
    def test_monitoring_sees_every_call_of_a_function_holding_a_breakpoint(
        self, tmp_path: pathlib.Path, count: int
    ) -> None:
        events = self.events(tmp_path, "monitoring-in-step", count)

        assert events["step:call"] == count, events

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="the monitoring backend is 3.14+")
    @pytest.mark.parametrize("count", [100, 1000])
    def test_monitoring_turns_events_back_on_at_the_next_stop(
        self, tmp_path: pathlib.Path, count: int
    ) -> None:
        events = self.events(tmp_path, "monitoring-stop-midway", count)

        assert events["step:call"] == 2, events


class TestTheStoppedFrameStaysTraced:
    """Frames on the stack at the stop keep raising line events after
    `continue` while any breakpoint is set: a loop in the stopped frame, and
    one in its caller after it returns, raise one per line they run."""

    SOURCE = """
    import json as elsewhere_module

    class Counting(pdb.Pdb):
        lines = Counter()

        def trace_dispatch(self, frame, event, arg):
            if event == 'line' and frame.f_code.co_name in ('stopped_here', 'its_caller'):
                Counting.lines[frame.f_code.co_name] += 1
            return super().trace_dispatch(frame, event, arg)

    def stopped_here(count):
        debugger = scripted(f'break {elsewhere_module.__file__}:1\\ncontinue\\n', cls=Counting)
        debugger.set_trace()
        total = 0
        for index in range(count):
            total += index
        return total

    def its_caller(count):
        stopped_here(0)
        total = 0
        for index in range(count):
            total += index
        return total

    results = {}
    for count in (100, 1000):
        Counting.lines = Counter()
        stopped_here(count)
        its_caller(count)
        results[count] = Counting.lines
    emit(results)
    """

    def test_their_lines_scale_with_the_loop(self, tmp_path: pathlib.Path) -> None:
        result = run_script(self.SOURCE, tmp_path)

        for count in (100, 1000):
            lines = result[str(count)]
            assert lines["stopped_here"] > count, result
            assert lines["its_caller"] > count, result


class TestStepEntersTheCall:
    """`step` stops at the next line, in whatever frame runs it; `next` runs
    the call without stopping in it."""

    SOURCE = """
    class Recording(pdb.Pdb):
        def interaction(self, frame, tb):
            stops.append(frame.f_code.co_name)
            super().interaction(frame, tb)

    def callee():
        inside = 1
        return inside

    def outer(command):
        scripted(f'{command}\\n' * 3 + 'continue\\n', cls=Recording).set_trace()
        callee()
        return 'done'

    results = {}
    for command in ('step', 'next'):
        stops = []
        outer(command)
        results[command] = stops
    emit(results)
    """

    def test_step_stops_in_the_callee_and_next_does_not(self, tmp_path: pathlib.Path) -> None:
        result = run_script(self.SOURCE, tmp_path)

        assert result["step"][0] == "outer"
        assert result["step"][-1] == "callee", result
        assert "callee" not in result["next"], result


class TestEachStopReevaluatesDisplays:
    """Each stop | O(d + x): every `display` of the frame is evaluated again."""

    SOURCE = """
    evaluations = []

    def watched(label):
        evaluations.append(label)
        return len(evaluations)

    def body():
        debugger = scripted('display watched("a")\\ndisplay watched("b")\\n'
                            'next\\nnext\\nnext\\nnext\\ncontinue\\n')
        debugger.set_trace()
        x = 1
        x = 2
        x = 3
        x = 4
        x = 5
        return x

    body()
    emit(evaluations)
    """

    def test_two_displays_over_four_stops(self, tmp_path: pathlib.Path) -> None:
        evaluations = run_script(self.SOURCE, tmp_path)

        assert evaluations == ["a", "b"] * 5


class TestListings:
    """`list` | O(n·b) with 11 lines by default; `longlist` | O(n) over the
    current function; `up` moves one frame."""

    SOURCE = """
    def long_function():
        debugger = scripted('list\\nlonglist\\ncontinue\\n')
        debugger.set_trace()
{padding}
        return debugger.stdout.getvalue()

    def inner():
        level = 'inner'
        debugger = scripted('up\\np level\\ncontinue\\n')
        debugger.set_trace()
        return debugger.stdout.getvalue()

    def outer():
        level = 'outer'
        return inner()

    listing = long_function()
    emit({{'listing': listing, 'up': outer()}})
    """

    def test_list_and_longlist_print_what_they_cover(self, tmp_path: pathlib.Path) -> None:
        padding = "\n".join(f"        value_{i} = {i}" for i in range(26))
        result = run_script(self.SOURCE.format(padding=padding), tmp_path)
        numbered = [
            line
            for line in result["listing"].replace("(Pdb) ", "\n").splitlines()
            if re.match(r"^\s*\d+\s", line)
        ]
        # list prints 11 lines, longlist the whole 30-line function
        assert len(numbered) == 11 + 30, numbered

    def test_up_moves_one_frame(self, tmp_path: pathlib.Path) -> None:
        result = run_script(self.SOURCE.format(padding="        pass"), tmp_path)

        assert "(Pdb) 'outer'" in result["up"]


class TestBreakRechecksTheStack:
    """`break` | O(d·b): during a stop it re-checks every frame, on 3.12.9+
    and 3.13.1+; before, it does not walk the stack."""

    SOURCE = """
    class Counting(pdb.Pdb):
        during_break = None

        def do_break(self, arg, temporary=False):
            self.checked = 0
            super().do_break(arg, temporary)
            Counting.during_break = self.checked

        def break_anywhere(self, frame):
            self.checked = getattr(self, 'checked', 0) + 1
            return super().break_anywhere(frame)

    def never():
        return 0

    def descend(depth):
        if depth:
            return descend(depth - 1)
        scripted('break never\\ncontinue\\n', cls=Counting).set_trace()
        return Counting.during_break

    emit({10: descend(10), 100: descend(100)})
    """

    def test_frames_checked_follow_the_depth(self, tmp_path: pathlib.Path) -> None:
        result = run_script(self.SOURCE, tmp_path)
        walks = sys.version_info >= (3, 13, 1) or (3, 12, 9) <= sys.version_info < (3, 13)

        if walks:
            assert result["100"] - result["10"] == 90, result
        else:
            assert result == {"10": 0, "100": 0}


class TestBreakpointCommands:
    """A condition runs every time its line does; `disable`, `enable`,
    `ignore`, `condition` and `clear` by number act on one breakpoint; `clear`
    with no argument clears them all."""

    SOURCE = """
    checks = []

    def check(index):
        checks.append(index)
        return index == 15

    def looping(commands):
        debugger = scripted(commands)
        debugger.set_trace()
        total = 0
        for index in range(20):
            total += index
        return debugger.stdout.getvalue()

    LINE = looping.__code__.co_firstlineno + 5
    results = {}
    results['condition'] = looping(f'break {LINE}, check(index)\\ncontinue\\np index\\nclear 1\\n'
                                   'continue\\n')
    results['checks'] = checks
    results['disabled'] = looping(f'break {LINE}\\ndisable 2\\ncontinue\\n')
    results['ignored'] = looping(f'break {LINE}\\nignore 3 4\\ncontinue\\np index\\n'
                                 'disable 3\\ncontinue\\n')
    results['recondition'] = looping(f'break {LINE}\\ncondition 4 index == 7\\ncontinue\\n'
                                     'p index\\nclear 4\\ncontinue\\n')
    results['reenabled'] = looping(f'break {LINE}\\ndisable 5\\nenable 5\\ncontinue\\n'
                                   'p index\\nclear 5\\ncontinue\\n')

    import bdb
    cleared = Counter()
    original = pdb.Pdb.clear_all_breaks

    def counting(self):
        cleared['calls'] += 1
        return original(self)

    pdb.Pdb.clear_all_breaks = counting
    sys.stdin = io.StringIO('y\\n')
    looping(f'break {LINE}\\nbreak {LINE + 1}\\nclear\\ncontinue\\n')
    results['cleared'] = cleared['calls']
    results['left'] = [bp for bp in bdb.Breakpoint.bpbynumber if bp is not None]
    emit(results)
    """

    @pytest.fixture(scope="class")
    @classmethod
    def results(cls, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
        return run_script(cls.SOURCE, tmp_path_factory.mktemp("bp"))

    def test_the_condition_runs_each_time_the_line_does(self, results: dict[str, Any]) -> None:
        assert "(Pdb) 15" in results["condition"]
        assert results["checks"] == list(range(16))

    def test_a_disabled_breakpoint_does_not_stop(self, results: dict[str, Any]) -> None:
        assert results["disabled"].count("(Pdb) ") == 3

    def test_ignore_skips_that_many_hits(self, results: dict[str, Any]) -> None:
        assert "(Pdb) 4" in results["ignored"]

    def test_condition_by_number_replaces_the_condition(self, results: dict[str, Any]) -> None:
        assert "(Pdb) 7" in results["recondition"]

    def test_enable_undoes_disable(self, results: dict[str, Any]) -> None:
        assert "(Pdb) 0" in results["reenabled"]

    def test_clear_without_arguments_clears_everything(self, results: dict[str, Any]) -> None:
        assert results["cleared"] == 1
        assert results["left"] == []


class TestInteractCopiesTheNamespace:
    """`interact` | O(g + l): the console gets a copy of the frame's globals
    and locals, so an assignment there does not reach the frame."""

    SOURCE = """
    import code
    seen = {}

    def fake_interact(self, banner=None, exitmsg=None):
        seen['names'] = sorted(self.locals)
        frame = seen.pop('frame')
        seen['expected'] = sorted({*frame.f_globals, *frame.f_locals})
        self.push('local_value = 99')

    code.InteractiveConsole.interact = fake_interact
    global_value = 5

    def frame_under_test():
        local_value = 1
        seen['frame'] = sys._getframe()
        scripted('interact\\ncontinue\\n').set_trace()
        return local_value

    returned = frame_under_test()
    emit({'returned': returned, 'names': seen['names'], 'expected': seen['expected']})
    """

    def test_every_name_is_copied_and_assignments_stay_behind(self, tmp_path: pathlib.Path) -> None:
        result = run_script(self.SOURCE, tmp_path)

        assert result["returned"] == 1
        assert {"local_value", "global_value", "frame_under_test", "pdb"} <= set(result["names"])
        assert result["names"] == result["expected"]


class TestPostMortem:
    """`post_mortem()` | O(c + d + e): the stack is the traceback's entries,
    and on 3.13+ an exception's chain is listed by `exceptions`, up to
    `MAX_CHAINED_EXCEPTION_DEPTH`."""

    SOURCE = """
    import contextlib

    def fail(depth):
        if depth:
            return fail(depth - 1)
        raise ValueError('bottom')

    def chained(links):
        error = KeyError(0)
        for index in range(links):
            try:
                raise error
            except Exception as inner:
                try:
                    raise ValueError(index) from inner
                except ValueError as outer:
                    error = outer
        return error

    def session(target, commands):
        out = io.StringIO()
        sys.stdin = io.StringIO(commands)
        with contextlib.redirect_stdout(out):
            pdb.post_mortem(target)
        return out.getvalue()

    results = {}
    for depth in (10, 50):
        try:
            fail(depth)
        except ValueError as error:
            where = session(error.__traceback__, 'where\\nquit\\n')
            results[f'where-{depth}'] = where.count('fail()')
    if sys.version_info >= (3, 13):
        listing = session(chained(30), 'exceptions\\nquit\\n')
        results['chain'] = len(re.findall(r'^(?:\\(Pdb\\) )?[ >] +\\d+ ', listing, re.M))
        listing = session(chained(1004), 'exceptions\\nquit\\n')
        results['long_chain'] = len(re.findall(r'^(?:\\(Pdb\\) )?[ >] +\\d+ ', listing, re.M))
        results['cap'] = pdb.Pdb.MAX_CHAINED_EXCEPTION_DEPTH
    emit(results)
    """

    @pytest.fixture(scope="class")
    @classmethod
    def results(cls, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
        return run_script(cls.SOURCE, tmp_path_factory.mktemp("pm"))

    def test_the_stack_is_the_traceback(self, results: dict[str, Any]) -> None:
        assert results["where-50"] - results["where-10"] == 40, results

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="exceptions is 3.13+")
    def test_exceptions_lists_the_chain(self, results: dict[str, Any]) -> None:
        assert results["chain"] == 31

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="exceptions is 3.13+")
    def test_a_long_chain_is_cut_at_the_cap(self, results: dict[str, Any]) -> None:
        assert results["cap"] == 999
        assert results["long_chain"] == 999


class TestPmReadsTheLastException:
    """`pm()` debugs `sys.last_exc` from 3.12, `sys.last_traceback` before."""

    SOURCE = """
    import contextlib

    def first():
        raise ValueError('first')

    def second():
        raise KeyError('second')

    for func, name in ((first, 'last_exc'), (second, 'last_traceback')):
        try:
            func()
        except Exception as error:
            setattr(sys, name, error if name == 'last_exc' else error.__traceback__)
    out = io.StringIO()
    sys.stdin = io.StringIO('quit\\n')
    with contextlib.redirect_stdout(out):
        pdb.pm()
    emit(out.getvalue())
    """

    def test_the_right_attribute_is_read(self, tmp_path: pathlib.Path) -> None:
        transcript = run_script(self.SOURCE, tmp_path)

        expected = "first()" if sys.version_info >= (3, 12) else "second()"
        assert expected in transcript, transcript


class TestModuleSetTraceAndBackends:
    """Before 3.14 `breakpoint()` and `pdb.set_trace()` build a `Pdb` on every
    call; from 3.14 they build a `'monitoring'` one once and reuse it, and the
    default backend for a `Pdb` built directly is `'settrace'`."""

    SOURCE = """
    import pdb, sys, json
    built = []
    original_init = pdb.Pdb.__init__

    def counting_init(self, *args, **kwargs):
        built.append(1)
        original_init(self, *args, **kwargs)

    pdb.Pdb.__init__ = counting_init
    ids, backends = [], []
    for enter in (breakpoint, pdb.set_trace):
        enter()
        instance = getattr(pdb.Pdb, '_last_pdb_instance', None)
        ids.append(id(instance) if instance is not None else None)
        backends.append(getattr(instance, 'backend', None))
    result = {'ids': ids, 'backends': backends, 'built': len(built)}
    pdb.Pdb.__init__ = original_init
    if sys.version_info >= (3, 14):
        import io
        mine = pdb.Pdb(stdin=io.StringIO('continue\\ncontinue\\n'), stdout=io.StringIO(),
                       readrc=False)
        mine.set_trace()
        pdb.set_trace(commands=['p 6 * 7'])
        result['reused'] = pdb.Pdb._last_pdb_instance is mine
        result['commands'] = '42' in mine.stdout.getvalue()
        result['default'] = pdb.get_default_backend()
        result['plain'] = pdb.Pdb(readrc=False).backend
        pdb.set_default_backend('monitoring')
        result['changed'] = pdb.Pdb(readrc=False).backend
        pdb.set_default_backend('settrace')
    sys.settrace(None)
    print()
    print(json.dumps(result))
    """

    @pytest.fixture(scope="class")
    @classmethod
    def result(cls, tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
        return run_script(
            cls.SOURCE,
            tmp_path_factory.mktemp("module"),
            stdin="continue\n" * 4,
            prelude=False,
        )

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="instance reuse is 3.14+")
    def test_set_trace_builds_one_monitoring_pdb_and_reuses_it(
        self, result: dict[str, Any]
    ) -> None:
        assert result["built"] == 1
        assert result["ids"][0] is not None
        assert result["ids"][0] == result["ids"][1]
        assert result["backends"] == ["monitoring", "monitoring"]
        assert result["reused"] is True
        assert result["commands"] is True

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="3.14+ reuses the instance")
    def test_before_314_every_call_builds_a_pdb(self, result: dict[str, Any]) -> None:
        assert result["built"] == 2

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="backends are 3.14+")
    def test_the_default_backend_is_settrace_and_can_be_changed(
        self, result: dict[str, Any]
    ) -> None:
        assert result["default"] == "settrace"
        assert result["plain"] == "settrace"
        assert result["changed"] == "monitoring"


class TestSetTraceAsync:
    """`set_trace_async()` (3.14+) stops inside a coroutine."""

    SOURCE = """
    import asyncio, io, json, pdb, sys

    async def work():
        inside = 'coroutine'
        await pdb.set_trace_async()
        return inside

    out = io.StringIO()
    import contextlib
    with contextlib.redirect_stdout(out):
        asyncio.run(work())
    sys.settrace(None)
    print()
    print(json.dumps(out.getvalue()))
    """

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="set_trace_async is 3.14+")
    def test_it_stops_in_the_coroutine(self, tmp_path: pathlib.Path) -> None:
        transcript = run_script(self.SOURCE, tmp_path, stdin="p inside\ncontinue\n", prelude=False)

        assert "'coroutine'" in transcript


class TestRunFunctions:
    """`run()` stops before the first line; `runeval()` and `runcall()` return
    what the code returns."""

    SOURCE = """
    def add(a, b):
        return a + b

    namespace = {}
    runner = scripted('continue\\n')
    runner.run('x = 1', namespace)
    results = {
        'first_stop': runner.stdout.getvalue(),
        'ran': namespace.get('x'),
        'runeval': scripted('continue\\n').runeval('6 * 7', {}),
        'runcall': scripted('continue\\n').runcall(add, 2, 3),
    }
    emit(results)
    """

    def test_values_and_the_first_stop(self, tmp_path: pathlib.Path) -> None:
        result = run_script(self.SOURCE, tmp_path)

        assert "<string>(1)<module>()" in result["first_stop"]
        assert result["ran"] == 1
        assert result["runeval"] == 42
        assert result["runcall"] == 5


class TestConstants:
    """`pdb.Restart` is an exception class; `MAX_CHAINED_EXCEPTION_DEPTH` is
    3.13+."""

    def test_restart_is_an_exception(self) -> None:
        import pdb

        assert issubclass(pdb.Restart, Exception)

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="3.13+")
    def test_the_chain_cap(self) -> None:
        import pdb

        assert pdb.Pdb.MAX_CHAINED_EXCEPTION_DEPTH == 999  # type: ignore[attr-defined]


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
        env={**os.environ, "HOME": str(cwd)},
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess, with closed stdin and an empty
    `HOME`, so the tracing it installs cannot reach the test process and no
    session can wait for input."""

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
        line, source = next((n, s) for n, s in _blocks() if "counted['call'] == 1_000" in s)
        mutated = source.replace("counted['call'] == 1_000", "counted['call'] == 999", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
