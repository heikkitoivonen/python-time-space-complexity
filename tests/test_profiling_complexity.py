"""Tests for docs/stdlib/profiling.md.

The page prices the package's two profilers by different units: tracing by
the calls the profiled code makes, sampling by the samples taken. The tracing
rows are `cProfile`'s, so they are settled by identity with the objects
tests/test_cprofile_complexity.py measures, plus one command-line round trip.
The sampling rows are settled end to end, by running the command-line tool
on a child process and reading what it produced: whether the target sees any
hook, how many entries each output format holds against how many samples
were taken, and what `dump` and `replay` print.

Measurement scope:

* `import profiling` in a fresh interpreter leaves no `profiling.*` module
  but the package in `sys.modules`; `profiling.__all__` is asserted.
* `profiling.tracing.Profile`, `run` and `runctx` are asserted to be
  `cProfile`'s objects, so every bound tests/test_cprofile_complexity.py
  settles for them holds here. `label()` is asserted on a code object and a
  built-in's name. `python -m profiling.tracing -o` over a script calling
  `leaf()` ten times writes a report with exactly 10 calls of `leaf`, and
  `profiling.tracing.run()` prints a report naming it.
* Hooks in the target: a script that records `sys.getprofile()`,
  `sys.gettrace()` and `sys.monitoring.get_tool()` for tool ids 0 to 5 sees
  the profiler tool registered under `python -m profiling.tracing`, and
  nothing at all while `python -m profiling.sampling run` samples it.
* Aggregation: one-second runs at the default 1 kHz over a target spinning in
  one function. `--collapsed` and `--pstats` hold fewer than 20 entries while
  their counts add up to at least 50 samples; `--gecko` holds one sample
  entry per sample, at least 50, over fewer than 20 stack-table entries; a
  `--binary` recording replayed to `--collapsed` and to `--gecko` gives the
  same sample total, at least 50. Both totals are asserted to equal the
  count the profiler prints as captured, less the failed samples its error
  rate reports (with one sample of rounding slack), so every sample taken
  was kept. The lower bound
  is far under the run's nominal 1,000 samples, so a loaded runner that
  misses samples still passes; the upper bound on entries is what separates
  aggregation from one entry per sample.
* `-d` ends the program: the target writes its pid, and after the profiler
  returns that pid is asserted gone within 10 seconds.
* `dump` is run from a process that is the target's parent, against a child
  blocked in `waiting()`: one `Stack dump for PID` header, the `waiting`
  frame, and an exit status of 0.
* The fenced block that runs the sampling profiler and the one that runs the
  tracing profiler each run in their own subprocess, and a mutated assertion
  in the tracing one is asserted to fail.

Not settled here:

* O(n·k) for a sampling run, and the O(k) of `dump`, are read from
  Lib/profiling/sampling/sample.py, which reads the whole stack once per
  sample, and from the collectors, which walk each sample's frames. k is not
  varied, and neither is the rate: n is only bounded from below.
* On 3.15.0 alone, `replay` of a recording whose thread status alternates
  between samples is quadratic in the length of each repeat record, up to
  the writer's cap on one (gh-152721). That version and that input shape
  are not tested.
* That the target is never paused without `--blocking`, and that `--blocking`
  pauses its threads, is taken from the official documentation and
  `_pause_threads()` in sample.py; it is not observed.
* `attach` needs permission to read a process that is not the profiler's
  child, which Linux's Yama `ptrace_scope` may refuse, so it is not run; its
  bounds are those of `run`, which shares the sampling loop.
* `--flamegraph`, `--heatmap`, `--jsonl` and `--live` are read as
  aggregating from their collectors in Lib/profiling/sampling: each keeps
  counters keyed by stack, frame or line. Only `--pstats`, `--collapsed`,
  `--gecko` and `--binary` are run. `-a` raising k is read from the CLI's
  documentation.
* The O(n·k) size of a `--binary` file is read from
  Modules/_remote_debugging/binary_io_writer.c: every sample writes its
  timestamp delta and status, a repeated stack adds nothing more, and a
  changed one adds the frames pushed since the thread's previous sample. The
  file's size is not measured.
* Platforms: the sampling tests run on Linux only. Reading another process's
  memory needs root or a debugger entitlement on macOS (`task_for_pid`) and
  administrator rights or `SeDebugPrivilege` on Windows, per the official
  documentation, so those platforms skip them.
* Name coverage: the official inventory names `profiling`,
  `profiling.sampling`, `profiling.tracing` and the tracing API, which the
  page covers. The audit also lists some 220 runtime discoveries under
  `profiling.sampling`'s implementation modules (`cli`, `collector`,
  `binary_collector`, `gecko_collector` and others) as needing
  classification; they are not in the official inventory, and the page
  covers the command line and the seven names in `profiling.sampling.__all__`
  instead.
* The package is new in Python 3.15, so this file skips on earlier versions.
"""

