"""Tests for docs/stdlib/profile.md.

The page prices `profile` by the event: every call and return the profiled
code makes is one Python-level call of the profiler's dispatcher, and the
profiler's table holds one entry per distinct function and one caller record
per distinct caller-callee pair. Both are settled by observation - a counting
wrapper around `Profile.dispatcher`, a counting timer, the table's size and
the report's line count - which needs no tolerance. Every profiling run
happens in a subprocess: `profile` installs `sys.setprofile()`, and a profile
function ever installed in the test process would disturb other files'
zero-peak allocation tests.

Measurement scope:

* One dispatch per event: a loop of n calls to an empty function records
  exactly n + 1 `call` and n + 1 `return` dispatches for n = 10 and 10,000,
  while a loop of 10 or 100,000 additions inside one frame records the same
  handful of dispatches for both. n calls of `len()` record n `c_return`
  dispatches and n + 1 `c_call` (the extra one is the `sys.setprofile(None)`
  that ends the run). A generator of k items consumed by a `for` loop records
  k + 1 resumptions as calls, for k = 10 and 1,000. A counting timer passed to
  `Profile()` is read at most twice at construction and exactly twice per
  dispatch during the run.
* Memory follows distinct functions: 10 and 10,000 calls of one function give
  the same number of table entries and caller records, and a `tracemalloc`
  peak over the run that grows less than 2x across 1,000 to 100,000 calls.
  Calling 20 against 2,000 distinct functions grows the table by the
  difference and the peak more than 20x. One function called from 50 distinct
  callers has 50 caller records, and called 50 times from one caller has one.
  The profiler's parallel stack, read from the private `Profile.cur` chain in
  the innermost frame, is the depth plus a constant for depths 10 and 500,
  and a recursive function is one table entry reported as `d/1` calls.
* Reports: `create_stats()` gives one `.stats` entry per table entry, with the
  call count equal to the sum of its callers. `print_stats()` prints one line
  per function: the line count is the same for 10 and 10,000 calls and grows
  by 1,980 lines from 20 to 2,000 distinct functions. `dump_stats()` writes a
  file `pstats.Stats(filename)` loads to the same keys; its size is the same
  for 10 and 10,000 calls and grows with distinct functions.
  `profile.run()` and `profile.runctx()` are asserted to return `None`, to
  print a report without `filename` and to write one, printing nothing, with
  it; `run()` resolves names in `__main__` and `runctx()` in the namespaces
  passed. `Profile.runctx()` returns the profiler and `Profile.run()`
  resolves names in `__main__`.
* `print_stats()`, and `runctx()` through its `sort` argument, are asserted
  to sort by both keys of a tuple on 3.13+ and to raise `KeyError` before
  3.13; the boundary is
  gh-69990, first tagged in v3.13.0 and not backported to 3.12.
* `Profile` is asserted to have no `enable()` or `disable()`; `runcall()`
  returns the function's result, and a second `runcall()` on one instance is
  asserted to raise `AssertionError` for four pairs of first and second
  calls.
* One thread, no nesting: a thread started inside `runcall()` leaves its
  target out of the table. Starting a run while a plain Python profile
  function or an enabled `cProfile.Profile` is installed raises
  `AssertionError`, and no profile function is installed afterwards.
* Calibration: `calibrate(m)` is observed through a counting `range` placed in
  the `profile` module's globals, which the calibration workload looks up:
  3(m + 1) calls covering 303m iterations for m = 10 and 1,000, so the work is
  linear in m. With a timer that advances by one per read, a `bias` of 0.25
  lowers the total recorded time by exactly 0.25 per dispatch, for 10 and
  1,000 calls, whether passed as `bias=` or set on `Profile.bias`; a bias of
  2 makes recorded times negative.
* The default timer is `time.process_time`, asserted by identity. A timing
  test charges less than 0.1 s to a function that sleeps for 0.3 s; waiting
  on I/O is not measured, and follows from the same timer's contract.
* Speed against `cProfile`, a timing test: 20,000 calls of an empty function
  cost more than 4x as much under `profile` as under `cProfile`, and the
  slowdown `profile` imposes on those calls is more than 10x the slowdown it
  imposes on 100,000 additions inside one frame.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The value `calibrate()` returns, and whether a bias set from it makes any
  reported time more accurate. Both depend on the machine and the moment of
  measurement, so only the returned type and the workload's size are
  asserted. That the dispatcher's own time leaks into each event, which is
  what the bias corrects, is read from the calibration comment and
  `trace_dispatch_i()` in Lib/profile.py.
* The f log f term of `print_stats()` and `run()` is the sort in
  Lib/pstats.py's `sort_stats()`; the tests count report lines, not the sort.
  The e term of `create_stats()` and `dump_stats()` is read from
  `snapshot_stats()` copying each callers dictionary, and is not varied
  separately from f in the report tests.
* The O(1) space of `calibrate()` is read from Lib/profile.py: its workload
  calls two functions, so the profiler it builds holds a fixed-size table.
* The failures on a reused profiler and under another profile function are
  `AssertionError` on an interpreter running assertions; under `-O` they
  surface as other exceptions or wrong numbers, and only the assertion form
  is tested.
* Timers returning a sequence, custom dispatchers, and subclasses that
  override the dispatch table are not exercised. Internal methods
  (`trace_dispatch*`, `simulate_call`, `simulate_cmd_complete`, `set_cmd`,
  `snapshot_stats`, `fake_code`, `fake_frame`, `dispatch`) and `main()`, the
  `python -m profile` entry point, are not documented on the page. The
  official inventory lists `Profile.enable()` and `Profile.disable()` under
  the class the two modules share, as cProfile-only; the page covers them by
  saying `profile.Profile` lacks them, which a test asserts.
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

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "profile.md"
EXPECTED_BLOCKS = 7

PRELUDE = """
import collections
import itertools
import json
import profile
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


