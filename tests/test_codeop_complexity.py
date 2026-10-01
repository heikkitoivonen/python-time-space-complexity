"""Tests for docs/stdlib/codeop.md.

The page prices every compiling call at O(n) in the length of the source it is
given, and the two constructors at O(1). Space is settled by traced
allocation, time by a ratio over a sixteen-fold step in the source, and the
behavioural claims - what each call returns, which flags survive between
calls, what a constructor does - by observation.

Measurement scope:

* `compile_command()`, a `Compile` instance and a `CommandCompiler` instance
  each compile a list display of 2,000 and of 20,000 elements (about 10 KB and
  100 KB of source). The traced peak grows more than 5x and less than 30x over
  that tenfold step: a constant-space call would stay flat and a quadratic one
  would grow about 100x. In a timing test, 16x the source (5,000 to 80,000
  elements) costs between 4x and 64x, which excludes both O(1) and O(n^2).
  Each callable is warmed on the smaller source first.
* The constructors are asserted to call nothing that compiles: `compile` is
  shadowed in `codeop`'s namespace by a counter that must stay at zero.
* `compile_command()` and a `CommandCompiler` return a code object for
  `print("hello")`, `None` for `if True:` and raise `SyntaxError` for
  `if True`.
* A `Compile` instance compiles with source, filename and mode passed
  positionally - the filename lands in `co_filename`, and two statements
  compile in `exec` mode but not in `eval` - and raises `TypeError` when `compile()`'s `dont_inherit` is
  passed as a fifth positional argument.
* `__future__` flags are read from `co_flags` with the `annotations` feature:
  set on later input for a `CommandCompiler` and a `Compile` after they have
  compiled the import, and clear for `compile_command()` on the same later
  input after it has compiled the import.
* The claim that an interactive loop compiles everything typed so far each
  time a line arrives is observed on `code.InteractiveConsole`: its `compile` attribute is a
  `CommandCompiler`, and a recording wrapper sees one call per pushed line,
  each with the whole buffer so far.
* Both fenced blocks run in their own subprocess, and a mutated assertion is
  asserted to make its block fail.

Not settled here:

* Only one shape of source is measured - a single long list display. The
  O(n) is the ordinary case: pathological sources, such as many distinct
  constants whose hashes collide in the compiler's constant tables, are not
  priced (the page names no such input) and not varied here. Deeply
  nested source, long string literals and many short statements are not
  varied, and a syntax error found early can stop the parse before the end of
  the source, so the O(n) is an upper bound for invalid input.
* The page makes no claim about how many times one call compiles its source
  (Lib/codeop.py compiles it more than once to tell incomplete input from
  invalid input); that is a constant factor and is not asserted here.
"""

from __future__ import annotations
import __future__

import code
import codeop
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import types
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "codeop.md"
EXPECTED_BLOCKS = 2
ANNOTATIONS = __future__.annotations.compiler_flag


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


def future_flags(code_object: Any) -> int:
    """The co_flags of a compiled result, which must not be `None`."""
    assert code_object is not None
    return code_object.co_flags


def source_of(elements: int) -> str:
    return "x = [" + "1, " * elements + "]"


def compile_command(source: str) -> Any:
    return codeop.compile_command(source)


def compile_instance(source: str) -> Any:
    return codeop.Compile()(source, "<input>", "single")


def command_compiler_instance(source: str) -> Any:
    return codeop.CommandCompiler()(source)


COMPILERS = pytest.mark.parametrize(
    "compiler",
    [compile_command, compile_instance, command_compiler_instance],
    ids=["compile_command", "Compile", "CommandCompiler"],
)