from __future__ import annotations

import importlib
import json
import marshal
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
from typing import Any

import pytest

if sys.version_info < (3, 15):
    pytest.skip("version: the profiling package is new in Python 3.15", allow_module_level=True)

tracing: Any = importlib.import_module("profiling.tracing")

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "profiling.md"
EXPECTED_BLOCKS = 2

SAMPLING_PLATFORMS = pytest.mark.skipif(
    sys.platform != "linux",
    reason=(
        "reading another process's memory needs task_for_pid rights on macOS and "
        "administrator rights or SeDebugPrivilege on Windows"
    ),
)

SPIN = "def spin():\n    while True:\n        pass\n\nspin()\n"

HOOKS = """\
import json, os, sys

state = [repr(sys.getprofile()), repr(sys.gettrace()),
         [sys.monitoring.get_tool(i) for i in range(6)]]
with open(sys.argv[1] + ".tmp", "w") as f:
    json.dump(state, f)
os.replace(sys.argv[1] + ".tmp", sys.argv[1])
"""


def run_cli(module: str, *args: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", module, *args],
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        cwd=cwd,
        check=False,
    )


def sample(*args: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    """Run the sampling profiler; skip if this machine forbids reading the child."""
    completed = run_cli("profiling.sampling", *args, cwd=cwd)
    if completed.returncode != 0 and re.search(
        r"[Pp]ermission|not permitted", completed.stderr
    ):  # pragma: no cover - depends on the sandbox
        pytest.skip("missing ptrace: this process may not read its child's memory here")
    assert completed.returncode == 0, completed.stderr
    return completed


class TestThePackageImportsNeitherProfiler:
    """`import profiling` | O(1) | O(1): the package names its two
    submodules and imports neither."""

    def test_only_the_package_is_imported(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys, profiling\n"
                "print(sorted(m for m in sys.modules if m.startswith('profiling')))\n"
                "print(profiling.__all__)\n",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=True,
        )

        assert completed.stdout.splitlines() == ["['profiling']", "('tracing', 'sampling')"]


class TestTracingIsCProfile:
    """The `profiling.tracing` rows carry `cProfile`'s bounds because they
    are `cProfile`'s objects; tests/test_cprofile_complexity.py measures
    those."""

    def test_the_objects_are_cprofile_s(self) -> None:
        import cProfile

        assert tracing.Profile is cProfile.Profile
        assert tracing.run is cProfile.run
        assert tracing.runctx is cProfile.runctx

    def test_label_is_the_report_key(self) -> None:
        def located() -> None:
            pass

        code = located.__code__

        assert tracing.label(code) == (code.co_filename, code.co_firstlineno, "located")
        assert tracing.label("<built-in method len>") == ("~", 0, "<built-in method len>")

    def test_the_command_line_counts_every_call(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "app.py").write_text(
            "def leaf():\n    pass\n\nfor _ in range(10):\n    leaf()\n", encoding="utf-8"
        )

        completed = run_cli("profiling.tracing", "-o", "app.prof", "app.py", cwd=tmp_path)
        assert completed.returncode == 0, completed.stderr
        stats = marshal.loads((tmp_path / "app.prof").read_bytes())

        assert [value[1] for key, value in stats.items() if key[2] == "leaf"] == [10]

    def test_run_prints_a_report(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "from profiling import tracing\n"
                "def leaf():\n    pass\n"
                "tracing.run('for _ in range(3): leaf()')\n",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=True,
        )

        assert re.search(r"^\s*3\s.*\(leaf\)$", completed.stdout, re.MULTILINE), completed.stdout


class TestOnlyTracingHooksTheTarget:
    """Tracing registers itself in the profiled process; sampling reads the
    target from outside, so the target sees no hook at all."""

    NOTHING = ["None", "None", [None] * 6]

    def test_tracing_registers_a_monitoring_tool(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "hooks.py").write_text(HOOKS, encoding="utf-8")

        completed = run_cli(
            "profiling.tracing", "-o", "out.prof", "hooks.py", "state.json", cwd=tmp_path
        )
        assert completed.returncode == 0, completed.stderr
        state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))

        assert state[2][vars(sys)["monitoring"].PROFILER_ID] is not None
        assert state != self.NOTHING

    @SAMPLING_PLATFORMS
    def test_sampling_leaves_the_target_untouched(self, tmp_path: pathlib.Path) -> None:
        # The script records the hooks over and over until the profiler ends
        # it, so the record covers the time it was being sampled; once it has
        # seen a hook it keeps that record.
        looped = (
            "first = None\n"
            "while True:\n"
            + textwrap.indent(HOOKS.replace("state = ", "state = first or "), "    ")
            + "    if state != ['None', 'None', [None] * 6]:\n"
            "        first = state\n"
        )
        (tmp_path / "hooks.py").write_text(looped, encoding="utf-8")

        sample("run", "-d", "1", "-o", "out.prof", "hooks.py", "state.json", cwd=tmp_path)
        state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
        stats = marshal.loads((tmp_path / "out.prof").read_bytes())

        assert state == self.NOTHING
        assert any(key[0].endswith("hooks.py") for key in stats), "the script was not sampled"