def counting(profiler):
    \"\"\"Wrap the profiler's dispatcher and count dispatches by event.\"\"\"
    events = collections.Counter()
    original = profiler.dispatcher

    def dispatcher(frame, event, arg):
        events[event] += 1
        return original(frame, event, arg)

    profiler.dispatcher = dispatcher
    return events


def distinct_functions(k):
    \"\"\"A function that calls k distinct functions once each.\"\"\"
    source = "".join(f"def g{i}():\\n    pass\\n" for i in range(k))
    source += "def call_all():\\n" + "".join(f"    g{i}()\\n" for i in range(k))
    namespace = {}
    exec(compile(source, f"<{k} functions>", "exec"), namespace)
    return namespace["call_all"]
"""


def probe(body: str) -> Any:
    """Run `body` after PRELUDE in a fresh interpreter; return its `result`.

    Profiling happens only in the child, so no profile function is ever
    installed in the test process.
    """
    source = PRELUDE + textwrap.dedent(body) + "\nprint(json.dumps(result))\n"
    completed = subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout.splitlines()[-1])


class TestOneDispatchPerEvent:
    """Every call and return is one Python-level dispatch; work inside a frame
    is none. Counted by wrapping `Profile.dispatcher`, so the two shapes -
    many short calls and one long call - separate exactly."""

    def test_each_python_call_is_two_dispatches(self) -> None:
        result = probe(
            """
            result = {}
            for n in (10, 10_000):
                profiler = profile.Profile()
                events = counting(profiler)
                profiler.runcall(many, n)
                result[n] = [events["call"], events["return"]]
            """
        )

        assert result == {"10": [11, 11], "10000": [10_001, 10_001]}

    def test_work_inside_one_frame_is_no_dispatch(self) -> None:
        result = probe(
            """
            result = []
            for n in (10, 100_000):
                profiler = profile.Profile()
                events = counting(profiler)
                assert profiler.runcall(loop, n) == n * (n - 1) // 2
                result.append(sum(events.values()))
            """
        )

        assert result[0] == result[1] <= 4, f"dispatches for 10 and 100,000 additions: {result}"

    def test_builtin_calls_are_two_events(self) -> None:
        result = probe(
            """
            def lengths(n):
                for _ in range(n):
                    len("x")

            profiler = profile.Profile()
            events = counting(profiler)
            profiler.runcall(lengths, 1_000)
            result = [events["c_call"], events["c_return"]]
            """
        )

        assert result == [1_001, 1_000], "one c_call is the setprofile(None) that ends the run"

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
                profiler = profile.Profile()
                profiler.runcall(consume, k)
                profiler.create_stats()
                (entry,) = [v for key, v in profiler.stats.items() if key[2] == "numbers"]
                result[k] = entry[1]
            """
        )

        assert result == {"10": 11, "1000": 1_001}

    def test_the_timer_is_read_twice_per_event(self) -> None:
        result = probe(
            """
            reads = [0]

            def timer():
                reads[0] += 1
                return reads[0]

            profiler = profile.Profile(timer)
            at_construction = reads[0]
            events = counting(profiler)
            profiler.runcall(many, 100)
            result = [at_construction, reads[0] - at_construction, sum(events.values())]
            """
        )
        at_construction, during, dispatches = result

        assert at_construction <= 2
        assert during == 2 * dispatches, f"{during} timer reads for {dispatches} dispatches"


