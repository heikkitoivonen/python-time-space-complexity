"""Tests for docs/stdlib/sre_parse.md.

The page prices the parser behind `re`: linear in the pattern except for two
quadratic shapes and nested non-capturing groups, a tree whose width is stored once, and a tokenizer that decodes a
`bytes` pattern up front. The alias rows are settled by identity and by a
fresh interpreter's warnings; the two quadratic shapes by counting the items
the parser shifts; the ordinary case by timing; the tree and tokenizer rows by
observation and traced allocation.

Measurement scope:

* The deprecation is observed in a fresh interpreter importing the module
  twice under `warnings.simplefilter('always')`: one `DeprecationWarning` from
  the first import and none from the second on 3.11+, none from either on
  3.10. Every non-dunder name of `re._parser` is asserted to be the same
  object in the alias on 3.11+; on 3.10 the module is `re.sre_parse`.
  Rebinding `sre_parse.parse` is asserted not to reach `re.compile()` on 3.11+
  and to reach it on 3.10.
* `parse()` over `x[ab]c*` repeated 100, 1,000 and 10,000 times, fastest of
  seven with the collector paused: each 10x step costs between 4x and 40x,
  admitting linear growth and excluding quadratic (100x). The two O(n²) shapes are settled by counting pointer
  moves. Two alternatives sharing a prefix of 1,000, 4,000 and 16,000
  characters shift exactly n(n+1) items through `SubPattern.__delitem__`,
  and unshared ones none. A run of g groups `(?:ab)` at one level, g =
  1,000, 4,000 and 16,000, shifts exactly g(g-1) items through slice
  assignment, and the same run of capturing groups `(ab)` none. Non-capturing
  groups nested d = 10 and 100 deep around L = 1,000 and 4,000 literals copy
  exactly d·L items through slice assignment; capturing groups copy none.
* `getwidth()` returns the same tuple object on a second call, stores a
  width on each nested `SubPattern`, ignores an item appended after the
  first, and (3.11+) reports `MAXWIDTH` as the upper width of `a*`;
  `SubPattern(state, data)` holds `data` itself; a slice is a new
  `SubPattern` whose list is a copy. `dump()` prints exactly what `re.DEBUG`
  prints before its code listing, and indents each of its six lines for five
  nested groups by two spaces per level.
* `Tokenizer(string)` over 1,000,000 characters: a `str` peaks under 100 KB
  of traced allocation, `bytes` over 1,000,000 bytes, and a `bytes`
  tokenizer's `decoded_string` is the Latin-1 decoding. `getwhile()` stops at
  its count and at the first character outside the set; `getuntil()` returns
  what precedes the terminator; `error()` returns an `re.error` without
  raising, carrying the line and column of the position; `checkgroupname()` (3.11+) rejects a non-identifier.
* `parse_template()` is asserted to take exactly t + 2 tokenizer steps on a
  plain template of 10,000 characters, and to return a flat list on 3.12+ and
  a `(groups, literals)` pair, expandable by `expand_template()`, on 3.10 and
  3.11. `fix_flags()` is asserted to add `SRE_FLAG_UNICODE` to a `str`
  pattern and to raise `ValueError` for `LOCALE` with `str` and `UNICODE`
  with `bytes`. `State` bookkeeping is observed through `groups`,
  `opengroup()`, `closegroup()` and `checkgroup()`; `opengroup()` raises
  for a repeated name and, with the module's `MAXGROUPS` patched to 3, for
  the third group opened.
* The constants' types, the version-bounded names (`Verbose` on 3.10 only,
  `MAXWIDTH` and `Tokenizer.checkgroupname` on 3.11+, `PatternError` on
  3.13+, `expand_template` on 3.10 and 3.11) and the re-exported opcodes are
  asserted by presence and identity.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* That `parse()` is linear for every shape other than the three named. Long
  literals, classes, repeats, capturing groups and prefix-free alternations
  are measured; lookarounds, conditionals and backreferences are not varied.
* `parse_template()`'s O(t) rests on the counted tokenizer steps plus a
  reading of Lib/re/_parser.py (Lib/sre_parse.py on 3.10): each step appends
  to a list and the pieces are joined once. `expand_template()`'s O(t + r)
  is read from the same file; it copies the literal list and joins the
  result.
* `closegroup()`'s O(w), `insert()`'s and `del`'s O(w), `dump()`'s O(w·d),
  and the O(d) recursion of `getwidth()` and `dump()` are read from the
  source, not measured; `dump()` output is compared, not timed.
  `error()`'s O(n), with a short `msg`, is read from `error.__init__` in Lib/re/_constants.py
  (Lib/sre_constants.py on 3.10), which counts the newlines before the
  position; it is not timed.
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
import tracemalloc
import warnings
from collections.abc import Callable
from typing import Any

import pytest

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    sre_parse: Any = importlib.import_module("sre_parse")
    sre_constants: Any = importlib.import_module("sre_constants")

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "sre_parse.md"
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


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def parser_module() -> Any:
    """The module `re` parses with: `re._parser` on 3.11+, this one on 3.10."""
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
    """`import sre_parse` | O(1) | Python 3.11+: warns on the first import
    only; the names are the same objects as `re._parser`'s. A fresh
    interpreter separates the first import from later ones."""

    def test_the_first_import_warns_and_the_second_does_not(self) -> None:
        result = run_python(
            "import warnings\n"
            "counts = []\n"
            "for _ in range(2):\n"
            "    with warnings.catch_warnings(record=True) as caught:\n"
            "        warnings.simplefilter('always')\n"
            "        import sre_parse\n"
            "    counts.append([w.category.__name__ for w in caught])\n"
            "print(counts)\n"
        )
        assert result.returncode == 0, result.stderr
        if sys.version_info >= (3, 11):
            assert result.stdout.strip() == "[['DeprecationWarning'], []]"
        else:
            assert result.stdout.strip() == "[[], []]"

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="re._parser is 3.11+")
    def test_every_name_is_the_parser_s_own_object(self) -> None:
        parser = importlib.import_module("re._parser")
        names = [name for name in vars(parser) if not name.startswith("__")]

        assert len(names) > 100
        for name in names:
            assert getattr(sre_parse, name) is getattr(parser, name), name

    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="3.10 is the implementation")
    def test_on_3_10_it_is_the_module_re_imports(self) -> None:
        internals: Any = re
        assert internals.sre_parse is sre_parse

    def test_rebinding_parse_here_reaches_re_only_on_3_10(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list[Any] = []
        original = sre_parse.parse

        def spy(pattern: Any, flags: int = 0, state: Any = None) -> Any:
            seen.append(pattern)
            return original(pattern, flags, state)

        monkeypatch.setattr(sre_parse, "parse", spy)
        re.purge()
        re.compile("rebinding-probe")
        re.purge()

        assert seen == ([] if sys.version_info >= (3, 11) else ["rebinding-probe"])


class TestParsingIsLinearInTheOrdinaryCase:
    """`sre_parse.parse(str, flags=0, state=None)` | O(n) | O(n); nothing is
    cached. Timed on a pattern with neither quadratic shape; 10x the pattern
    costs about 10x, where quadratic growth would cost 100x."""

    @pytest.mark.timing
    def test_each_step_in_pattern_length_costs_a_linear_step(self) -> None:
        times = [
            best_ns(lambda p="x[ab]c*" * repeat: sre_parse.parse(p))
            for repeat in (100, 1_000, 10_000)
        ]

        steps = [later / earlier for earlier, later in zip(times, times[1:], strict=False)]
        assert all(4 < step < 40 for step in steps), (
            f"10x the pattern should cost about 10x, not 100x: {times} ns, steps {steps}"
        )

    def test_each_call_parses_afresh(self) -> None:
        first = sre_parse.parse("ab+")
        second = sre_parse.parse("ab+")

        assert first is not second and first.data is not second.data
        assert repr(first) == repr(second)


class TestTheTwoQuadraticShapes:
    """O(n²) when a group's alternatives share a long common prefix, or when a
    long run of non-capturing groups sits at one level. Each shifted item is
    one pointer moved, so counting them measures the quadratic term without a
    stopwatch; a linear parse would shift none."""

    def test_a_shared_prefix_shifts_quadratically_many_items(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        subpattern = parser_module().SubPattern
        delete = subpattern.__delitem__
        shifted = [0]

        def counting_delete(self: Any, index: Any) -> None:
            shifted[0] += len(self.data) - 1 if index == 0 else 0
            delete(self, index)

        monkeypatch.setattr(subpattern, "__delitem__", counting_delete)

        def items_shifted(pattern: str) -> int:
            shifted[0] = 0
            sre_parse.parse(pattern)
            return shifted[0]

        for length in (1_000, 4_000, 16_000):
            shared = "x" * length + "a|" + "x" * length + "b"
            assert items_shifted(shared) == length * (length + 1), f"prefix of {length}"
        assert items_shifted("x" * 16_000 + "a|" + "y" * 16_000 + "b") == 0

    def test_a_run_of_non_capturing_groups_shifts_quadratically_many_items(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        subpattern = parser_module().SubPattern
        assign = subpattern.__setitem__
        shifted = [0]

        def counting_assign(self: Any, index: Any, code: Any) -> None:
            if isinstance(index, slice) and len(code) != index.stop - index.start:
                shifted[0] += len(self.data) - index.stop
            assign(self, index, code)

        monkeypatch.setattr(subpattern, "__setitem__", counting_assign)

        def items_shifted(pattern: str) -> int:
            shifted[0] = 0
            sre_parse.parse(pattern)
            return shifted[0]

        for groups in (1_000, 4_000, 16_000):
            assert items_shifted("(?:ab)" * groups) == groups * (groups - 1), f"{groups} groups"
        assert items_shifted("(ab)" * 16_000) == 0, "capturing groups are not spliced"

    def test_nested_non_capturing_groups_copy_their_contents_once_per_level(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        subpattern = parser_module().SubPattern
        assign = subpattern.__setitem__
        copied = [0]

        def counting_assign(self: Any, index: Any, code: Any) -> None:
            if isinstance(index, slice):
                copied[0] += len(code)
            assign(self, index, code)

        monkeypatch.setattr(subpattern, "__setitem__", counting_assign)

        for depth in (10, 100):
            for length in (1_000, 4_000):
                copied[0] = 0
                sre_parse.parse("(?:" * depth + "a" * length + ")" * depth)
                assert copied[0] == depth * length, f"depth {depth}, length {length}"
        copied[0] = 0
        sre_parse.parse("(" * 100 + "a" * 4_000 + ")" * 100)
        assert copied[0] == 0, "capturing groups are not spliced"

    def test_both_shapes_produce_the_flattened_tree_the_page_shows(self) -> None:
        literal = sre_constants.LITERAL
        tree = sre_parse.parse("abc|abd")
        flat = sre_parse.parse("(?:ab)(?:cd)")

        assert tree[0] == (literal, ord("a")) and tree[1] == (literal, ord("b"))
        assert tree[2][0] is sre_constants.IN and len(tree) == 3
        assert list(flat) == [(literal, ord(c)) for c in "abcd"]


class TestSubPattern:
    """`SubPattern(state, data=None)` wraps without copying; a slice copies;
    `getwidth()` is stored on the first call; `dump()` prints the tree
    `re.DEBUG` prints."""

    def test_construction_wraps_the_list_it_is_given(self) -> None:
        data = [(sre_constants.LITERAL, ord("a"))]
        sub = sre_parse.SubPattern(sre_parse.State(), data)

        assert sub.data is data
        assert len(sub) == 1 and sub[0] == data[0]

    def test_a_slice_is_a_new_subpattern_over_a_copy(self) -> None:
        tree = sre_parse.parse("abcd")
        piece = tree[1:3]

        assert isinstance(piece, sre_parse.SubPattern)
        assert piece.data == tree.data[1:3] and piece.data is not tree.data
        piece.append((sre_constants.LITERAL, ord("z")))
        assert len(tree) == 4

    def test_getwidth_is_stored_on_the_first_call(self) -> None:
        tree = sre_parse.parse(r"(?P<word>\w{1,4})-\d{2,4}")
        width = tree.getwidth()

        assert width == (4, 9)
        assert tree.getwidth() is width

    def test_getwidth_stores_a_width_on_every_nested_subpattern(self) -> None:
        tree = sre_parse.parse("x(?:a(?:bc)*)*")
        body = tree[1][1][2]
        inner = body[1][1][2]
        assert (body.width, inner.width) == (None, None)

        tree.getwidth()
        assert body.width[0] == 1 and inner.width == (2, 2)

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="MAXWIDTH is 3.11+")
    def test_maxwidth_caps_the_reported_width(self) -> None:
        assert sre_parse.parse("a*").getwidth() == (0, sre_parse.MAXWIDTH)

    def test_an_item_appended_afterwards_is_not_counted(self) -> None:
        tree = sre_parse.parse("ab")
        assert tree.getwidth() == (2, 2)

        tree.append((sre_constants.LITERAL, ord("c")))
        assert tree.getwidth() == (2, 2)
        assert sre_parse.parse("abc").getwidth() == (3, 3)

    def test_insert_and_delete_edit_the_list_in_place(self) -> None:
        tree = sre_parse.parse("ac")
        tree.insert(1, (sre_constants.LITERAL, ord("b")))
        assert [code for _, code in tree] == [ord(c) for c in "abc"]
        del tree[0]
        assert [code for _, code in tree] == [ord(c) for c in "bc"]

    def test_dump_indents_each_line_by_its_depth(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            sre_parse.parse("(" * 5 + "a" + ")" * 5).dump()

        lines = output.getvalue().splitlines()
        assert len(lines) == 6 and lines[-1].strip() == "LITERAL 97"
        for depth, line in enumerate(lines):
            assert len(line) - len(line.lstrip(" ")) == 2 * depth, line

    def test_dump_prints_what_re_debug_prints(self) -> None:
        pattern = r"(a|bc)+\d"
        dumped = io.StringIO()
        with contextlib.redirect_stdout(dumped):
            sre_parse.parse(pattern).dump()
        debugged = io.StringIO()
        with contextlib.redirect_stdout(debugged):
            re.compile(pattern, re.DEBUG)

        assert dumped.getvalue()
        assert debugged.getvalue().startswith(dumped.getvalue())


class TestState:
    """`State()`, `State.groups`, `opengroup()`, `closegroup()` and
    `checkgroup()`: the group bookkeeping of one parse."""

    def test_groups_counts_group_zero_and_each_opened_group(self) -> None:
        state = sre_parse.State()
        assert state.groups == 1

        gid = state.opengroup("word")
        assert gid == 1 and state.groups == 2
        assert state.groupdict == {"word": 1}
        assert not state.checkgroup(gid), "an open group cannot be referred to yet"

        state.closegroup(gid, sre_parse.parse("abc"))
        assert state.checkgroup(gid)

    def test_opening_past_maxgroups_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(parser_module(), "MAXGROUPS", 3)
        state = sre_parse.State()
        state.opengroup()
        state.opengroup()

        with pytest.raises(re.error, match="too many groups"):
            state.opengroup()

    def test_a_repeated_name_raises(self) -> None:
        state = sre_parse.State()
        state.opengroup("word")

        with pytest.raises(re.error, match="redefinition"):
            state.opengroup("word")

    def test_parse_fills_the_state_it_is_given(self) -> None:
        state = sre_parse.State()
        tree = sre_parse.parse(r"(?P<a>x)(?P<b>y)", 0, state)

        assert tree.state is state
        assert state.groupdict == {"a": 1, "b": 2}


class TestTokenizer:
    """`Tokenizer(string)` | O(1) for `str`, O(n) for `bytes`, plus the
    stepping and scanning methods."""

    def test_a_str_pattern_is_not_copied(self) -> None:
        pattern = "a" * 1_000_000
        sre_parse.Tokenizer("warm")

        assert peak_bytes(lambda: sre_parse.Tokenizer(pattern)) < 100_000

    def test_a_bytes_pattern_is_decoded_as_latin_1(self) -> None:
        tokens = sre_parse.Tokenizer(b"a\xe9")

        assert tokens.decoded_string == "a\xe9"
        assert tokens.string == b"a\xe9"

    def test_a_bytes_pattern_is_decoded_up_front(self) -> None:
        pattern = b"a" * 1_000_000
        sre_parse.Tokenizer(b"warm")

        assert peak_bytes(lambda: sre_parse.Tokenizer(pattern)) > 1_000_000

    def test_stepping_and_positions(self) -> None:
        tokens = sre_parse.Tokenizer(r"a\db")

        assert tokens.next == "a"
        assert tokens.get() == "a"
        assert tokens.get() == r"\d", "an escape is one step"
        assert tokens.tell() == 3 and tokens.pos == 3
        assert tokens.match("b") and tokens.next is None
        tokens.seek(1)
        assert tokens.next == r"\d"

    def test_getwhile_stops_at_its_count_or_the_set(self) -> None:
        assert sre_parse.Tokenizer("12345").getwhile(3, sre_parse.DIGITS) == "123"
        assert sre_parse.Tokenizer("12x45").getwhile(5, sre_parse.DIGITS) == "12"

    def test_getuntil_returns_what_precedes_the_terminator(self) -> None:
        tokens = sre_parse.Tokenizer("name>rest")

        assert tokens.getuntil(">", "group name") == "name"
        assert tokens.next == "r"

    def test_error_locates_its_line_and_column(self) -> None:
        tokens = sre_parse.Tokenizer("ab\ncd\nef")
        tokens.seek(7)
        error = tokens.error("here")

        assert (error.lineno, error.colno) == (3, 2)

    def test_error_returns_rather_than_raises(self) -> None:
        error = sre_parse.Tokenizer("abc").error("bad thing")

        assert isinstance(error, re.error)
        assert error.pattern == "abc"

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="Python 3.11+")
    def test_checkgroupname_rejects_a_non_identifier(self) -> None:
        tokens = sre_parse.Tokenizer("x")
        extra = (0,) if sys.version_info < (3, 12) else ()

        tokens.checkgroupname("good_name", 0, *extra)
        with pytest.raises(re.error, match="bad character in group name"):
            tokens.checkgroupname("1bad", 0, *extra)


class TestTemplatesAndFlags:
    """`parse_template()` | O(t); `expand_template()` on 3.10 and 3.11;
    `fix_flags()` | O(1)."""

    def test_parse_template_takes_one_tokenizer_step_per_character(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        tokenizer = parser_module().Tokenizer
        step = tokenizer._Tokenizer__next
        steps = [0]

        def counting_step(self: Any) -> None:
            steps[0] += 1
            step(self)

        pattern = re.compile("a")
        template = "x" * 10_000
        monkeypatch.setattr(tokenizer, "_Tokenizer__next", counting_step)
        sre_parse.parse_template(template, pattern)

        assert steps[0] == len(template) + 2  # one to prime, one to find the end

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="the flat form is 3.12+")
    def test_the_result_is_a_flat_list_from_3_12(self) -> None:
        template = sre_parse.parse_template(r"\2-\1", re.compile(r"(\w+) (\w+)"))

        assert template == ["", 2, "-", 1, ""]
        assert not hasattr(sre_parse, "expand_template")

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="the pair form is 3.10-3.11")
    def test_the_result_is_a_pair_before_3_12(self) -> None:
        pattern = re.compile(r"(\w+) (\w+)")
        template = sre_parse.parse_template(r"\2-\1", pattern)

        assert template == ([(0, 2), (2, 1)], [None, "-", None])
        match = pattern.match("hello world")
        assert sre_parse.expand_template(template, match) == "world-hello"

    def test_fix_flags(self) -> None:
        unicode = sre_constants.SRE_FLAG_UNICODE

        assert sre_parse.fix_flags("a", 0) == unicode
        assert sre_parse.fix_flags("a", sre_constants.SRE_FLAG_ASCII) & unicode == 0
        assert sre_parse.fix_flags(b"a", 0) == 0
        with pytest.raises(ValueError):
            sre_parse.fix_flags("a", sre_constants.SRE_FLAG_LOCALE)
        with pytest.raises(ValueError):
            sre_parse.fix_flags(b"a", unicode)


class TestConstantsAndExceptions:
    """The character sets, escape tables, flag tables, version-bounded names
    and re-exported opcodes."""

    def test_the_character_sets_are_frozensets(self) -> None:
        for name in ("DIGITS", "OCTDIGITS", "HEXDIGITS", "ASCIILETTERS", "WHITESPACE"):
            assert isinstance(getattr(sre_parse, name), frozenset), name
        assert isinstance(sre_parse.SPECIAL_CHARS, str)
        assert set(sre_parse.REPEAT_CHARS) == set("*+?{")

    def test_the_escape_and_flag_tables_are_dicts(self) -> None:
        for name in ("ESCAPES", "CATEGORIES", "FLAGS"):
            assert type(getattr(sre_parse, name)) is dict, name
        assert sre_parse.ESCAPES[r"\n"] == (sre_constants.LITERAL, ord("\n"))
        assert sre_parse.CATEGORIES[r"\d"][0] is sre_constants.IN
        assert sre_parse.FLAGS["i"] == sre_constants.SRE_FLAG_IGNORECASE
        assert isinstance(sre_parse.TYPE_FLAGS, int)
        assert isinstance(sre_parse.GLOBAL_FLAGS, int)

    def test_the_version_bounded_names(self) -> None:
        assert hasattr(sre_parse, "Verbose") == (sys.version_info < (3, 11))
        assert hasattr(sre_parse, "MAXWIDTH") == (sys.version_info >= (3, 11))
        assert hasattr(sre_parse.Tokenizer, "checkgroupname") == (sys.version_info >= (3, 11))
        assert hasattr(sre_parse, "expand_template") == (sys.version_info < (3, 12))
        assert hasattr(sre_parse, "PatternError") == (sys.version_info >= (3, 13))
        assert ("t" in sre_parse.FLAGS) == (sys.version_info < (3, 13))

    def test_the_inline_t_flag_is_rejected_from_3_13(self) -> None:
        if sys.version_info >= (3, 13):
            with pytest.raises(re.error):
                sre_parse.parse("(?t)a")
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                sre_parse.parse("(?t)a")

    def test_the_exception_is_re_s(self) -> None:
        assert sre_parse.error is re.error
        if sys.version_info >= (3, 13):
            assert sre_parse.PatternError is re.error

    def test_the_opcodes_are_sre_constants_own(self) -> None:
        for name in ("LITERAL", "IN", "BRANCH", "SUBPATTERN", "MAXREPEAT", "SRE_FLAG_VERBOSE"):
            assert getattr(sre_parse, name) is getattr(sre_constants, name), name


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
    """Each block runs in its own subprocess, so the first-import warning the
    first block records is not swallowed by an earlier import, and asserts its
    own result. Version-dependent blocks branch on `sys.version_info`."""

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
        line, source = next((n, s) for n, s in _blocks() if "width == (4, 9)" in s)
        mutated = source.replace("width == (4, 9)", "width == (4, 8)", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
