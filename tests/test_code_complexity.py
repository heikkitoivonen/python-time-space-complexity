"""Tests for docs/stdlib/code.md.

The page prices the interactive-interpreter classes by what they compile and
what they walk: `runsource()` and `compile_command()` compile the source they
are handed a fixed number of times, a console hands the whole buffered block
to the compiler on every `push()`, and `showtraceback()` walks every frame.
Compile work is settled by observation, with a counting `codeop.Compile`
subclass installed as the interpreter's compiler that records the length of
every source it compiles; namespace and output rows are settled by identity
and by recording `write()`. Stopwatch tests corroborate the compile counts.

Measurement scope:

* `InteractiveInterpreter(locals)` keeps the mapping it is given (`is`), and
  building one over a 100,000-entry dict peaks under 5 KB. The default
  namespace is `{'__name__': '__console__', '__doc__': None}`, and
  `InteractiveConsole` and `interact(local=...)` use the mapping they are
  given too.
* `compile_command()` calls the compiler one to three times on complete,
  incomplete and invalid input and on blank or comment-only input (which is
  compiled as `pass`), and the characters compiled stay under 3c + 3, with c
  at least 4. It is `codeop.compile_command` itself.
* `push()`: for blocks of 100 and 400 lines of 20 characters, the characters
  compiled over the block's pushes grow more than 12x for the 4x block
  (O(b·c) predicts 16x, O(c) 4x), and each push compiles the whole buffer,
  the last one included. At about 12,000 characters (within 10%), 400 short
  lines compile more than 5x the characters of 40 long ones, so the line
  count is a term of its own. A timing test pushes blocks of 25, 100 and 400
  lines a line at a time, where each 4x step costs more than 8x, and
  hands blocks of 400, 1,600 and 6,400 lines to one
  `runsource(symbol='exec')` call each, where each 4x step costs less than
  8x. That one call hands the compiler under 3c + 3 characters.
* `resetbuffer()` empties the buffer; in a timing test, dropping 1,000,000
  distinct buffered lines costs more than 100x dropping 1,000.
* `runsource()` returns `True` for incomplete input with nothing run,
  `False` for complete input after running it, and `False` for a syntax
  error after reporting it through `write()`. `runcode()` reports an
  exception through `write()` and lets `SystemExit` propagate. With
  `sys.excepthook` replaced, the hook receives the exception and `write()`
  is not called; every other test restores the default hook first.
* `showtraceback()`: a recursion 50 and 500 frames deep through one
  function prints output of the same length within 10 characters, because
  the traceback collapses repeated lines, while the traced peak of
  `showtraceback()` alone, called inside the `except` block after the
  traceback exists, grows more than 5x; through 50 and 500 distinct
  functions the output grows more than 5x. The exception message and each
  source line are held to a fixed length.
* `showsyntaxerror()`: an offending line of 100,000 characters prints more
  than 50x the output of one of 100, and 1,000 valid lines before the error
  add under 50 characters.
* `write()` hands `sys.stderr.write` the object it was given.
* `raw_input()` reads one line from `sys.stdin`, without its newline, and
  raises `EOFError` at end of input.
* `interact()` calls `push()` once per line read and returns when `readfunc`
  raises `EOFError`; the banner and exit message arrive through `write()`.
  Without `local_exit`, `exit()` inside the console raises `SystemExit` out
  of `interact()` on every supported version. With `local_exit=True`
  (3.13+), `exit()` ends only the console, later lines are not run, and
  `builtins.exit` is the original object afterwards; before 3.13 the keyword
  raises `TypeError`, and both sides of that boundary are asserted.
* Every fenced Python block runs in its own subprocess with stdin at end of
  input, and a mutated assertion in one of them is asserted to fail.

Not settled here:

* Compiling is priced as linear in the characters compiled. The tests count
  characters handed to the compiler, and only the timing tests observe what
  compiling them costs; pathological nesting and very long single tokens are
  not varied.
* `x`, the cost of the code being run, is the caller's; no row prices it.
* `write()`'s O(w) is the cost of the stream it writes to, `sys.stderr` by
  default; only identity of the argument is asserted.
* `raw_input()` and `interact()` without `readfunc` read `sys.stdin`
  through `input()`, which uses libedit or GNU readline on a terminal
  depending on the build. No test here has a TTY; `sys.stdin` is replaced
  with a `StringIO`.
* `code.Quitter` (3.13+) is undocumented and outside `__all__`, and
  `code.CommandCompiler` is `codeop.CommandCompiler`, which belongs to the
  codeop page; neither has a row here.
* Tracebacks with chained exceptions are not varied, and a replaced
  `sys.excepthook` costs whatever it does.
"""