@SAMPLING_PLATFORMS
class TestOutputsAggregateOrKeepEverySample:
    """`--pstats`, `--collapsed` | O(u·k): one entry per distinct stack or
    location, however many samples land on it. `--gecko` | O(n + u·k)
    and `--binary` | O(n·k): one entry per sample. A one-second run over a target that
    spins in one function separates the two by the count of entries."""

    MIN_SAMPLES = 50
    MAX_ENTRIES = 20

    @staticmethod
    def collapsed_totals(path: pathlib.Path) -> tuple[int, int]:
        lines = path.read_text(encoding="utf-8").splitlines()
        return len(lines), sum(int(line.rsplit(" ", 1)[1]) for line in lines)

    @staticmethod
    def gecko_totals(path: pathlib.Path) -> tuple[int, int]:
        profile = json.loads(path.read_text(encoding="utf-8"))
        samples = sum(thread["samples"]["length"] for thread in profile["threads"])
        stacks = sum(thread["stackTable"]["length"] for thread in profile["threads"])
        return stacks, samples

    def test_collapsed_keeps_one_line_per_stack(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "spin.py").write_text(SPIN, encoding="utf-8")

        sample("run", "-d", "1", "--collapsed", "-o", "out.txt", "spin.py", cwd=tmp_path)
        lines, samples = self.collapsed_totals(tmp_path / "out.txt")

        assert samples >= self.MIN_SAMPLES
        assert lines < self.MAX_ENTRIES, f"{lines} lines for {samples} samples"

    def test_pstats_keeps_one_entry_per_location(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "spin.py").write_text(SPIN, encoding="utf-8")

        sample("run", "-d", "1", "--pstats", "-o", "out.prof", "spin.py", cwd=tmp_path)
        stats = marshal.loads((tmp_path / "out.prof").read_bytes())
        entries = {key: value for key, value in stats.items() if key != ("__sampled__",)}
        samples = sum(value[0] for value in entries.values())

        assert samples >= self.MIN_SAMPLES
        assert len(entries) < self.MAX_ENTRIES, f"{len(entries)} entries for {samples} samples"

    @staticmethod
    def captured(completed: subprocess.CompletedProcess[str]) -> tuple[int, int]:
        """The samples the profiler reports taking, and how many of them failed."""
        taken = re.search(r"Captured ([\d,]+) samples?", completed.stdout)
        rate = re.search(r"Error rate: ([\d.]+)", completed.stdout)
        assert taken is not None and rate is not None, completed.stdout
        count = int(taken.group(1).replace(",", ""))
        return count, round(count * float(rate.group(1)) / 100)

    def test_gecko_keeps_one_entry_per_sample(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "spin.py").write_text(SPIN, encoding="utf-8")

        run = sample("run", "-d", "1", "--gecko", "-o", "out.json", "spin.py", cwd=tmp_path)
        stacks, samples = self.gecko_totals(tmp_path / "out.json")
        taken, failed = self.captured(run)

        assert samples >= self.MIN_SAMPLES
        assert abs(samples - (taken - failed)) <= 1, (
            f"{samples} entries, {taken} taken, {failed} failed"
        )
        assert stacks < self.MAX_ENTRIES, f"{stacks} stacks for {samples} samples"

    def test_binary_keeps_every_sample_for_replay(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "spin.py").write_text(SPIN, encoding="utf-8")

        run = sample("run", "-d", "1", "--binary", "-o", "out.bin", "spin.py", cwd=tmp_path)
        sample("replay", "--collapsed", "-o", "out.txt", "out.bin", cwd=tmp_path)
        sample("replay", "--gecko", "-o", "out.json", "out.bin", cwd=tmp_path)
        lines, collapsed = self.collapsed_totals(tmp_path / "out.txt")
        stacks, timeline = self.gecko_totals(tmp_path / "out.json")
        taken, failed = self.captured(run)

        assert collapsed >= self.MIN_SAMPLES
        assert abs(collapsed - (taken - failed)) <= 1, (
            f"{collapsed} replayed, {taken} taken, {failed} failed"
        )
        assert timeline == collapsed
        assert lines < self.MAX_ENTRIES
        assert stacks < self.MAX_ENTRIES


