"""Tests for docs/stdlib/pipes.md.

The page prices the Python process's share of a pipeline: keeping the list
of steps, building the `/bin/sh` command line from it, and the one end of an
`open()` pipeline that Python reads or writes. The commands' own work is
outside every bound. The step-list rows are settled by timing 1,000 calls at
two template sizes and by traced allocation; the command-line rows by timing
and tracing `copy()` with `os.system()` replaced by a recorder, so that only
the building is measured; where the data goes, the temporary files and the
wait status by running real pipelines under `/bin/sh`. The module exists on
Python 3.10, 3.11 and 3.12 only, so every test that touches it takes the
`pipes` fixture, which skips from 3.13; run them with one of those
interpreters. Lib/pipes.py differs between v3.10.19, v3.11.14 and v3.12.12
only in the import-time DeprecationWarning added in 3.11: no bound moves.

Measurement scope:

* Nothing runs before `open()` or `copy()`: with `os.system()`, `os.popen()`
  and `tempfile.mkstemp()` replaced by functions that raise, `Template()`,
  `append()` and `prepend()` of file kinds, `clone()`, `reset()` and
  `debug()` all succeed.
* `append()` and `prepend()` are timed as 1,000 calls onto a copy of a
  template holding 1,000 and 100,000 `'--'` steps: 100x the steps costs
  `prepend()` more than 10x, where linear gives about 67x, and `append()`
  under 3x. `reset()` of 1,000,000 steps costs more than 10x what 10,000 do,
  where linear gives 100x; the steps are shared with the template they were
  cloned from, so the time is dropping the references, not freeing the
  tuples. `clone()`'s traced peak at 100,000 steps is more than 20x that at
  1,000.
* `append()` raises `ValueError` for an unknown kind, a `'.-'` step, a step
  after a `'-.'` step, and a file kind whose command lacks `$IN` or `$OUT`,
  and `TypeError` for a command that is not a string; `prepend()` raises for
  a `'-.'` step and a step before a `'.-'` step.
* `clone()` gets the debug flag, and a step added to either template after
  the clone changes only that template's command line.
* Building the command line: with `os.system()` recording, `copy()` over
  1,000, 4,000 and 16,000 steps of a 60-character command costs more than 8x
  per 4x step, where linear gives 4x and quadratic 16x; at 2,000 and 32,000
  steps of a 3-character command the traced peak rises between 8x and 40x,
  where linear gives 16x. `open()` passes `os.popen()` the same command line
  that `copy()` passes `os.system()`, so the two share the bound. With
  `debug(True)` the command line is printed and starts with `set -x; `, and
  under `/bin/sh` the shell writes a `+ ` trace to its standard error.
* `copy()` of a 4,000,000-character file through `tr` has a traced peak under
  100 KB and writes the whole file. That bounds the allocation; that the data
  never reaches the process at all is read from the source, where `copy()`
  is one `os.system()` call. `copy()` returns 0 for a pipeline that
  succeeds, and a wait status whose exit code is 3, without raising, for
  `exit 3`. The status is the shell's last command's: exit code 1 for a pipe
  whose last step fails, 0 for one whose first step fails, and 0 when the
  last step fails after a temporary file, where `rm -f` runs last.
* `open()` returns while its pipeline waits: a step that looks for a file the
  test creates only after `open()` has returned finds it. Closing what
  `open(path, 'w')` returned waits: a step that sleeps 0.3 seconds before
  writing has written the file when the `with` block ends. Reading 4,000,000
  characters through `open(path, 'r')` peaks over 4 MB; the O(b) time of
  reading and writing that end is the file object's and is not timed. With
  no steps,
  `open()` returns a built-in text file without calling `os.popen()`.
  Closing returns `None` after `cat` and a wait status whose exit code is 3
  after `{ cat; exit 3; }`.
  `open()` raises `ValueError` for a mode other than `'r'` or `'w'`, for
  `'r'` on a template ending with `'-.'`, and for `'w'` on one starting with
  `'.-'`.
* Temporary files: `tempfile.mkstemp()` is called once for a `'ff'` step
  followed by a `'--'` step, and not at all for two `'--'` steps. The file it
  made no longer exists once `copy()` returns, nor once what `open()`
  returned is closed. A step after a temporary file starts after the step
  before it ends: the earlier step sleeps 0.3 seconds and then creates a
  marker, and the later step sees the marker.
* The kind constants are the six strings; `pipes.quote` is `shlex.quote`.
* The import warns on 3.11 and 3.12, not on 3.10, and raises
  `ModuleNotFoundError` from 3.13.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* The O(n²) build follows from `makepipeline()` extending the command line
  with `cmdlist = cmdlist + ' |\\n' + cmd`, which copies the line so far
  once per step, and from the `rm -f` line growing the same way per
  temporary file; read from Lib/pipes.py at v3.12.12. Only `'--'` steps of a
  fixed command length are varied in the timing; command length and the
  number of temporary files are not.
* `quote()` is O(k) by the `shlex` page's bound; it is the same function and
  is not measured here.
* Starting the shell, the commands' work and the time spent waiting for them
  are outside every bound and are not measured.
* `/bin/sh` is what `os.system()` and `os.popen()` run on Unix; tests that
  run a pipeline skip on Windows, which has no `/bin/sh`. The rest have no
  platform-specific subject. CI runs only the timing tests on 3.10 to 3.12,
  and none of them starts a shell, so the pipeline tests are run by hand on
  one of those versions; they have been run on Linux, not on macOS.
* The deprecation in 3.11 and the removal in 3.13 come from the 3.12
  documentation and PEP 594.
* The page-scoped audit checks no names on 3.13 and later, which have no
  `pipes`. Run on 3.12 it checks nine names - the module, `Template` and its
  `append`, `clone`, `copy`, `debug`, `open`, `prepend` and `reset` methods -
  and reports none missing. Its classification list names
  `Template.makepipeline()`, `Template.open_r()` and `Template.open_w()`,
  the helpers `copy()` and `open()` call, the module-level `makepipeline()`
  they call in turn, and the `stepkinds` list; none is on the page, nor are
  the `debugging` and `steps` attributes. `makepipeline()` called directly
  creates the temporary files and leaves them, since only the shell that
  runs the command line removes them.
"""