from __future__ import annotations

import builtins
import code
import codeop
import contextlib
import io
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from itertools import pairwise
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "code.md"
EXPECTED_BLOCKS = 7


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


class CountingCompile(codeop.Compile):
    """A `codeop.Compile` that records the length of every source it compiles."""

    def __init__(self) -> None:
        super().__init__()
        self.lengths: list[int] = []

    def __call__(self, source: str, *args: Any, **kwargs: Any) -> Any:
        self.lengths.append(len(source))
        return super().__call__(source, *args, **kwargs)


class Recorder(code.InteractiveConsole):
    """A console whose output is recorded instead of written to stderr."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.output: list[str] = []

    def write(self, data: str) -> None:
        self.output.append(data)


def counting(interpreter: code.InteractiveInterpreter) -> CountingCompile:
    """Install a counting compiler behind the interpreter's `compile`."""
    compiler = CountingCompile()
    interpreter.compile.compiler = compiler  # type: ignore[attr-defined]
    return compiler


def block(lines: int, width: int = 20) -> list[str]:
    """A function definition of `lines` lines of `width` characters, then a blank line."""
    body = [f"    v{index:06d} = " for index in range(lines - 1)]
    body = [line + "1" * max(1, width - len(line)) for line in body]
    return ["def f():", *body, ""]


def compiled_chars(lines: list[str]) -> int:
    console = code.InteractiveConsole({})
    compiler = counting(console)
    for line in lines:
        console.push(line)
    assert "f" in console.locals, "the block did not run"
    return sum(compiler.lengths)


@pytest.fixture(autouse=True)
def _default_excepthook(monkeypatch: pytest.MonkeyPatch) -> None:
    # Error output reaches write() only while sys.excepthook is the default;
    # some test environments replace it (the exceptiongroup backport on 3.10).
    monkeypatch.setattr(sys, "excepthook", sys.__excepthook__)


def reader(lines: list[str]) -> Callable[[str], str]:
    """A `readfunc` that returns `lines` in turn, then raises EOFError."""
    source = iter(lines)

    def readfunc(prompt: str = "") -> str:
        try:
            return next(source)
        except StopIteration:
            raise EOFError from None

    return readfunc


class TestTheInterpreterUsesTheGivenNamespace:
    """`InteractiveInterpreter(locals=None)` | O(1) | O(1): the mapping is
    used, not copied, so construction is independent of its size."""

    def test_the_mapping_is_kept_not_copied(self) -> None:
        namespace = {"x": 10}

        interp = code.InteractiveInterpreter(namespace)
        interp.runsource("y = x + 5")

        assert interp.locals is namespace
        assert namespace["y"] == 15

    @pytest.mark.serial
    def test_construction_does_not_grow_with_the_namespace(self) -> None:
        namespace = {f"n{index}": index for index in range(100_000)}

        peak = peak_bytes(lambda: code.InteractiveInterpreter(namespace))

        assert peak < 5_000, f"construction over 100,000 names allocated {peak} bytes"

    def test_the_default_namespace(self) -> None:
        assert code.InteractiveInterpreter().locals == {"__name__": "__console__", "__doc__": None}

    def test_the_console_and_interact_use_the_given_mapping_too(self) -> None:
        namespace: dict[str, Any] = {}

        assert code.InteractiveConsole(namespace).locals is namespace
        with contextlib.redirect_stderr(io.StringIO()):
            code.interact(readfunc=reader(["z = 3"]), local=namespace, banner="", exitmsg="")

        assert namespace["z"] == 3


class TestRunsourceReportsWhetherMoreIsNeeded:
    """`runsource()` | O(c) + x: `True` means more input is needed; `False`
    covers both code that ran and a syntax error that was reported."""

    def test_complete_input_runs_and_returns_false(self) -> None:
        interp = code.InteractiveInterpreter({})

        assert interp.runsource("a = 1") is False
        assert interp.locals["a"] == 1

    def test_incomplete_input_runs_nothing_and_returns_true(self) -> None:
        interp = code.InteractiveInterpreter({})

        assert interp.runsource("if True:\n    a = 1") is True
        assert "a" not in interp.locals

    def test_a_syntax_error_is_reported_through_write_not_raised(self) -> None:
        interp = Recorder({})

        assert interp.runsource("a = = 1") is False
        assert "SyntaxError" in "".join(interp.output)

    def test_one_exec_call_compiles_under_3c_characters(self) -> None:
        lines = block(400)
        source = "\n".join(lines) + "\n"
        interp = code.InteractiveInterpreter({})
        compiler = counting(interp)

        assert interp.runsource(source, symbol="exec") is False
        assert "f" in interp.locals
        assert sum(compiler.lengths) <= 3 * len(source) + 3, compiler.lengths


