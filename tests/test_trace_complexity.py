"""Tests for docs/stdlib/trace.md.

The page prices tracing by its hook: every call event reaches the global hook,
every line of non-ignored code reaches a local one, and what the tracer keeps
is one entry per distinct line, function or caller-callee pair. Those claims
are settled by observation - counting hook calls, reading the frame's
`f_trace`, counting `gc.get_referrers()` calls, and comparing the tracer's
tables with the work done - and by a traced peak that separates O(L) from
O(e) by orders of magnitude. No test here times anything.

Measurement scope:

* Count mode: a loop of 1,000 and 1,000,000 iterations keeps four counted
  lines, the counts sum to the line events (2n + 3), and the local hook is
  called 2n + 4 times (the line events plus the return). The traced peak of
  the 1,000,000-iteration run, after a warm-up run on the same tracer, is under
  200 KB, where one word per event would be 8 MB.
* Modes: the traced frame's `f_trace` is the local hook under `count` and
  `trace`, and `None` under `countfuncs` and `countcallers`; the global hook
  is called once per call under `countfuncs` for a function looping 10,000
  times. `countcallers` over `countfuncs` over `count`/`trace` is observed by
  which table fills. Trace mode prints 101 lines for a 50-iteration loop
  (51 loop headers, 50 bodies) and leaves the traced file in `linecache`;
  the default `Trace()` both counts and prints. With every mode flag false,
  `runfunc()` sees an installed hook still in place and neither run removes
  it.
* First sighting: `gc.get_referrers()` is called at most three times per new
  code object for a plain function and a method, zero times when the same
  functions run again on the same tracer (1,000 calls), and again on a new
  tracer.
* Ignoring: `ignoredirs` on the json package leaves `counts` empty while the
  global hook still runs; `ignoremods=['json']` does not ignore
  `json/decoder.py`, `['decoder', '__init__']` does. The ignore list is
  iterated once per module name across 100 calls. `runctx()` with no
  globals counts nothing for functions `cmd` defines. `countfuncs` and
  `countcallers` record `json.loads` despite `ignoredirs` and a function
  defined in `runctx()` with no globals.
* Runs: `runctx()` traces a thread it starts and `runfunc()` does not; both
  leave `sys.gettrace()` at `None` after one was installed, and `runctx()`
  leaves `threading.gettrace()` at `None` too. `run()` executes in the
  `__main__` module's namespace (a substituted one here); `runfunc()` returns
  the function's result. The constructor does not open `infile`: its
  contents are changed after construction and the new ones are what
  `results()` merges.
* Results: `results().counts` is the tracer's dict, `counter` and
  `calledfuncs` are copies, and a second `results()` with `infile` merges
  the file again (5 becomes 10). `update()` sums counts and unions the
  function and caller tables.
* Reports: `write_results()` on a module of 10 and of 2,000 lines, one line
  executed, writes a `.cover` file with every source line; with
  `show_missing` it calls `_find_executable_linenos` once per file, and
  without it never. `<string>` counts produce no file; without `coverdir`
  the file lands beside the source; `outfile` receives a pickle of the three
  tables; `summary` prints a line per module. A counted file that was
  deleted raises `FileNotFoundError`, and on 3.13+ `ignore_missing_files`
  skips it.
* Command line: `--count --missing --coverdir` writes the counts, and
  `--report --file` rewrites them from the counts file without running the
  program, observed by a marker file the program creates.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* Each hook call is O(1) and the global hook's ignore check is O(m + d) on a
  module's first call: read from Lib/trace.py (`localtrace_count` is one dict
  update, `_Ignore.names` caches per module name). Only the once-per-module
  iteration is observed; m and d are not varied.
* `gc.get_referrers()` being O(H) is the gc page's row, not measured here:
  the tests count the scans, not what each one visits.
* `write_results()` is O(S) per file: compile, tokenize and the per-line
  write are read from Lib/trace.py; the tests vary S and check the output
  length, not time. The F log F, P log P and summary's M log M sorts are
  read from source.
* The CLI rows' bounds follow from the API rows they call; only the
  behaviour is observed.
* Undocumented helpers are not on the page: `Trace.globaltrace_*`,
  `Trace.localtrace_*`, `Trace.file_module_function_of`,
  `CoverageResults.is_ignored_filename`, `CoverageResults.write_results_file`
  and `trace.main` (reached through `python -m trace`).
* Timing mode (`timing=True`), coroutines, generators and exception events
  are not varied.
"""

