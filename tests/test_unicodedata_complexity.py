"""Tests for docs/stdlib/unicodedata.md.

The page prices every property and name function as a table read for one
code point, and normalization as the one operation that walks a string. The
table reads are settled by observation - each function rejects a second
character, and every assigned name fits under a fixed cap - with one timing
check that the code point does not move the cost. Whether normalization
allocates is settled by identity and traced allocation, which need no
tolerance; its growth class, and the ASCII short-circuit, by comparing sizes
two or three orders of magnitude apart.

Measurement scope:

* Every property function, `name()` and `ucd_3_2_0`'s copies raise
  `TypeError` for a two-character string. `category()` on an ASCII letter
  and on an astral emoji, 20,000 calls each, stays within 3x. A scan of every
  code point finds no name longer than the 256 characters `lookup()` accepts
  and exactly the six documented `east_asian_width()` values.
* `lookup()` on a fresh 100,000-character non-ASCII string peaks above
  150 KB, its UTF-8 encoding; the same length in ASCII peaks under 2 KB.
  Case-insensitivity, an alias (`LATIN CAPITAL LETTER GHA`) and a two-code-
  point named sequence are asserted by result; `name()` of the alias's
  character is asserted to be the formal name.
* `normalize()` returns the input object for NFC text the quick check
  confirms (a 100,000-character run of U+00E9), with a traced peak under
  1 KB, and builds a new object with a peak over 400 KB for 100,000 copies
  of `"q\\u0301"`, which is already NFC. NFD of 10,000 and 1,000,000 Hangul
  syllables, each expanding to two jamo, stays under 1,000x for the 100x
  step, against 10,000x for a quadratic. On an ASCII string 1,000x longer it
  costs under 10x more on 3.11+, and over 100x more on 3.10, which scans.
* `is_normalized()` peaks under 1 KB on the confirmed U+00E9 run and over
  400 KB on the `"q\\u0301"` run, which falls back to building the NFC form.
  An ASCII string is answered at least 10x faster than an accented string
  of the same 200,000 characters on 3.11+. On a run of combining marks
  whose classes cycle through inversions, 20x the marks costs under 5x -
  the check answers at the first inversion - and on a run of one mark,
  which falls back, under 100x, against 400x for a quadratic sort. Both
  arms hold on releases with and without the CVE-2026-3276 fix.
* `ucd_3_2_0` reports version 3.2.0, is a `UCD`, returns a new object from
  `normalize()` on ASCII input, and allocates over 100 KB for
  `is_normalized()` on 100,000 ASCII characters. `UCD()` raises
  `TypeError`. `unicodedata.unidata_version` is a dotted version string.
* The identifier key's two normalizations: `casefold()` of NFKC U+01F0
  is asserted not to be NFKC, and NFKC after `casefold()` is asserted to
  turn MATHEMATICAL BOLD CAPITAL A into a capital `A`.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The patched O(n) bound for an adversarial combining run is measured by
  `tests/test_complexity_caveats.py::TestUnicodeDataCaveats`, which the CI
  timing job runs on each supported line's first patched release.
  Distributor backports under an older version number are not detected.
* The O(n²) bound before the patch follows from the insertion sort in
  Modules/unicodedata.c up to 3.14.5; 20x the marks in one inverted run
  measured about 500x on 3.14.2 and 410x on 3.10.19. No test asserts it,
  since CI runs only patched releases.
* That `ucd_3_2_0.is_normalized()` shares the unpatched quadratic follows
  from Modules/unicodedata.c, whose quick check returns "maybe" for any
  input under the 3.2.0 database. It measured about 750x for 20x the marks
  on 3.14.2 and 390x on 3.10.19; no patched interpreter can show it, so
  only its allocation on ASCII is asserted.
* The page-scoped audit reports `UCD`'s methods and
  `ucd_3_2_0.unidata_version` as unclassified runtime discoveries. They are
  the module functions bound to the 3.2.0 database, priced by the rows for
  those functions and the `ucd_3_2_0` row.
* The O(m) time of `lookup()` for an accepted name is read from
  Modules/unicodedata.c (a hash table up to 3.12, a DAWG walk from 3.13);
  names are too short to time it.
* NFKC, NFKD and the Unicode 3.2.0 database are not varied in the timing
  tests, and neither are code points outside the BMP beyond `category()`.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import unicodedata
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "unicodedata.md"
EXPECTED_BLOCKS = 6

PROPERTY_FUNCTIONS = (
    "bidirectional",
    "category",
    "combining",
    "decimal",
    "decomposition",
    "digit",
    "east_asian_width",
    "mirrored",
    "name",
    "numeric",
)


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


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs, after one untraced warm-up."""
    func()
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class TestPropertiesAreTableReads:
    """Every property function and `name()` | O(1) | O(1).

    They take exactly one character, so there is no size to grow; the timing
    check separates a table read from a search that depends on the code point.
    """

    @pytest.mark.parametrize("database", [unicodedata, unicodedata.ucd_3_2_0])
    @pytest.mark.parametrize("function", PROPERTY_FUNCTIONS)
    def test_a_second_character_is_rejected(self, database: Any, function: str) -> None:
        with pytest.raises(TypeError, match="unicode character"):
            getattr(database, function)("ab")

    @pytest.mark.timing
    def test_the_code_point_does_not_move_the_cost(self) -> None:
        low = best_ns(lambda: [unicodedata.category("a") for _ in range(20_000)])
        high = best_ns(lambda: [unicodedata.category("\U0001f600") for _ in range(20_000)])

        ratio = max(low, high) / min(low, high)
        assert ratio < 3.0, f"both are table reads: ascii={low:.0f}ns astral={high:.0f}ns"

    def test_names_are_bounded_and_widths_are_the_documented_six(self) -> None:
        longest = 0
        widths: set[str] = set()
        for code in range(sys.maxunicode + 1):
            char = chr(code)
            longest = max(longest, len(unicodedata.name(char, "")))
            widths.add(unicodedata.east_asian_width(char))

        assert 0 < longest <= 256, f"the longest name has {longest} characters"
        assert widths == {"W", "F", "Na", "H", "A", "N"}

    def test_missing_values_raise_unless_a_default_is_given(self) -> None:
        for function in (unicodedata.decimal, unicodedata.digit, unicodedata.numeric):
            with pytest.raises(ValueError):
                function("a")
            assert function("a", None) is None
        with pytest.raises(ValueError):
            unicodedata.name("\ue000")
        assert unicodedata.name("\ue000", None) is None

    def test_empty_results_for_unassigned_properties(self) -> None:
        assert unicodedata.decomposition("a") == ""
        assert unicodedata.bidirectional(chr(0x378)) == ""
        assert unicodedata.mirrored("a") == 0
        assert unicodedata.mirrored("(") == 1