class TestMemoryFollowsDistinctFunctions:
    """`runcall` | O(c) | O(f + e + d): the table has one entry per distinct
    function and one caller record per distinct caller, and the parallel stack
    follows the depth. Call count is held apart from each of them."""

    def test_the_table_does_not_grow_with_calls(self) -> None:
        result = probe(
            """
            result = []
            for n in (10, 10_000):
                profiler = profile.Profile()
                profiler.runcall(many, n)
                profiler.create_stats()
                records = sum(len(v[4]) for v in profiler.stats.values())
                result.append([len(profiler.stats), records])
            """
        )

        assert result[0] == result[1], (
            f"entries and caller records for 10 and 10,000 calls: {result}"
        )

    def test_peak_allocation_does_not_follow_calls(self) -> None:
        result = probe(
            """
            import tracemalloc

            def peak(n):
                profiler = profile.Profile()
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
                profiler = profile.Profile()
                tracemalloc.start()
                try:
                    profiler.runcall(call_all)
                    peak = tracemalloc.get_traced_memory()[1]
                finally:
                    tracemalloc.stop()
                result.append([len(profiler.timings), peak])
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
                profiler = profile.Profile()
                profiler.runcall(function)
                profiler.create_stats()
                (entry,) = [v for k, v in profiler.stats.items() if k[2] == "leaf"]
                result.append([entry[1], len(entry[4])])
            """
        )

        assert result == [[50, 50], [50, 1]]

    def test_the_parallel_stack_follows_depth(self) -> None:
        result = probe(
            """
            def depth(d, profiler, seen):
                if d == 0:
                    node, length = profiler.cur, 0
                    while node:
                        node, length = node[-1], length + 1
                    seen.append(length)
                    return
                depth(d - 1, profiler, seen)

            result = {}
            for d in (10, 500):
                profiler, seen = profile.Profile(), []
                profiler.runcall(depth, d, profiler, seen)
                profiler.create_stats()
                (entry,) = [v for k, v in profiler.stats.items() if k[2] == "depth"]
                result[d] = [seen[0], len(profiler.stats), entry[0], entry[1]]
            """
        )
        shallow, deep = result["10"], result["500"]

        assert deep[0] - shallow[0] == 490, f"stack lengths at depths 10 and 500: {result}"
        assert shallow[1] == deep[1], "a deeper recursion added table entries"
        assert shallow[2:] == [1, 11] and deep[2:] == [1, 501], "primitive and total calls"


