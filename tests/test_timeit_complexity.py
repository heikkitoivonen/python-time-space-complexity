"""Tests for docs/stdlib/timeit.md.

The page prices the module's own work around the caller's statement: a
compile when a `Timer` is built, then per run one setup and `number`
executions between two clock reads. Execution counts are settled by counting
callables and by a fake clock, which need no tolerance; the compile and the
space rows by counting `compile` calls and by traced allocation; one timing
test settles the cost of a callable statement.

Measurement scope:

* `Timer()` runs neither statement nor setup, and calls `compile` at least
  once while `timeit()` calls it never. Its traced peak, and the memory it
  still holds afterwards, grow more than 20x from a 100-line statement to a
  10,000-line one; for a callable statement, 100x the function's body leaves
  the peak within 2x.
* `timeit(number=n)` calls a counting statement exactly n times and a
  counting setup once, for n of 0, 1 and 1,000; `repeat(r, n)` calls the
  setup r times and the statement r·n times and returns r floats, for the
  method and the module-level functions alike. A statement appending to a
  list the setup built sees that list at every length from 0 to n - 1, and
  each run starts from the new list its setup builds. On a fake clock, a
  setup that advances it by 1,000 ticks leaves the returned duration at the
  statement's own ticks.
* One run of `pass` peaks under 5 KB at a million loops, the same bound as
  at a thousand. `repeat(10_000, 1)` peaks more than 20x above
  `repeat(10, 1)`, the r floats it returns.
* Garbage collection is observed off inside the loop, back on afterwards
  when it was on before, even when the statement raises, left off when it
  was off before, and on inside the loop when the setup calls `gc.enable()`.
  A setup that enables it while it was off before is not varied.
* `autorange()` runs against a fake clock that advances a fixed tick per
  execution, for five tick sizes: the trials follow 1, 2, 5, 10, ... up to
  the first whose time reaches 0.2, the one before it stays under 0.2, the
  executions total fewer than twice the returned count, and the setup runs
  once per trial.
* A callable statement that does nothing takes more than twice as long per
  loop as the string `pass`, at 100,000 loops, fastest of five.
* `print_exc()` writes the statement's source line with the traceback, to
  `file` or by default to stderr. `default_timer` is `time.perf_counter`.
* `python -m timeit -n 1000 -r 3` prints the best of three at 1,000 loops;
  with `-v` and no `-n`, the trial lines follow 1, 2, 5, ... and end at the
  count the repeats then use.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* O(c) for `Timer()` is shown only by allocation, and O(r) for `repeat()`
  likewise; both are bounded from below, not from above, and time is not
  measured. `autorange()`'s O(1) space and `print_exc()`'s O(c + t) are read
  from Lib/timeit.py: the first keeps two numbers per trial, the second
  splits the source into `linecache` and hands the traceback, whose
  formatted length is t, to `traceback.print_exc`.
* That the command line prints the minimum per-loop time, rather than the
  mean or total, is read from Lib/timeit.py `main()`; the tests check its
  label and the repeat count only.
* The clock and the `autorange()` callback are priced at O(1) per call by
  definition; custom ones of other cost are not varied.
* That the fastest of several runs is the one least disturbed by other
  processes is the module's own advice, not something a test can settle.
* Statement and setup costs s and u are the caller's; the bounds count them
  as given and no statement's cost is varied beyond the counts above.
"""

from __future__ import annotations

import gc
import io
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import timeit
import tracemalloc
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "timeit.md"
EXPECTED_BLOCKS = 7


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


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def held_bytes(func: Callable[[], Any]) -> int:
    """Traced allocation still held after func returns, with its result kept."""
    tracemalloc.start()
    try:
        result = func()
        held = tracemalloc.get_traced_memory()[0]
        del result
        return held
    finally:
        tracemalloc.stop()


