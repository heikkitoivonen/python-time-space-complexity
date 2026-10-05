"""Tests for docs/stdlib/opcode.md.

The page prices the module as tables built once at import: reading one is
attribute access, indexing `opname` or looking a name up in `opmap` is O(1),
and the one operation that grows is membership in a `has*` list, which scans
it. Identity and type checks settle the table rows, a counting `__eq__`
settles the list scan with no tolerance, and `stack_effect()` is settled by
its results plus one timing test on the size of `oparg`.

Measurement scope:

* Every name in `opcode.__all__` is the same object on two reads and is the
  object `dis` exports under that name. `opmap` is a dict, `opname` a list
  and `cmp_op` a tuple; every `opmap` entry indexes back to its own name
  through `opname`, and every number outside `opmap` reads `'<n>'` unless
  it names one of 3.14's specialized instructions. In a module of 300
  constants, every `LOAD_CONST` past index 255 follows an `EXTENDED_ARG`
  carrying the index's high byte.
* `op in has*` is a probe whose reflected `__eq__` counts calls: it is called
  once per entry for every non-empty `has*` list, and never against a `set`
  of the same list, where only the probe's `__hash__` runs.
* `HAVE_ARGUMENT` on 3.12+: no opcode in `opmap` below it is in `hasarg`,
  and at least one at or above it is not. Before 3.13, where
  `stack_effect()` without an `oparg` raises exactly for the opcodes that use
  one, it raises for every opcode under 256 at or above `HAVE_ARGUMENT` and
  for none below. `opname` has 256 entries before 3.12 and more from 3.12,
  when `opmap` gains pseudo-instructions numbered from 256 and
  `INSTRUMENTED_*` opcodes.
* `hasarg` and `hasexc` exist from 3.12 and `hasjump` from 3.13, and are
  absent before; on 3.13+ `hasjrel is hasjump`. `hasjabs` is empty on 3.11+.
* `stack_effect(BUILD_TUPLE, n)` is `1 - n` for n of 0, 3 and 2**30, and a
  timing test bounds the 2**30 call under 3x the n = 1 call, where a cost
  linear in `oparg` would be a billion times larger. For every opcode in
  `opmap` that accepts the call, `jump=None` returns the larger of the
  `jump=True` and `jump=False` effects, and at least one opcode has two
  different effects so the comparison is not vacuous. On 3.13+ a missing
  `oparg` gives `BUILD_TUPLE` its zero-item effect of 1, and an `oparg`
  passed to `POP_TOP` is ignored; before 3.13 a missing `oparg` for
  `LOAD_CONST` and a surplus one for `POP_TOP` raise `ValueError`.
* Every fenced Python block runs in its own subprocess and asserts its own
  result, and a mutated assertion in one of them is asserted to fail.

Not settled here:

* That opcode numbers, names and the contents of the `has*` lists change
  between releases needs two interpreters in one test. On the supported
  range `LOAD_CONST` is 100 on 3.10 to 3.12, 83 on 3.13 and 82 on 3.14, and
  `HAVE_ARGUMENT` is 90, 44 and 43 over the same releases.
* Treating every table as O(1) to read and index rests on their types and on
  Lib/opcode.py building them once at import; the tables are bounded by the
  opcode count of the release, so there is no size to vary.
* `stack_effect()` is a C function in Python/compile.c (3.10 to 3.12) and
  generated metadata (3.13+); its O(1) in the opcode is read from that
  source, and only `oparg` is varied.
* Names outside `__all__` and the `dis` documentation are not on the page:
  `opcode.i`, `opcode.op` and (3.14) `opcode.m` are loop variables left at
  module level; `MIN_INSTRUMENTED_OPCODE` (3.12+), and on 3.12 alone
  `ENABLE_SPECIALIZATION`, `MIN_PSEUDO_OPCODE`, `MAX_PSEUDO_OPCODE`,
  `is_pseudo` and `oplists`, are internals the module imports or builds.
  `hasnargs`, in `__all__` on 3.10 and 3.11 and always empty, was never in
  the `dis` documentation and is not on the page either.
"""

from __future__ import annotations

import dis
import opcode
import pathlib
import re
import subprocess
import sys
import textwrap
import time
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "opcode.md"
EXPECTED_BLOCKS = 4

HAS_LISTS = [name for name in opcode.__all__ if name.startswith("has")]


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 1) -> float:
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


class CountingProbe:
    """An object whose `__eq__` counts calls and never matches."""

    def __init__(self) -> None:
        self.comparisons = 0
        self.hashes = 0

    def __eq__(self, other: object) -> bool:
        self.comparisons += 1
        return False

    def __hash__(self) -> int:
        self.hashes += 1
        return -12_345


