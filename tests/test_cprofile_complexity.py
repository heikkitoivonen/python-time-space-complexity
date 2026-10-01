"""Tests for docs/stdlib/cprofile.md.

The page prices `cProfile` by the event: every call and return the profiled
code makes is one call of the profiler's C hook, which reads the timer once,
and the profiler's table holds one entry per distinct function and one caller
record per distinct caller-callee pair. Events are counted with a counting
timer and the table is read through `getstats()`, `.stats` and the printed
report, which needs no tolerance. Every profiling run happens in a
subprocess: from 3.12 the profiler switches `sys.monitoring` events on, and
before that it installs `sys.setprofile()`; either, ever enabled in the test
process, would disturb other files' zero-peak allocation tests.

Measurement scope:

* One timer read per event: a counting timer is read 0 times at
  construction, and 2(n + 1) times for a loop of n calls to an empty function
  with `builtins=False`, for n = 10 and 1,000, against 2 reads for a loop of
  10 or 100,000 additions inside one frame. A function making 1,000 `len()`
  calls gives 2,004 reads with `builtins=True` - two per `len()` call, two
  for the function and two for the `disable()` call that ends the run - and
  1,000 calls of `<built-in method builtins.len>`; with `builtins=False` it
  gives 2 reads and no `len` entry. A generator of k items consumed by a
  `for` loop is k + 1 calls, for k = 10 and 1,000. A recursion of depth d is one entry reported as `d/1`
  calls, for d = 10 and 500.
* Memory follows distinct functions: 10 and 10,000 calls of one function give
  the same table, and a `tracemalloc` peak over the run that grows less than
  2x across 1,000 to 100,000 calls. Calling 20 against 2,000 distinct
  functions grows `getstats()` by 1,980 entries and the peak more than 20x.
  One function called from 50 distinct callers has 50 caller records, and
  called 50 times from one caller has one; 50 closures made by one `def` and
  called once each are one entry of 50 calls; `subcalls=False` leaves every
  callers dictionary empty and every `getstats()` `calls` field `None`. A
  recursion of depth 5,000 peaks more than 20x above one of depth 10, after
  subtracting each depth's unprofiled peak.
* Reports: `getstats()` has one entry per function and lists its callees.
  `snapshot_stats()` leaves the profiler recording, and `create_stats()`,
  `dump_stats()` and `print_stats()` stop it, observed by a call made
  afterwards. `print_stats()` prints the same number of lines for 10 and
  10,000 calls, 1,980 more for 2,000 distinct functions than for 20, and the
  file name of a function compiled from `/nowhere/deep/mod.py` without its
  directory. `dump_stats()` writes a file `pstats.Stats(filename)` loads to
  the same keys, whose size is the same for 10 and 10,000 calls and grows
  with distinct functions. `cProfile.run()` is asserted to return `None` and
  to print a report headed "Ordered by: call count" for `sort="ncalls"`,
  resolving names in `__main__`; `cProfile.runctx()` to return `None` and,
  given a filename, to write the report there and print nothing, resolving
  names in the namespaces passed. The order of the report's rows is
  `pstats`'s, and is not checked here.
* `print_stats()`, and `runctx()` through its `sort` argument, are asserted to
  accept a tuple of two keys on 3.13+, naming both in the report's
  "Ordered by" heading, and to raise `KeyError` before 3.13.
* The command line, `python -m cProfile`, is run on a script: `-s ncalls`
  prints a report headed "Ordered by: call count" with the script's function
  at 10 calls, `-o` writes a file and prints
  nothing, and that file holds the script's function and no call of
  `compile()`. `-m` profiles a module found on the path.
* Switching: two enabled stretches, a `with` block and a `runcall()` add to
  one table; `with` returns the profiler and records nothing after the block.
  `runcall()` returns the function's result, `Profile.runctx()` returns the
  profiler, `Profile.run()` resolves names in `__main__`, and `clear()`
  leaves `getstats()` empty. `cProfile.label()` is asserted on a code object
  and a built-in's name.
* Flags passed to `Profile()`: `Profile(subcalls=False, builtins=False)`
  followed by `runcall()` records no built-in and no caller before 3.14, and
  both on 3.14; passed to `enable()` they hold on every version.
* Threads and nesting: four threads of 1,000 calls started inside
  `runcall()`, and a thread started before `enable()` that makes 500 calls
  while it is on, have their calls recorded with exact counts on 3.12+, and
  none before. A second profiler enabled while one is active raises
  `ValueError` on 3.12+; before 3.12 it starts, and the first records nothing
  afterwards, not even a call made once the second has stopped.
* Timers: a timer counting one per read with `timeunit=0.001` charges each
  empty call exactly 0.001 s. A timing test charges at least 0.25 s of a 0.3 s
  sleep under the default timer and less than 0.1 s under
  `time.process_time`.
* `enable()` and `disable()` visit every thread's stack on 3.12+: a timing
  test parks another thread 10,000 frames deep and finds an enable/disable
  pair more than 3x dearer than with it parked 10 frames deep, and another
  finds the pair more than 3x dearer under 200 frames of distinct 201-statement
  functions than under 200 of one-statement functions, which is the bytecode
  part of s. Their space is O(1): after one pair at the top level, the
  pair's traced peak under 2,000 frames of distinct 201-statement functions
  never run under a profiler is under 2x its peak under 10 one-statement
  frames, on every version.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* That `cProfile` costs less per event than `profile` is the timing test
  `TestSlowerThanCProfile` in tests/test_profile_complexity.py.
* The f log f term of `print_stats()`, `run()`, `runctx()` and the command
  line is the sort in Lib/pstats.py's `sort_stats()`; the tests count report
  lines, not the sort. The e term of `getstats()`, `snapshot_stats()` and
  `dump_stats()` is read from Modules/_lsprof.c's per-entry walk of each
  callee tree and Lib/cProfile.py's `snapshot_stats()`, and is not varied
  apart from f in the report tests. `clear()`'s O(f + e + d) is read from
  `clearEntries()`, which frees every entry, sub-entry and cached frame
  context.
* Table lookups are priced at O(1). The table is a randomised self-adjusting
  binary tree keyed by code object address (Modules/rotatingtree.c), with no
  worst-case bound; profiling one call each of 1,000 to 64,000 distinct
  functions cost the same per function on 3.14, which is the only shape
  measured.
* Before 3.12 `enable()` is O(1), read from Modules/_lsprof.c installing one
  profile function; `disable()` there flushes the still-open frames, which is
  where s comes from, and is not measured.
* Times recorded for calls in other threads on 3.12+: the threads share one
  stack of open calls, so only call counts are asserted. That d then counts
  the open calls of all threads together is read from that shared stack in
  Modules/_lsprof.c; the depth test uses one thread.
* `dump_stats()`'s round trip compares keys only, not call counts or caller
  records.
* Name coverage: the official inventory files these APIs under `profile`, so
  the page audit checks no `cProfile` names and lists all 16 under needs
  classification - `Profile`, its eleven public methods, `label`, `main`,
  `run` and `runctx`. Each has a row on the page.
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import textwrap
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "cprofile.md"
EXPECTED_BLOCKS = 8

PRELUDE = """
import cProfile
import json
import sys