from __future__ import annotations

import contextlib
import importlib
import importlib.util
import io
import os
import pathlib
import re
import shlex
import subprocess
import sys
import tempfile
import textwrap
import time
import tracemalloc
import warnings
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "pipes.md"
EXPECTED_BLOCKS = 5

needs_sh = pytest.mark.skipif(
    sys.platform == "win32", reason="the pipelines run under /bin/sh, which Windows does not have"
)


def best_ns(func: Callable[[], Any], repeats: int = 5) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        elapsed = float(time.perf_counter_ns() - start)
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def best_ns_with_setup(
    setup: Callable[[], Any], func: Callable[[Any], Any], repeats: int = 5
) -> float:
    """Fastest of `repeats` runs of func(setup()), timing func alone."""
    best: float | None = None
    for _ in range(repeats):
        subject = setup()
        start = time.perf_counter_ns()
        func(subject)
        elapsed = float(time.perf_counter_ns() - start)
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


def test_the_module_exists_only_before_3_13() -> None:
    assert (importlib.util.find_spec("pipes") is not None) == (sys.version_info < (3, 13))


@pytest.fixture
def pipes() -> Iterator[Any]:
    if sys.version_info >= (3, 13):
        pytest.skip("version: pipes was removed in Python 3.13")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        yield importlib.import_module("pipes")


def template(pipes: Any, steps: int, cmd: str = "cat") -> Any:
    t = pipes.Template()
    for _ in range(steps):
        t.append(cmd, "--")
    return t


def write(path: pathlib.Path, text: str) -> pathlib.Path:
    path.write_text(text, encoding="utf-8")
    return path


