"""Tests for docs/stdlib/doctest.md.

The page prices the module in three stages - finding, parsing, running - and
puts the weight on one fact: every `DocTest` copies its globals. Space claims
are settled by traced allocation, which separates the shapes by orders of
magnitude; which work a call does is settled by counting it (DocTests found,
source lines visited, examples run, parser calls); the parse and comparison
bounds are settled by timing at three sizes a decade apart.

Measurement scope:

* `DocTestFinder.find()` over a synthetic module holding 5,000 integers: 100
  one-example docstrings peak over 5x what 10 do, and 100 docstrings over
  50,000 globals peak over 10x what they do over 500, so the space is t·g.
  Every `DocTest.globs` is a distinct dictionary equal to the module's.
* `testmod()` over 200 undocumented functions and one documented one runs 202
  `DocTest`s (the module, every function), against 1 with `exclude_empty=True`;
  the traced peak over 5,000 globals is over 50x larger for the default.
  `doctest.master` is set to `None` before each measured call.
* Class line numbers: with `linecache.getlines` returning a list that counts
  the lines read, 20 documented classes placed after 2,000 comment lines read
  more than 20 x 2,000 lines; 20 documented functions in the same position
  read fewer than 100, and 20 undocumented classes found with
  `exclude_empty=False` read none. Comment lines keep `o` fixed while `n` grows.
* `DocTestRunner.run()` over 40 examples that each print 200,000 characters
  peaks under 2x one such example; one example printing all 8,000,000
  characters peaks over 10x, so the measurement can see a held batch.
  `run()` empties `test.globs` by default and keeps it with
  `clear_globs=False`.
* A counter in the globals shows `REPORT_ONLY_FIRST_FAILURE` running every
  example after a failure and `FAIL_FAST` running none; `DebugRunner` raises
  `DocTestFailure` and `UnexpectedException` carrying their attributes, with
  the globals left in place.
* `testsource()` on a module of 30 documented functions calls
  `DocTestParser.get_doctest` 31 times (the module docstring included) to
  return one of them.
* Timing: `DocTestParser.parse()` over 400, 4,000 and 40,000 examples grows
  under 30x per decade (a linear parse gives 10x, a quadratic one 100x);
  `check_output()` with `ELLIPSIS | NORMALIZE_WHITESPACE` over outputs of
  10,000 to 1,000,000 characters does the same. `output_difference()` with
  `REPORT_NDIFF` on 100 changed lines costs over 5x `REPORT_UDIFF` and
  `REPORT_CDIFF`.
* `DocTestSuite()` builds one case per docstring with examples and runs no
  example while building; running a case leaves the `DocTest`'s globals as
  they were, so it runs twice. `DocFileSuite()` reads its file at build time:
  a later edit to the file does not reach the suite. `testfile()` runs the
  whole file in one namespace; `run_docstring_examples()` does not descend
  into a class's methods.
* From 3.13, `attempted` and `tries` include skipped examples and
  `skipped`/`skips` count them, and a `DocTestSuite` case with every example
  skipped is reported skipped; before 3.13 `attempted` excludes them. Both
  sides are guarded on `sys.version_info`.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* The `o`, `d` and `n·(c + 1)` terms are read from Lib/doctest.py
  (`DocTestFinder._find`, `_find_lineno`), as is the n in
  `run_docstring_examples()`, which reads `f`'s source file through the same
  finder; only t, g and the class scan are varied. The `log t` term is the `tests.sort()` in `find()` and the name sort
  in `summarize()`, not measured.
* `output_difference()` with a diff flag is priced by difflib's own page; only
  the ordering of `REPORT_NDIFF` against the other two is measured, on one
  shape: every line changed by one word.
* `debug()`, `debug_src()` and `debug_script()` start an interactive `pdb`
  session; only `debug_src(..., pm=True)` on a script that does not raise,
  which never enters the debugger, is run.
* The examples' own cost, x, is the caller's, and so is time spent at a
  debugger prompt.
* Scanning a source line is priced at O(1), a cost-model assumption: a
  module with a few very long lines is outside the n terms.
* `DocTestCase` takes its saved copy of the globals at construction on 3.10
  and in `setUp()` from 3.11; only the restored result is asserted.
* `DocTestCase`, `DocFileCase`, `DocFileTest`, `SkipDocTestCase`,
  `DocTestRunner.merge`, `debug_script` and the `_colorize` names doctest
  imports (`ANSIColors`, `can_colorize`) are outside the official API
  inventory; the page names `DocTestSuite`'s cases and `debug_script` without
  giving the rest rows.
"""