def effect(op: int, jump: bool | None) -> int:
    """`stack_effect` with `oparg` 0, or none where the opcode refuses one before 3.13."""
    try:
        return opcode.stack_effect(op, 0, jump=jump)
    except ValueError:
        return opcode.stack_effect(op, jump=jump)


class TestTablesAreBuiltOnce:
    """`opmap`, `opname`, `cmp_op`, the `has*` lists and the constants | O(1) |
    O(1): built at import, read without computing anything, and re-exported
    by `dis` as the same objects."""

    @pytest.mark.parametrize("name", opcode.__all__)
    def test_every_name_is_the_same_object_on_each_read(self, name: str) -> None:
        assert getattr(opcode, name) is getattr(opcode, name)

    @pytest.mark.parametrize("name", opcode.__all__)
    def test_dis_re_exports_the_same_object(self, name: str) -> None:
        assert getattr(dis, name) is getattr(opcode, name)

    def test_the_tables_are_a_dict_a_list_and_a_tuple(self) -> None:
        assert type(opcode.opmap) is dict
        assert type(opcode.opname) is list
        assert type(opcode.cmp_op) is tuple
        assert all(type(getattr(opcode, name)) is list for name in HAS_LISTS)

    def test_opmap_indexes_back_through_opname(self) -> None:
        assert all(opcode.opname[op] == name for name, op in opcode.opmap.items())

    def test_an_unused_number_reads_as_a_placeholder(self) -> None:
        used = set(opcode.opmap.values())
        unused = [op for op in range(len(opcode.opname)) if op not in used]
        placeholders = [op for op, name in enumerate(opcode.opname) if name.startswith("<")]

        # 3.14 also names its specialized instructions, which opmap leaves out.
        specialized = set(getattr(opcode, "_specialized_opmap", {}))
        named = {opcode.opname[op] for op in unused} - {f"<{op}>" for op in unused}

        assert placeholders, "every opcode number is in use"
        assert set(placeholders) <= set(unused)
        assert all(opcode.opname[op] == f"<{op}>" for op in placeholders)
        assert named <= specialized, f"unused numbers with names: {sorted(named - specialized)}"

    def test_extended_arg_widens_the_next_argument(self) -> None:
        source = "\n".join(f"x = 'c{index}'" for index in range(300))
        code = compile(source, "<constants>", "exec")

        instructions = list(dis.get_instructions(code))
        wide = [
            index
            for index, instr in enumerate(instructions)
            if instr.opname == "LOAD_CONST" and instr.arg is not None and instr.arg > 255
        ]

        assert wide, "no LOAD_CONST past index 255"
        for index in wide:
            prefix = instructions[index - 1]
            assert prefix.opcode == opcode.EXTENDED_ARG
            assert prefix.arg == instructions[index].arg >> 8  # type: ignore[operator]

    def test_the_constants(self) -> None:
        assert opcode.cmp_op == ("<", "<=", "==", "!=", ">", ">=")
        assert opcode.opname[opcode.EXTENDED_ARG] == "EXTENDED_ARG"
        assert type(opcode.HAVE_ARGUMENT) is int


class TestMembershipScansTheList:
    """`op in opcode.hasconst`, on any `has*` list | O(h) | O(1): a list scan,
    which a `set` built once replaces with one hash."""

    @pytest.mark.parametrize("name", HAS_LISTS)
    def test_a_miss_compares_against_every_entry(self, name: str) -> None:
        entries = getattr(opcode, name)
        probe = CountingProbe()

        assert probe not in entries
        assert probe.comparisons == len(entries)

    def test_the_scan_is_not_vacuous(self) -> None:
        assert max(len(getattr(opcode, name)) for name in HAS_LISTS) > 5

    @pytest.mark.parametrize("name", HAS_LISTS)
    def test_a_set_of_the_list_hashes_once_and_compares_nothing(self, name: str) -> None:
        entries = set(getattr(opcode, name))
        probe = CountingProbe()

        assert probe not in entries
        assert probe.comparisons == 0
        assert probe.hashes == 1