from __future__ import annotations

import contextlib
import gc
import importlib.util
import io
import json
import linecache
import os
import pathlib
import pickle
import re
import subprocess
import sys
import textwrap
import threading
import trace
import tracemalloc
import types
from collections.abc import Callable, Iterator
from typing import Any, cast

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "trace.md"
EXPECTED_BLOCKS = 8


@pytest.fixture(autouse=True)
def _restore_trace_hooks() -> Iterator[None]:
    """Every run ends with `settrace(None)`; put back whatever was installed."""
    saved = sys.gettrace()
    saved_threading = threading.gettrace()
    yield
    sys.settrace(saved)
    threading.settrace(saved_threading)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def _no_collection_while_tracing() -> Iterator[None]:
    """A finalizer run by a collection inside a traced call is traced too.

    Garbage left by earlier test files (an unclosed shelf, say) would add its
    modules to the counts and the ignore cache, so collect it first.
    """
    gc.collect()
    was_enabled = gc.isenabled()
    gc.disable()
    yield
    if was_enabled:
        gc.enable()


@pytest.fixture(autouse=True)
def _forget_new_linecache_entries() -> Iterator[None]:
    """Printing and reports load sources into `linecache`; drop the ones added here."""
    before = set(linecache.cache)
    yield
    for name in set(linecache.cache) - before:
        linecache.cache.pop(name, None)


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def load_module(path: pathlib.Path, source: str) -> types.ModuleType:
    """A module loaded from a real file, so its globals carry `__file__`."""
    path.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def loop(n: int) -> int:
    total = 0
    for _ in range(n):
        total += 1
    return total


def counts_of(tracer: trace.Trace) -> dict[tuple[str, int], int]:
    """`Trace.counts`, typed as what it holds: (filename, line) keys."""
    return cast("dict[tuple[str, int], int]", tracer.counts)


def own_lines(tracer: trace.Trace, func: Callable[..., Any]) -> dict[int, int]:
    """Counts for `func`'s lines, keyed by offset from its `def`."""
    code = func.__code__
    return {
        line - code.co_firstlineno: hits
        for (name, line), hits in counts_of(tracer).items()
        if name == code.co_filename
    }


class TestCountingKeepsOneEntryPerLine:
    """`Trace(count=True, trace=False)` | O(e + c) | O(L): the hook runs once
    per line event, the table does not grow with repetitions."""

    @pytest.mark.parametrize("n", [1_000, 1_000_000])
    def test_counts_sum_to_the_line_events_over_four_entries(self, n: int) -> None:
        tracer = trace.Trace(count=True, trace=False)

        assert tracer.runfunc(loop, n) == n

        assert own_lines(tracer, loop) == {1: 1, 2: n + 1, 3: n, 4: 1}
        assert len(tracer.counts) == 4

    def test_the_local_hook_runs_once_per_line_event(self) -> None:
        calls = []
        for n in (1_000, 100_000):
            tracer = trace.Trace(count=True, trace=False)
            inner = tracer.localtrace

            def counting(frame: Any, why: str, arg: Any, inner: Any = inner) -> Any:
                calls.append(why)
                return inner(frame, why, arg)

            tracer.localtrace = counting
            calls.clear()
            tracer.runfunc(loop, n)

            assert calls.count("line") == 2 * n + 3
            assert len(calls) == 2 * n + 4, "the line events plus one return"

    def test_the_peak_does_not_follow_the_events(self) -> None:
        tracer = trace.Trace(count=True, trace=False)
        tracer.runfunc(loop, 10)  # warm the code objects and the table

        peak = peak_bytes(lambda: tracer.runfunc(loop, 1_000_000))

        assert peak < 200_000, f"a million line events peaked at {peak} bytes"
        assert len(tracer.counts) == 4