class TestCompilingIsLinearInTheSource:
    """Every compiling row: O(n) time and O(n) space, n = source length."""

    @pytest.mark.serial
    @COMPILERS
    def test_the_peak_follows_the_source(self, compiler: Callable[[str], Any]) -> None:
        small, large = source_of(2_000), source_of(20_000)
        compiler(small)

        small_peak = peak_bytes(lambda: compiler(small))
        large_peak = peak_bytes(lambda: compiler(large))

        assert 5 * small_peak < large_peak < 30 * small_peak, (
            f"10x the source: {small_peak} B against {large_peak} B"
        )

    @pytest.mark.timing
    @COMPILERS
    def test_sixteen_times_the_source_costs_sixteen_times_the_time(
        self, compiler: Callable[[str], Any]
    ) -> None:
        small, large = source_of(5_000), source_of(80_000)
        compiler(small)

        ratio = best_ns(lambda: compiler(large)) / best_ns(lambda: compiler(small))

        assert 4 < ratio < 64, f"16x the source cost x{ratio:.1f}"


class TestConstructorsCompileNothing:
    """`codeop.Compile()` and `codeop.CommandCompiler()`: O(1)."""

    @pytest.mark.parametrize("factory", [codeop.Compile, codeop.CommandCompiler])
    def test_building_one_calls_no_compiler(
        self, factory: Callable[[], Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[Any] = []
        monkeypatch.setattr(codeop, "compile", lambda *a, **k: calls.append(a), raising=False)

        factory()

        assert calls == []


class TestThreeAnswers:
    """Complete input compiles, incomplete input is `None`, invalid input raises."""

    @pytest.mark.parametrize(
        "check", [codeop.compile_command, codeop.CommandCompiler()], ids=["function", "instance"]
    )
    def test_each_answer(self, check: Callable[[str], Any]) -> None:
        assert isinstance(check('print("hello")'), types.CodeType)
        assert check("if True:") is None
        with pytest.raises(SyntaxError):
            check("if True")


class TestCompileTakesThreeOfCompilesArguments:
    """`Compile` takes the source, filename and mode arguments of `compile()`, not all of them."""

    def test_source_filename_and_mode_are_honoured(self) -> None:
        compiled = codeop.Compile()("x = 1\ny = 2\n", "<page>", "exec")

        assert isinstance(compiled, types.CodeType)
        assert compiled.co_filename == "<page>"
        with pytest.raises(SyntaxError):
            codeop.Compile()("x = 1\ny = 2\n", "<page>", "eval")

    def test_dont_inherit_is_not_accepted_positionally(self) -> None:
        compiler: Any = codeop.Compile()
        with pytest.raises(TypeError):
            compiler("x = 1", "<input>", "exec", 0, True)


class TestFutureStatementsAreRemembered:
    """`Compile` and `CommandCompiler` keep `__future__` flags; the function does not."""

    def test_a_command_compiler_keeps_them(self) -> None:
        session = codeop.CommandCompiler()
        assert not future_flags(session("x = 1")) & ANNOTATIONS

        session("from __future__ import annotations")

        assert future_flags(session("x = 1")) & ANNOTATIONS

    def test_a_compile_instance_keeps_them(self) -> None:
        compiler = codeop.Compile()
        assert not future_flags(compiler("x = 1", "<input>", "exec")) & ANNOTATIONS

        compiler("from __future__ import annotations", "<input>", "exec")

        assert future_flags(compiler("x = 1", "<input>", "exec")) & ANNOTATIONS

    def test_compile_command_forgets_them(self) -> None:
        codeop.compile_command("from __future__ import annotations")

        assert not future_flags(codeop.compile_command("x = 1")) & ANNOTATIONS


class TestAnInteractiveLoopRecompilesItsBuffer:
    """An interactive loop recompiles everything typed so far on each line."""

    def test_the_console_compiles_the_whole_buffer_on_every_line(self) -> None:
        console = code.InteractiveConsole()
        assert isinstance(console.compile, codeop.CommandCompiler)
        seen: list[str] = []
        real = console.compile

        def recording(source: str, *args: Any, **kwargs: Any) -> Any:
            seen.append(source)
            return real(source, *args, **kwargs)

        console.compile = recording  # type: ignore[assignment]
        for line in ["if True:", "    x = 1", "    y = 2"]:
            console.push(line)

        assert seen == ["if True:", "if True:\n    x = 1", "if True:\n    x = 1\n    y = 2"]


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
        line, source = next((n, s) for n, s in _blocks() if "assert session(" in s)
        mutated = source.replace("assert session(", "assert not session(", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