@SAMPLING_PLATFORMS
class TestRunAndDump:
    """`run` with `-d` stops sampling and ends the program; `dump pid`
    reads the stack once and prints it."""

    def test_duration_ends_the_program(self, tmp_path: pathlib.Path) -> None:
        (tmp_path / "spin.py").write_text(
            "import os, sys\n"
            "with open(sys.argv[1], 'w') as f:\n"
            "    f.write(str(os.getpid()))\n" + SPIN,
            encoding="utf-8",
        )

        sample("run", "-d", "1", "-o", "out.prof", "spin.py", "pid.txt", cwd=tmp_path)
        pid = int((tmp_path / "pid.txt").read_text(encoding="utf-8"))

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        else:
            raise AssertionError(f"the profiled program, pid {pid}, outlived the profiler")

    def test_dump_prints_one_stack(self, tmp_path: pathlib.Path) -> None:
        # The dumping process must be the target's parent, which Linux's
        # Yama ptrace scope allows even where it forbids attaching elsewhere.
        wrapper = textwrap.dedent(
            """
            import runpy, subprocess, sys

            child = subprocess.Popen(
                [sys.executable, "-c",
                 "import time\\ndef waiting():\\n    print('up', flush=True)\\n"
                 "    time.sleep(60)\\nwaiting()\\n"],
                stdout=subprocess.PIPE, stdin=subprocess.DEVNULL,
            )
            try:
                assert child.stdout.readline() == b"up\\n"
                sys.argv = ["profiling.sampling", "dump", str(child.pid)]
                runpy.run_module("profiling.sampling", run_name="__main__", alter_sys=True)
            finally:
                child.kill()
                child.wait()
            """
        )
        completed = subprocess.run(
            [sys.executable, "-c", wrapper],
            capture_output=True,
            text=True,
            timeout=120,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        if completed.returncode != 0 and re.search(
            r"[Pp]ermission|not permitted", completed.stderr
        ):  # pragma: no cover - depends on the sandbox
            pytest.skip("missing ptrace: this process may not read its child's memory here")

        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.count("Stack dump for PID") == 1, completed.stdout
        assert "in waiting" in completed.stdout


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


def _samples(source: str) -> bool:
    return "profiling.sampling" in source


class TestDocumentedExamples:
    """Each block runs in its own subprocess and asserts its own result. The
    block that runs the sampling profiler needs the platforms the sampling
    tests run on."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS
        assert [_samples(source) for _, source in blocks] == [False, True]

    def test_the_tracing_block_runs(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if not _samples(s))
        result = _run_block(source, tmp_path)

        assert result.returncode == 0, f"{PAGE.name}:{line}\n{result.stderr.strip()}"

    @SAMPLING_PLATFORMS
    def test_the_sampling_block_runs(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if _samples(s))
        result = _run_block(source, tmp_path)
        if result.returncode != 0 and re.search(
            r"[Pp]ermission|not permitted", result.stderr
        ):  # pragma: no cover - depends on the sandbox
            pytest.skip("missing ptrace: this process may not read its child's memory here")

        assert result.returncode == 0, f"{PAGE.name}:{line}\n{result.stderr.strip()}"

    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "ncalls == '1000'" in s)
        mutated = source.replace("ncalls == '1000'", "ncalls == '999'", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