class TestLookupReadsTheName:
    """`lookup(name)` | O(m) | O(m): case-insensitive, with aliases and named
    sequences, and a non-ASCII name encoded to UTF-8 first.

    Each measurement uses a string no earlier call has seen, since the UTF-8
    form is cached on the string object.
    """

    def test_a_non_ascii_name_is_encoded(self) -> None:
        def attempt(name: str) -> Callable[[], None]:
            def run() -> None:
                with pytest.raises(KeyError):
                    unicodedata.lookup(name)

            return run

        warm = "é" * 10
        attempt(warm)()
        fresh = "é" * 100_000
        ascii_name = "A" * 100_000

        tracemalloc.start()
        try:
            attempt(fresh)()
            non_ascii_peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        ascii_peak = peak_bytes(attempt(ascii_name))

        assert non_ascii_peak > 150_000, f"a non-ASCII name allocated only {non_ascii_peak}"
        assert ascii_peak < 2_000, f"an ASCII name allocated {ascii_peak}"

    def test_names_aliases_and_sequences(self) -> None:
        assert unicodedata.lookup("greek small letter mu") == "μ"
        gha = unicodedata.lookup("LATIN CAPITAL LETTER GHA")
        assert unicodedata.name(gha) == "LATIN CAPITAL LETTER OI"
        assert len(unicodedata.lookup("LATIN CAPITAL LETTER A WITH MACRON AND GRAVE")) == 2
        with pytest.raises(KeyError, match="undefined character name"):
            unicodedata.lookup("GREEK SMALL LETTER M")