class TestModesInstallDifferentHooks:
    """The modes rows: `count` and `trace` install a line hook, `countfuncs`
    and `countcallers` do not; `countcallers` overrides `countfuncs`, which
    overrides `count` and `trace`."""

    @staticmethod
    def frame_hook() -> Any:
        return sys._getframe().f_trace  # noqa: SLF001

    @pytest.mark.parametrize(
        ("kwargs", "hooked"),
        [
            ({"count": True, "trace": False}, True),
            ({"count": False, "trace": True}, True),
            ({"count": False, "trace": False, "countfuncs": True}, False),
            ({"count": False, "trace": False, "countcallers": True}, False),
        ],
    )
    def test_only_the_line_modes_install_a_line_hook(
        self, kwargs: dict[str, bool], hooked: bool
    ) -> None:
        tracer = trace.Trace(**kwargs)  # type: ignore[arg-type]

        with contextlib.redirect_stdout(io.StringIO()):
            hook = tracer.runfunc(self.frame_hook)

        if hooked:
            assert hook == tracer.localtrace
        else:
            assert hook is None

    def test_countfuncs_calls_the_hook_once_per_call(self) -> None:
        tracer = trace.Trace(count=False, trace=False, countfuncs=True)
        events: list[str] = []
        inner = tracer.globaltrace

        def counting(frame: Any, why: Any, arg: Any) -> Any:
            events.append(why)
            return inner(frame, why, arg)

        tracer.globaltrace = counting
        tracer.runfunc(loop, 10_000)

        assert events == ["call"]
        assert tracer.counts == {}
        assert len(tracer.results().calledfuncs) == 1

    def test_precedence_decides_which_table_fills(self) -> None:
        everything = trace.Trace(count=True, trace=True, countfuncs=True, countcallers=True)
        funcs = trace.Trace(count=True, trace=True, countfuncs=True)

        everything.runfunc(loop, 3)
        funcs.runfunc(loop, 3)

        first = everything.results()
        assert (first.counts, first.calledfuncs) == ({}, {})
        assert len(first.callers) == 1
        second = funcs.results()
        assert (second.counts, second.callers) == ({}, {})
        assert len(second.calledfuncs) == 1

    def test_trace_mode_prints_a_line_per_event(self, tmp_path: pathlib.Path) -> None:
        module = load_module(
            tmp_path / "printed.py", "def repeat(n):\n    for _ in range(n):\n        pass\n"
        )
        assert module.__file__ not in linecache.cache
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            trace.Trace(count=False, trace=True).runfunc(module.repeat, 50)

        printed = [line for line in output.getvalue().splitlines() if "): " in line]
        assert len(printed) == 101
        assert module.__file__ in linecache.cache, "the printed source stays cached"

    @pytest.mark.skipif(sys.platform != "linux", reason="Linux-only")
    def test_the_defaults_count_and_print(self) -> None:
        tracer = trace.Trace()
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            tracer.runfunc(loop, 5)

        assert own_lines(tracer, loop)[3] == 5
        assert sum("): " in line for line in output.getvalue().splitlines()) == 2 * 5 + 3