class TestReports:
    """`create_stats`, `print_stats` and `dump_stats` are O(f + e), plus the
    sort for `print_stats`: the report has one line per function, and the
    module functions print it or write it."""

    def test_create_stats_counts_calls_from_the_callers(self) -> None:
        result = probe(
            """
            profiler = profile.Profile()
            profiler.runcall(many, 100)
            profiler.create_stats()
            result = [
                len(profiler.stats) == len(profiler.timings),
                all(v[1] == sum(v[4].values()) for v in profiler.stats.values()),
                [v[:2] for k, v in profiler.stats.items() if k[2] == "leaf"],
            ]
            """
        )

        assert result == [True, True, [[100, 100]]]

    def test_the_printed_report_follows_functions_not_calls(self) -> None:
        result = probe(
            """
            import contextlib
            import io

            def lines(function, *args):
                profiler = profile.Profile()
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

    def test_dump_stats_round_trips_through_pstats(self, tmp_path: pathlib.Path) -> None:
        result = probe(
            f"""
            import os
            import pstats

            def dumped(name, function, *args):
                profiler = profile.Profile()
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

    def test_run_prints_a_report_and_returns_none(self) -> None:
        result = probe(
            """
            import __main__
            import contextlib
            import io

            __main__.leaf = leaf
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                returned = profile.run("leaf()")
            result = [returned, "function calls" in output.getvalue()]
            """
        )

        assert result == [None, True]

    def test_run_with_a_filename_writes_instead_of_printing(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "run.prof"
        result = probe(
            f"""
            import contextlib
            import io
            import pstats

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                returned = profile.runctx("helper()", {{"helper": leaf}}, None, {str(path)!r})
            names = {{name for _, _, name in pstats.Stats({str(path)!r}).stats}}
            result = [returned, output.getvalue(), "leaf" in names]
            """
        )

        assert result == [None, "", True]

    def test_profile_runctx_returns_the_profiler_and_run_uses_main(self) -> None:
        result = probe(
            """
            import __main__

            profiler = profile.Profile()
            returned = profiler.runctx("helper()", {"helper": leaf}, None)
            __main__.helper = leaf
            second = profile.Profile()
            second.run("helper()")
            second.create_stats()
            result = [returned is profiler, any(k[2] == "leaf" for k in second.stats)]
            """
        )

        assert result == [True, True]

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
        profiler = profile.Profile()
        profiler.runcall(many, 10)
        result = [
            ordered(lambda: profiler.print_stats(keys)),
            ordered(lambda: profile.runctx("helper()", {"helper": leaf}, None, sort=keys)),
        ]
        """

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="a tuple sort needs 3.13")
    def test_print_stats_takes_a_tuple_of_keys(self) -> None:
        assert probe(self.PRINT_TUPLE) == [True, True]

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="3.13+ accepts the tuple")
    def test_print_stats_rejects_a_tuple_before_313(self) -> None:
        assert probe(self.PRINT_TUPLE) == ["KeyError", "KeyError"]


class TestOneRunPerProfiler:
    """`runcall` returns the function's result and is the only switch: there
    is no `enable()`/`disable()`, and one instance takes one `runcall()`."""

    def test_there_is_no_enable_or_disable(self) -> None:
        result = probe(
            """
            result = [hasattr(profile.Profile, name) for name in ("enable", "disable")]
            """
        )

        assert result == [False, False]

    def test_runcall_returns_the_result(self) -> None:
        assert probe("result = profile.Profile().runcall(loop, 10)") == 45

    def test_a_second_runcall_on_one_instance_fails(self) -> None:
        result = probe(
            """
            def caller():
                leaf()

            result = []
            for first, args, second in [
                (leaf, (), leaf),
                (caller, (), caller),
                (leaf, (), caller),
                (sum, (range(3),), leaf),
            ]:
                profiler = profile.Profile()
                profiler.runcall(first, *args)
                try:
                    profiler.runcall(second)
                except AssertionError:
                    result.append(sys.getprofile() is None)
                else:
                    result.append("second run succeeded")
            """
        )

        assert result == [True, True, True, True]


class TestOneThreadNoNesting:
    """`sys.setprofile()` covers the calling thread only, and a run cannot
    start under another profile function."""

    def test_a_thread_started_during_the_run_is_not_profiled(self) -> None:
        result = probe(
            """
            import threading

            def worker():
                leaf()

            def spawn():
                thread = threading.Thread(target=worker)
                thread.start()
                thread.join()

            profiler = profile.Profile()
            profiler.runcall(spawn)
            names = {name for _, _, name in profiler.timings}
            result = ["spawn" in names, "worker" in names, "leaf" in names]
            """
        )

        assert result == [True, False, False]

    @pytest.mark.parametrize("outer", ["python", "cProfile"])
    def test_a_run_under_another_profile_function_fails(self, outer: str) -> None:
        result = probe(
            f"""
            import cProfile

            outer = {outer!r}
            if outer == "python":
                sys.setprofile(lambda frame, event, arg: None)
            else:
                enclosing = cProfile.Profile()
                enclosing.enable()
            try:
                profile.Profile().runcall(leaf)
            except AssertionError:
                result = ["failed", sys.getprofile() is None]
            else:
                result = ["nested", sys.getprofile() is None]
            finally:
                sys.setprofile(None)
            """
        )

        assert result == ["failed", True]


class TestCalibration:
    """`calibrate(m)` | O(m); `bias` is subtracted from every event's time.
    The calibrated value itself is machine-dependent and not asserted."""

    def test_calibrate_does_work_linear_in_m(self) -> None:
        result = probe(
            """
            import builtins

            calls = []

            def counting_range(*args):
                calls.append(args[0])
                return builtins.range(*args)

            profile.range = counting_range
            result = {}
            for m in (10, 1_000):
                calls.clear()
                value = profile.Profile().calibrate(m)
                result[m] = [len(calls), sum(calls), type(value).__name__]
            del profile.range
            """
        )

        assert result == {"10": [33, 3_030, "float"], "1000": [3_003, 303_000, "float"]}

    BIAS = """
        def run(n, bias, on_class):
            reads = itertools.count()
            if on_class:
                profile.Profile.bias = bias
                profiler = profile.Profile(lambda: next(reads))
                profile.Profile.bias = 0
            else:
                profiler = profile.Profile(lambda: next(reads), bias)
            events = counting(profiler)
            profiler.runcall(many, n)
            profiler.create_stats()
            total = sum(v[2] for v in profiler.stats.values())
            smallest = min(v[2] for v in profiler.stats.values())
            return total, sum(events.values()), smallest
        """

    @pytest.mark.parametrize("on_class", [False, True], ids=["argument", "class"])
    def test_bias_is_subtracted_once_per_event(self, on_class: bool) -> None:
        result = probe(
            textwrap.dedent(self.BIAS)
            + textwrap.dedent(f"""
            result = []
            for n in (10, 1_000):
                plain, dispatches, _ = run(n, 0, False)
                biased, same_dispatches, _ = run(n, 0.25, {on_class})
                assert dispatches == same_dispatches
                result.append([plain - biased, 0.25 * dispatches])
            """)
        )

        for removed, expected in result:
            assert removed == pytest.approx(expected), f"bias removed {removed}, not {expected}"

    def test_a_bias_set_too_high_makes_times_negative(self) -> None:
        result = probe(textwrap.dedent(self.BIAS) + "result = run(100, 2, False)[2]\n")

        assert result < 0


class TestTimers:
    """`Profile()` defaults to `time.process_time`, CPU time."""

    def test_the_default_timer_is_process_time(self) -> None:
        result = probe(
            """
            import time

            result = profile.Profile().timer is time.process_time
            """
        )

        assert result is True

    @pytest.mark.timing
    def test_sleeping_is_not_charged(self) -> None:
        result = probe(
            """
            import time

            def sleeper():
                time.sleep(0.3)

            profiler = profile.Profile()
            profiler.runcall(sleeper)
            profiler.create_stats()
            result = sum(v[3] for k, v in profiler.stats.items() if k[2] == "sleeper")
            """
        )

        assert result < 0.1, f"a 0.3 s sleep was charged {result} s"


class TestSlowerThanCProfile:
    """The dispatch is Python, so short calls cost far more under `profile`
    than under `cProfile`, and far more than work inside one frame does."""

    @pytest.mark.timing
    def test_many_short_calls_cost_more_than_under_cprofile(self) -> None:
        result = probe(
            """
            import cProfile
            import time

            def best(function, repeats=5):
                fastest = None
                for _ in range(repeats):
                    start = time.perf_counter_ns()
                    function()
                    elapsed = time.perf_counter_ns() - start
                    fastest = elapsed if fastest is None else min(fastest, elapsed)
                return fastest

            calls = 20_000
            additions = 100_000
            result = {
                "calls": best(lambda: many(calls)),
                "calls_profile": best(lambda: profile.Profile().runcall(many, calls)),
                "calls_cprofile": best(lambda: cProfile.Profile().runcall(many, calls)),
                "loop": best(lambda: loop(additions)),
                "loop_profile": best(lambda: profile.Profile().runcall(loop, additions)),
            }
            """
        )
        against_cprofile = result["calls_profile"] / result["calls_cprofile"]
        calls_slowdown = result["calls_profile"] / result["calls"]
        loop_slowdown = result["loop_profile"] / result["loop"]

        assert against_cprofile > 4, f"profile against cProfile: x{against_cprofile:.1f}"
        assert calls_slowdown > loop_slowdown * 10, (
            f"slowdown x{calls_slowdown:.1f} on calls, x{loop_slowdown:.1f} on a loop: {result}"
        )


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
    """Each block runs in its own subprocess, so no profile function reaches
    the test process, and asserts its own result."""

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