class TestNormalizeAllocatesOnlyWhenItRebuilds:
    """`normalize(form, unistr)` | O(n) | O(n), or O(1) returned unchanged.

    The unchanged case is identity and a traced peak under a kilobyte; the
    rebuilt case includes a string that was already NFC, which the quick check
    can only call "maybe".
    """

    CONFIRMED = "é" * 100_000
    MAYBE = "q\u0301" * 100_000

    def test_confirmed_input_comes_back_unallocated(self) -> None:
        text = self.CONFIRMED
        assert unicodedata.normalize("NFC", text) is text

        peak = peak_bytes(lambda: unicodedata.normalize("NFC", text))
        assert peak < 1_000, f"returning the input allocated {peak} bytes"

    def test_already_normalized_but_maybe_is_rebuilt(self) -> None:
        text = self.MAYBE
        assert unicodedata.is_normalized("NFC", text)

        result = unicodedata.normalize("NFC", text)
        assert result == text and result is not text

        peak = peak_bytes(lambda: unicodedata.normalize("NFC", text))
        assert peak > 400_000, f"rebuilding 200,000 characters allocated only {peak} bytes"

    def test_decomposition_and_recomposition(self) -> None:
        decomposed = "cafe\u0301"
        assert unicodedata.normalize("NFC", decomposed) == "café"
        assert unicodedata.normalize("NFD", "café") == decomposed
        assert unicodedata.normalize("NFKC", "ﬁ") == "fi"
        assert unicodedata.normalize("NFD", "가") == "가"

    @pytest.mark.timing
    def test_an_expanding_decomposition_is_linear(self) -> None:
        small = "가" * 10_000
        large = "가" * 1_000_000

        ratio = best_ns(lambda: unicodedata.normalize("NFD", large), repeats=5) / best_ns(
            lambda: unicodedata.normalize("NFD", small), repeats=5
        )
        assert ratio < 1_000, (
            f"100x the syllables should cost about 100x, not a quadratic's 10,000x: {ratio:.0f}x"
        )


class TestAsciiIsAnsweredFromAFlag:
    """`normalize()` and `is_normalized()` are O(1) for ASCII on 3.11+, and
    scan it on 3.10."""

    SMALL = "a" * 1_000
    LARGE = "a" * 1_000_000

    def ratio(self, function: Callable[[str, str], object]) -> float:
        large, small = self.LARGE, self.SMALL
        return best_ns(lambda: function("NFC", large), inner=5) / best_ns(
            lambda: function("NFC", small), inner=5
        )

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 11), reason="the ASCII flag check is 3.11+")
    @pytest.mark.parametrize("function", [unicodedata.normalize, unicodedata.is_normalized])
    def test_ascii_length_does_not_matter(self, function: Callable[[str, str], object]) -> None:
        ratio = self.ratio(function)
        assert ratio < 10, f"1,000x the ASCII text cost {ratio:.0f}x"

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="3.10 scans ASCII text")
    @pytest.mark.parametrize("function", [unicodedata.normalize, unicodedata.is_normalized])
    def test_ascii_is_scanned_on_3_10(self, function: Callable[[str, str], object]) -> None:
        ratio = self.ratio(function)
        assert ratio > 100, f"1,000x the ASCII text cost only {ratio:.0f}x"

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 11), reason="the ASCII flag check is 3.11+")
    def test_other_text_of_the_same_length_is_scanned(self) -> None:
        ascii_text = "a" * 200_000
        accented = "é" * 200_000

        ascii_time = best_ns(lambda: unicodedata.is_normalized("NFC", ascii_text))
        accented_time = best_ns(lambda: unicodedata.is_normalized("NFC", accented))

        assert accented_time > ascii_time * 10, (
            f"ASCII short-circuits, other text is scanned: "
            f"ascii={ascii_time:.0f}ns accented={accented_time:.0f}ns"
        )