def leaf():
    pass


def many(n):
    for _ in range(n):
        leaf()


def loop(n):
    total = 0
    for i in range(n):
        total += i
    return total


def names(profiler):
    profiler.create_stats()
    return {key[2]: value[1] for key, value in profiler.stats.items()}


def distinct_functions(k):
    \"\"\"A function that calls k distinct functions once each.\"\"\"
    source = "".join(f"def g{i}():\\n    pass\\n" for i in range(k))
    source += "def call_all():\\n" + "".join(f"    g{i}()\\n" for i in range(k))
    namespace = {}
    exec(compile(source, f"<{k} functions>", "exec"), namespace)
    return namespace["call_all"]


def chain(k, lines):
    \"\"\"k distinct nested functions, each `lines` statements long, calling `fn` at the bottom.\"\"\"
    body = "    if fn is None:\\n" + "        x = 1\\n" * lines if lines else ""
    source = "".join(f"def h{i}(fn):\\n{body}    return h{i + 1}(fn)\\n" for i in range(k))
    source += f"def h{k}(fn):\\n    return fn()\\n"
    namespace = {}
    exec(source, namespace)
    return namespace["h0"]


class Ticks:
    \"\"\"A timer that advances by one on every read, and counts the reads.\"\"\"

    def __init__(self):
        self.reads = 0

    def __call__(self):
        self.reads += 1
        return self.reads
