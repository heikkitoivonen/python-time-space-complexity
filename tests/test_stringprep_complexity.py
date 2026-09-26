"""Tests for docs/stdlib/stringprep.md.

The page prices every function at O(1) because each takes a single character:
there is no input size to vary. The tests therefore settle the premise rather
than time the call - that a code point or a longer string is rejected, that
the mappings' output is bounded over every code point, that `nameprep()`
stays linear on combining marks that normalization must reorder, and that each table
answers for the characters the page names. The claims about Unicode 3.2 and
about how `encodings.idna.nameprep()` uses the tables are settled by
observation.

Measurement scope:

* All 19 functions are called with `ord('A')` and with `'ab'`: 18 raise
  `TypeError` for both, and `in_table_c11()` returns `False` for both.
* `map_table_b2()` and `map_table_b3()` are called on every code point,
  surrogates included; the longest result of either is asserted to be 4
  characters, and a result of that length is asserted to occur.
* `stringprep.unicodedata` is asserted to be `unicodedata.ucd_3_2_0`. U+1F600,
  category So today, is asserted to be in table A.1; U+06DD, bidirectional AL
  in Unicode 3.2 and AN today, is asserted to be in D.1; U+17B4, L in 3.2 and
  NSM today, is asserted to be in D.2.
* Each table row is asserted on members and non-members named on the page:
  the ASCII and non-ASCII spaces and controls, with the combined `c11_c12` and
  `c21_c22` asserted equal to the union of their halves over every code
  point; private use, a non-character, a surrogate, and
  one member each of C.6 through C.9; and a non-character excluded from A.1.
* `nameprep()` is observed through counting wrappers on the module's
  functions: over labels of 10 and 1,000 characters it calls `in_table_b1()`
  once per input character and `map_table_b2()` once per character B.1 keeps,
  and it rejects a private-use character and a label mixing R and L
  characters. The `idna` codec is observed calling `nameprep()` for a
  non-ASCII label. A timing test runs `nameprep()` on `"a"` followed by
  1,000 and 16,000 pairs of U+0315 U+0300, combining marks NFKC must
  reorder, and asserts the 16x input costs under x64, between the x16 of a
  linear pass and the x256 of a quadratic one; about x16 was measured on
  3.10 and 3.14. That excludes quadratic growth for this input family over
  this interval; it does not separate O(n) from O(n log n), and other
  reordering shapes are not measured.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* That each call is O(1) is definitional once the input is one character:
  every function does a bounded amount of work on it, NFKC in `map_table_b2()`
  included, which normalizes one character's folding and decomposition (18
  characters for U+FDFA), per Lib/stringprep.py, identical across 3.10 to
  3.14. No timing test is run on a single call.
* `map_table_b3()`'s fallback, `str.lower()`, uses the interpreter's Unicode
  version rather than 3.2; the page claims 3.2 only for category and
  bidirectional lookups.
* The generated data sets `b1_set`, `b3_exceptions`, `c22_specials`, `c6_set`,
  `c7_set`, `c8_set` and `c9_set`, and the `unicodedata` alias, are module
  globals outside the official API; the page does not document them.
"""

from __future__ import annotations

import codecs
import pathlib
import re
import stringprep
import subprocess
import sys
import textwrap
import time
import unicodedata
from collections.abc import Callable, Iterator
from encodings import idna
from functools import partial

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "stringprep.md"
EXPECTED_BLOCKS = 4

FUNCTIONS = [
    "in_table_a1",
    "in_table_b1",
    "map_table_b2",
    "map_table_b3",
    "in_table_c11",
    "in_table_c12",
    "in_table_c11_c12",
    "in_table_c21",
    "in_table_c22",
    "in_table_c21_c22",
    "in_table_c3",
    "in_table_c4",
    "in_table_c5",
    "in_table_c6",
    "in_table_c7",
    "in_table_c8",
    "in_table_c9",
    "in_table_d1",
    "in_table_d2",
]


def best_ns(func: Callable[[], object], repeats: int = 5) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        elapsed = time.perf_counter_ns() - start
        best = elapsed if best is None else min(best, elapsed)
    assert best is not None
    return best


