"""Tests for docs/stdlib/sre_compile.md.

The page prices `compile()` as O(n + r): linear in the pattern once it is
parsed, plus the code points its character-class ranges span below U+10000,
with no cache in front of it. The alias rows are settled by identity and by a
fresh interpreter's warnings; the missing cache by identity and by counting
calls into the parser; the two size variables by timing, holding one fixed
while the other grows.

Measurement scope:

* The deprecation is observed in a fresh interpreter importing the module
  twice under `warnings.simplefilter('always')`: one `DeprecationWarning`
  from the first import and none from the second on 3.11+, none on 3.10.
  Every non-dunder name of `re._compiler` is asserted to be the same object
  in the alias on 3.11+; on 3.10 the module is `re.sre_compile`. Rebinding
  `sre_compile.compile` is asserted not to reach `re.compile()` on 3.11+ and
  to reach it on 3.10.
* `compile()` over `x[ab]c*` repeated 100, 1,000 and 10,000 times, fastest
  of seven with the collector paused: each 10x step costs between 4x and
  40x, admitting linear growth and excluding quadratic (100x).
* The r term holds the pattern at five characters: `[\\u0100-\\u0101]`
  (r = 2), `[\\u0100-\\u0fff]` (r = 3,840) and `[\\u0100-\\uffff]`
  (r = 65,280). The widest costs more than 20x the narrowest, and the 17x
  step in r from the middle one costs between 5x and 60x, where quadratic
  growth would cost 289x. `[\\U00010000-\\U0010ffff]`, 1,048,576 code points
  above U+FFFF, costs under a tenth of the widest BMP range, and matches its
  top and bottom code points.
* Groups nested d = 10 and 100 deep around L = 1,000 and 4,000 literals:
  the literal-prefix search returns exactly (d + 1)·L prefix items in all,
  against L for the same literals unnested.
* Two calls with the same string return two `Pattern` objects and call the
  parser twice; `re.compile()` returns one object. A tree from
  `sre_parse.parse()` compiles with no parser call, twice, to patterns whose
  `.pattern` is `None` and whose `groupindex` comes from the tree.
* `dis()` output is observed under `re.DEBUG`, after the parse-tree dump:
  it ends with `SUCCESS`. `isstring()` is asserted for `str`, `bytes` and a
  non-string, `MAXCODE` against `_sre.CODESIZE`, and `error` and
  `PatternError` (3.13+) against `re.error`.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* That compiling a tree is O(w + r) apart from the literal-prefix copying
  counted above: the code generator is read from Lib/re/_compiler.py
  (Lib/sre_compile.py on 3.10), and only the ordinary-pattern timing above
  is measured. Lookarounds, conditionals and
  flags are not varied; the r term is timed without `IGNORECASE`, whose
  range walk also case-folds each code point.
* `dis()`'s O(c·d) time and O(c) space are read from the source: it indents
  each line by its nesting level and keeps a set of the jump targets seen. Its output is checked, not
  timed.
* The module is undocumented; which names it exposes is taken from the
  released sources of 3.10 to 3.14, not from a documented contract.
"""

from __future__ import annotations

import contextlib
import gc
import importlib
import io
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import warnings
from collections.abc import Callable
from typing import Any

import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    sre_compile: Any = importlib.import_module("sre_compile")
    sre_parse: Any = importlib.import_module("sre_parse")

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "sre_compile.md"
EXPECTED_BLOCKS = 4


def best_ns(func: Callable[[], Any], repeats: int = 7) -> float:
    """Fastest of `repeats` runs, in nanoseconds, with the collector paused."""
    best: float | None = None
    gc.collect()
    enabled = gc.isenabled()
    gc.disable()
    try:
        for _ in range(repeats):
            start = time.perf_counter_ns()
            func()
            elapsed = time.perf_counter_ns() - start
            best = elapsed if best is None else min(best, elapsed)
    finally:
        if enabled:
            gc.enable()
    assert best is not None
    return best


def parser_module() -> Any:
    """The module the compiler parses with: `re._parser` on 3.11+, `sre_parse` on 3.10."""
    return getattr(re, "_parser", None) or sre_parse