"""

LEN = "<built-in method builtins.len>"


def probe(body: str, cwd: pathlib.Path | None = None) -> Any:
    """Run `body` after PRELUDE in a fresh interpreter; return its `result`.

    Profiling happens only in the child, so no profiler is ever enabled in
    the test process.
    """
    source = PRELUDE + textwrap.dedent(body) + "\nprint(json.dumps(result))\n"
    completed = subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        cwd=cwd,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout.splitlines()[-1])


class TestOneTimerReadPerEvent:
    """Every call and return is one event and one timer read; work inside a
    frame is none. Counted with a timer that counts its reads, so many short
    calls and one long call separate exactly."""

    def test_each_python_call_is_two_reads(self) -> None:
        result = probe(
            """
            result = {}
            for n in (10, 1_000):
                ticks = Ticks()
                profiler = cProfile.Profile(ticks)
                at_construction = ticks.reads
                profiler.enable(builtins=False)
                many(n)
                profiler.disable()
                result[n] = [at_construction, ticks.reads]
            """
        )

        assert result == {"10": [0, 22], "1000": [0, 2_002]}

    def test_work_inside_one_frame_is_no_event(self) -> None:
        result = probe(
            """
            result = []
            for n in (10, 100_000):
                ticks = Ticks()
                profiler = cProfile.Profile(ticks)
                profiler.enable(builtins=False)
                assert loop(n) == n * (n - 1) // 2
                profiler.disable()
                result.append(ticks.reads)
            """
        )

        assert result == [2, 2], f"timer reads for 10 and 100,000 additions: {result}"

    def test_builtin_calls_are_events_unless_switched_off(self) -> None:
        result = probe(
            f"""
            def lengths(n):
                for _ in range(n):
                    len("x")

            result = {{}}
            for builtins in (True, False):
                ticks = Ticks()
                profiler = cProfile.Profile(ticks)
                profiler.enable(builtins=builtins)
                lengths(1_000)
                profiler.disable()
                reads = ticks.reads
                result[str(builtins)] = [names(profiler).get({LEN!r}), reads]
            """
        )

        assert result == {"True": [1_000, 2_004], "False": [None, 2]}, (
            "two reads per len() call, two for lengths() and, with builtins, two for disable()"
        )

    def test_each_generator_resumption_is_a_call(self) -> None:
        result = probe(
            """
            def numbers(k):
                for i in range(k):
                    yield i

            def consume(k):
                for _ in numbers(k):
                    pass

            result = {}
            for k in (10, 1_000):
                profiler = cProfile.Profile()
                profiler.runcall(consume, k)
                result[k] = names(profiler)["numbers"]
            """
        )

        assert result == {"10": 11, "1000": 1_001}

    def test_a_recursion_is_one_entry_with_primitive_calls(self) -> None:
        result = probe(
            """
            import pstats

            def depth(d):
                return 0 if d == 0 else depth(d - 1)

            result = {}
            for d in (10, 500):
                profiler = cProfile.Profile()
                profiler.runcall(depth, d - 1)
                by_name = pstats.Stats(profiler).get_stats_profile().func_profiles
                result[d] = by_name["depth"].ncalls
            """
        )

        assert result == {"10": "10/1", "500": "500/1"}


class TestMemoryFollowsDistinctFunctions:
    """`runcall` | O(c) | O(f + e + d): the table has one entry per distinct
    function and one caller record per distinct caller, and the stack of open
    calls follows the depth. Call count is held apart from each of them."""

    def test_the_table_does_not_grow_with_calls(self) -> None:
        result = probe(
            """
            result = []
            for n in (10, 10_000):
                profiler = cProfile.Profile()
                profiler.runcall(many, n)
                profiler.create_stats()
                records = sum(len(v[4]) for v in profiler.stats.values())
                result.append([len(profiler.stats), records])
            """
        )

        assert result[0] == result[1], f"entries and caller records for 10 and 10,000: {result}"

    def test_peak_allocation_does_not_follow_calls(self) -> None:
        result = probe(
            """
            import tracemalloc

            def peak(n):
                profiler = cProfile.Profile()
                tracemalloc.start()
                try:
                    profiler.runcall(many, n)
                    return tracemalloc.get_traced_memory()[1]
                finally:
                    tracemalloc.stop()

            peak(10)
            result = [peak(1_000), peak(100_000)]
            """
        )

        assert result[1] < result[0] * 2, f"100x the calls peaked at {result} bytes"

    def test_the_table_grows_with_distinct_functions(self) -> None:
        result = probe(
            """
            import tracemalloc

            result = []
            for k in (20, 2_000):
                call_all = distinct_functions(k)
                call_all()
                profiler = cProfile.Profile()
                tracemalloc.start()
                try:
                    profiler.runcall(call_all)
                    peak = tracemalloc.get_traced_memory()[1]
                finally:
                    tracemalloc.stop()
                result.append([len(profiler.getstats()), peak])
            """
        )
        (small_entries, small_peak), (large_entries, large_peak) = result

        assert large_entries - small_entries == 1_980
        assert large_peak > small_peak * 20, f"100x the functions peaked at {result}"

    def test_one_caller_record_per_distinct_caller(self) -> None:
        result = probe(
            """
            source = "".join(f"def c{i}():\\n    leaf()\\n" for i in range(50))
            namespace = {"leaf": leaf}
            exec(source, namespace)
            callers = [namespace[f"c{i}"] for i in range(50)]

            def fifty_callers():
                for caller in callers:
                    caller()

            def one_caller():
                for _ in range(50):
                    leaf()

            result = []
            for function in (fifty_callers, one_caller):
                profiler = cProfile.Profile()
                profiler.runcall(function)
                profiler.create_stats()
                (entry,) = [v for k, v in profiler.stats.items() if k[2] == "leaf"]
                result.append([entry[1], len(entry[4])])
            """
        )

        assert result == [[50, 50], [50, 1]]

    def test_closures_of_one_def_are_one_function(self) -> None:
        result = probe(
            """
            def make(i):
                def closure():
                    return i
                return closure

            closures = [make(i) for i in range(50)]

            def call_all():
                for closure in closures:
                    closure()

            profiler = cProfile.Profile()
            profiler.runcall(call_all)
            result = [
                entry.callcount
                for entry in profiler.getstats()
                if getattr(entry.code, "co_name", None) == "closure"
            ]
            """
        )

        assert result == [50]

    def test_subcalls_false_keeps_no_caller_records(self) -> None:
        result = probe(
            """
            profiler = cProfile.Profile()
            profiler.enable(subcalls=False)
            many(10)
            profiler.disable()
            raw = [entry.calls for entry in profiler.getstats()]
            profiler.create_stats()
            result = [
                all(calls is None for calls in raw),
                all(v[4] == {} for v in profiler.stats.values()),
                names(profiler)["leaf"],
            ]
            """
        )

        assert result == [True, True, 10]

    def test_the_open_calls_follow_depth(self) -> None:
        result = probe(
            """
            import tracemalloc

            sys.setrecursionlimit(20_000)

            def depth(d):
                if d:
                    depth(d - 1)

            def peak(d, profiled):
                depth(d)
                tracemalloc.start()
                try:
                    if profiled:
                        cProfile.Profile().runcall(depth, d)
                    else:
                        depth(d)
                    return tracemalloc.get_traced_memory()[1]
                finally:
                    tracemalloc.stop()

            result = [peak(d, True) - peak(d, False) for d in (10, 5_000)]
            """
        )

        assert result[1] > result[0] * 20, f"profiling depth 10 and 5,000 added {result} bytes"


class TestReports:
    """`getstats`, `snapshot_stats`, `create_stats` and `dump_stats` are
    O(f + e), plus the sort for `print_stats`: one entry or line per function.
    The ones built on `create_stats` stop the profiler."""

    def test_getstats_lists_each_function_and_its_callees(self) -> None:
        result = probe(
            """
            profiler = cProfile.Profile()
            profiler.enable(builtins=False)
            many(100)
            profiler.disable()
            entries = {entry.code.co_name: entry for entry in profiler.getstats()}
            callees = [sub.code.co_name for sub in entries["many"].calls]
            result = [sorted(entries), entries["leaf"].callcount, callees, entries["leaf"].calls]
            """
        )

        assert result == [["leaf", "many"], 100, ["leaf"], None]

    def test_only_snapshot_stats_leaves_the_profiler_recording(
        self, tmp_path: pathlib.Path
    ) -> None:
        result = probe(
            f"""
            import contextlib
            import io

            result = {{}}
            for method in ("snapshot_stats", "create_stats", "dump_stats", "print_stats"):
                profiler = cProfile.Profile()
                profiler.enable()
                leaf()
                with contextlib.redirect_stdout(io.StringIO()):
                    if method == "dump_stats":
                        profiler.dump_stats({str(tmp_path / "out.prof")!r})
                    else:
                        getattr(profiler, method)()
                leaf()
                profiler.disable()
                result[method] = names(profiler)["leaf"]
            """
        )

        assert result == {"snapshot_stats": 2, "create_stats": 1, "dump_stats": 1, "print_stats": 1}

    def test_the_printed_report_follows_functions_not_calls(self) -> None:
        result = probe(
            """
            import contextlib
            import io

            def lines(function, *args):
                profiler = cProfile.Profile()
                profiler.runcall(function, *args)
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    profiler.print_stats()
                return len(output.getvalue().splitlines())

            result = [
                lines(many, 10),
                lines(many, 10_000),
                lines(distinct_functions(20)),
                lines(distinct_functions(2_000)),
            ]
            """
        )
        few_calls, many_calls, few_functions, many_functions = result

        assert few_calls == many_calls
        assert many_functions - few_functions == 1_980

    def test_the_printed_report_strips_directories(self) -> None:
        result = probe(
            """
            import contextlib
            import io

            namespace = {}
            exec(compile("def located():\\n    pass\\n", "/nowhere/deep/mod.py", "exec"), namespace)
            profiler = cProfile.Profile()
            profiler.runcall(namespace["located"])
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                profiler.print_stats()
            report = output.getvalue()
            result = ["mod.py:1(located)" in report, "/nowhere/deep" in report]
            """
        )

        assert result == [True, False]

    def test_dump_stats_round_trips_through_pstats(self, tmp_path: pathlib.Path) -> None:
        result = probe(
            f"""
            import os
            import pstats

            def dumped(name, function, *args):
                profiler = cProfile.Profile()
                profiler.runcall(function, *args)
                path = os.path.join({str(tmp_path)!r}, name)
                profiler.dump_stats(path)
                keys = sorted(map(list, profiler.stats))
                loaded = sorted(map(list, pstats.Stats(path).stats))
                return [keys == loaded, os.path.getsize(path)]

            result = [
                dumped("few", many, 10),
                dumped("many", many, 10_000),
                dumped("functions", distinct_functions(2_000)),
            ]
            """
        )
        (few_ok, few_size), (many_ok, many_size), (functions_ok, functions_size) = result

        assert few_ok and many_ok and functions_ok
        assert few_size == many_size
        assert functions_size > few_size * 20

    def test_run_prints_a_report_headed_by_its_sort_and_returns_none(self) -> None:
        result = probe(
            """
            import __main__
            import contextlib
            import io

            __main__.leaf = leaf
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                returned = cProfile.run("leaf()", sort="ncalls")
            report = output.getvalue()
            result = [returned, "function calls" in report, "Ordered by: call count" in report]
            """
        )

        assert result == [None, True, True]

    def test_runctx_with_a_filename_writes_instead_of_printing(
        self, tmp_path: pathlib.Path
    ) -> None:
        path = tmp_path / "run.prof"
        result = probe(
            f"""
            import contextlib
            import io
            import pstats

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                returned = cProfile.runctx("helper()", {{"helper": leaf}}, None, {str(path)!r})
            names = {{name for _, _, name in pstats.Stats({str(path)!r}).stats}}
            result = [returned, output.getvalue(), "leaf" in names]
            """
        )

        assert result == [None, "", True]

    PRINT_TUPLE = """
        import contextlib
        import io

        def ordered(report):
            output = io.StringIO()
            try:
                with contextlib.redirect_stdout(output):
                    report()
            except KeyError:
                return "KeyError"
            return "Ordered by: internal time, call count" in output.getvalue()

        keys = ("tottime", "ncalls")
        profiler = cProfile.Profile()
        profiler.runcall(many, 10)
        result = [
            ordered(lambda: profiler.print_stats(keys)),
            ordered(lambda: cProfile.runctx("helper()", {"helper": leaf}, None, sort=keys)),
        ]
        """

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="a tuple sort needs 3.13")
    def test_print_stats_takes_a_tuple_of_keys(self) -> None:
        assert probe(self.PRINT_TUPLE) == [True, True]

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="3.13+ accepts the tuple")
    def test_print_stats_rejects_a_tuple_before_313(self) -> None:
        assert probe(self.PRINT_TUPLE) == ["KeyError", "KeyError"]


class TestCommandLine:
    """`python -m cProfile [-o outfile] [-s sort] (-m module | script)`: the
    report is printed under the sort's heading, or written to a file; compiling the script is
    not part of the profile."""

    SCRIPT = "def leaf():\n    pass\n\nfor _ in range(10):\n    leaf()\n"

    @staticmethod
    def run(*args: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "cProfile", *args],
            capture_output=True,
            text=True,
            timeout=120,
            stdin=subprocess.DEVNULL,
            cwd=cwd,
            check=True,
        )

    def test_a_script_s_report_is_headed_by_its_sort(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "app.py").write_text(self.SCRIPT, encoding="utf-8")

        report = self.run("-s", "ncalls", "app.py", cwd=tmp_path).stdout

        assert "Ordered by: call count" in report
        assert re.search(r"^\s*10\s.*app\.py:1\(leaf\)$", report, re.MULTILINE), report

    def test_outfile_is_written_and_nothing_printed(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "app.py").write_text(self.SCRIPT, encoding="utf-8")

        completed = self.run("-o", "app.prof", "app.py", cwd=tmp_path)
        result = probe(
            f"""
            import pstats

            stats = pstats.Stats({str(tmp_path / "app.prof")!r}).stats
            result = [
                [v[1] for k, v in stats.items() if k[2] == "leaf"],
                any("compile" in k[2] for k in stats),
            ]
            """
        )

        assert completed.stdout == ""
        assert result == [[10], False]

    def test_a_module_is_profiled_with_m(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "appmodule.py").write_text(self.SCRIPT, encoding="utf-8")

        report = self.run("-m", "appmodule", cwd=tmp_path).stdout

        assert re.search(r"^\s*10\s.*appmodule\.py:1\(leaf\)$", report, re.MULTILINE), report


class TestSwitchingOnAndOff:
    """`enable`/`disable`, `with`, `runcall`, `runctx` and `run` all add to
    one table; `clear` empties it."""

    def test_every_enabled_stretch_adds_to_one_table(self) -> None:
        result = probe(
            """
            profiler = cProfile.Profile()
            for _ in range(2):
                profiler.enable()
                leaf()
                profiler.disable()
            leaf()
            with profiler as entered:
                leaf()
            leaf()
            returned = profiler.runcall(loop, 10)
            result = [names(profiler)["leaf"], entered is profiler, returned]
            """
        )

        assert result == [3, True, 45]

    def test_runctx_returns_the_profiler_and_run_uses_main(self) -> None:
        result = probe(
            """
            import __main__

            profiler = cProfile.Profile()
            returned = profiler.runctx("helper()", {"helper": leaf}, None)
            __main__.helper = leaf
            second = cProfile.Profile()
            second.run("helper()")
            result = [returned is profiler, names(second).get("leaf")]
            """
        )

        assert result == [True, 1]

    def test_clear_discards_everything(self) -> None:
        result = probe(
            """
            profiler = cProfile.Profile()
            profiler.runcall(many, 10)
            before = len(profiler.getstats())
            profiler.clear()
            result = [before, profiler.getstats()]
            """
        )

        assert result[0] > 0
        assert result[1] == []

    def test_label_is_the_report_key(self) -> None:
        import cProfile

        def located() -> None:
            pass

        code = located.__code__

        assert cProfile.label(code) == (code.co_filename, code.co_firstlineno, "located")
        assert cProfile.label("<built-in method builtins.len>") == (
            "~",
            0,
            "<built-in method builtins.len>",
        )


class TestFlagsBelongOnEnable:
    """On 3.14 an argument-less `enable()` - the one `runcall()`, `run()`,
    `runctx()` and `with` call - turns `subcalls` and `builtins` back on;
    passed to `enable()` itself they hold everywhere."""

    CONSTRUCTOR = f"""
        def caller():
            for _ in range(3):
                leaf()
                len("x")

        profiler = cProfile.Profile(subcalls=False, builtins=False)
        profiler.runcall(caller)
        profiler.create_stats()
        result = [
            {LEN!r} in {{k[2] for k in profiler.stats}},
            [len(v[4]) for k, v in profiler.stats.items() if k[2] == "leaf"],
        ]
        """

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="3.14 resets the flags")
    def test_constructor_flags_hold_before_314(self) -> None:
        assert probe(self.CONSTRUCTOR) == [False, [0]]

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="the reset starts in 3.14")
    def test_runcall_resets_constructor_flags_on_314(self) -> None:
        assert probe(self.CONSTRUCTOR) == [True, [1]]

    def test_flags_passed_to_enable_hold(self) -> None:
        result = probe(
            f"""
            profiler = cProfile.Profile()
            profiler.enable(subcalls=False, builtins=False)
            for _ in range(3):
                leaf()
                len("x")
            profiler.disable()
            profiler.create_stats()
            result = [
                {LEN!r} in {{k[2] for k in profiler.stats}},
                [len(v[4]) for k, v in profiler.stats.items() if k[2] == "leaf"],
            ]
            """
        )

        assert result == [False, [0]]


class TestThreadsAndNesting:
    """From 3.12 the events come from `sys.monitoring`: every thread's calls
    are recorded, and a second profiler cannot be enabled under the first."""

    THREADS = """
        import threading

        def spawn():
            threads = [threading.Thread(target=many, args=(1_000,)) for _ in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        profiler = cProfile.Profile()
        profiler.runcall(spawn)
        counts = names(profiler)
        result = [[counts.get("spawn"), counts.get("many"), counts.get("leaf")]]

        go, finished = threading.Event(), threading.Event()

        def waiting():
            go.wait()
            many(500)
            finished.set()

        thread = threading.Thread(target=waiting)
        thread.start()
        profiler = cProfile.Profile()
        profiler.enable()
        go.set()
        finished.wait()
        profiler.disable()
        thread.join()
        counts = names(profiler)
        result.append([counts.get("many"), counts.get("leaf")])
        """

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="sys.monitoring arrives in 3.12")
    def test_every_thread_s_calls_are_recorded(self) -> None:
        assert probe(self.THREADS) == [[1, 4, 4_000], [1, 500]]

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="3.12+ records every thread")
    def test_only_the_enabling_thread_is_recorded_before_312(self) -> None:
        assert probe(self.THREADS) == [[1, None, None], [None, None]]

    NESTED = """
        def after():
            pass

        outer = cProfile.Profile()
        outer.enable()
        try:
            cProfile.Profile().runcall(leaf)
        except ValueError:
            outcome = "ValueError"
        else:
            outcome = "nested"
        after()
        outer.disable()
        result = [outcome, "after" in names(outer)]
        """

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="sys.monitoring arrives in 3.12")
    def test_a_second_profiler_raises(self) -> None:
        assert probe(self.NESTED) == ["ValueError", True]

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="3.12+ raises instead")
    def test_a_second_profiler_takes_over_before_312(self) -> None:
        assert probe(self.NESTED) == ["nested", False]

    def test_switching_allocates_nothing_per_frame(self) -> None:
        result = probe(
            """
            import tracemalloc

            sys.setrecursionlimit(10_000)

            def switch_peak():
                profiler = cProfile.Profile()
                tracemalloc.start()
                try:
                    profiler.enable()
                    profiler.disable()
                    return tracemalloc.get_traced_memory()[1]
                finally:
                    tracemalloc.stop()

            switch_peak()
            result = [chain(10, 0)(switch_peak), chain(2_000, 200)(switch_peak)]
            """
        )

        assert result[1] < result[0] * 2, (
            f"enable+disable under 10 small and 2,000 large frames peaked at {result} bytes"
        )

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 12), reason="sys.monitoring arrives in 3.12")
    def test_switching_visits_every_thread_s_stack(self) -> None:
        result = probe(
            """
            import threading
            import time

            sys.setrecursionlimit(20_000)
            threading.stack_size(64 * 1024 * 1024)

            def parked(d, ready, done):
                if d:
                    return parked(d - 1, ready, done)
                ready.set()
                done.wait()

            def switch_ns():
                fastest = None
                for _ in range(20):
                    profiler = cProfile.Profile()
                    start = time.perf_counter_ns()
                    profiler.enable()
                    profiler.disable()
                    elapsed = time.perf_counter_ns() - start
                    fastest = elapsed if fastest is None else min(fastest, elapsed)
                return fastest

            result = []
            for d in (10, 10_000):
                ready, done = threading.Event(), threading.Event()
                thread = threading.Thread(target=parked, args=(d, ready, done))
                thread.start()
                ready.wait()
                result.append(switch_ns())
                done.set()
                thread.join()
            """
        )

        assert result[1] > result[0] * 3, (
            f"enable+disable with another thread 10 and 10,000 frames deep: {result} ns"
        )


class TestSwitchingCostsWhatIsRunning:
    """From 3.12, `enable()` and `disable()` are O(s): s counts the bytecode of
    the functions on the stack as well as the frames."""

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 12), reason="sys.monitoring arrives in 3.12")
    def test_larger_functions_on_the_stack_cost_more(self) -> None:
        result = probe(
            """
            import time

            sys.setrecursionlimit(10_000)

            def switch_ns():
                fastest = None
                for _ in range(5):
                    profiler = cProfile.Profile()
                    start = time.perf_counter_ns()
                    profiler.enable()
                    profiler.disable()
                    elapsed = time.perf_counter_ns() - start
                    fastest = elapsed if fastest is None else min(fastest, elapsed)
                return fastest

            result = [chain(200, 0)(switch_ns), chain(200, 200)(switch_ns)]
            """
        )

        assert result[1] > result[0] * 3, (
            f"enable+disable under 200 frames of 1 and of 201 statements: {result} ns"
        )


class TestTimers:
    """The default timer is a wall clock; a custom one is read once per event,
    and `timeunit` scales an integer timer to seconds."""

    def test_timeunit_scales_integer_ticks(self) -> None:
        result = probe(
            """
            profiler = cProfile.Profile(Ticks(), timeunit=0.001)
            profiler.enable(builtins=False)
            many(100)
            profiler.disable()
            profiler.create_stats()
            result = [v[2] for k, v in profiler.stats.items() if k[2] == "leaf"]
            """
        )

        assert result == [pytest.approx(0.1)]

    @pytest.mark.timing
    def test_sleeping_is_charged_by_the_default_timer_only(self) -> None:
        result = probe(
            """
            import time

            def sleeper():
                time.sleep(0.3)

            result = []
            for profiler in (cProfile.Profile(), cProfile.Profile(time.process_time)):
                profiler.runcall(sleeper)
                profiler.create_stats()
                result.append(sum(v[3] for k, v in profiler.stats.items() if k[2] == "sleeper"))
            """
        )
        wall, cpu = result

        assert wall >= 0.25, f"a 0.3 s sleep was charged {wall} s by the default timer"
        assert cpu < 0.1, f"a 0.3 s sleep was charged {cpu} s of CPU time"


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
    """Each block runs in its own subprocess, so no profiler reaches the test
    process, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "ncalls == '10000'" in s)
        mutated = source.replace("ncalls == '10000'", "ncalls == '9999'", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