class TestHaveArgument:
    """`HAVE_ARGUMENT`: opcodes below it ignore their argument; on 3.12+
    `hasarg` is the test, because some at or above it ignore theirs too."""

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="version: hasarg is 3.12+")
    def test_nothing_below_it_uses_an_argument(self) -> None:
        below = [name for name, op in opcode.opmap.items() if op < opcode.HAVE_ARGUMENT]

        assert below
        assert not [name for name in below if opcode.opmap[name] in opcode.hasarg]  # type: ignore[attr-defined]

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="version: hasarg is 3.12+")
    def test_some_at_or_above_it_use_none(self) -> None:
        hasarg = set(opcode.hasarg)  # type: ignore[attr-defined]

        ignoring = [
            name
            for name, op in opcode.opmap.items()
            if op >= opcode.HAVE_ARGUMENT and op not in hasarg
        ]

        assert ignoring, "HAVE_ARGUMENT still splits opmap exactly"

    @pytest.mark.skipif(
        sys.version_info >= (3, 13), reason="version: stack_effect accepts a missing oparg on 3.13+"
    )
    def test_it_splits_the_real_opcodes_before_313(self) -> None:
        """Before 3.13 `stack_effect()` refuses a missing `oparg` exactly when
        the opcode uses one, so it reports the split independently."""
        mismatched = []
        for name, op in opcode.opmap.items():
            if op >= 256:
                continue
            try:
                opcode.stack_effect(op)
                needs_arg = False
            except ValueError:
                needs_arg = True
            if needs_arg != (op >= opcode.HAVE_ARGUMENT):
                mismatched.append(name)

        assert not mismatched

    def test_the_tables_cover_pseudo_and_instrumented_opcodes_from_312(self) -> None:
        instrumented = [name for name in opcode.opmap if name.startswith("INSTRUMENTED_")]
        if sys.version_info >= (3, 12):
            assert len(opcode.opname) > 256
            assert max(opcode.opmap.values()) >= 256
            assert instrumented
        else:
            assert len(opcode.opname) == 256
            assert not instrumented


class TestCollectionsByVersion:
    """`hasarg` and `hasexc` are 3.12+, `hasjump` is 3.13+ and is `hasjrel`,
    and `hasjabs` is empty on 3.11+."""

    @pytest.mark.parametrize("name", ["hasarg", "hasexc"])
    def test_hasarg_and_hasexc_arrive_in_312(self, name: str) -> None:
        assert hasattr(opcode, name) == (sys.version_info >= (3, 12))

    def test_hasjump_arrives_in_313_as_hasjrel(self) -> None:
        assert hasattr(opcode, "hasjump") == (sys.version_info >= (3, 13))
        if sys.version_info >= (3, 13):
            assert opcode.hasjrel is opcode.hasjump  # type: ignore[attr-defined]

    def test_hasjabs_is_empty_from_311(self) -> None:
        assert (opcode.hasjabs == []) == (sys.version_info >= (3, 11))


class TestStackEffect:
    """`stack_effect(opcode, oparg=None, *, jump=None)` | O(1) | O(1):
    independent of the size of `oparg`; `jump=None` is the larger branch."""

    BUILD_TUPLE = opcode.opmap["BUILD_TUPLE"]

    @pytest.mark.parametrize("oparg", [0, 3, 2**30])
    def test_an_item_count_enters_as_a_number(self, oparg: int) -> None:
        assert opcode.stack_effect(self.BUILD_TUPLE, oparg) == 1 - oparg

    @pytest.mark.timing
    def test_a_huge_oparg_costs_what_a_small_one_does(self) -> None:
        small = best_ns(lambda: opcode.stack_effect(self.BUILD_TUPLE, 1), inner=1_000)
        huge = best_ns(lambda: opcode.stack_effect(self.BUILD_TUPLE, 2**30), inner=1_000)

        ratio = huge / small
        assert ratio < 3, (
            f"oparg 2**30 took {huge:.0f}ns against {small:.0f}ns for 1 (x{ratio:.2f}); "
            "a cost linear in oparg would be x1e9"
        )

    def test_jump_none_is_the_larger_branch(self) -> None:
        differing = 0
        for name, op in opcode.opmap.items():
            try:
                taken, not_taken, either = (effect(op, jump) for jump in (True, False, None))
            except ValueError:
                continue
            assert either == max(taken, not_taken), name
            differing += taken != not_taken

        assert differing, "no opcode has two branch effects; the check is vacuous"

    def test_pop_top(self) -> None:
        assert opcode.stack_effect(opcode.opmap["POP_TOP"]) == -1

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="version: lenient oparg is 3.13+")
    def test_a_missing_oparg_is_zero_and_a_surplus_one_is_ignored(self) -> None:
        assert opcode.stack_effect(self.BUILD_TUPLE) == 1  # the zero-item effect
        assert opcode.stack_effect(opcode.opmap["POP_TOP"], 5) == -1

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="version: lenient oparg is 3.13+")
    def test_a_missing_or_surplus_oparg_raises_before_313(self) -> None:
        with pytest.raises(ValueError, match="requires oparg"):
            opcode.stack_effect(opcode.opmap["LOAD_CONST"])
        with pytest.raises(ValueError, match="does not permit oparg"):
            opcode.stack_effect(opcode.opmap["POP_TOP"], 5)


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
        line, source = next((n, s) for n, s in _blocks() if "== 1 - 2**30" in s)
        mutated = source.replace("== 1 - 2**30", "== 2**30", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