class TestAvailability:
    """`import pipes` works on 3.10 to 3.12, warning from 3.11, and fails
    from 3.13."""

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="the module exists before 3.13")
    def test_importing_it_from_3_13_raises(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("pipes")

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="pipes was removed in 3.13")
    def test_importing_it_warns_from_3_11(self) -> None:
        result = subprocess.run(
            [sys.executable, "-W", "error::DeprecationWarning", "-c", "import pipes"],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        assert (result.returncode != 0) == (sys.version_info >= (3, 11)), result.stderr
        if sys.version_info >= (3, 11):
            assert "DeprecationWarning" in result.stderr
            assert "pipes" in result.stderr


class TestBuildingRunsNothing:
    """`pipes.Template()` | O(1): nothing runs until `open()` or `copy()`."""

    def test_no_shell_and_no_temporary_file_before_open_or_copy(
        self, pipes: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def refuse(*args: Any, **kwargs: Any) -> Any:
            raise AssertionError(f"called with {args}")

        monkeypatch.setattr(os, "system", refuse)
        monkeypatch.setattr(os, "popen", refuse)
        monkeypatch.setattr(tempfile, "mkstemp", refuse)

        t = pipes.Template()
        t.append("sort $IN > $OUT", "ff")
        t.prepend("cat $IN > $OUT", "ff")
        t.debug(True)
        t.clone().reset()
        t.reset()


class TestStepChecks:
    """`append(cmd, kind)` and `prepend(cmd, kind)` reject what the Notes
    list, before anything runs."""

    @pytest.mark.parametrize(
        ("kind", "cmd", "message"),
        [
            ("xx", "cat", "bad kind"),
            ("", "cat", "bad kind"),
            (".-", "echo", "SOURCE can only be prepended"),
            ("ff", "sort", r"missing \$IN"),
            ("-f", "sort", r"missing \$OUT"),
            ("f-", "cat $OUT", r"missing \$IN"),
        ],
    )
    def test_append_rejects(self, pipes: Any, kind: str, cmd: str, message: str) -> None:
        with pytest.raises(ValueError, match=message):
            pipes.Template().append(cmd, kind)

    def test_nothing_follows_a_sink(self, pipes: Any) -> None:
        t = pipes.Template()
        t.append("cat > /dev/null", "-.")

        with pytest.raises(ValueError, match="already ends with SINK"):
            t.append("cat", "--")

    def test_a_command_must_be_a_string(self, pipes: Any) -> None:
        with pytest.raises(TypeError):
            pipes.Template().append(["cat"], "--")

    def test_prepend_swaps_source_and_sink(self, pipes: Any) -> None:
        t = pipes.Template()
        t.prepend("echo hi", ".-")

        with pytest.raises(ValueError, match="already begins with SOURCE"):
            t.prepend("cat", "--")
        with pytest.raises(ValueError, match="SINK can only be appended"):
            pipes.Template().prepend("cat > /dev/null", "-.")
        with pytest.raises(ValueError, match=r"missing \$IN"):
            pipes.Template().prepend("sort", "ff")


class TestTheStepList:
    """`append` | O(1) amortized, `prepend` | O(n), `reset` | O(n),
    `clone` | O(n) | O(n). 100x the steps separates constant from linear by
    two orders of magnitude."""

    @staticmethod
    def thousand_calls(method: str) -> Callable[[Any], None]:
        def run(t: Any) -> None:
            add = getattr(t, method)
            for _ in range(1_000):
                add("cat", "--")

        return run

    @pytest.mark.timing
    def test_prepend_grows_with_the_steps_and_append_does_not(self, pipes: Any) -> None:
        durations: dict[str, list[float]] = {"append": [], "prepend": []}
        for steps in (1_000, 100_000):
            base = template(pipes, steps)
            for method in durations:
                durations[method].append(
                    best_ns_with_setup(base.clone, self.thousand_calls(method))
                )

        prepend = durations["prepend"][1] / durations["prepend"][0]
        append = durations["append"][1] / durations["append"][0]
        assert prepend > 10, f"100x the steps: prepend x{prepend:.1f} ({durations})"
        assert append < 3, f"100x the steps: append x{append:.1f} ({durations})"

    @pytest.mark.timing
    def test_reset_grows_with_the_steps(self, pipes: Any) -> None:
        durations = []
        for steps in (10_000, 1_000_000):
            base = template(pipes, steps)
            durations.append(best_ns_with_setup(base.clone, lambda t: t.reset()))

        ratio = durations[1] / durations[0]
        assert ratio > 10, f"100x the steps: reset x{ratio:.1f} ({durations} ns)"

    def test_clone_copies_the_step_list(self, pipes: Any) -> None:
        peaks = []
        for steps in (1_000, 100_000):
            base = template(pipes, steps)
            peaks.append(peak_bytes(base.clone))

        assert peaks[1] > peaks[0] * 20, f"100x the steps: clone peaked at {peaks}"

    def test_a_clone_is_independent_and_keeps_the_debug_flag(self, pipes: Any) -> None:
        t = template(pipes, 1)
        t.debug(True)
        twin = t.clone()
        assert twin.debugging == 1

        twin.append("sort", "--")
        t.prepend("head", "--")

        with contextlib.redirect_stdout(io.StringIO()):
            assert t.makepipeline("a", "b") == "set -x; head <a |\ncat >b"
            assert twin.makepipeline("a", "b") == "set -x; cat <a |\nsort >b"


class Recorder:
    """Stands in for `os.system()` and `os.popen()`, keeping the command."""

    def __init__(self) -> None:
        self.commands: list[str] = []

    def system(self, cmd: str) -> int:
        self.commands.append(cmd)
        return 0

    def popen(self, cmd: str, mode: str = "r") -> io.StringIO:
        self.commands.append(cmd)
        return io.StringIO()


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> Recorder:
    rec = Recorder()
    monkeypatch.setattr(os, "system", rec.system)
    monkeypatch.setattr(os, "popen", rec.popen)
    return rec


class TestBuildingTheCommandLine:
    """`open()` and `copy()` | O(n²) | O(n): both build the whole command line
    before the shell starts, and that is quadratic in the steps."""

    @pytest.mark.timing
    def test_four_times_the_steps_costs_far_more_than_four_times(
        self, pipes: Any, recorder: Recorder
    ) -> None:
        durations = []
        for steps in (1_000, 4_000, 16_000):
            t = template(pipes, steps, cmd="c" * 60)
            durations.append(best_ns(lambda t=t: t.copy("a", "b")))

        ratios = [later / earlier for earlier, later in zip(durations, durations[1:], strict=False)]
        assert all(ratio > 8 for ratio in ratios), (
            f"4x steps cost {[f'x{r:.1f}' for r in ratios]} ({durations} ns); "
            "linear gives x4, quadratic x16"
        )

    def test_the_peak_grows_linearly_with_the_steps(self, pipes: Any, recorder: Recorder) -> None:
        peaks = []
        for steps in (2_000, 32_000):
            t = template(pipes, steps)
            t.copy("a", "b")  # warm
            recorder.commands.clear()
            peaks.append(peak_bytes(lambda t=t: t.copy("a", "b")))
            recorder.commands.clear()

        ratio = peaks[1] / peaks[0]
        assert 8 < ratio < 40, f"16x the steps peaked x{ratio:.1f} ({peaks}); linear gives x16"

    def test_open_and_copy_build_the_same_command_line(
        self, pipes: Any, recorder: Recorder
    ) -> None:
        t = template(pipes, 3)

        t.copy("in", "")
        t.open("in", "r")
        t.copy("", "out")
        t.open("out", "w")

        assert recorder.commands[0] == recorder.commands[1]
        assert recorder.commands[2] == recorder.commands[3]

    def test_debug_prints_the_command_line_and_adds_set_x(
        self, pipes: Any, recorder: Recorder, capsys: pytest.CaptureFixture[str]
    ) -> None:
        t = template(pipes, 1)
        t.copy("a", "b")
        assert capsys.readouterr().out == ""

        t.debug(True)
        t.copy("a", "b")

        assert capsys.readouterr().out == "cat <a >b\n"
        assert recorder.commands == ["cat <a >b", "set -x; cat <a >b"]

    @needs_sh
    def test_under_debug_the_shell_traces_each_command(
        self, pipes: Any, tmp_path: pathlib.Path, capfd: pytest.CaptureFixture[str]
    ) -> None:
        source = write(tmp_path / "in", "x\n")
        t = pipes.Template()
        t.append("tr a-z A-Z", "--")
        t.debug(True)

        assert t.copy(str(source), str(tmp_path / "out")) == 0

        err = capfd.readouterr().err
        assert re.search(r"^\++ tr a-z A-Z", err, re.MULTILINE), err


@needs_sh
class TestCopy:
    """`copy(infile, outfile)`: runs the pipeline and waits; the data never
    passes through Python; a failure is a status, not an exception."""

    def test_the_data_does_not_pass_through_python(
        self, pipes: Any, tmp_path: pathlib.Path
    ) -> None:
        source = write(tmp_path / "in", "b\na\n" * 1_000_000)
        target = tmp_path / "out"
        t = pipes.Template()
        t.append("tr a-z A-Z", "--")

        status: list[int] = []
        peak = peak_bytes(lambda: status.append(t.copy(str(source), str(target))))

        assert status == [0]
        assert target.stat().st_size == 4_000_000
        assert peak < 100_000, f"copying 4 MB through tr peaked at {peak} bytes in Python"

    def test_it_returns_the_wait_status(self, pipes: Any, tmp_path: pathlib.Path) -> None:
        source = write(tmp_path / "in", "x\n")
        t = pipes.Template()
        t.append("exit 3", "--")

        status = t.copy(str(source), str(tmp_path / "out"))

        assert os.waitstatus_to_exitcode(status) == 3

    @pytest.mark.parametrize(
        ("first", "last", "code"),
        [
            (("cat", "--"), ("{ cat > /dev/null; false; }", "--"), 1),
            (("{ cat > /dev/null; false; }", "--"), ("cat", "--"), 0),
            (("sort $IN > $OUT", "ff"), ("{ cat > /dev/null; false; }", "--"), 0),
        ],
        ids=["last-step-fails", "first-step-fails", "last-step-fails-before-rm"],
    )
    def test_the_status_is_the_last_command_s(
        self,
        pipes: Any,
        tmp_path: pathlib.Path,
        first: tuple[str, str],
        last: tuple[str, str],
        code: int,
    ) -> None:
        source = write(tmp_path / "in", "x\n")
        t = pipes.Template()
        t.append(*first)
        t.append(*last)

        status = t.copy(str(source), str(tmp_path / "out"))

        assert os.waitstatus_to_exitcode(status) == code


class TestOpen:
    """`open(file, rw)`: starts the pipeline without waiting; Python reads or
    writes one end, at O(b); closing waits and returns the status."""

    @needs_sh
    def test_it_returns_while_the_pipeline_runs(self, pipes: Any, tmp_path: pathlib.Path) -> None:
        source = write(tmp_path / "in", "data\n")
        go = tmp_path / "go"
        t = pipes.Template()
        t.append(
            f"for i in $(seq 1000); do [ -e {go} ] && break; sleep 0.01; done; "
            f"[ -e {go} ] && echo found; cat",
            "--",
        )

        f = t.open(str(source), "r")
        go.touch()
        with f:
            assert f.read() == "found\ndata\n"

    @needs_sh
    def test_closing_a_write_end_waits_for_the_pipeline(
        self, pipes: Any, tmp_path: pathlib.Path
    ) -> None:
        target = tmp_path / "out"
        t = pipes.Template()
        t.append("sleep 0.3; tr a-z A-Z", "--")

        with t.open(str(target), "w") as f:
            f.write("hello world")

        assert target.read_text(encoding="utf-8") == "HELLO WORLD"

    @needs_sh
    def test_closing_returns_the_status(self, pipes: Any, tmp_path: pathlib.Path) -> None:
        source = write(tmp_path / "in", "x\n")
        succeeding = pipes.Template()
        succeeding.append("cat", "--")
        failing = pipes.Template()
        failing.append("{ cat; exit 3; }", "--")

        ok = succeeding.open(str(source), "r")
        assert ok.read() == "x\n"
        bad = failing.open(str(source), "r")
        assert bad.read() == "x\n"

        assert ok.close() is None
        assert os.waitstatus_to_exitcode(bad.close()) == 3

    @needs_sh
    def test_reading_the_end_passes_the_data_through_python(
        self, pipes: Any, tmp_path: pathlib.Path
    ) -> None:
        source = write(tmp_path / "in", "b\na\n" * 1_000_000)
        t = pipes.Template()
        t.append("tr a-z A-Z", "--")

        with t.open(str(source), "r") as f:
            peak = peak_bytes(f.read)

        assert peak > 4_000_000, f"reading 4,000,000 characters peaked at {peak} bytes"

    def test_with_no_steps_it_is_the_built_in_open(
        self, pipes: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = write(tmp_path / "in", "x\n")

        def refuse(*args: Any) -> Any:
            raise AssertionError("os.popen() was called")

        monkeypatch.setattr(os, "popen", refuse)
        with pipes.Template().open(str(source), "r") as f:
            assert type(f) is io.TextIOWrapper
            assert f.read() == "x\n"

    def test_it_rejects_what_cannot_be_opened(self, pipes: Any) -> None:
        t = template(pipes, 1)
        with pytest.raises(ValueError, match="rw must be"):
            t.open("x", "a")

        sink = pipes.Template()
        sink.append("cat > /dev/null", "-.")
        with pytest.raises(ValueError, match="SINK"):
            sink.open("x", "r")

        source = pipes.Template()
        source.prepend("echo hi", ".-")
        with pytest.raises(ValueError, match="SOURCE"):
            source.open("x", "w")


class TestTemporaryFiles:
    """A boundary where either side is a file gets a temporary file when the
    command line is built; the shell deletes it when the pipeline ends, and
    the later step starts after the earlier one ends."""

    @pytest.fixture
    def made(self, monkeypatch: pytest.MonkeyPatch) -> list[str]:
        names: list[str] = []
        original = tempfile.mkstemp

        def recording(*args: Any, **kwargs: Any) -> tuple[int, str]:
            fd, name = original(*args, **kwargs)
            names.append(name)
            return fd, name

        monkeypatch.setattr(tempfile, "mkstemp", recording)
        return names

    def test_only_a_file_boundary_gets_one(
        self, pipes: Any, recorder: Recorder, made: list[str]
    ) -> None:
        both_pipes = template(pipes, 2)
        both_pipes.copy("a", "b")
        assert made == []

        t = pipes.Template()
        t.append("sort $IN > $OUT", "ff")
        t.append("tr a-z A-Z", "--")
        t.copy("a", "b")
        try:
            assert len(made) == 1
        finally:
            for name in made:
                os.remove(name)

    @needs_sh
    def test_copy_leaves_none_behind(
        self, pipes: Any, tmp_path: pathlib.Path, made: list[str]
    ) -> None:
        source = write(tmp_path / "in", "pear\napple\n")
        target = tmp_path / "out"
        t = pipes.Template()
        t.append("sort $IN > $OUT", "ff")
        t.append("tr a-z A-Z", "--")

        assert t.copy(str(source), str(target)) == 0

        assert len(made) == 1
        assert not os.path.exists(made[0])
        assert target.read_text(encoding="utf-8") == "APPLE\nPEAR\n"

    @needs_sh
    def test_open_leaves_none_behind_once_closed(
        self, pipes: Any, tmp_path: pathlib.Path, made: list[str]
    ) -> None:
        source = write(tmp_path / "in", "pear\napple\n")
        t = pipes.Template()
        t.append("sort $IN > $OUT", "ff")
        t.append("tr a-z A-Z", "--")

        with t.open(str(source), "r") as f:
            assert f.read() == "APPLE\nPEAR\n"

        assert len(made) == 1
        assert not os.path.exists(made[0])

    @needs_sh
    def test_the_later_step_starts_after_the_earlier_ends(
        self, pipes: Any, tmp_path: pathlib.Path
    ) -> None:
        source = write(tmp_path / "in", "x\n")
        marker = tmp_path / "first-done"
        t = pipes.Template()
        # Braces, so that the redirection the module appends covers the whole list.
        t.append(f"{{ cat > $OUT; sleep 0.3; touch {marker}; }}", "-f")
        t.append(f"{{ cat $IN > /dev/null; [ -e {marker} ] && echo after || echo during; }}", "f-")

        assert t.copy(str(source), str(tmp_path / "out")) == 0

        assert (tmp_path / "out").read_text(encoding="utf-8") == "after\n"


class TestConstantsAndQuote:
    """The kind constants are the strings; `pipes.quote` is `shlex.quote`."""

    def test_the_kind_constants(self, pipes: Any) -> None:
        assert (
            pipes.STDIN_STDOUT,
            pipes.STDIN_FILEOUT,
            pipes.FILEIN_STDOUT,
            pipes.FILEIN_FILEOUT,
            pipes.SOURCE,
            pipes.SINK,
        ) == ("--", "-f", "f-", "ff", ".-", "-.")

    def test_quote_is_shlex_quote(self, pipes: Any) -> None:
        assert pipes.quote is shlex.quote


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
    """Each block runs in its own subprocess and working directory, on the
    versions that still have the module, and asserts its own result."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    @needs_sh
    def test_every_block_runs(self, pipes: Any, tmp_path: pathlib.Path) -> None:
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

    @needs_sh
    def test_the_runner_notices_a_broken_assertion(
        self, pipes: Any, tmp_path: pathlib.Path
    ) -> None:
        line, source = next((n, s) for n, s in _blocks() if "waitstatus_to_exitcode" in s)
        mutated = source.replace(
            "waitstatus_to_exitcode(status) == 3", "waitstatus_to_exitcode(status) == 4", 1
        )

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