class TestFirstSightingScansTheHeap:
    """`countfuncs` / `countcallers` | O(H) the first time each function is
    seen: names come from `gc.get_referrers()`, cached per tracer."""

    class Holder:
        def method(self) -> int:
            return 2

    @staticmethod
    def plain() -> int:
        return 1

    def run_many(self, times: int) -> None:
        holder = self.Holder()
        for _ in range(times):
            self.plain()
            holder.method()

    @pytest.fixture
    def referrer_calls(self, monkeypatch: pytest.MonkeyPatch) -> list[int]:
        calls: list[int] = []
        real = gc.get_referrers

        def counting(*objects: Any) -> list[Any]:
            calls.append(1)
            return real(*objects)

        monkeypatch.setattr(trace, "gc", types.SimpleNamespace(get_referrers=counting))
        return calls

    @pytest.mark.parametrize("mode", ["countfuncs", "countcallers"])
    def test_each_function_is_named_once_per_tracer(
        self, mode: str, referrer_calls: list[int]
    ) -> None:
        tracer = trace.Trace(count=False, trace=False, **{mode: True})  # type: ignore[arg-type]

        tracer.runfunc(self.run_many, 1)
        first = len(referrer_calls)
        referrer_calls.clear()
        tracer.runfunc(self.run_many, 1_000)
        again = len(referrer_calls)
        referrer_calls.clear()
        trace.Trace(count=False, trace=False, **{mode: True}).runfunc(  # type: ignore[arg-type]
            self.run_many, 1
        )

        # run_many, plain and method; countcallers also names runfunc, the first caller.
        assert 3 <= first <= 3 * 4, f"{first} scans for the first sighting"
        assert again == 0, f"{again} scans after the functions were seen"
        assert len(referrer_calls) == first, "a new tracer starts with an empty cache"


class TestIgnoring:
    """Ignored modules and code without `__file__`: call events only, no line
    events; `ignoremods` matches base names; the check is cached per module."""

    PACKAGE = os.path.dirname(json.__file__)

    def files(self, tracer: trace.Trace) -> set[str]:
        return {os.path.relpath(name, self.PACKAGE) for name, _ in tracer.counts}

    def test_ignoredirs_removes_the_line_events(self) -> None:
        traced = trace.Trace(count=True, trace=False)
        ignored = trace.Trace(count=True, trace=False, ignoredirs=[self.PACKAGE])
        calls: list[str] = []
        inner = ignored.globaltrace

        def counting(frame: Any, why: Any, arg: Any) -> Any:
            calls.append(why)
            return inner(frame, why, arg)

        ignored.globaltrace = counting
        traced.runfunc(json.loads, "[1, 2]")
        ignored.runfunc(json.loads, "[1, 2]")

        assert "decoder.py" in self.files(traced)
        assert ignored.counts == {}
        assert calls and set(calls) == {"call"}

    def test_ignoremods_matches_base_names_not_dotted_ones(self) -> None:
        dotted = trace.Trace(count=True, trace=False, ignoremods=["json", "json.decoder"])
        bare = trace.Trace(count=True, trace=False, ignoremods=["decoder", "__init__"])

        dotted.runfunc(json.loads, "[1, 2]")
        bare.runfunc(json.loads, "[1, 2]")

        assert {"__init__.py", "decoder.py"} <= self.files(dotted)
        assert bare.counts == {}

    def test_the_ignore_list_is_walked_once_per_module(self) -> None:
        walks: list[int] = []

        class CountingSet(set):  # type: ignore[type-arg]
            def __iter__(self) -> Iterator[Any]:
                walks.append(1)
                return super().__iter__()

        tracer = trace.Trace(count=True, trace=False, ignoremods=["unrelated"])
        tracer.ignore._mods = CountingSet(tracer.ignore._mods)  # type: ignore[attr-defined]  # noqa: SLF001

        def many() -> None:
            for _ in range(100):
                json.loads("[1]")

        tracer.runfunc(many)

        seen = tracer.ignore._ignore  # type: ignore[attr-defined]  # noqa: SLF001
        module_names = set(seen) - {"<string>"}
        assert len(walks) == len(module_names) <= 3, (walks, module_names)

    @pytest.mark.parametrize("mode", ["countfuncs", "countcallers"])
    def test_the_function_modes_skip_the_ignore_check(self, mode: str) -> None:
        tracer = trace.Trace(
            count=False,
            trace=False,
            ignoredirs=[self.PACKAGE],
            **{mode: True},  # type: ignore[arg-type]
        )

        tracer.runfunc(json.loads, "[1, 2]")
        tracer.runctx("def g():\n    return 1\ng()\n")

        results = tracer.results()
        if mode == "countfuncs":
            recorded = {(os.path.basename(path), name) for path, _, name in results.calledfuncs}
        else:
            recorded = {(os.path.basename(path), name) for _, (path, _, name) in results.callers}
        assert ("__init__.py", "loads") in recorded
        assert ("<string>", "g") in recorded

    def test_code_without_file_in_its_globals_is_not_traced(self) -> None:
        source = "def g():\n    return 1\ng()\n"
        bare = trace.Trace(count=True, trace=False)
        with_file = trace.Trace(count=True, trace=False)

        bare.runctx(source)
        with_file.runctx(source, {"__file__": "virtual.py"})

        assert bare.counts == {}
        assert ("<string>", 2) in with_file.counts