def every_character() -> Iterator[str]:
    """Every code point, surrogates included, as a one-character string."""
    for code in range(sys.maxunicode + 1):
        yield chr(code)


class TestEveryFunctionTakesOneCharacter:
    """Each row is O(1) because the argument is one character, not a string or
    a code point; passing either is rejected, except by `in_table_c11()`."""

    def test_the_page_prices_every_function(self) -> None:
        text = PAGE.read_text(encoding="utf-8")

        assert all(f"`stringprep.{name}(code)`" in text for name in FUNCTIONS)

    @pytest.mark.parametrize("name", [n for n in FUNCTIONS if n != "in_table_c11"])
    @pytest.mark.parametrize("argument", [ord("A"), "ab"])
    def test_a_code_point_or_a_longer_string_raises(self, name: str, argument: object) -> None:
        function: Callable[[object], object] = getattr(stringprep, name)

        with pytest.raises(TypeError):
            function(argument)

    @pytest.mark.parametrize("argument", [ord(" "), "  "])
    def test_in_table_c11_returns_false_instead(self, argument: object) -> None:
        assert stringprep.in_table_c11(argument) is False  # type: ignore[arg-type]


class TestMappingsAreBounded:
    """`map_table_b2` and `map_table_b3` | O(1) | O(1): one character folds to
    at most 4, checked over every code point."""

    @pytest.mark.parametrize("name", ["map_table_b2", "map_table_b3"])
    def test_no_character_maps_to_more_than_four(self, name: str) -> None:
        function: Callable[[str], str] = getattr(stringprep, name)

        longest = max(len(function(char)) for char in every_character())

        assert longest == 4, f"{name} produced a {longest}-character result"

    def test_the_page_examples(self) -> None:
        assert stringprep.map_table_b3("A") == "a"
        assert stringprep.map_table_b3("\u00df") == "ss"
        assert stringprep.map_table_b2("\u2122") == "tm"


class TestTablesFollowUnicode32:
    """Category and bidirectional lookups read Unicode 3.2, not the
    interpreter's current database."""

    def test_the_module_reads_the_3_2_database(self) -> None:
        assert getattr(stringprep, "unicodedata") is unicodedata.ucd_3_2_0  # noqa: B009
        assert unicodedata.ucd_3_2_0.unidata_version == "3.2.0"

    def test_a_character_assigned_later_is_unassigned(self) -> None:
        emoji = "\U0001f600"

        assert unicodedata.ucd_3_2_0.category(emoji) == "Cn"
        assert unicodedata.category(emoji) == "So"
        assert stringprep.in_table_a1(emoji)

    def test_bidirectional_tables_use_3_2_categories(self) -> None:
        assert unicodedata.ucd_3_2_0.bidirectional("\u06dd") == "AL"
        assert unicodedata.bidirectional("\u06dd") == "AN"
        assert stringprep.in_table_d1("\u06dd")
        assert unicodedata.ucd_3_2_0.bidirectional("\u17b4") == "L"
        assert unicodedata.bidirectional("\u17b4") == "NSM"
        assert stringprep.in_table_d2("\u17b4")


