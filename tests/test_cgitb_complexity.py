"""Tests for docs/stdlib/cgitb.md.

The page prices the module by the report it builds: installing a hook does no
work, and formatting walks every frame of the traceback, showing `context`
source lines and the names on the failing line for each. The module exists on
Python 3.10, 3.11 and 3.12 only, so every runtime test takes the `cgitb`
fixture, which skips from 3.13, and CI's 3.10 to 3.12 jobs are where they run;
availability itself is asserted on every version. The released Lib/cgitb.py
differs between v3.10.19, v3.11.14 and v3.12.12 only in the import-time
DeprecationWarning, the markup of the HTML heading and a `type(...) is dict`
check rewritten as `isinstance`. Size is settled by counting the numbered
source lines a text report shows, which needs no tolerance, and by the length
of the returned report; time by two timing tests.

Measurement scope:

* `cgitb.text()` over a recursion of d frames shows exactly one numbered
  source line per frame at `context=1`, so 100 more frames show 100 more
  lines, and exactly three per frame at `context=3`. The `html()` and
  `text()` reports are measured at 50, 200 and 800 frames: the second
  increment in length is within 3.5x to 4.5x of the first, where a linear
  report gives 4x and a quadratic one 16x. At 200 frames, `context=9`
  makes both reports more than 1.5x longer than `context=1`.
* In timing tests, `html()` over 800 frames costs between 4x and 64x what it
  costs over 50, where linear predicts 16x and quadratic 256x, and
  `context=40` costs more than 1.5x `context=1` over 200 frames. Fastest of
  five.
* `enable()` is observed to replace `sys.excepthook` with a `Hook` carrying
  its arguments and the `sys.stdout` current at the call, and to call neither
  formatter. A `Hook` built inside `contextlib.redirect_stdout()` writes to
  that stream after the redirection ends. `cgitb.handler` is observed in a
  fresh subprocess to write to the import-time `sys.stdout` while a later
  redirection captures nothing.
* `html()` and `text()` return a string and write nothing to stdout or
  stderr. `Hook.handle()` and calling a `Hook` return `None` and write the
  report to `file`; `handle()` with no argument reports `sys.exc_info()`.
* With `display=0`, `handle()` is observed, for both formats, to call the
  formatter once and to write neither the report nor its exception message
  to `file`; with `logdir` and a formatter replaced by one returning a fixed
  string over 10,000 characters long, two calls create two files, each
  holding exactly that string, named `.txt` or `.html` by format.
* A caught exception never reaches an installed hook: the counting
  formatters see no call. A local's value that `cgitb.text()` prints is
  absent from `traceback.format_exception()`'s output.
* Every fenced Python block runs in its own subprocess. The four that import
  `cgitb` run on 3.10 to 3.12 only; the `traceback` one runs everywhere and
  carries the runner's mutation check.

Not settled here:

* The deprecation in 3.11 and the removal in 3.13 come from PEP 594 and the
  3.12 documentation. The import warning is asserted on 3.11 and 3.12 and its
  absence on 3.10; `ModuleNotFoundError` from 3.13 is asserted.
* `enable()` and `Hook()` are O(1) by Lib/cgitb.py: each stores five
  attributes, and `enable()` assigns `sys.excepthook`.
* The bounds exclude the `repr()` of each value shown, which `pydoc`
  truncates only after a custom `__repr__` has run, and the first read of
  each source file into `linecache`. Neither is varied. The exception's
  attributes are listed with `dir()` and are not varied either; the
  measurements use `ValueError`.
* The page prices one source line, each frame's failing statement with the
  names in it, and the exception message as O(1). Line length, the physical
  lines of a failing statement, which `scanvars()` tokenizes to its end, the
  number of names in it, the message length, and frames from
  different source files are not varied. Frames whose source is unavailable
  show no lines, and a file shorter than `context` shows fewer; the
  exact-count tests use frames from this file. `context=0` is outside the page's
  bounds, which take c as at least 1.
* `reset()`, `small()`, `strong()`, `grey()`, `lookup()` and `scanvars()` are
  undocumented helpers of the formatters. The page covers the four documented
  functions and the `Hook` class that `enable()` installs.
"""