class TestRunVariants:
    """`run`, `runctx` and `runfunc`: which threads, which namespace, what
    happens to an installed hook, and what the constructor reads."""

    @staticmethod
    def worker() -> int:
        return 1

    def spawn(self) -> None:
        thread = threading.Thread(target=self.worker)
        thread.start()
        thread.join()

    def worker_line(self) -> tuple[str, int]:
        code = self.worker.__code__
        return code.co_filename, code.co_firstlineno + 2

    def test_runctx_traces_new_threads_and_runfunc_does_not(self) -> None:
        by_func = trace.Trace(count=True, trace=False)
        by_ctx = trace.Trace(count=True, trace=False)

        by_func.runfunc(self.spawn)
        by_ctx.runctx("spawn()", {"spawn": self.spawn})

        assert self.worker_line() not in counts_of(by_func)
        assert counts_of(by_ctx)[self.worker_line()] == 1

    def test_both_leave_no_hook_behind(self) -> None:
        def existing(frame: Any, why: str, arg: Any) -> None:
            return None

        sys.settrace(existing)
        trace.Trace(count=True, trace=False).runfunc(loop, 1)
        after_runfunc = sys.gettrace()
        sys.settrace(existing)
        threading.settrace(existing)
        trace.Trace(count=True, trace=False).runctx("pass")
        after_runctx = (sys.gettrace(), threading.gettrace())
        sys.settrace(None)

        assert after_runfunc is None
        assert after_runctx == (None, None)

    def test_with_every_mode_off_no_hook_is_touched(self) -> None:
        def existing(frame: Any, why: str, arg: Any) -> None:
            return None

        idle = trace.Trace(count=False, trace=False)
        sys.settrace(existing)
        threading.settrace(existing)
        seen = idle.runfunc(sys.gettrace)
        idle.runctx("pass")
        after = (sys.gettrace(), threading.gettrace())
        sys.settrace(None)

        assert seen is existing
        assert after == (existing, existing)
        assert idle.counts == {}

    def test_runfunc_returns_the_result(self) -> None:
        assert trace.Trace(count=True, trace=False).runfunc(loop, 7) == 7

    def test_run_executes_in_main(self, monkeypatch: pytest.MonkeyPatch) -> None:
        main = types.ModuleType("__main__")
        main.__dict__.update({"__file__": "main.py", "loop": loop})
        monkeypatch.setitem(sys.modules, "__main__", main)
        tracer = trace.Trace(count=True, trace=False)

        tracer.run("result = loop(5)")

        assert main.__dict__["result"] == 5
        assert own_lines(tracer, loop)[3] == 5

    def test_the_constructor_does_not_read_infile(self, tmp_path: pathlib.Path) -> None:
        counts_file = tmp_path / "counts"
        counts_file.write_bytes(pickle.dumps(({("x.py", 1): 1}, {}, {})))

        tracer = trace.Trace(count=True, trace=False, infile=str(counts_file))
        counts_file.write_bytes(pickle.dumps(({("x.py", 1): 40}, {}, {})))

        assert tracer.results().counts == {("x.py", 1): 40}