def run_python(source: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestTheModuleIsADeprecatedAlias:
    """`import sre_compile` | O(1) | Python 3.11+: warns on the first import
    only; the names are the same objects as `re._compiler`'s, and rebinding
    one does not reach `re`."""

    def test_the_first_import_warns_and_the_second_does_not(self) -> None:
        result = run_python(
            "import warnings\n"
            "counts = []\n"
            "for _ in range(2):\n"
            "    with warnings.catch_warnings(record=True) as caught:\n"
            "        warnings.simplefilter('always')\n"
            "        import sre_compile\n"
            "    counts.append([w.category.__name__ for w in caught])\n"
            "print(counts)\n"
        )
        assert result.returncode == 0, result.stderr
        if sys.version_info >= (3, 11):
            assert result.stdout.strip() == "[['DeprecationWarning'], []]"
        else:
            assert result.stdout.strip() == "[[], []]"

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="re._compiler is 3.11+")
    def test_every_name_is_the_compiler_s_own_object(self) -> None:
        compiler = importlib.import_module("re._compiler")
        names = [name for name in vars(compiler) if not name.startswith("__")]

        assert len(names) > 100
        for name in names:
            assert getattr(sre_compile, name) is getattr(compiler, name), name

    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="3.10 is the implementation")
    def test_on_3_10_it_is_the_module_re_imports(self) -> None:
        internals: Any = re
        assert internals.sre_compile is sre_compile

    def test_rebinding_compile_here_reaches_re_only_on_3_10(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list[Any] = []
        original = sre_compile.compile

        def spy(pattern: Any, flags: int = 0) -> Any:
            seen.append(pattern)
            return original(pattern, flags)

        monkeypatch.setattr(sre_compile, "compile", spy)
        re.purge()
        re.compile("rebinding-probe")
        re.purge()

        assert seen == ([] if sys.version_info >= (3, 11) else ["rebinding-probe"])


class TestCompilingIsLinearInThePattern:
    """`sre_compile.compile(p, flags=0)` | O(n + r): the n term, timed with r
    held at zero. 10x the pattern costs about 10x, where quadratic growth
    would cost 100x."""

    @pytest.mark.timing
    def test_each_step_in_pattern_length_costs_a_linear_step(self) -> None:
        times = [
            best_ns(lambda p="x[ab]c*" * repeat: sre_compile.compile(p))
            for repeat in (100, 1_000, 10_000)
        ]

        steps = [later / earlier for earlier, later in zip(times, times[1:], strict=False)]
        assert all(4 < step < 40 for step in steps), (
            f"10x the pattern should cost about 10x, not 100x: {times} ns, steps {steps}"
        )


class TestCharacterClassRangesCostTheirSpan:
    """The r term: a range costs the code points it spans below U+10000, so
    classes of the same five characters differ by the width of their range.
    Ranges above U+FFFF stay ranges."""

    @pytest.mark.timing
    def test_a_wide_range_costs_far_more_than_a_narrow_one_of_equal_length(self) -> None:
        narrow = best_ns(lambda: sre_compile.compile("[\u0100-\u0101]"))
        wide = best_ns(lambda: sre_compile.compile("[\u0100-\uffff]"))

        assert wide > 20 * narrow, f"r = 65,280 cost {wide:.0f}ns against {narrow:.0f}ns at r = 2"

    @pytest.mark.timing
    def test_a_range_above_u_ffff_is_not_walked(self) -> None:
        wide = best_ns(lambda: sre_compile.compile("[\u0100-\uffff]"))
        astral = best_ns(lambda: sre_compile.compile("[\U00010000-\U0010ffff]"))

        assert astral * 10 < wide, f"1,048,576 astral code points cost {astral:.0f}ns"

    @pytest.mark.timing
    def test_the_cost_grows_linearly_in_the_span(self) -> None:
        middle = best_ns(lambda: sre_compile.compile("[\u0100-\u0fff]"))
        wide = best_ns(lambda: sre_compile.compile("[\u0100-\uffff]"))

        ratio = wide / middle
        assert 5 < ratio < 60, f"17x the span cost {ratio:.1f}x; quadratic would be 289x"

    def test_the_patterns_are_equal_in_length(self) -> None:
        assert len("[\u0100-\u0101]") == len("[\u0100-\u0fff]") == len("[\u0100-\uffff]") == 5

    def test_a_range_above_the_bmp_matches_at_both_ends(self) -> None:
        astral = sre_compile.compile("[\U00010000-\U0010ffff]")

        assert astral.match("\U00010000") and astral.match("\U0010ffff")
        assert astral.match("\uffff") is None

    def test_the_cjk_example_matches(self) -> None:
        assert sre_compile.compile("[\u4e00-\u9fff]+").fullmatch("\u6f22\u5b57")
        assert 0x9FFF - 0x4E00 + 1 == 20_992


class TestNestedGroupsCopyTheLiteralPrefix:
    """Groups nested d deep around a leading literal cost O(n·d): each level
    returns the literal prefix it found and its parent extends its own with
    it. Counting the prefix items returned measures the copying directly."""

    def test_each_level_copies_the_prefix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        compiler = getattr(re, "_compiler", None) or sre_compile
        original = compiler._get_literal_prefix
        returned = [0]

        def counting_prefix(pattern: Any, flags: int) -> Any:
            result = original(pattern, flags)
            returned[0] += len(result[0])
            return result

        monkeypatch.setattr(compiler, "_get_literal_prefix", counting_prefix)

        for depth in (10, 100):
            for length in (1_000, 4_000):
                tree = sre_parse.parse("(" * depth + "a" * length + ")" * depth)
                returned[0] = 0
                sre_compile.compile(tree)
                assert returned[0] == (depth + 1) * length, f"depth {depth}, length {length}"
        tree = sre_parse.parse("a" * 4_000)
        returned[0] = 0
        sre_compile.compile(tree)
        assert returned[0] == 4_000


class TestThereIsNoCache:
    """Each call returns a new `Pattern`, and a string is parsed on every
    call; a tree is not parsed again."""

    @pytest.fixture
    def parse_calls(self, monkeypatch: pytest.MonkeyPatch) -> list[Any]:
        parser = parser_module()
        original = parser.parse
        calls: list[Any] = []

        def counting_parse(pattern: Any, flags: int = 0, state: Any = None) -> Any:
            calls.append(pattern)
            return original(pattern, flags, state)

        monkeypatch.setattr(parser, "parse", counting_parse)
        return calls

    def test_two_calls_return_two_patterns_and_parse_twice(self, parse_calls: list[Any]) -> None:
        first = sre_compile.compile(r"\d+")
        second = sre_compile.compile(r"\d+")

        assert first is not second
        assert parse_calls == [r"\d+", r"\d+"]

    def test_re_compile_returns_the_cached_object(self) -> None:
        re.purge()
        assert re.compile(r"\d+") is re.compile(r"\d+")
        re.purge()

    def test_a_tree_compiles_without_a_parse(self, parse_calls: list[Any]) -> None:
        tree = sre_parse.parse(r"(?P<year>\d{4})-(?P<month>\d\d)")
        parse_calls.clear()

        pattern = sre_compile.compile(tree)
        again = sre_compile.compile(tree)

        assert parse_calls == []
        assert pattern.pattern is None and again.pattern is None
        assert pattern.groupindex == {"year": 1, "month": 2}
        assert pattern.match("2024-05").group("month") == "05"
        assert again.match("1999-12")


class TestHelpersAndConstants:
    """`isstring()`, `dis()`, `MAXCODE`, and the exception."""

    def test_isstring(self) -> None:
        assert sre_compile.isstring("a") and sre_compile.isstring(b"a")
        assert not sre_compile.isstring(bytearray(b"a"))

    def test_dis_prints_the_code_under_debug(self) -> None:
        tree_only = io.StringIO()
        with contextlib.redirect_stdout(tree_only):
            sre_parse.parse("ab", re.DEBUG)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            sre_compile.compile("ab", re.DEBUG)

        listing = output.getvalue()[len(tree_only.getvalue()) :]
        assert output.getvalue().startswith(tree_only.getvalue())
        assert "INFO" in listing and listing.rstrip().endswith("SUCCESS")

    def test_maxcode_is_the_largest_code(self) -> None:
        sre = importlib.import_module("_sre")
        assert sre_compile.MAXCODE == (1 << (sre.CODESIZE * 8)) - 1

    def test_the_exception_is_re_s(self) -> None:
        assert sre_compile.error is re.error
        assert hasattr(sre_compile, "PatternError") == (sys.version_info >= (3, 13))
        with pytest.raises(re.error):
            sre_compile.compile("(unclosed")


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
    """Each block runs in its own subprocess and asserts its own result.
    Version-dependent blocks branch on `sys.version_info`."""

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
        line, source = next((n, s) for n, s in _blocks() if "assert first is not second" in s)
        mutated = source.replace("assert first is not second", "assert first is second", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