from __future__ import annotations

import contextlib
import importlib
import importlib.util
import io
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import traceback
import warnings
from collections.abc import Callable, Iterator
from types import TracebackType
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "cgitb.md"
EXPECTED_BLOCKS = 5
REMOVED = sys.version_info >= (3, 13)

ExcInfo = tuple[type[BaseException], BaseException, TracebackType]


def best_ns(func: Callable[[], Any], repeats: int = 5) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        elapsed = time.perf_counter_ns() - start
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def recurse(depth: int) -> None:
    if depth == 0:
        raise ValueError("bottom")
    recurse(depth - 1)


def exc_info(depth: int) -> ExcInfo:
    """The `sys.exc_info()` of an exception raised `depth` calls down."""
    try:
        recurse(depth)
    except ValueError:
        info = sys.exc_info()
        assert info[0] is not None and info[1] is not None and info[2] is not None
        return info[0], info[1], info[2]
    raise AssertionError("recurse() did not raise")


def source_lines(report: str) -> int:
    """Numbered source lines in a text report."""
    return sum(1 for line in report.splitlines() if re.match(r" *[0-9]+ ", line))


def test_the_module_exists_only_before_3_13() -> None:
    assert (importlib.util.find_spec("cgitb") is not None) == (not REMOVED)


def test_importing_it_warns_from_3_11() -> None:
    result = subprocess.run(
        [sys.executable, "-W", "error::DeprecationWarning", "-c", "import cgitb"],
        capture_output=True,
        text=True,
        timeout=60,
        stdin=subprocess.DEVNULL,
        check=False,
    )

    if REMOVED:
        assert "ModuleNotFoundError" in result.stderr
    elif sys.version_info >= (3, 11):
        assert "DeprecationWarning" in result.stderr
    else:
        assert result.returncode == 0, result.stderr


@pytest.fixture
def cgitb() -> Iterator[Any]:
    if REMOVED:
        pytest.skip("version: cgitb was removed in Python 3.13")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        yield importlib.import_module("cgitb")


