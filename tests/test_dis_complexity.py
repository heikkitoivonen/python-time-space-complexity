"""Tests for docs/stdlib/dis.md.

The page prices every decoding entry point per code object: the line table and
the jump targets are collected first, then the bytecode is walked once. That
structure is settled by observation: `dis.findlabels` is replaced with a
counting wrapper, and each entry point is asserted to call it once per code
object it decodes and never for one it only wraps or describes. The j·t term
is then settled on `findlabels` alone by timing, laziness and held space by
traced allocation, and the scope of each entry point (which code objects,
which frame) by the text it produces.

Measurement scope:

* The j·t term: `findlabels()` on a function of 500 `if x == i: return i`
  branches against one of 8,000 (16x the code, each branch one target) must
  grow more than 40x, where a linear walk predicts 16x and a quadratic one
  256x; 78x to 136x was measured on 3.10 to 3.14. The control is 2,500
  against 40,000 lines of `x = x + 1`, with no targets, which must grow less
  than 40x and measured 17x to 18x.
* The per-instruction target lookup: 1,000 branches followed by 20,000
  straight lines, against 21,000 straight lines, through
  `list(get_instructions())`. On 3.10 the branchy function must cost more
  than 3x the straight one (measured 6x to 7x at 5,000 and 40,000 tail
  lines); on 3.11+ less than 2x (measured 1.0x to 1.4x).
* Laziness: draining `get_instructions()` over a one-line function of about
  40,000 code units without keeping the instructions peaks under 50 KB, and
  `list()` of it over 5 MB. That input has one line and no targets, so it
  shows the instructions are not retained; it does not measure how the line
  and target tables grow. Draining `findlinestarts()` over 20,000 lines
  peaks under 10 KB, and `list()` of it over 1 MB.
* `Bytecode()` calls `findlabels` zero times; its peak grows more than 10x
  from 1,000 to 20,000 lines (measured 19x to 25x), so the line table is
  read at construction. Every `iter()` over it calls `findlabels` once more.
* `code_info()` over 100 and 50,000 lines of `x = x + 1`, whose tables are
  identical, must stay within 20x (measured 1.0x to 2.8x) where a walk of the
  bytecode predicts 500x; its line count grows with the constant table.
  `show_code()` prints it and `Bytecode.info()` returns it.
* `dis()` on a function with one nested function calls `findlabels` twice,
  prints "Disassembly of" for the nested one, and not at `depth=0`;
  `disassemble()` and `Bytecode.dis()` call it once and print no nested
  listing. A class is listed in sorted attribute order. `python -m dis` on a
  file lists a nested function.
* Tracebacks: `from_traceback()` holds the innermost frame's code and its
  `tb_lasti`; `distb(tb)` produces the same text as `disassemble()` on the
  first entry's frame; `dis()` with no argument produces the same text as
  `from_traceback()` on `sys.last_traceback` (and `sys.last_exc` from 3.12).
* The opcode collections are asserted to be lists, `opmap` a dict, and the
  version-gated collections, `Positions`, the 3.13 `Instruction` fields,
  `starts_line`'s type and `findlinestarts()` yielding `None` are asserted on
  the versions each row names.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* Whether jump targets are collected at the `get_instructions()` call (3.13+)
  or at the first `next()` (3.10-3.12). The page claims only that they are
  collected before the first instruction, which is what is asserted.

* Treating the formatting of one constant or name as O(1) is a cost-model
  assumption; a large constant costs its `repr()` wherever it is formatted.
* Compile cost for a source-string argument, and the O(m log m) sort of a
  class or module's attributes, which is read from Lib/dis.py's `dis()`; only
  the sorted order is observed.
* `adaptive=True` with tier-two executors attached: each `ENTER_EXECUTOR` is
  resolved through `_opcode.get_executor()`, which scans the code object.
  Executors are not attached in a default build, so that path is not reached.
* `Formatter`, `ArgResolver`, `print_instructions()`, `get_executor()`,
  `pretty_flags()`, `deoptmap`, `Instruction.label` and `Instruction.make()`
  are in the module namespace but not in the official documentation or
  `__all__`, and are not priced on the page.
  `main()` is the `python -m dis` entry point, priced under that row.
* `stack_effect()`, the named-tuple fields and the opcode tables are O(1) by
  construction: a C table lookup, a tuple index, a list index or dict lookup.
  They are exercised, not timed.
"""

