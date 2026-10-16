"""Tests for docs/stdlib/xml.md.

The page's own rows are the two 3.15 string checks in the `xml` package;
everything else it links to has its own page and tests. Both checks are one
regular-expression call over the string (Lib/xml/utils.py in 3.15), so their
cost is settled by timing at three sizes ten times apart and their space by
traced allocation.

Measurement scope:

* `is_valid_text()` over a valid string of 10,000, 100,000 and 1,000,000
  characters: each 10x step costs more than 4x and under 30x, so the cost
  is linear in the whole string.
  The same lengths with an illegal first character cost under 3x across the
  hundredfold range, so the search stops at the first illegal character.
* `is_valid_name()` over a name of the same three lengths, valid but for a
  final `<`: each 10x step costs more than 4x, and under 30x, where a
  backtracking match would be quadratic and cost about 100x.
* Space: with a 1,000,000-character string already allocated, neither check
  raises the traced peak by more than 10,000 bytes.
* The accepted and refused examples on the page: names may not start with a
  digit or contain `<`, and text may hold TAB and LF but not BEL.

Not settled here:

* The functions do not exist before 3.15, so every test here skips on 3.11
  to 3.14, and the page's example guards itself the same way.
* Only ASCII strings are timed; the character classes are the same width for
  any code point, but non-ASCII input is not varied.
"""

from __future__ import annotations

import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import xml
from collections.abc import Callable
from itertools import pairwise
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "xml.md"
EXPECTED_BLOCKS = 1
SIZES = (10_000, 100_000, 1_000_000)

needs_315 = pytest.mark.skipif(sys.version_info < (3, 15), reason="the checks are 3.15+")
validators: Any = xml


def best_ns(func: Callable[[], Any], repeats: int = 7) -> float:
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


@needs_315
class TestTheChecksAnswerCorrectly:
    """The two rows' results, on the shapes the page names."""

    def test_names(self) -> None:
        assert validators.is_valid_name("item-1")
        assert validators.is_valid_name("ns:tag")
        assert not validators.is_valid_name("1item")
        assert not validators.is_valid_name("a<b")
        assert not validators.is_valid_name("")

    def test_text(self) -> None:
        assert validators.is_valid_text("tab\tand newline\n\r")
        assert not validators.is_valid_text("bell\x07")
        assert not validators.is_valid_text("￾")
        assert validators.is_valid_text("")


@needs_315
@pytest.mark.timing
class TestTheChecksAreLinear:
    """`is_valid_name(name)`, `is_valid_text(data)` | O(n) | O(1)."""

    def test_valid_text_reads_the_whole_string(self) -> None:
        strings = [("a" * size,) for size in SIZES]
        times = [best_ns(lambda s=s: validators.is_valid_text(*s)) for s in strings]

        for small, large in pairwise(times):
            ratio = large / small
            assert 4 < ratio < 30, f"10x the text cost x{ratio:.1f} ({times})"

    def test_text_stops_at_the_first_illegal_character(self) -> None:
        strings = ["\x01" + "a" * size for size in SIZES]
        for text in strings:
            validators.is_valid_text(text)  # warm the pattern cache
        times = [best_ns(lambda t=t: validators.is_valid_text(t)) for t in strings]

        assert times[-1] < times[0] * 3, f"100x the text cost x{times[-1] / times[0]:.1f}"

    def test_a_name_is_matched_in_one_linear_pass(self) -> None:
        names = ["a" * size + "<" for size in SIZES]
        times = [best_ns(lambda n=n: validators.is_valid_name(n)) for n in names]

        for small, large in pairwise(times):
            ratio = large / small
            assert 4 < ratio < 30, f"10x the name cost x{ratio:.1f} ({times})"


@needs_315
class TestTheChecksAllocateNothingPerCharacter:
    def test_the_peak_does_not_follow_the_string(self) -> None:
        text = "a" * 1_000_000
        validators.is_valid_text(text)
        validators.is_valid_name(text)

        assert peak_bytes(lambda: validators.is_valid_text(text)) < 10_000
        assert peak_bytes(lambda: validators.is_valid_name(text)) < 10_000


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
    """The page's one block runs in its own subprocess and asserts its results."""

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

    @needs_315
    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = _blocks()[0]
        mutated = source.replace(
            "assert not xml.is_valid_name('1item')", "assert xml.is_valid_name('1item')", 1
        )

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