class TestIsNormalizedFallsBackOnlyWhenUnsure:
    """`is_normalized(form, unistr)` | O(n) | O(1), or O(n) when the quick
    check is inconclusive, and O(n) on releases without the CVE-2026-3276
    fix too."""

    def test_a_confirmed_answer_allocates_nothing(self) -> None:
        text = TestNormalizeAllocatesOnlyWhenItRebuilds.CONFIRMED
        assert unicodedata.is_normalized("NFC", text)

        peak = peak_bytes(lambda: unicodedata.is_normalized("NFC", text))
        assert peak < 1_000, f"a confirmed answer allocated {peak} bytes"

    def test_an_inconclusive_check_builds_the_normal_form(self) -> None:
        text = TestNormalizeAllocatesOnlyWhenItRebuilds.MAYBE

        peak = peak_bytes(lambda: unicodedata.is_normalized("NFC", text))
        assert peak > 400_000, f"the fallback allocated only {peak} bytes"

    def test_answers(self) -> None:
        assert unicodedata.is_normalized("NFC", "café")
        assert not unicodedata.is_normalized("NFC", "cafe\u0301")
        assert unicodedata.is_normalized("NFD", "cafe\u0301")
        assert not unicodedata.is_normalized("NFD", "a\u0301\u0316")
        assert unicodedata.is_normalized("NFC", "")

    @pytest.mark.timing
    def test_the_fallback_never_sees_an_inversion(self) -> None:
        """The check answers `False` at the first combining-class inversion,
        and an inversion is what makes the unpatched sort quadratic, so the
        fallback only runs over marks already in order."""

        def inverted(marks: int) -> str:
            return "a" + "".join(chr(0x0300 + (i % 40)) for i in range(marks))

        def ordered(marks: int) -> str:
            return "a" + "\u0301" * marks

        small, large = inverted(1_000), inverted(20_000)
        assert not unicodedata.is_normalized("NFC", large)
        flat = best_ns(lambda: unicodedata.is_normalized("NFC", large)) / best_ns(
            lambda: unicodedata.is_normalized("NFC", small)
        )
        assert flat < 5, f"the first inversion should settle it, but 20x cost {flat:.1f}x"

        small, large = ordered(1_000), ordered(20_000)
        # False as well, but only after building the NFC form: "a" + U+0301 composes
        assert not unicodedata.is_normalized("NFC", large)
        fallback = best_ns(lambda: unicodedata.is_normalized("NFC", large)) / best_ns(
            lambda: unicodedata.is_normalized("NFC", small)
        )
        assert fallback < 100, (
            f"an ordered run should cost about 20x for 20x the marks, not {fallback:.1f}x"
        )


class TestUcd320HasNoQuickCheck:
    """`ucd_3_2_0` | the same functions against Unicode 3.2.0, whose
    `normalize()` and `is_normalized()` build the normal form even for
    ASCII."""

    def test_it_is_the_3_2_0_database(self) -> None:
        old = unicodedata.ucd_3_2_0
        assert old.unidata_version == "3.2.0"
        assert isinstance(old, unicodedata.UCD)
        assert old.category("\u20b9") == "Cn"
        assert unicodedata.category("\u20b9") == "Sc"

    def test_ascii_is_rebuilt(self) -> None:
        text = "ascii"
        result = unicodedata.ucd_3_2_0.normalize("NFC", text)
        assert result == text and result is not text

    def test_is_normalized_allocates_even_for_ascii(self) -> None:
        text = "a" * 100_000
        peak = peak_bytes(lambda: unicodedata.ucd_3_2_0.is_normalized("NFC", text))
        assert peak > 100_000, f"is_normalized on 3.2.0 allocated only {peak} bytes"

    def test_ucd_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            unicodedata.UCD()

    def test_the_current_version_is_a_dotted_string(self) -> None:
        assert re.fullmatch(r"\d+\.\d+\.\d+", unicodedata.unidata_version)


class TestComparingIdentifiersNormalizesTwice:
    """The Common Patterns key normalizes on both sides of `casefold()`,
    because each step can undo the other."""

    def test_folding_can_leave_nfkc(self) -> None:
        folded = unicodedata.normalize("NFKC", "\u01f0").casefold()
        assert not unicodedata.is_normalized("NFKC", folded)

    def test_nfkc_can_produce_a_capital(self) -> None:
        bold_capital = "\U0001d400"
        assert unicodedata.normalize("NFKC", bold_capital.casefold()) == "A"
        folded = unicodedata.normalize("NFKC", bold_capital).casefold()
        assert unicodedata.normalize("NFKC", folded) == "a"


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
        line, source = next((n, s) for n, s in _blocks() if "is not maybe" in s)
        mutated = source.replace("is not maybe", "is maybe", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