from __future__ import annotations

import dis
import io
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import types
from collections.abc import Callable, Iterable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "dis.md"
EXPECTED_BLOCKS = 8


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


def drain(iterable: Iterable[Any]) -> None:
    """Consume an iterable without keeping what it yields."""
    for _ in iterable:
        pass


def function_code(source: str, name: str = "f") -> types.CodeType:
    namespace: dict[str, Any] = {}
    exec(source, namespace)
    return namespace[name].__code__


def branches(count: int, tail: int = 0) -> types.CodeType:
    """A function of `count` branches, each one jump target, then `tail` lines."""
    body = "".join(f"    if x == {i}: return {i}\n" for i in range(count))
    body += "    x = x + 1\n" * tail
    return function_code(f"def f(x):\n{body}    return x\n")


def straight(lines: int) -> types.CodeType:
    """A function of `lines` identical statements and no jump targets."""
    return function_code("def f(x):\n" + "    x = x + 1\n" * lines + "    return x\n")


def wide(names: int) -> types.CodeType:
    """A one-line function whose bytecode grows with `names`."""
    return function_code("def f(x):\n    return [" + ", ".join(["x"] * names) + "]\n")


# Compiled from unannotated source: from 3.14 an annotated inner function
# carries a third, `__annotate__`, code object.
OUTER = function_code(
    "def outer():\n    def inner():\n        return 1\n    return inner\n", "outer"
)


def targets(code: types.CodeType) -> list[int]:
    """findlabels() on the raw bytecode, which is what it documents taking."""
    raw: Any = code.co_code
    return dis.findlabels(raw)