class TestResults:
    """`Trace.results()` | O(L + F + P): `counts` is shared, the rest copied,
    and `infile` merges again on every call; `update()` merges another."""

    def test_counts_is_shared_and_the_rest_are_copies(self) -> None:
        tracer = trace.Trace(count=True, trace=False)
        tracer.runfunc(loop, 3)

        results = tracer.results()

        assert results.counts is tracer.counts
        assert results.counter == tracer.counts
        assert results.counter is not tracer.counts
        assert results.calledfuncs is not tracer._calledfuncs  # type: ignore[attr-defined]  # noqa: SLF001

    def test_every_call_merges_infile_again(self, tmp_path: pathlib.Path) -> None:
        counts_file = tmp_path / "counts"
        counts_file.write_bytes(pickle.dumps(({("x.py", 1): 5}, {}, {})))
        tracer = trace.Trace(count=True, trace=False, infile=str(counts_file))

        tracer.results()
        tracer.results()

        assert tracer.counts == {("x.py", 1): 10}

    def test_update_sums_counts_and_unions_the_tables(self) -> None:
        mine = trace.CoverageResults({("a.py", 1): 2}, {("a.py", "a", "f"): 1})
        other = trace.CoverageResults(
            {("a.py", 1): 3, ("b.py", 4): 1},
            {("b.py", "b", "g"): 1},
            callers={(("a.py", "a", "f"), ("b.py", "b", "g")): 1},
        )

        mine.update(other)

        assert mine.counts == {("a.py", 1): 5, ("b.py", 4): 1}
        assert set(mine.calledfuncs) == {("a.py", "a", "f"), ("b.py", "b", "g")}
        assert len(mine.callers) == 1