class TestRuncodeReportsOrPropagates:
    """`runcode()` | O(x): an exception goes to `showtraceback()`, but
    `SystemExit` propagates."""

    def test_an_exception_is_shown_through_write(self) -> None:
        interp = Recorder({})

        interp.runcode(compile("1 / 0", "<input>", "single"))

        assert "ZeroDivisionError" in "".join(interp.output)

    def test_a_replaced_excepthook_receives_it_instead(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        hooked: list[type[BaseException]] = []
        monkeypatch.setattr(sys, "excepthook", lambda typ, value, tb: hooked.append(typ))
        interp = Recorder({})

        interp.runcode(compile("1 / 0", "<input>", "single"))

        assert hooked == [ZeroDivisionError]
        assert interp.output == []

    def test_system_exit_propagates(self) -> None:
        interp = code.InteractiveInterpreter({})

        with pytest.raises(SystemExit) as caught:
            interp.runcode(compile("raise SystemExit(3)", "<input>", "exec"))

        assert caught.value.code == 3


class TestCompileCommandCompilesAFewTimes:
    """`compile_command()` | O(c) | O(c): the source is compiled up to three
    times to tell complete, incomplete and invalid input apart."""

    @pytest.fixture
    def compiled(self, monkeypatch: pytest.MonkeyPatch) -> list[str]:
        sources: list[str] = []
        original = codeop._compile  # type: ignore[attr-defined]

        def recording(source: str, *args: Any, **kwargs: Any) -> Any:
            sources.append(source)
            return original(source, *args, **kwargs)

        monkeypatch.setattr(codeop, "_compile", recording)
        return sources

    def test_it_is_the_codeop_function(self) -> None:
        assert code.compile_command is codeop.compile_command

    @pytest.mark.parametrize(
        ("source", "outcome"),
        [
            ("x = 1", "code"),
            ("if x:", "incomplete"),
            ("x = (", "incomplete"),
            ("if x", "invalid"),
            ("def f(:", "invalid"),
            ("", "code"),
            ("# a comment", "code"),
        ],
    )
    def test_at_most_three_compiles_of_the_source(
        self, compiled: list[str], source: str, outcome: str
    ) -> None:
        try:
            result = code.compile_command(source)
        except SyntaxError:
            observed = "invalid"
        else:
            observed = "incomplete" if result is None else "code"

        assert observed == outcome
        assert 1 <= len(compiled) <= 3, compiled
        assert sum(map(len, compiled)) <= 3 * max(len(source), len("pass")) + 3, compiled


class TestPushRecompilesTheWholeBuffer:
    """`push(line)` | O(c) + x, and a block of b lines costs O(b·c) over its
    pushes. Characters handed to the compiler separate that from O(c) with no
    tolerance; the timing tests corroborate it."""

    def test_every_push_compiles_the_whole_buffer(self) -> None:
        lines = block(50)
        console = code.InteractiveConsole({})
        compiler = counting(console)

        for count, line in enumerate(lines, start=1):
            compiler.lengths.clear()
            console.push(line)
            buffered = len("\n".join(lines[:count]))
            assert max(compiler.lengths) >= buffered, (count, compiler.lengths)

        assert console.buffer == []

    def test_four_times_the_lines_compiles_about_sixteen_times_the_characters(self) -> None:
        small = compiled_chars(block(100))
        large = compiled_chars(block(400))

        ratio = large / small
        assert ratio > 12, f"4x the lines compiled x{ratio:.2f} the characters; O(c) gives x4"

    def test_the_line_count_matters_at_a_fixed_character_count(self) -> None:
        many = block(400, width=30)
        few = block(40, width=300)
        many_chars, few_chars = len("\n".join(many)), len("\n".join(few))
        assert abs(many_chars - few_chars) < many_chars * 0.1, (many_chars, few_chars)

        ratio = compiled_chars(many) / compiled_chars(few)

        assert ratio > 5, f"10x the lines at {many_chars} characters compiled x{ratio:.2f}"

    @pytest.mark.timing
    def test_pushing_a_block_is_quadratic_and_compiling_it_once_is_not(self) -> None:
        def pushed(lines: list[str]) -> Callable[[], None]:
            def run() -> None:
                console = code.InteractiveConsole({})
                for line in lines:
                    console.push(line)

            return run

        def once(lines: list[str]) -> Callable[[], Any]:
            source = "\n".join(lines) + "\n"
            return lambda: code.InteractiveInterpreter({}).runsource(source, symbol="exec")

        push_ns = [best_ns(pushed(block(size))) for size in (25, 100, 400)]
        once_ns = [best_ns(once(block(size)), repeats=7) for size in (400, 1_600, 6_400)]
        push_steps = [later / earlier for earlier, later in pairwise(push_ns)]
        once_steps = [later / earlier for earlier, later in pairwise(once_ns)]

        assert all(step > 8 for step in push_steps), f"pushes: {push_ns} ns, steps {push_steps}"
        assert all(step < 8 for step in once_steps), f"once: {once_ns} ns, steps {once_steps}"


class TestResetbufferDropsTheLines:
    """`resetbuffer()` | O(b) | O(1)."""

    def test_it_empties_the_buffer(self) -> None:
        console = code.InteractiveConsole({})
        assert console.push("while True:") is True

        console.resetbuffer()

        assert console.buffer == []
        assert console.push("x = 1") is False

    @pytest.mark.timing
    def test_dropping_more_lines_costs_more(self) -> None:
        def drop(lines: int) -> float:
            best: float | None = None
            for _ in range(5):
                console = code.InteractiveConsole({})
                console.buffer = [str(index) for index in range(lines)]
                start = time.perf_counter_ns()
                console.resetbuffer()
                elapsed = time.perf_counter_ns() - start
                best = elapsed if best is None else min(best, elapsed)
            assert best is not None
            return best

        small, large = drop(1_000), drop(1_000_000)

        assert large > small * 100, f"1,000x the lines: {small:.0f}ns to {large:.0f}ns"


class TestShowtracebackWalksEveryFrame:
    """`showtraceback()` | O(f) | O(f), even where the printed traceback
    collapses repeated lines."""

    @staticmethod
    def failing(depth: int, distinct: bool) -> tuple[Recorder, Callable[[], None]]:
        interp = Recorder({})
        if distinct:
            chain = "\n".join(f"def f{i}(): f{i + 1}()" for i in range(depth))
            interp.runsource(f"{chain}\ndef f{depth}(): 1 / 0\n", symbol="exec")
            call = compile("f0()", "<input>", "single")
        else:
            interp.runsource("def f(n):\n    if n: f(n - 1)\n    else: 1 / 0\n", symbol="exec")
            call = compile(f"f({depth})", "<input>", "single")
        return interp, lambda: interp.runcode(call)

    def test_collapsed_output_still_walks_every_frame(self) -> None:
        results = []
        for depth in (50, 500):
            interp = Recorder({})
            interp.runsource("def f(n):\n    if n: f(n - 1)\n    else: 1 / 0\n", symbol="exec")
            peaks = []
            for _ in range(2):  # the first pass warms the formatter
                try:
                    exec(f"f({depth})", interp.locals)
                except ZeroDivisionError:
                    peaks.append(peak_bytes(interp.showtraceback))
            results.append((peaks[-1], len(interp.output[-1])))

        (small_peak, small_out), (large_peak, large_out) = results
        assert abs(large_out - small_out) < 10, f"output lengths {small_out}, {large_out}"
        assert large_peak > small_peak * 5, f"peaks {small_peak}, {large_peak}"

    def test_distinct_frames_are_all_printed(self) -> None:
        lengths = []
        for depth in (50, 500):
            interp, fail = self.failing(depth, distinct=True)
            fail()
            lengths.append(len(interp.output[-1]))

        assert lengths[1] > lengths[0] * 5, lengths


class TestShowsyntaxerrorFormatsOneLine:
    """`showsyntaxerror(filename=None)` | O(k) | O(k): the offending line,
    with no stack and no earlier lines."""

    @staticmethod
    def shown(source: str) -> str:
        interp = Recorder({})
        try:
            compile(source, "<string>", "exec")
        except SyntaxError:
            interp.showsyntaxerror()
        else:
            raise AssertionError("the source compiled")
        return "".join(interp.output)

    def test_the_output_grows_with_the_offending_line(self) -> None:
        short = self.shown("x = = " + "1" * 100)
        long = self.shown("x = = " + "1" * 100_000)

        assert len(long) > len(short) * 50, (len(short), len(long))

    def test_earlier_lines_add_nothing(self) -> None:
        alone = self.shown("x = = 1")
        after = self.shown("y = 1\n" * 1_000 + "x = = 1")

        assert abs(len(after) - len(alone)) < 50, (alone, after)


class TestWriteGoesToStderr:
    """`write(data)` | O(w): `data` is handed to `sys.stderr.write`."""

    def test_the_same_object_reaches_stderr(self, monkeypatch: pytest.MonkeyPatch) -> None:
        received: list[str] = []

        class Stream:
            def write(self, text: str) -> int:
                received.append(text)
                return len(text)

        monkeypatch.setattr(sys, "stderr", Stream())
        data = "x" * 1_000

        code.InteractiveInterpreter().write(data)

        assert len(received) == 1
        assert received[0] is data


class TestRawInputReadsStdin:
    """`raw_input(prompt="")` | O(k): one line through `input()`."""

    def test_one_line_without_its_newline(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO("first\nsecond\n"))
        monkeypatch.setattr(sys, "stdout", io.StringIO())

        console = code.InteractiveConsole()

        assert console.raw_input(">>> ") == "first"
        assert console.raw_input() == "second"
        with pytest.raises(EOFError):
            console.raw_input()


class TestInteractPushesEachLine:
    """`interact()` | O(b·c) + x per block: one `push()` per line read, until
    `raw_input()` raises `EOFError`."""

    def test_one_push_per_line_until_eof(self) -> None:
        pushed: list[str] = []

        class Counting(Recorder):
            def push(self, line: str, *args: Any, **kwargs: Any) -> bool:
                pushed.append(line)
                return super().push(line, *args, **kwargs)

        lines = ["def f():", "    return 7", "", "r = f()"]
        console = Counting({})
        console.raw_input = reader(lines)  # type: ignore[method-assign]

        console.interact(banner="BANNER", exitmsg="BYE")

        assert pushed == lines
        assert console.locals["r"] == 7
        assert console.output[0] == "BANNER\n"
        assert console.output[-1] == "BYE\n"

    def test_readfunc_replaces_raw_input(self) -> None:
        taken: list[str] = []

        def readfunc(prompt: str) -> str:
            taken.append(prompt)
            if len(taken) > 2:
                raise EOFError
            return "pass"

        with contextlib.redirect_stderr(io.StringIO()):
            code.interact(readfunc=readfunc, banner="", exitmsg="")

        assert len(taken) == 3


class TestExitInsideAConsole:
    """`local_exit` (3.13+) makes `exit()` end only the console; without it,
    `SystemExit` leaves `interact()`."""

    @pytest.fixture(autouse=True)
    def _spare_stdin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # The site builtin exit() closes sys.stdin before raising.
        monkeypatch.setattr(sys, "stdin", io.StringIO())

    def test_without_local_exit_system_exit_propagates(self) -> None:
        console = Recorder({})
        console.raw_input = reader(["a = 1", "exit()", "a = 2"])  # type: ignore[method-assign]

        with pytest.raises(SystemExit):
            console.interact(banner="", exitmsg="")

        assert console.locals["a"] == 1

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="local_exit is 3.13+")
    def test_local_exit_ends_only_the_console(self) -> None:
        original_exit = builtins.exit
        console = Recorder({}, local_exit=True)
        console.raw_input = reader(["a = 1", "exit()", "a = 2"])  # type: ignore[method-assign]

        console.interact(banner="", exitmsg="")

        assert console.locals["a"] == 1
        assert builtins.exit is original_exit

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="local_exit exists from 3.13")
    def test_local_exit_is_rejected_before_313(self) -> None:
        with pytest.raises(TypeError):
            code.InteractiveConsole({}, local_exit=True)  # type: ignore[call-arg]
        with pytest.raises(TypeError):
            code.interact(readfunc=reader([]), local_exit=True)  # type: ignore[call-arg]


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
    """Each block runs in its own subprocess with stdin from /dev/null, so a
    block that reached `sys.stdin` would see end of input rather than hang,
    and asserts its own result."""

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
        target = "assert namespace['first'] == 1"
        line, source = next((n, s) for n, s in _blocks() if target in s)
        mutated = source.replace(target, "assert namespace['first'] == 3", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0

    def test_no_block_blocks_on_stdin(self) -> None:
        """`interact()` and `raw_input()` read `sys.stdin` by default; every
        block that reaches them supplies its own input."""
        for line, source in _blocks():
            if "interact(" in source:
                assert "readfunc" in source or "def raw_input" in source, f"{PAGE.name}:{line}"