def listing(func: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
    buffer = io.StringIO()
    func(*args, file=buffer, **kwargs)
    return buffer.getvalue()


@pytest.fixture
def label_calls(monkeypatch: pytest.MonkeyPatch) -> list[bytes]:
    """Record every call to dis.findlabels, which each decoding pass makes."""
    calls: list[bytes] = []
    original: Any = dis.findlabels

    def counting(code: bytes) -> list[int]:
        calls.append(code)
        return original(code)

    monkeypatch.setattr(dis, "findlabels", counting)
    return calls


class TestEachPassCollectsJumpTargetsOnce:
    """Every decoding row is O(n + j·t) per code object; `Bytecode()` is O(n).

    A counting `findlabels` separates the entry points that decode from those
    that only wrap or describe a code object, with no tolerance.
    """

    def test_get_instructions_collects_targets_before_the_first(
        self, label_calls: list[bytes]
    ) -> None:
        instructions = dis.get_instructions(OUTER)
        next(instructions)
        assert label_calls == [OUTER.co_code]
        drain(instructions)
        assert len(label_calls) == 1

    def test_building_a_bytecode_decodes_nothing(self, label_calls: list[bytes]) -> None:
        dis.Bytecode(OUTER)
        assert label_calls == []

    def test_every_pass_over_a_bytecode_starts_again(self, label_calls: list[bytes]) -> None:
        bytecode = dis.Bytecode(OUTER)
        drain(bytecode)
        drain(bytecode)
        assert len(label_calls) == 2

    def test_dis_decodes_each_nested_code_object(self, label_calls: list[bytes]) -> None:
        listing(dis.dis, OUTER)
        assert len(label_calls) == 2

    def test_single_object_entry_points_decode_once(self, label_calls: list[bytes]) -> None:
        listing(dis.disassemble, OUTER)
        dis.Bytecode(OUTER).dis()
        assert label_calls == [OUTER.co_code] * 2

    def test_code_info_decodes_nothing(self, label_calls: list[bytes]) -> None:
        dis.code_info(OUTER)
        dis.Bytecode(OUTER).info()
        listing(dis.show_code, OUTER)
        assert label_calls == []


class TestJumpTargetsAreQuadratic:
    """`findlabels(code)` | O(n + j·t): each target is checked against the
    targets already found. 16x the branches separates 16x from 256x."""

    @pytest.mark.timing
    def test_sixteen_times_the_targets_costs_more_than_forty_times(self) -> None:
        small, large = branches(500), branches(8000)
        assert len(targets(large)) == 8000

        ratio = best_ns(lambda: targets(large)) / best_ns(lambda: targets(small))
        assert ratio > 40, f"16x the branches cost x{ratio:.1f}; linear would be x16"

    @pytest.mark.timing
    def test_sixteen_times_the_code_without_targets_stays_linear(self) -> None:
        small, large = straight(2500), straight(40000)
        assert targets(large) == []

        ratio = best_ns(lambda: targets(large)) / best_ns(lambda: targets(small))
        assert ratio < 40, f"16x the code with no targets cost x{ratio:.1f}"


class TestTargetLookupPerInstruction:
    """Version Notes: from 3.11 each instruction's offset is looked up in a set
    of targets; on 3.10 it scans the list, O(n·t). A thousand targets ahead of
    a long straight tail separates the two."""

    @pytest.mark.timing
    def test_a_thousand_targets_only_cost_the_tail_on_3_10(self) -> None:
        branchy, plain = branches(1000, tail=20000), straight(21000)

        ratio = best_ns(lambda: list(dis.get_instructions(branchy)), repeats=3) / best_ns(
            lambda: list(dis.get_instructions(plain)), repeats=3
        )
        if sys.version_info < (3, 11):
            assert ratio > 3, f"1,000 targets cost x{ratio:.2f} over straight code on 3.10"
        else:
            assert ratio < 2, f"1,000 targets cost x{ratio:.2f} over straight code"


class TestIterationIsLazy:
    """`get_instructions()` | O(n) space held, one `Instruction` at a time;
    `findlinestarts()` | O(1) space. Traced allocation, orders of magnitude
    apart."""

    def test_draining_instructions_holds_one_at_a_time(self) -> None:
        code = wide(20000)
        assert len(code.co_code) // 2 > 40000
        drain(dis.get_instructions(code))

        streamed = peak_bytes(lambda: drain(dis.get_instructions(code)))
        kept = peak_bytes(lambda: list(dis.get_instructions(code)))
        assert streamed < 50_000, streamed
        assert kept > 5_000_000, kept

    def test_findlinestarts_is_a_generator(self) -> None:
        code = straight(20000)
        assert isinstance(dis.findlinestarts(code), types.GeneratorType)

        streamed = peak_bytes(lambda: drain(dis.findlinestarts(code)))
        kept = peak_bytes(lambda: list(dis.findlinestarts(code)))
        assert streamed < 10_000, streamed
        assert kept > 1_000_000, kept

    def test_building_a_bytecode_reads_the_line_table(self) -> None:
        small, large = straight(1000), straight(20000)
        dis.Bytecode(small)

        ratio = peak_bytes(lambda: dis.Bytecode(large)) / peak_bytes(lambda: dis.Bytecode(small))
        assert ratio > 10, f"20x the lines grew the construction peak x{ratio:.1f}"


class TestCodeInfoReadsTablesOnly:
    """`code_info(x)` | O(k): the tables, never the bytecode."""

    @pytest.mark.timing
    def test_bytecode_length_does_not_enter(self) -> None:
        short, long = straight(100), straight(50000)
        assert dis.code_info(short) == dis.code_info(long)

        ratio = best_ns(lambda: dis.code_info(long), repeats=20) / best_ns(
            lambda: dis.code_info(short), repeats=20
        )
        assert ratio < 20, f"500x the bytecode cost code_info x{ratio:.1f}"

    def test_output_grows_with_the_constant_table(self) -> None:
        def constants(count: int) -> types.CodeType:
            body = "".join(f"    x = x + {i}\n" for i in range(1000, 1000 + count))
            return function_code(f"def f(x):\n{body}    return x\n")

        small, large = constants(10), constants(1000)
        assert len(large.co_consts) - len(small.co_consts) == 990
        grown = len(dis.code_info(large).splitlines()) - len(dis.code_info(small).splitlines())
        assert grown == 990

    def test_show_code_and_info_are_code_info(self) -> None:
        info = dis.code_info(OUTER)
        assert listing(dis.show_code, OUTER) == info + "\n"
        assert dis.Bytecode(OUTER).info() == info


class TestWhatEachEntryPointCovers:
    """`dis()` follows nested code objects down to `depth`; `disassemble()` and
    `Bytecode.dis()` stay on one."""

    def test_dis_lists_the_nested_function(self) -> None:
        assert "Disassembly of <code object inner" in listing(dis.dis, OUTER)
        assert "Disassembly of" not in listing(dis.dis, OUTER, depth=0)

    def test_disassemble_and_bytecode_dis_stay_on_one_code_object(self) -> None:
        assert dis.disco is dis.disassemble
        assert "Disassembly of" not in listing(dis.disassemble, OUTER)
        assert "Disassembly of" not in dis.Bytecode(OUTER).dis()
        assert dis.Bytecode(OUTER).dis() == listing(dis.dis, OUTER, depth=0)

    def test_a_class_is_listed_in_sorted_attribute_order(self) -> None:
        class Sample:
            def zeta(self) -> int:
                return 1

            def alpha(self) -> int:
                return 2

        text = listing(dis.dis, Sample)
        assert text.index("Disassembly of alpha") < text.index("Disassembly of zeta")

    def test_the_command_line_lists_nested_code(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "sample.py"
        source.write_text("def outer():\n    def inner():\n        return 1\n    return inner\n")
        result = subprocess.run(
            [sys.executable, "-m", "dis", str(source)],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=True,
        )
        assert "Disassembly of <code object inner" in result.stdout


def _raise_inner() -> float:
    return 1 / 0


def _raise_outer() -> float:
    return _raise_inner()


def _traceback() -> types.TracebackType:
    try:
        _raise_outer()
    except ZeroDivisionError as error:
        assert error.__traceback__ is not None
        return error.__traceback__
    raise AssertionError("no exception raised")


def _innermost(tb: types.TracebackType) -> types.TracebackType:
    while tb.tb_next is not None:
        tb = tb.tb_next
    return tb


class TestTracebacks:
    """`from_traceback()` | O(f + n) walks to the innermost frame; `distb(tb)`
    disassembles the entry it is given; `distb()` and `dis()` with no argument
    walk the last traceback."""

    def test_from_traceback_takes_the_innermost_frame(self) -> None:
        tb = _traceback()
        bytecode: Any = dis.Bytecode.from_traceback(tb)
        assert bytecode.codeobj is _raise_inner.__code__
        assert bytecode.current_offset == _innermost(tb).tb_lasti

    def test_distb_disassembles_the_entry_it_is_given(self) -> None:
        tb = _traceback()
        assert tb.tb_frame.f_code is not _raise_inner.__code__
        expected = listing(dis.disassemble, tb.tb_frame.f_code, tb.tb_lasti)
        assert listing(dis.distb, tb) == expected

    def test_no_argument_walks_the_last_traceback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        tb = _traceback()
        error = ZeroDivisionError()
        error.__traceback__ = tb
        monkeypatch.setattr(sys, "last_traceback", tb, raising=False)
        if sys.version_info >= (3, 12):
            monkeypatch.setattr(sys, "last_exc", error, raising=False)

        expected = dis.Bytecode.from_traceback(tb).dis()
        assert listing(dis.dis) == expected
        assert listing(dis.distb) == expected


class TestInstructionFields:
    """The Instruction and Positions rows, and the versions they name."""

    def test_fields_are_named_tuple_fields(self) -> None:
        first = next(dis.get_instructions(OUTER))
        assert isinstance(first, tuple)
        assert dis.opname[first.opcode] == first.opname
        assert first.offset == 0
        for field in ("arg", "argval", "argrepr", "starts_line", "is_jump_target"):
            assert hasattr(first, field)

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="Positions is Python 3.11+")
    def test_positions_arrive_in_3_11(self) -> None:
        positions_type: Any = vars(dis)["Positions"]
        instructions: list[Any] = list(dis.get_instructions(OUTER))
        positioned = [i for i in instructions if i.positions.lineno is not None]
        assert positioned
        assert isinstance(positioned[0].positions, positions_type)
        assert positions_type()._fields == ("lineno", "end_lineno", "col_offset", "end_col_offset")

    def test_starts_line_is_a_bool_from_3_13(self) -> None:
        first: Any = next(dis.get_instructions(OUTER))
        if sys.version_info >= (3, 13):
            assert first.starts_line is True
            assert first.line_number == OUTER.co_firstlineno
        else:
            assert first.starts_line == next(dis.findlinestarts(OUTER))[1]

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="the fields are Python 3.13+")
    def test_the_3_13_fields(self) -> None:
        instructions: list[Any] = list(dis.get_instructions(branches(3)))
        for instr in instructions:
            assert instr.oparg == instr.arg
            assert dis.opname[instr.baseopcode] == instr.baseopname
            assert instr.start_offset <= instr.offset < instr.cache_offset <= instr.end_offset
            assert instr.jump_target is None or instr.jump_target % 2 == 0
            assert instr.cache_info is None or isinstance(instr.cache_info, list)

    def test_findlinestarts_yields_none_from_3_13(self) -> None:
        code = function_code("def f():\n    try:\n        g()\n    except E:\n        pass\n")
        lines = [line for _, line in dis.findlinestarts(code)]
        assert (None in lines) is (sys.version_info >= (3, 13))