@pytest.fixture
def formatter_calls(cgitb: Any, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Count calls to `cgitb.html` and `cgitb.text`, which `Hook.handle` looks up
    as module globals on every call."""
    calls: list[str] = []
    for name in ("html", "text"):
        original = getattr(cgitb, name)

        def counting(info: Any, context: int = 5, *, _name: str = name, _f: Any = original) -> str:
            calls.append(_name)
            return _f(info, context)

        monkeypatch.setattr(cgitb, name, counting)
    return calls


@pytest.fixture
def restore_excepthook() -> Iterator[None]:
    original = sys.excepthook
    yield
    sys.excepthook = original


class TestEnablingOnlyInstalls:
    """`enable()` | O(1) | O(1): it replaces `sys.excepthook` and formats
    nothing until an uncaught exception reaches the hook."""

    @pytest.mark.usefixtures("restore_excepthook")
    def test_enable_installs_a_hook_and_formats_nothing(
        self, cgitb: Any, formatter_calls: list[str], tmp_path: pathlib.Path
    ) -> None:
        out = io.StringIO()

        with contextlib.redirect_stdout(out):
            result = cgitb.enable(display=0, logdir=str(tmp_path), context=2, format="text")

        hook: Any = sys.excepthook
        assert result is None
        assert isinstance(hook, cgitb.Hook)
        assert (hook.display, hook.logdir, hook.context, hook.format) == (
            0,
            str(tmp_path),
            2,
            "text",
        )
        assert hook.file is out
        assert formatter_calls == []
        assert out.getvalue() == ""

    @pytest.mark.usefixtures("restore_excepthook")
    def test_a_caught_exception_never_reaches_the_hook(
        self, cgitb: Any, formatter_calls: list[str]
    ) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            cgitb.enable(format="text")

        try:
            recurse(3)
        except ValueError:
            pass

        assert formatter_calls == []
        assert out.getvalue() == ""

    def test_a_hook_keeps_the_stdout_current_when_it_was_built(self, cgitb: Any) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            hook = cgitb.Hook(format="text")

        hook(*exc_info(2))

        assert "ValueError" in out.getvalue()

    def test_handler_writes_to_the_import_time_stdout(self, cgitb: Any) -> None:
        del cgitb  # the claim needs a fresh import, so it runs in a subprocess
        script = textwrap.dedent(
            """
            import contextlib, io, warnings
            warnings.simplefilter('ignore', DeprecationWarning)
            import cgitb
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                try:
                    1 / 0
                except ZeroDivisionError:
                    cgitb.handler()
            assert captured.getvalue() == '', captured.getvalue()
            """
        )

        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        assert "ZeroDivisionError" in result.stdout
        assert result.stdout.lstrip().startswith("<!--: spam"), "the report is HTML"


class TestReportGrowsWithFramesAndContext:
    """`html()`, `text()`, `handler()`, `Hook.handle()` | O(d·c) | O(d·c):
    every frame shows c source lines and the names on its failing line."""

    def test_each_frame_shows_one_line_at_context_1(self, cgitb: Any) -> None:
        shallow = source_lines(cgitb.text(exc_info(10), 1))
        deep = source_lines(cgitb.text(exc_info(110), 1))

        assert deep - shallow == 100

    def test_each_frame_shows_c_lines(self, cgitb: Any) -> None:
        info = exc_info(10)

        one = source_lines(cgitb.text(info, 1))
        three = source_lines(cgitb.text(info, 3))

        assert three == 3 * one, (one, three)

    @pytest.mark.parametrize("name", ["html", "text"])
    def test_the_report_grows_linearly_with_depth(self, cgitb: Any, name: str) -> None:
        formatter = getattr(cgitb, name)
        lengths = [len(formatter(exc_info(depth))) for depth in (50, 200, 800)]

        growth = (lengths[2] - lengths[1]) / (lengths[1] - lengths[0])

        assert 3.5 < growth < 4.5, f"{name}: lengths {lengths}, increment ratio {growth:.2f}"

    @pytest.mark.parametrize("name", ["html", "text"])
    def test_the_report_grows_with_context(self, cgitb: Any, name: str) -> None:
        formatter = getattr(cgitb, name)
        info = exc_info(200)

        narrow, wide = len(formatter(info, 1)), len(formatter(info, 9))

        assert wide > narrow * 1.5, f"{name}: context 1 gave {narrow}, context 9 gave {wide}"

    @pytest.mark.timing
    def test_time_is_linear_in_depth(self, cgitb: Any) -> None:
        shallow, deep = exc_info(50), exc_info(800)
        cgitb.html(shallow)
        cgitb.html(deep)

        ratio = best_ns(lambda: cgitb.html(deep)) / best_ns(lambda: cgitb.html(shallow))

        assert 4 < ratio < 64, f"16x the frames cost x{ratio:.1f}; linear is x16, quadratic x256"

    @pytest.mark.timing
    def test_time_grows_with_context(self, cgitb: Any) -> None:
        info = exc_info(200)
        cgitb.html(info, 40)

        narrow = best_ns(lambda: cgitb.html(info, 1))
        wide = best_ns(lambda: cgitb.html(info, 40))

        assert wide > narrow * 1.5, f"context 40 cost {wide:.0f}ns against {narrow:.0f}ns"


class TestFormattersReturnAndHooksWrite:
    """`html()` and `text()` return the report and write nothing; a `Hook`
    writes it to `file` and returns `None`."""

    @pytest.mark.parametrize("name", ["html", "text"])
    def test_a_formatter_writes_nothing(
        self, cgitb: Any, name: str, capsys: pytest.CaptureFixture[str]
    ) -> None:
        report = getattr(cgitb, name)(exc_info(2))

        assert isinstance(report, str) and "ValueError" in report
        assert capsys.readouterr() == ("", "")

    def test_html_is_html_and_text_is_not(self, cgitb: Any) -> None:
        info = exc_info(2)

        assert "<body" in cgitb.html(info)
        assert "<body" not in cgitb.text(info)

    def test_calling_a_hook_writes_and_returns_none(self, cgitb: Any) -> None:
        out = io.StringIO()
        hook = cgitb.Hook(file=out, format="text")

        assert hook(*exc_info(2)) is None
        assert "bottom" in out.getvalue()

    def test_handle_without_info_reports_the_current_exception(self, cgitb: Any) -> None:
        out = io.StringIO()
        hook = cgitb.Hook(file=out, format="text")

        try:
            int("not a number")
        except ValueError:
            assert hook.handle() is None

        assert "invalid literal" in out.getvalue()


class TestDisplayZeroStillFormats:
    """`Hook.handle()`: the report is built even with `display=0`; `logdir`
    gets one new file per call."""

    @pytest.mark.parametrize("fmt", ["text", "html"])
    def test_display_0_formats_but_does_not_write_the_report(
        self, cgitb: Any, formatter_calls: list[str], fmt: str
    ) -> None:
        out = io.StringIO()
        hook = cgitb.Hook(display=0, file=out, format=fmt)

        hook.handle(exc_info(2))

        assert formatter_calls == [fmt]
        assert "bottom" not in out.getvalue()
        assert "A problem occurred" in out.getvalue()

    @pytest.mark.parametrize(("fmt", "suffix"), [("text", ".txt"), ("html", ".html")])
    def test_logdir_gets_the_whole_report_in_a_new_file_per_call(
        self,
        cgitb: Any,
        tmp_path: pathlib.Path,
        monkeypatch: pytest.MonkeyPatch,
        fmt: str,
        suffix: str,
    ) -> None:
        report = "".join(f"line {index}\n" for index in range(1_250))
        assert len(report) > 10_000
        monkeypatch.setattr(cgitb, fmt, lambda info, context=5: report)
        out = io.StringIO()
        hook = cgitb.Hook(display=0, logdir=str(tmp_path), file=out, format=fmt)

        hook.handle(exc_info(2))
        hook.handle(exc_info(2))

        names = sorted(os.listdir(tmp_path))
        assert len(names) == 2 and all(name.endswith(suffix) for name in names)
        for name in names:
            assert (tmp_path / name).read_text(encoding="utf-8") == report
        assert "line 0" not in out.getvalue()


class TestTracebackAsTheReplacement:
    """`traceback.format_exception()` shows no variable values."""

    @staticmethod
    def three_frames() -> BaseException:
        def inner(value: str) -> None:
            raise KeyError(value)

        def middle() -> None:
            local_value = "sentinel-0451"
            inner(local_value)

        try:
            middle()
        except KeyError as error:
            return error
        raise AssertionError("middle() did not raise")

    def test_no_local_value_is_shown(self) -> None:
        text = "".join(traceback.format_exception(self.three_frames()))

        assert "local_value" in text
        assert "sentinel-0451" not in text.replace("KeyError: 'sentinel-0451'", "")

    def test_cgitb_shows_the_value(self, cgitb: Any) -> None:
        error = self.three_frames()

        report = cgitb.text((type(error), error, error.__traceback__))

        assert "local_value = 'sentinel-0451'" in report


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
        [sys.executable, "-W", "ignore::DeprecationWarning", str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and asserts its own result. The
    blocks that import `cgitb` need 3.10, 3.11 or 3.12."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        assert sum("import cgitb" in source for _, source in blocks) == EXPECTED_BLOCKS - 1

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            if "import cgitb" in source and REMOVED:
                continue
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == (1 if REMOVED else EXPECTED_BLOCKS)
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "render_error" in s)
        mutated = source.replace("startswith('<pre>Traceback')", "startswith('<pre>Error')", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