from __future__ import annotations

import doctest
import linecache
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import types
import unittest
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "doctest.md"
EXPECTED_BLOCKS = 10


def best_ns(func: Callable[[], Any], repeats: int = 5, inner: int = 1) -> float:
    """Fastest of `repeats` runs, in nanoseconds per call."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        for _ in range(inner):
            func()
        elapsed = (time.perf_counter_ns() - start) / inner
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def make_module(name: str, *, globals_: int, documented: int, undocumented: int = 0) -> Any:
    """A module with `globals_` integers and functions defined in it."""
    module = types.ModuleType(name)
    namespace = module.__dict__
    for index in range(globals_):
        namespace[f"v{index}"] = index
    for index in range(documented):
        exec(f"def d{index}():\n    '''\n    >>> 1\n    1\n    '''\n", namespace)
    for index in range(undocumented):
        exec(f"def u{index}(): pass\n", namespace)
    return module


def discard(text: str) -> None:
    """An `out` for `DocTestRunner.run` that drops the report."""


@pytest.fixture(autouse=True)
def _restore_master() -> Iterator[None]:
    """testmod() and testfile() merge into the module-level `doctest.master`."""
    saved = doctest.master
    yield
    doctest.master = saved


class TestFinderCopiesGlobalsPerDocTest:
    """`DocTestFinder.find()` | O(d + t·g + n) space: each DocTest copies g."""

    def test_space_grows_with_the_docstrings(self) -> None:
        finder = doctest.DocTestFinder()
        few = make_module("few", globals_=5_000, documented=10)
        many = make_module("many", globals_=5_000, documented=100)

        few_peak = peak_bytes(lambda: finder.find(few))
        many_peak = peak_bytes(lambda: finder.find(many))

        assert many_peak > few_peak * 5, f"10x the docstrings: {few_peak} -> {many_peak} bytes"

    def test_space_grows_with_the_globals(self) -> None:
        finder = doctest.DocTestFinder()
        small = make_module("small", globals_=500, documented=100)
        large = make_module("large", globals_=50_000, documented=100)

        small_peak = peak_bytes(lambda: finder.find(small))
        large_peak = peak_bytes(lambda: finder.find(large))

        assert large_peak > small_peak * 10, f"100x the globals: {small_peak} -> {large_peak}"

    def test_every_doctest_holds_its_own_copy(self) -> None:
        module = make_module("copies", globals_=10, documented=3)

        tests = doctest.DocTestFinder().find(module)

        assert len(tests) == 3
        assert len({id(test.globs) for test in tests}) == 3
        for test in tests:
            assert test.globs == module.__dict__
            assert test.globs is not module.__dict__

    def test_results_are_sorted_by_name(self) -> None:
        module = make_module("sorted_names", globals_=0, documented=12)

        names = [test.name for test in doctest.DocTestFinder().find(module)]

        assert names == sorted(names)


class TestTestmodIncludesUndocumentedObjects:
    """`testmod()` passes `exclude_empty=False`: every function and class walked
    becomes a DocTest with its own copy of the globals."""

    @staticmethod
    def _count_runs(monkeypatch: pytest.MonkeyPatch) -> list[str]:
        seen: list[str] = []
        original = doctest.DocTestRunner.run

        def counting(self: doctest.DocTestRunner, test: doctest.DocTest, *args: Any, **kw: Any):
            seen.append(test.name)
            return original(self, test, *args, **kw)

        monkeypatch.setattr(doctest.DocTestRunner, "run", counting)
        return seen

    def test_the_default_runs_a_doctest_per_function(self, monkeypatch: pytest.MonkeyPatch) -> None:
        module = make_module("walked", globals_=0, documented=1, undocumented=200)
        seen = self._count_runs(monkeypatch)

        results = doctest.testmod(module, report=False)

        assert len(seen) == 202, "the module, the documented function and 200 undocumented ones"
        assert results.attempted == 1

    def test_exclude_empty_runs_only_the_documented_one(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        module = make_module("excluded", globals_=0, documented=1, undocumented=200)
        seen = self._count_runs(monkeypatch)

        results = doctest.testmod(module, report=False, exclude_empty=True)

        assert seen == ["excluded.d0"]
        assert results.attempted == 1 and results.failed == 0

    def test_the_default_pays_for_the_copies(self) -> None:
        module = make_module("costly", globals_=5_000, documented=1, undocumented=200)

        doctest.master = None
        default = peak_bytes(lambda: doctest.testmod(module, report=False))
        doctest.master = None
        excluded = peak_bytes(lambda: doctest.testmod(module, report=False, exclude_empty=True))

        assert default > excluded * 50, f"default {default} bytes, exclude_empty {excluded}"


class CountingLines(list[str]):
    """A list of source lines that counts how many are read."""

    reads = 0

    def __iter__(self) -> Iterator[str]:
        for line in super().__iter__():
            CountingLines.reads += 1
            yield line

    def __getitem__(self, index: Any) -> Any:
        CountingLines.reads += 1
        return super().__getitem__(index)


class TestClassLineNumbersScanTheSource:
    """`find()` has an n·c term: a class's docstring line is found by scanning
    the module source from the top, a function's from its own first line."""

    PADDING = 2_000
    COUNT = 20

    def _lines_read(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, body: str, name: str
    ) -> int:
        path = tmp_path / f"{name}.py"
        path.write_text("# padding\n" * self.PADDING + body, encoding="utf-8")
        module = types.ModuleType(name)
        module.__file__ = str(path)
        exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)
        original = linecache.getlines

        def counting(filename: str, module_globals: Any = None) -> list[str]:
            return CountingLines(original(filename, module_globals))

        monkeypatch.setattr(linecache, "getlines", counting)
        CountingLines.reads = 0
        tests = doctest.DocTestFinder().find(module)
        monkeypatch.undo()
        assert len(tests) == self.COUNT
        assert all(test.lineno is not None and test.lineno >= self.PADDING for test in tests)
        return CountingLines.reads

    def test_each_class_scans_from_the_top(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        body = "".join(f"class C{i}:\n    '''\n    >>> 1\n    1\n    '''\n" for i in range(20))

        reads = self._lines_read(tmp_path, monkeypatch, body, "scan_classes")

        assert reads > self.COUNT * self.PADDING, f"{reads} lines read for 20 classes"

    def test_a_function_starts_at_its_own_line(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        body = "".join(f"def f{i}():\n    '''\n    >>> 1\n    1\n    '''\n" for i in range(20))

        reads = self._lines_read(tmp_path, monkeypatch, body, "scan_functions")

        assert reads < 100, f"{reads} lines read for 20 functions"

    def test_an_undocumented_class_is_not_scanned(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        path = tmp_path / "scan_bare.py"
        body = "".join(f"class C{i}: pass\n" for i in range(self.COUNT))
        path.write_text("# padding\n" * self.PADDING + body, encoding="utf-8")
        module = types.ModuleType("scan_bare")
        module.__file__ = str(path)
        exec(compile(path.read_text(encoding="utf-8"), str(path), "exec"), module.__dict__)
        original = linecache.getlines
        monkeypatch.setattr(
            linecache, "getlines", lambda name, g=None: CountingLines(original(name, g))
        )
        CountingLines.reads = 0

        tests = doctest.DocTestFinder(exclude_empty=False).find(module, globs={})

        assert len(tests) == self.COUNT + 1
        assert CountingLines.reads == 0


class TestParserIsLinear:
    """`DocTestParser.parse()` | O(s) | O(s), and what it returns."""

    @pytest.mark.timing
    def test_parse_time_grows_linearly(self) -> None:
        parser = doctest.DocTestParser()
        texts = {n: "Some prose.\n>>> x = 1\n>>> x\n1\n" * n for n in (200, 2_000, 20_000)}

        costs = {n: best_ns(lambda t=text: parser.parse(t), repeats=3) for n, text in texts.items()}

        for low, high in ((200, 2_000), (2_000, 20_000)):
            ratio = costs[high] / costs[low]
            assert ratio < 30, f"10x the text cost x{ratio:.1f}; linear is x10, quadratic x100"

    def test_parse_keeps_the_prose_and_get_examples_drops_it(self) -> None:
        text = "Prose.\n>>> 1 + 1\n2\n\nMore prose.\n>>> print('a')\na\n"
        parser = doctest.DocTestParser()

        pieces = parser.parse(text)
        examples = parser.get_examples(text)

        assert [type(piece) for piece in pieces] == [
            str,
            doctest.Example,
            str,
            doctest.Example,
            str,
        ]
        assert examples == [piece for piece in pieces if isinstance(piece, doctest.Example)]
        assert [example.lineno for example in examples] == [1, 5]
        assert pieces[2] == "\nMore prose.\n"
        assert [example.want for example in examples] == ["2\n", "a\n"]

    def test_get_doctest_copies_the_globals(self) -> None:
        globs = {"a": 1}

        test = doctest.DocTestParser().get_doctest(">>> a\n1\n", globs, "t", "f.py", 3)

        assert test.globs == globs and test.globs is not globs
        assert (test.name, test.filename, test.lineno) == ("t", "f.py", 3)
        assert test.docstring == ">>> a\n1\n"

    def test_a_directive_sets_options_on_one_example(self) -> None:
        text = ">>> 1  # doctest: +ELLIPSIS, -NORMALIZE_WHITESPACE\n1\n>>> 2\n2\n"

        first, second = doctest.DocTestParser().get_examples(text)

        assert first.options == {doctest.ELLIPSIS: True, doctest.NORMALIZE_WHITESPACE: False}
        assert second.options == {}


class TestDocTestAndExample:
    """`DocTest(...)` | O(g); `Example(...)` | O(1), copying only to add a newline."""

    def test_doctest_keeps_the_examples_and_copies_the_globals(self) -> None:
        examples = [doctest.Example("1\n", "1\n")]
        globs = {"x": 1}

        test = doctest.DocTest(examples, globs, "name", None, None, None)

        assert test.examples is examples
        assert test.globs == globs and test.globs is not globs

    def test_example_keeps_strings_that_end_in_a_newline(self) -> None:
        source, want, exc_msg = "f()\n", "1\n", "ValueError: x\n"

        example = doctest.Example(source, want, exc_msg, lineno=4, indent=2)

        assert example.source is source
        assert example.want is want
        assert example.exc_msg is exc_msg
        assert (example.lineno, example.indent, example.options) == (4, 2, {})

    def test_example_adds_a_missing_newline(self) -> None:
        example = doctest.Example("f()", "1", "ValueError: x")

        assert example.source == "f()\n"
        assert example.want == "1\n"
        assert example.exc_msg == "ValueError: x\n"
        assert doctest.Example("f()", "").want == ""


class TestRunnerHoldsOneExamplesOutput:
    """`DocTestRunner.run()` | O(e + g + x) | O(a): output is captured per
    example and discarded once it has been checked."""

    CHUNK = 200_000

    def _test(self, source: str, want: str, repeat: int) -> doctest.DocTest:
        examples = [doctest.Example(source, want) for _ in range(repeat)]
        return doctest.DocTest(examples, {}, "big", None, 0, None)

    def test_the_peak_is_one_example_not_the_sum(self) -> None:
        source = f"print('x' * {self.CHUNK})"
        want = "x" * self.CHUNK + "\n"
        one = self._test(source, want, 1)
        many = self._test(source, want, 40)
        runner = doctest.DocTestRunner(verbose=False)

        one_peak = peak_bytes(lambda: runner.run(one, out=discard))
        many_peak = peak_bytes(lambda: runner.run(many, out=discard))

        assert runner.failures == 0
        assert many_peak < one_peak * 2, f"40 examples peaked at {many_peak}, one at {one_peak}"

    def test_one_large_output_is_visible(self) -> None:
        source = f"print('x' * {self.CHUNK})"
        one = self._test(source, "x" * self.CHUNK + "\n", 1)
        size = self.CHUNK * 40
        whole = self._test(f"print('x' * {size})", "x" * size + "\n", 1)
        runner = doctest.DocTestRunner(verbose=False)

        one_peak = peak_bytes(lambda: runner.run(one, out=discard))
        whole_peak = peak_bytes(lambda: runner.run(whole, out=discard))

        assert runner.failures == 0
        assert whole_peak > one_peak * 10, f"{whole_peak} bytes against {one_peak}"

    def test_run_clears_the_globals_unless_told_not_to(self) -> None:
        parser = doctest.DocTestParser()
        runner = doctest.DocTestRunner(verbose=False)
        kept = parser.get_doctest(">>> y = 2\n", {}, "kept", None, 0)
        cleared = parser.get_doctest(">>> y = 2\n", {}, "cleared", None, 0)

        runner.run(kept, clear_globs=False)
        runner.run(cleared)

        assert kept.globs["y"] == 2
        assert cleared.globs == {}

    def test_the_counters_and_results_accumulate(self) -> None:
        parser = doctest.DocTestParser()
        runner = doctest.DocTestRunner(verbose=False)
        passing = parser.get_doctest(">>> 1\n1\n>>> 2\n2\n", {}, "passing", None, 0)
        failing = parser.get_doctest(">>> 1\n2\n", {}, "failing", None, 0)

        first = runner.run(passing, out=discard)
        second = runner.run(failing, out=discard)

        assert first == doctest.TestResults(0, 2)
        assert (second.failed, second.attempted) == (1, 1)
        assert (runner.tries, runner.failures) == (3, 1)
        assert isinstance(first, tuple) and first.failed == 0 and first.attempted == 2


class TestStoppingAtTheFirstFailure:
    """Only `FAIL_FAST` stops running examples; `DebugRunner` raises."""

    TEXT = ">>> 1\n2\n>>> calls.append(1)\n>>> calls.append(2)\n"

    def _run(self, flags: int) -> list[int]:
        calls: list[int] = []
        test = doctest.DocTestParser().get_doctest(self.TEXT, {"calls": calls}, "t", None, 0)
        doctest.DocTestRunner(optionflags=flags, verbose=False).run(test, out=discard)
        return calls

    def test_report_only_first_failure_still_runs_everything(self) -> None:
        assert self._run(doctest.REPORT_ONLY_FIRST_FAILURE) == [1, 2]

    def test_fail_fast_runs_nothing_after_the_failure(self) -> None:
        assert self._run(doctest.FAIL_FAST) == []

    def test_no_flag_runs_everything(self) -> None:
        assert self._run(0) == [1, 2]

    def test_debug_runner_raises_on_a_mismatch_and_keeps_the_globals(self) -> None:
        test = doctest.DocTestParser().get_doctest(self.TEXT, {"calls": []}, "t", None, 0)

        with pytest.raises(doctest.DocTestFailure) as caught:
            doctest.DebugRunner(verbose=False).run(test)

        assert caught.value.test is test
        assert caught.value.example is test.examples[0]
        assert caught.value.got == "1\n"
        assert test.globs["calls"] == []

    def test_debug_runner_raises_on_an_unexpected_exception(self) -> None:
        test = doctest.DocTestParser().get_doctest(">>> raise KeyError\n", {}, "t", None, 0)

        with pytest.raises(doctest.UnexpectedException) as caught:
            doctest.DebugRunner(verbose=False).run(test)

        assert caught.value.test is test
        assert caught.value.example is test.examples[0]
        assert caught.value.exc_info[0] is KeyError

    def test_debug_runner_clears_the_globals_after_a_pass(self) -> None:
        test = doctest.DocTestParser().get_doctest(">>> x = 2\n", {}, "t", None, 0)

        doctest.DebugRunner(verbose=False).run(test)

        assert test.globs == {}


class TestReporting:
    """The `report_*` hooks, `summarize()` and `set_unittest_reportflags()`."""

    def test_start_and_success_write_only_when_verbose(self) -> None:
        test = doctest.DocTestParser().get_doctest(">>> 1\n1\n", {}, "t", None, 0)
        example = test.examples[0]
        quiet: list[str] = []
        loud: list[str] = []

        doctest.DocTestRunner(verbose=False).report_start(quiet.append, test, example)
        doctest.DocTestRunner(verbose=False).report_success(quiet.append, test, example, "1\n")
        doctest.DocTestRunner(verbose=True).report_start(loud.append, test, example)
        doctest.DocTestRunner(verbose=True).report_success(loud.append, test, example, "1\n")

        assert quiet == []
        assert loud[0].startswith("Trying:\n    1\nExpecting:\n    1\n")
        assert loud[1] == "ok\n"

    def test_failure_reports_the_output_difference(self) -> None:
        test = doctest.DocTestParser().get_doctest(">>> 1\n2\n", {}, "t", None, 0)
        runner = doctest.DocTestRunner(verbose=False)
        written: list[str] = []

        runner.report_failure(written.append, test, test.examples[0], "1\n")

        assert written[0].endswith("Expected:\n    2\nGot:\n    1\n")

    def test_unexpected_exception_reports_the_traceback(self) -> None:
        test = doctest.DocTestParser().get_doctest(">>> f()\n", {}, "t", None, 0)
        written: list[str] = []
        try:
            raise ValueError("boom")
        except ValueError as error:
            assert error.__traceback__ is not None
            exc_info = (ValueError, error, error.__traceback__)

        doctest.DocTestRunner(verbose=False).report_unexpected_exception(
            written.append, test, test.examples[0], exc_info
        )

        assert "Exception raised:" in written[0]
        assert "ValueError: boom" in written[0]

    def test_summarize_aggregates_by_name(self, capsys: pytest.CaptureFixture[str]) -> None:
        parser = doctest.DocTestParser()
        runner = doctest.DocTestRunner(verbose=False)
        for name in ("b", "a", "b"):
            runner.run(parser.get_doctest(">>> 1\n1\n", {}, name, None, 0))

        results = runner.summarize(verbose=True)

        report = capsys.readouterr().out
        assert (results.failed, results.attempted) == (0, 3)
        assert report.index(" in a") < report.index(" in b")
        assert "2 tests in b" in report

    def test_set_unittest_reportflags_returns_the_previous_value(self) -> None:
        original = doctest.set_unittest_reportflags(doctest.REPORT_NDIFF)
        try:
            assert doctest.set_unittest_reportflags(original) == doctest.REPORT_NDIFF
            with pytest.raises(ValueError, match="Only reporting flags"):
                doctest.set_unittest_reportflags(doctest.ELLIPSIS)
        finally:
            doctest.set_unittest_reportflags(original)


class TestOutputChecker:
    """`check_output()` | O(w + a) under every comparison flag;
    `output_difference()` | O(w + a) without a diff flag."""

    @pytest.mark.timing
    def test_check_output_stays_linear_with_the_loose_flags(self) -> None:
        checker = doctest.OutputChecker()
        flags = doctest.ELLIPSIS | doctest.NORMALIZE_WHITESPACE
        costs: dict[int, float] = {}
        for size in (10_000, 100_000, 1_000_000):
            got = "word " * (size // 5) + "end\n"
            want = "word  word ... end\n"
            assert checker.check_output(want, got, flags)
            costs[size] = best_ns(lambda w=want, g=got: checker.check_output(w, g, flags))

        for low, high in ((10_000, 100_000), (100_000, 1_000_000)):
            ratio = costs[high] / costs[low]
            assert ratio < 30, f"10x the output cost x{ratio:.1f}; linear is x10"

    def test_the_flags_change_what_matches(self) -> None:
        checker = doctest.OutputChecker()

        assert checker.check_output("1\n", "True\n", 0)
        assert not checker.check_output("1\n", "True\n", doctest.DONT_ACCEPT_TRUE_FOR_1)
        assert checker.check_output("a\n<BLANKLINE>\n", "a\n\n", 0)
        assert not checker.check_output("a\n<BLANKLINE>\n", "a\n\n", doctest.DONT_ACCEPT_BLANKLINE)
        assert checker.check_output("a  b\n", "a b\n", doctest.NORMALIZE_WHITESPACE)
        assert checker.check_output("[1, ..., 9]\n", "[1, 2, 9]\n", doctest.ELLIPSIS)
        assert not checker.check_output("[1, ..., 9]\n", "[1, 2, 9]\n", 0)

    def test_ignore_exception_detail_matches_on_the_type(self) -> None:
        test = doctest.DocTestParser().get_doctest(
            ">>> raise ValueError('x')\nTraceback (most recent call last):\nValueError: y\n",
            {},
            "t",
            None,
            0,
        )

        strict = doctest.DocTestRunner(verbose=False).run(test, out=discard, clear_globs=False)
        loose = doctest.DocTestRunner(
            optionflags=doctest.IGNORE_EXCEPTION_DETAIL, verbose=False
        ).run(test, out=discard)

        assert strict.failed == 1
        assert loose.failed == 0

    def test_the_plain_difference_lists_both_outputs(self) -> None:
        example = doctest.Example("f()", "a\nb\n")

        text = doctest.OutputChecker().output_difference(example, "a\nc\n", 0)

        assert text == "Expected:\n    a\n    b\nGot:\n    a\n    c\n"

    def test_the_diff_flags_produce_diffs(self) -> None:
        example = doctest.Example("f()", "a\nb\nc\nd\n")
        checker = doctest.OutputChecker()
        got = "a\nB\nc\nd\n"

        assert "unified diff" in checker.output_difference(example, got, doctest.REPORT_UDIFF)
        assert "context diff" in checker.output_difference(example, got, doctest.REPORT_CDIFF)
        assert "ndiff" in checker.output_difference(example, got, doctest.REPORT_NDIFF)

    @pytest.mark.timing
    def test_ndiff_is_the_dearest_diff(self) -> None:
        lines = 100
        example = doctest.Example("f()", "".join(f"line {i} value aaaa\n" for i in range(lines)))
        got = "".join(f"line {i} value bbbb\n" for i in range(lines))
        checker = doctest.OutputChecker()

        udiff = best_ns(lambda: checker.output_difference(example, got, doctest.REPORT_UDIFF))
        cdiff = best_ns(lambda: checker.output_difference(example, got, doctest.REPORT_CDIFF))
        ndiff = best_ns(
            lambda: checker.output_difference(example, got, doctest.REPORT_NDIFF), repeats=1
        )

        assert ndiff > udiff * 5, f"ndiff {ndiff:.0f}ns against udiff {udiff:.0f}ns"
        assert ndiff > cdiff * 5, f"ndiff {ndiff:.0f}ns against cdiff {cdiff:.0f}ns"


class TestOptionFlags:
    """`register_optionflag(name)` | O(1), and the flag groups."""

    def test_registering_twice_returns_the_same_flag(self) -> None:
        name = "DOCS_TEST_FLAG"
        assert name not in doctest.OPTIONFLAGS_BY_NAME
        try:
            flag = doctest.register_optionflag(name)
            assert doctest.register_optionflag(name) == flag
            assert flag & (doctest.COMPARISON_FLAGS | doctest.REPORTING_FLAGS) == 0
        finally:
            doctest.OPTIONFLAGS_BY_NAME.pop(name, None)

    def test_the_groups_are_unions_of_their_flags(self) -> None:
        comparison = (
            doctest.DONT_ACCEPT_TRUE_FOR_1
            | doctest.DONT_ACCEPT_BLANKLINE
            | doctest.NORMALIZE_WHITESPACE
            | doctest.ELLIPSIS
            | doctest.SKIP
            | doctest.IGNORE_EXCEPTION_DETAIL
        )
        reporting = (
            doctest.REPORT_UDIFF
            | doctest.REPORT_CDIFF
            | doctest.REPORT_NDIFF
            | doctest.REPORT_ONLY_FIRST_FAILURE
            | doctest.FAIL_FAST
        )

        assert doctest.COMPARISON_FLAGS == comparison
        assert doctest.REPORTING_FLAGS == reporting


class TestSkippedExamples:
    """Version Notes: from 3.13 skipped examples are counted in `attempted`
    and in `skipped`, and an all-skipped suite case is reported skipped."""

    TEXT = ">>> 1  # doctest: +SKIP\n2\n>>> 1\n1\n"

    def _run(self) -> tuple[doctest.TestResults, doctest.DocTestRunner]:
        test = doctest.DocTestParser().get_doctest(self.TEXT, {}, "t", None, 0)
        runner = doctest.DocTestRunner(verbose=False)
        return runner.run(test, out=discard), runner

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="skipped counts are 3.13+")
    def test_skipped_examples_are_counted(self) -> None:
        results, runner = self._run()

        assert (results.failed, results.attempted) == (0, 2)
        assert results.skipped == 1  # type: ignore[attr-defined]
        assert (runner.tries, runner.skips) == (2, 1)  # type: ignore[attr-defined]

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="3.12 and earlier")
    def test_skipped_examples_are_not_attempted_before_3_13(self) -> None:
        results, runner = self._run()

        assert (results.failed, results.attempted) == (0, 1)
        assert runner.tries == 1

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="SkipTest for suites is 3.13+")
    def test_an_all_skipped_case_is_reported_skipped(self) -> None:
        module = types.ModuleType("all_skipped")
        exec("def f():\n    '''\n    >>> 1  # doctest: +SKIP\n    2\n    '''\n", module.__dict__)
        module.__file__ = "all_skipped.py"
        result = unittest.TestResult()

        doctest.DocTestSuite(module).run(result)

        assert len(result.skipped) == 1 and result.wasSuccessful()


class TestUnittestIntegration:
    """`DocTestSuite()` finds at build time and makes one case per docstring
    with examples; `DocFileSuite()` reads its files at build time."""

    def test_the_suite_has_a_case_per_docstring_with_examples(self) -> None:
        module = make_module("suite_cases", globals_=0, documented=3, undocumented=5)
        module.__file__ = "suite_cases.py"
        exec("def empty():\n    'no examples here'\n", module.__dict__)

        suite = doctest.DocTestSuite(module)

        assert suite.countTestCases() == 3

    def test_building_runs_nothing_and_a_case_runs_twice(self) -> None:
        module = types.ModuleType("suite_runs")
        exec(
            "calls = []\ndef f():\n    '''\n    >>> calls.append(1)\n    >>> marker = 1\n    '''\n",
            module.__dict__,
        )
        module.__file__ = "suite_runs.py"

        suite = doctest.DocTestSuite(module)
        assert module.calls == []
        [case] = list(suite)
        before = dict(case._dt_test.globs)  # type: ignore[attr-defined]

        for _ in range(2):
            result = unittest.TestResult()
            case.run(result)
            assert result.wasSuccessful()

        assert module.calls == [1, 1]
        assert case._dt_test.globs == before  # type: ignore[attr-defined]

    def test_doc_file_suite_reads_the_file_when_built(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "guide.txt"
        path.write_text(">>> 1 + 1\n2\n", encoding="utf-8")

        suite = doctest.DocFileSuite(str(path), module_relative=False)
        path.write_text(">>> 1 + 1\n3\n", encoding="utf-8")
        result = unittest.TestResult()
        suite.run(result)

        assert result.testsRun == 1 and result.wasSuccessful()


class TestConvenienceFunctions:
    """`testfile()`, `run_docstring_examples()`, `script_from_examples()`,
    `testsource()` and `debug_src()`."""

    def test_testfile_shares_one_namespace(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "shared.txt"
        path.write_text("Intro.\n\n>>> value = 7\n\nLater.\n\n>>> value\n7\n", encoding="utf-8")

        results = doctest.testfile(str(path), module_relative=False, report=False)

        assert (results.failed, results.attempted) == (0, 2)

    def test_run_docstring_examples_does_not_recurse(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        namespace: dict[str, Any] = {}
        exec(
            "class K:\n"
            "    '''\n    >>> calls.append('class')\n    '''\n"
            "    def method(self):\n"
            "        '''\n        >>> calls.append('method')\n        '''\n",
            namespace,
        )
        calls: list[str] = []

        doctest.run_docstring_examples(namespace["K"], {"calls": calls}, name="K")

        assert calls == ["class"]
        assert capsys.readouterr().out == ""

    def test_script_from_examples_comments_the_prose(self) -> None:
        script = doctest.script_from_examples("Text.\n>>> x = 1\n>>> x\n1\n")

        assert script == "# Text.\nx = 1\nx\n# Expected:\n## 1\n"

    def test_testsource_parses_every_docstring_to_return_one(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        module = make_module("source_walk", globals_=0, documented=30)
        module.__doc__ = "Module docstring."
        sys.modules["source_walk"] = module
        calls: list[str] = []
        original = doctest.DocTestParser.get_doctest

        def counting(self: doctest.DocTestParser, string: str, *args: Any) -> doctest.DocTest:
            calls.append(string)
            return original(self, string, *args)

        monkeypatch.setattr(doctest.DocTestParser, "get_doctest", counting)
        try:
            script = doctest.testsource(module, "source_walk.d7")
        finally:
            del sys.modules["source_walk"]

        assert script == "1\n# Expected:\n## 1\n"
        assert len(calls) == 31

    def test_debug_src_post_mortem_runs_a_passing_script(self) -> None:
        globs = {"box": []}

        doctest.debug_src(">>> box.append(1)\n", pm=True, globs=globs)

        assert globs["box"] == [1]
        assert set(globs) == {"box"}


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
    """Each block runs in its own subprocess, so `testmod()` sees only that
    block's `__main__`, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "run(doctest.FAIL_FAST) == []" in s)
        mutated = source.replace("run(doctest.FAIL_FAST) == []", "run(doctest.FAIL_FAST) == [1]", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