class Counter:
    """A callable that counts its calls."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> None:
        self.calls += 1


class FakeClock:
    """A clock that advances by `tick` each time the statement runs."""

    def __init__(self, tick: float) -> None:
        self.now = 0.0
        self.tick = tick
        self.executions = 0

    def statement(self) -> None:
        self.now += self.tick
        self.executions += 1

    def __call__(self) -> float:
        return self.now


class TestTimerCompilesAtConstruction:
    """`Timer(stmt, setup)` | O(c) | O(c): compiles the strings; runs neither."""

    def test_construction_runs_neither_statement_nor_setup(self) -> None:
        stmt, setup = Counter(), Counter()
        seen: list[str] = []

        timeit.Timer(stmt, setup)
        timeit.Timer("seen.append('stmt')", "seen.append('setup')", globals={"seen": seen})

        assert stmt.calls == setup.calls == 0
        assert seen == []

    def test_compiling_happens_at_construction_not_per_run(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        compiles: list[str] = []

        def counting_compile(source: str, *args: Any, **kwargs: Any) -> Any:
            compiles.append(source)
            return compile(source, *args, **kwargs)

        monkeypatch.setattr(timeit, "compile", counting_compile, raising=False)
        timer = timeit.Timer("y = 1", "x = 0")
        at_construction = len(compiles)
        timer.timeit(number=100)
        timer.repeat(repeat=3, number=100)

        assert at_construction >= 1
        assert len(compiles) == at_construction, "a run compiled the statement again"

    @staticmethod
    def _statement(lines: int) -> str:
        return "\n".join(f"v{index} = {index}" for index in range(lines))

    def test_building_it_allocates_with_the_source(self) -> None:
        small, large = self._statement(100), self._statement(10_000)

        peaks = [peak_bytes(lambda s=s: timeit.Timer(s)) for s in (small, large)]

        assert peaks[1] > peaks[0] * 20, f"100x the source: peaks {peaks}"

    def test_the_timer_holds_memory_with_the_source(self) -> None:
        small, large = self._statement(100), self._statement(10_000)

        held = [held_bytes(lambda s=s: timeit.Timer(s)) for s in (small, large)]

        assert held[1] > held[0] * 20, f"100x the source: held {held}"

    def test_a_callable_contributes_no_source(self) -> None:
        functions = []
        for lines in (10, 1_000):
            namespace: dict[str, Any] = {}
            body = textwrap.indent(self._statement(lines), "    ")
            exec(f"def work():\n{body}\n", namespace)
            functions.append(namespace["work"])
            timeit.Timer(namespace["work"])  # warm the template's compile

        peaks = [peak_bytes(lambda f=f: timeit.Timer(f)) for f in functions]

        assert peaks[1] < peaks[0] * 2, f"100x the function body: peaks {peaks}"


class TestOneRunIsOneSetupAndNLoops:
    """`Timer.timeit(n)` | O(u + n·s) | O(1); `Timer.repeat(r, n)` |
    O(r·(u + n·s)) | O(r); the module functions wrap one `Timer` each."""

    @pytest.mark.parametrize("number", [0, 1, 1_000])
    def test_timeit_runs_setup_once_and_the_statement_n_times(self, number: int) -> None:
        stmt, setup = Counter(), Counter()

        result = timeit.Timer(stmt, setup).timeit(number=number)

        assert (setup.calls, stmt.calls) == (1, number)
        assert isinstance(result, float)

    def test_repeat_runs_setup_once_per_run(self) -> None:
        stmt, setup = Counter(), Counter()

        results = timeit.Timer(stmt, setup).repeat(repeat=4, number=250)

        assert (setup.calls, stmt.calls) == (4, 1_000)
        assert len(results) == 4

    def test_the_module_functions_count_the_same(self) -> None:
        stmt, setup = Counter(), Counter()

        timeit.timeit(stmt, setup, number=7)
        results = timeit.repeat(stmt, setup, repeat=3, number=5)

        assert (setup.calls, stmt.calls) == (1 + 3, 7 + 15)
        assert len(results) == 3

    def test_state_carries_across_loops_and_resets_per_run(self) -> None:
        lengths: list[int] = []
        runs: list[list[int]] = []
        timer = timeit.Timer(
            "lengths.append(len(x)); x.insert(0, 1)",
            setup="x = []; runs.append(x)",
            globals={"lengths": lengths, "runs": runs},
        )

        timer.repeat(repeat=2, number=50)

        assert lengths == list(range(50)) * 2
        assert len(runs) == 2 and runs[0] is not runs[1]

    def test_setup_runs_before_the_clock_starts(self) -> None:
        clock = FakeClock(1.0)

        def setup() -> None:
            clock.now += 1_000

        assert timeit.Timer(clock.statement, setup, timer=clock).timeit(number=3) == 3.0

    def test_one_run_holds_nothing_per_loop(self) -> None:
        timer = timeit.Timer("pass")
        timer.timeit(number=10)  # warm

        peaks = [peak_bytes(lambda n=n: timer.timeit(number=n)) for n in (1_000, 1_000_000)]

        assert max(peaks) < 5_000, f"a run of pass peaked at {peaks}"

    def test_repeat_holds_one_float_per_run(self) -> None:
        timer = timeit.Timer("pass")
        timer.repeat(repeat=10, number=1)  # warm

        peaks = [peak_bytes(lambda r=r: timer.repeat(repeat=r, number=1)) for r in (10, 10_000)]

        assert peaks[1] > peaks[0] * 20, f"1,000x the repeats: peaks {peaks}"

    def test_an_exception_in_the_statement_propagates(self) -> None:
        with pytest.raises(ZeroDivisionError):
            timeit.timeit("1 / 0", number=1)


class TestGarbageCollectionIsOffDuringTheLoop:
    """`timeit()` switches the cyclic collector off for the loop and switches
    it back on afterwards if it was on."""

    @pytest.fixture(autouse=True)
    def _restore_gc(self) -> Iterator[None]:
        was_enabled = gc.isenabled()
        yield
        if was_enabled:
            gc.enable()
        else:
            gc.disable()

    @staticmethod
    def _seen(setup: str = "pass") -> list[bool]:
        seen: list[bool] = []
        timeit.timeit(
            "seen.append(gc.isenabled())",
            setup=setup,
            number=3,
            globals={"seen": seen, "gc": gc},
        )
        return seen

    def test_the_collector_is_off_inside_and_back_on_after(self) -> None:
        gc.enable()

        assert self._seen() == [False, False, False]
        assert gc.isenabled()

    def test_it_is_restored_when_the_statement_raises(self) -> None:
        gc.enable()

        with pytest.raises(ZeroDivisionError):
            timeit.timeit("1 / 0", number=1)

        assert gc.isenabled()

    def test_it_stays_off_when_it_was_off(self) -> None:
        gc.disable()

        self._seen()

        assert not gc.isenabled()

    def test_setup_can_turn_it_back_on(self) -> None:
        gc.enable()

        assert self._seen(setup="gc.enable()") == [True, True, True]


class TestAutorangeDoublesUntilPointTwoSeconds:
    """`Timer.autorange()` | O(k·s + u·log k): trials of 1, 2, 5, 10, ...
    loops until one takes at least 0.2 s, settled on a fake clock."""

    SEQUENCE = [m * 10**e for e in range(8) for m in (1, 2, 5)]

    @pytest.mark.parametrize("tick", [0.5, 2**-4, 2**-9, 2**-12, 2**-16])
    def test_trials_follow_the_sequence_and_total_under_twice_the_count(self, tick: float) -> None:
        clock = FakeClock(tick)
        setup = Counter()
        trials: list[tuple[int, float]] = []

        number, taken = timeit.Timer(clock.statement, setup, timer=clock).autorange(
            lambda n, t: trials.append((n, t))
        )

        counts = [n for n, _ in trials]
        assert counts == self.SEQUENCE[: len(counts)]
        assert trials[-1] == (number, taken)
        assert taken >= 0.2
        assert all(t < 0.2 for _, t in trials[:-1])
        assert clock.executions == sum(counts) < 2 * number
        assert setup.calls == len(trials)


class TestCallableStatementsAddACall:
    """A callable `stmt` is called once per loop; a string runs inline."""

    @pytest.mark.timing
    def test_a_callable_costs_more_than_inline_pass(self) -> None:
        inline = timeit.Timer("pass")
        called = timeit.Timer(lambda: None)

        durations = [best_ns(lambda t=t: t.timeit(number=100_000)) for t in (inline, called)]
        ratio = durations[1] / durations[0]

        assert ratio > 2, f"a no-op call per loop against pass: {durations} ns, x{ratio:.2f}"


class TestPrintExcAndDefaultTimer:
    """`print_exc()` shows the compiled source; `default_timer` is `perf_counter`."""

    def test_print_exc_writes_the_statement_line(self) -> None:
        timer = timeit.Timer("value = 1 / 0")
        output = io.StringIO()

        try:
            timer.timeit(number=1)
        except ZeroDivisionError:
            timer.print_exc(file=output)

        assert "value = 1 / 0" in output.getvalue()
        assert "ZeroDivisionError" in output.getvalue()

    def test_print_exc_defaults_to_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        timer = timeit.Timer("missing_name")
        try:
            timer.timeit(number=1)
        except NameError:
            timer.print_exc()

        captured = capsys.readouterr()
        assert "missing_name" in captured.err
        assert captured.out == ""

    def test_default_timer_is_perf_counter(self) -> None:
        assert timeit.default_timer is time.perf_counter


class TestCommandLine:
    """`python -m timeit`: autorange unless a positive `-n`, then `-r`
    repeats; the best per-loop time."""

    @staticmethod
    def _run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "timeit", *args],
            capture_output=True,
            text=True,
            timeout=120,
            stdin=subprocess.DEVNULL,
            check=True,
        )

    def test_a_given_number_skips_the_search(self) -> None:
        result = self._run("-v", "-n", "1000", "-r", "3", "pass")

        assert "loops ->" not in result.stdout
        assert "1000 loops, best of 3: " in result.stdout

    def test_without_a_number_it_searches_then_repeats_the_count_found(self) -> None:
        result = self._run("-v", "-r", "2", "-s", "import time", "time.sleep(0.005)")

        trials = [int(n) for n in re.findall(r"^(\d+) loops? -> ", result.stdout, re.MULTILINE)]
        assert trials == TestAutorangeDoublesUntilPointTwoSeconds.SEQUENCE[: len(trials)]
        assert f"{trials[-1]} loops, best of 2: " in result.stdout
        raw = re.search(r"^raw times: (.*)$", result.stdout, re.MULTILINE)
        assert raw is not None and len(raw.group(1).split(", ")) == 2


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
    """Each block runs in its own subprocess and asserts its own result."""

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
        target = "[len(x) for x in runs] == [100, 100, 100]"
        line, source = next((n, s) for n, s in _blocks() if target in s)
        mutated = source.replace(target, "[len(x) for x in runs] == [100, 200, 300]", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