class TestWriteResults:
    """`write_results()` | O(L + S + F log F + P log P): one `.cover` per
    counted file holding every source line."""

    @staticmethod
    def module_of(path: pathlib.Path, filler: int) -> types.ModuleType:
        padding = "".join(f"unused_{index} = {index}\n" for index in range(filler))
        return load_module(path, "def one():\n    return 1\n" + padding)

    @pytest.mark.parametrize("filler", [8, 1_998])
    def test_the_report_holds_the_whole_file(self, tmp_path: pathlib.Path, filler: int) -> None:
        module = self.module_of(tmp_path / "subject.py", filler)
        tracer = trace.Trace(count=True, trace=False)
        tracer.runfunc(module.one)
        coverdir = tmp_path / "cover"

        tracer.results().write_results(show_missing=True, coverdir=str(coverdir))

        [report] = coverdir.iterdir()
        lines = report.read_text(encoding="utf-8").splitlines()
        assert len(lines) == filler + 2
        assert lines[1].split(":")[0].strip() == "1"
        assert sum(line.startswith(">>>>>>") for line in lines) == filler + 1

    @pytest.mark.parametrize("show_missing", [True, False])
    def test_show_missing_compiles_each_file_once(
        self, tmp_path: pathlib.Path, show_missing: bool, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        first = self.module_of(tmp_path / "first.py", 3)
        second = self.module_of(tmp_path / "second.py", 3)
        tracer = trace.Trace(count=True, trace=False)
        tracer.runfunc(first.one)
        tracer.runfunc(second.one)
        compiled: list[str] = []
        real = trace._find_executable_linenos  # type: ignore[attr-defined]  # noqa: SLF001

        def counting(filename: str) -> Any:
            compiled.append(filename)
            return real(filename)

        monkeypatch.setattr(trace, "_find_executable_linenos", counting)

        tracer.results().write_results(show_missing=show_missing, coverdir=str(tmp_path / "c"))

        project = {name for name in compiled if name.startswith(str(tmp_path))}
        assert len(project) == len(compiled) == (2 if show_missing else 0), compiled

    def test_string_code_has_no_report_and_reports_default_beside_the_source(
        self, tmp_path: pathlib.Path
    ) -> None:
        module = self.module_of(tmp_path / "beside.py", 0)
        tracer = trace.Trace(count=True, trace=False)
        tracer.runctx("one()", {"__file__": "virtual.py", "one": module.one})
        assert ("<string>", 1) in tracer.counts

        tracer.results().write_results(show_missing=False)

        assert sorted(path.name for path in tmp_path.iterdir() if path.suffix == ".cover") == [
            "beside.cover"
        ]

    def test_outfile_and_summary(self, tmp_path: pathlib.Path) -> None:
        module = self.module_of(tmp_path / "summed.py", 0)
        counts_file = tmp_path / "counts"
        tracer = trace.Trace(count=True, trace=False, outfile=str(counts_file))
        tracer.runfunc(module.one)
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            tracer.results().write_results(summary=True, coverdir=str(tmp_path / "c"))

        counts, calledfuncs, callers = pickle.loads(counts_file.read_bytes())
        assert counts == tracer.counts
        assert (calledfuncs, callers) == ({}, {})
        assert "summed" in output.getvalue()

    def test_a_deleted_file_raises(self, tmp_path: pathlib.Path) -> None:
        results = trace.CoverageResults({(str(tmp_path / "gone.py"), 1): 1})

        with pytest.raises(FileNotFoundError), contextlib.redirect_stderr(io.StringIO()):
            results.write_results(show_missing=False, coverdir=str(tmp_path))

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="added in 3.13")
    def test_ignore_missing_files_skips_it(self, tmp_path: pathlib.Path) -> None:
        results = trace.CoverageResults({(str(tmp_path / "gone.py"), 1): 1})

        results.write_results(
            show_missing=False,
            coverdir=str(tmp_path),
            ignore_missing_files=True,  # type: ignore[call-arg]
        )

        assert list(tmp_path.iterdir()) == []


class TestCommandLine:
    """`python -m trace --count ...` runs and reports; `--report --file`
    reports from saved counts without running anything."""

    def test_count_then_report_without_running(self, tmp_path: pathlib.Path) -> None:
        program = tmp_path / "prog.py"
        marker = tmp_path / "ran"
        program.write_text(
            f"open({str(marker)!r}, 'a').close()\nfor i in range(10):\n    pass\n",
            encoding="utf-8",
        )
        coverdir = tmp_path / "cover"
        counts_file = tmp_path / "counts"
        base = [sys.executable, "-m", "trace", "--coverdir", str(coverdir)]

        subprocess.run(
            [*base, "--count", "--file", str(counts_file), str(program)],
            check=True,
            capture_output=True,
            cwd=tmp_path,
            timeout=120,
        )
        report = coverdir / "prog.cover"
        assert report.read_text(encoding="utf-8").splitlines()[1].split(":")[0].strip() == "11"
        marker.unlink()
        report.unlink()

        subprocess.run(
            [*base, "--report", "--file", str(counts_file)],
            check=True,
            capture_output=True,
            cwd=tmp_path,
            timeout=120,
        )

        assert report.exists()
        assert not marker.exists(), "--report ran the program"


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
    """Each block runs in its own subprocess and working directory, so no
    trace hook, report file or counts file outlives it, and asserts its own
    result."""

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
        line, source = next((n, s) for n, s in _blocks() if "assert by_dir.counts == {}" in s)
        mutated = source.replace("assert by_dir.counts == {}", "assert by_dir.counts != {}", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