class TestTableMembership:
    """Each table row's description, on members and non-members."""

    def test_a1_excludes_noncharacters(self) -> None:
        assert not stringprep.in_table_a1("\ufdd0")
        assert not stringprep.in_table_a1("A")

    def test_b1(self) -> None:
        assert stringprep.in_table_b1("\u00ad")
        assert not stringprep.in_table_b1("A")

    def test_spaces(self) -> None:
        assert stringprep.in_table_c11(" ")
        assert not stringprep.in_table_c11("\u3000")
        assert stringprep.in_table_c12("\u3000")
        assert not stringprep.in_table_c12(" ")

    def test_controls(self) -> None:
        assert stringprep.in_table_c21("\x07")
        assert not stringprep.in_table_c21("\x85")
        assert stringprep.in_table_c22("\x85")
        assert not stringprep.in_table_c22("\x07")

    def test_the_combined_tables_are_the_unions(self) -> None:
        for char in every_character():
            assert stringprep.in_table_c11_c12(char) == (
                stringprep.in_table_c11(char) or stringprep.in_table_c12(char)
            ), hex(ord(char))
            assert stringprep.in_table_c21_c22(char) == (
                stringprep.in_table_c21(char) or stringprep.in_table_c22(char)
            ), hex(ord(char))

    def test_c3_to_c9(self) -> None:
        assert stringprep.in_table_c3("\ue000")
        assert stringprep.in_table_c4("\ufdd0")
        assert stringprep.in_table_c4("\U0010ffff")
        assert stringprep.in_table_c5("\ud800")
        assert stringprep.in_table_c6("\ufff9")
        assert stringprep.in_table_c7("\u2ff0")
        assert stringprep.in_table_c8("\u200e")
        assert stringprep.in_table_c9("\U000e0001")
        tests = [getattr(stringprep, f"in_table_c{index}") for index in range(3, 10)]
        assert not any(test("A") for test in tests)

    def test_bidirectional(self) -> None:
        assert stringprep.in_table_d1("\u05d0")
        assert stringprep.in_table_d1("\u0627")
        assert not stringprep.in_table_d1("A")
        assert stringprep.in_table_d2("A")
        assert not stringprep.in_table_d2("\u05d0")


class TestNameprepAppliesTheTables:
    """`nameprep()` asks the tables a fixed set of questions per character, so
    a label costs O(n): B.1 and B.2 to map, then the prohibited and
    bidirectional tables."""

    @staticmethod
    def count_calls(monkeypatch: pytest.MonkeyPatch, name: str) -> list[str]:
        calls: list[str] = []
        original = getattr(stringprep, name)

        def counting(char: str) -> object:
            calls.append(char)
            return original(char)

        monkeypatch.setattr(stringprep, name, counting)
        return calls

    @pytest.mark.parametrize("length", [10, 1_000])
    def test_one_lookup_per_character(self, monkeypatch: pytest.MonkeyPatch, length: int) -> None:
        label = ("ab\u00ad" * length)[:length]
        b1 = self.count_calls(monkeypatch, "in_table_b1")
        b2 = self.count_calls(monkeypatch, "map_table_b2")

        idna.nameprep(label)

        assert len(b1) == length
        assert len(b2) == length - label.count("\u00ad")

    @pytest.mark.timing
    def test_reordering_combining_marks_stays_linear(self) -> None:
        """Alternating U+0315 (class 232) and U+0300 (class 230) is the shape
        canonical reordering must sort: 16x the marks predicts x16 if linear
        and x256 if quadratic."""
        labels = ["a" + "\u0315\u0300" * pairs for pairs in (1_000, 16_000)]
        assert unicodedata.ucd_3_2_0.normalize("NFD", labels[0])[1] == "\u0300"

        small, large = (best_ns(partial(idna.nameprep, label)) for label in labels)
        ratio = large / small

        assert ratio < 64, f"16x the marks cost x{ratio:.1f} ({small:.0f}ns to {large:.0f}ns)"

    def test_the_page_example(self) -> None:
        assert idna.nameprep("Stra\u00dfe\u00ad") == "strasse"

    def test_it_checks_the_prohibited_tables(self) -> None:
        with pytest.raises(UnicodeError):
            idna.nameprep("a\ue000")

    def test_it_checks_the_bidirectional_tables(self) -> None:
        with pytest.raises(UnicodeError):
            idna.nameprep("\u05d0a")

    def test_the_idna_codec_calls_it(self, monkeypatch: pytest.MonkeyPatch) -> None:
        labels: list[str] = []
        original = idna.nameprep

        def counting(label: str) -> str:
            labels.append(label)
            return original(label)

        monkeypatch.setattr(idna, "nameprep", counting)

        assert codecs.encode("stra\u00dfe.com", "idna") == b"strasse.com"
        assert "stra\u00dfe" in labels


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
        line, source = next((n, s) for n, s in _blocks() if "== 'strasse'" in s)
        mutated = source.replace("== 'strasse'", "== 'stra\u00dfe'", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