class TestOpcodeCollections:
    """The collections are lists and dicts read in O(1); membership in a
    `has*` list scans it, which is why the page builds a set."""

    def test_the_tables(self) -> None:
        assert isinstance(dis.opname, list)
        assert isinstance(dis.opmap, dict)
        assert isinstance(dis.cmp_op, tuple)
        assert dis.opname[dis.opmap["POP_TOP"]] == "POP_TOP"
        assert dis.EXTENDED_ARG == dis.opmap["EXTENDED_ARG"]
        assert isinstance(dis.HAVE_ARGUMENT, int)

    def test_the_has_collections_are_lists(self) -> None:
        names = ["hasconst", "hasname", "haslocal", "hasfree", "hascompare", "hasjrel", "hasjabs"]
        if sys.version_info >= (3, 12):
            names += ["hasarg", "hasexc"]
        else:
            assert not hasattr(dis, "hasarg")
        for name in names:
            assert isinstance(getattr(dis, name), list), name

    def test_hasjump_is_hasjrel_from_3_13(self) -> None:
        if sys.version_info >= (3, 13):
            assert dis.hasjump is dis.hasjrel  # pyright: ignore[reportAttributeAccessIssue]
        else:
            assert not hasattr(dis, "hasjump")

    def test_stack_effect(self) -> None:
        assert dis.stack_effect(dis.opmap["POP_TOP"]) == -1


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
        line, source = next((n, s) for n, s in _blocks() if "assert targets == 200" in s)
        mutated = source.replace("assert targets == 200", "assert targets == 201", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
