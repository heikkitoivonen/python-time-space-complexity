"""Tests for docs/stdlib/fnmatch.md.

The page prices a match as one regex match of a cached, compiled pattern, and
the first use of a pattern as its translation and compilation. Compilation and
caching are settled by counting calls to `re.compile`, which needs no
tolerance; case normalization by counting `normcase` calls and by swapping
`os.path` for `ntpath`; space by traced allocation; and the matching bounds by
timing ratios over sizes 100x apart.

Measurement scope:

* `fnmatchcase()` with `*.txt` against names of `a` 10,000 and 1,000,000
  characters long, so the match fails: the larger costs more than 10x and
  less than 1,000x the smaller, which separates O(n) from both O(1) and
  O(n^2). A literal run of 10 and of 1,000 characters (`*aaa...b*`) against
  20,000 `a`s: the longer run costs more than 10x, which is the p in O(n·p);
  the same holds for runs of 10 and 1,000 `?`.
  Two stars and thirty-two (`*a*a...*b`) against 2,000 `a`s stay within 100x
  of each other, where backtracking between wildcards would not finish.
* A matched 1,000,000-character name peaks under 10,000 traced bytes in
  `fnmatchcase()` and, on POSIX, `fnmatch()`; `posixpath.normcase(s)` returns
  `s` itself. Against a 100,001-character name, `*a` repeated 500 times peaks
  within 1,000 bytes of `*a` twice on 3.11+, and more than 5,000 bytes above it
  on 3.10, whose translation captures a group per interior star. With `os.path` swapped for `ntpath`, `fnmatch()` ignores case
  and normalizes both arguments, and `filter()` normalizes the pattern once
  and each of 50 names once; under `posixpath` it normalizes the pattern only.
* A fresh pattern is compiled exactly once across `fnmatchcase()` twice,
  `fnmatch()`, `filter()` and, on 3.14+, `filterfalse()`. `translate()`
  compiles nothing and does not fill the cache. A pattern survives 32,767
  (3.11+) or 255 (3.10) newer distinct patterns and is compiled again after
  32,768 or 256, which is the cache size. Of two patterns, the one used
  last survives 32,767 (or 255) newer patterns and the other is compiled
  again, so
  eviction is least recently used, not first in; the counting `re.compile`
  returns a placeholder for the filler patterns, so only translation is paid
  for them.
* The first use of a pattern - `translate()` and compilation, through
  `fnmatchcase()` with a pattern not yet cached - and `translate()` alone,
  on literal patterns of 1,000 and 100,000 characters: more than 10x and
  less than 1,000x.
* `filter()` reads a generator once and returns matches in input order;
  100,000 names none of which match peak under 10 KB, all of which match over
  400 KB, so the space is the result. Two `filter()` calls over a recording
  list take every name twice; one `any()` pass takes each once and lists a
  name matched by two patterns once. `filterfalse()` returns the complement
  of `filter()` (3.14+).
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* That `re.compile()` is O(p) for every pattern shape. Only literal patterns
  are timed; bracket- and star-heavy patterns were not varied.
* The O(n·p) worst case is measured for one shape, a literal run that
  matches all but its last character at every position; `?` and bracket
  runs were not varied.
* Windows case normalization is simulated by `ntpath` on other platforms; CI
  on Windows runs it against the real `os.path`. Bytes patterns and the
  cache's total memory are not measured.
"""

from __future__ import annotations

import fnmatch
import ntpath
import os
import pathlib
import posixpath
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "fnmatch.md"
EXPECTED_BLOCKS = 9
CACHE_SIZE = 256 if sys.version_info < (3, 11) else 32_768


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
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def fresh(tag: str = "") -> str:
    """A pattern no other test has used, so it is not in the cache yet."""
    return f"{tag}{uuid.uuid4().hex}*.txt"


@pytest.fixture
def compiles(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record every regex source fnmatch compiles."""
    seen: list[str] = []
    real = re.compile

    def counting(source: Any, flags: Any = 0) -> Any:
        seen.append(source)
        return real(source, flags)

    monkeypatch.setattr(re, "compile", counting)
    return seen


class TestMatchingIsLinearInTheName:
    """`fnmatchcase()` is O(n·p): O(n) for a short literal tail, n·p for a
    long run after a `*` that keeps almost matching, and never exponential."""

    @pytest.mark.timing
    def test_a_short_tail_scales_with_the_name(self) -> None:
        short, long = "a" * 10_000, "a" * 1_000_000
        fnmatch.fnmatchcase(short, "*.txt")

        short_ns = best_ns(lambda: fnmatch.fnmatchcase(short, "*.txt"), inner=20)
        long_ns = best_ns(lambda: fnmatch.fnmatchcase(long, "*.txt"))
        ratio = long_ns / short_ns

        assert 10 < ratio < 1_000, f"100x the name: x{ratio:.1f}"

    @pytest.mark.timing
    def test_a_long_literal_run_multiplies_the_cost(self) -> None:
        name = "a" * 20_000
        short_run, long_run = "*" + "a" * 10 + "b*", "*" + "a" * 1_000 + "b*"
        fnmatch.fnmatchcase(name, short_run)
        fnmatch.fnmatchcase(name, long_run)

        short_ns = best_ns(lambda: fnmatch.fnmatchcase(name, short_run))
        long_ns = best_ns(lambda: fnmatch.fnmatchcase(name, long_run))

        assert long_ns > short_ns * 10, f"100x the run: x{long_ns / short_ns:.1f}"

    @pytest.mark.timing
    def test_a_long_run_of_question_marks_multiplies_the_cost(self) -> None:
        name = "a" * 20_000
        short_run, long_run = "*" + "?" * 10 + "b*", "*" + "?" * 1_000 + "b*"
        fnmatch.fnmatchcase(name, short_run)
        fnmatch.fnmatchcase(name, long_run)

        short_ns = best_ns(lambda: fnmatch.fnmatchcase(name, short_run))
        long_ns = best_ns(lambda: fnmatch.fnmatchcase(name, long_run))

        assert long_ns > short_ns * 10, f"100x the run: x{long_ns / short_ns:.1f}"

    @pytest.mark.timing
    def test_more_wildcards_do_not_backtrack(self) -> None:
        name = "a" * 2_000
        few, many = "*a" * 2 + "*b", "*a" * 32 + "*b"
        assert not fnmatch.fnmatchcase(name, few)
        assert not fnmatch.fnmatchcase(name, many)

        few_ns = best_ns(lambda: fnmatch.fnmatchcase(name, few), inner=20)
        many_ns = best_ns(lambda: fnmatch.fnmatchcase(name, many), inner=20)

        assert many_ns < few_ns * 100, f"16x the stars: x{many_ns / few_ns:.1f}"


class TestMatchingHoldsNothingPerName:
    """On POSIX `normcase` returns its argument and a match allocates nothing
    in proportion to the name; only on 3.10 does it grow with the stars."""

    def test_posix_normcase_returns_its_argument(self) -> None:
        name = "Report.TXT"
        assert posixpath.normcase(name) is name

    @pytest.mark.skipif(
        os.path is not posixpath, reason="platform: ntpath.normcase copies its argument"
    )
    def test_fnmatch_does_not_copy_a_long_name(self) -> None:
        name = "a" * 1_000_000 + ".txt"
        assert fnmatch.fnmatch(name, "*.txt")

        assert peak_bytes(lambda: fnmatch.fnmatch(name, "*.txt")) < 10_000

    def test_fnmatchcase_does_not_copy_a_long_name(self) -> None:
        name = "a" * 1_000_000 + ".txt"
        assert fnmatch.fnmatchcase(name, "*.txt")

        assert peak_bytes(lambda: fnmatch.fnmatchcase(name, "*.txt")) < 10_000

    def test_space_follows_interior_stars_only_on_3_10(self) -> None:
        name = "xa" * 50_000 + "b"
        few, many = "*a" * 2 + "*b", "*a" * 500 + "*b"
        assert fnmatch.fnmatchcase(name, few)
        assert fnmatch.fnmatchcase(name, many)

        few_peak = peak_bytes(lambda: fnmatch.fnmatchcase(name, few))
        many_peak = peak_bytes(lambda: fnmatch.fnmatchcase(name, many))

        if sys.version_info < (3, 11):
            assert many_peak > few_peak + 5_000, f"{few_peak} vs {many_peak} bytes"
        else:
            assert many_peak < few_peak + 1_000, f"{few_peak} vs {many_peak} bytes"


class TestFnmatchNormalizesCase:
    """`fnmatch()` passes both arguments through `os.path.normcase`; on
    Windows that ignores case, and `filter()` normalizes each name."""

    def test_fnmatchcase_always_counts_case(self) -> None:
        assert not fnmatch.fnmatchcase("Report.TXT", "*.txt")

    def test_ntpath_normcase_makes_fnmatch_ignore_case(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []
        real = ntpath.normcase

        def counting(path: Any) -> Any:
            calls.append(path)
            return real(path)

        monkeypatch.setattr(os, "path", ntpath)
        monkeypatch.setattr(ntpath, "normcase", counting)

        assert fnmatch.fnmatch("Report.TXT", "*.txt")
        assert calls == ["Report.TXT", "*.txt"]

        calls.clear()
        names = [f"File{i}.TXT" for i in range(50)]
        assert fnmatch.filter(names, "file*.txt") == names
        assert len(calls) == len(names) + 1

    def test_posix_filter_normalizes_only_the_pattern(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[str] = []
        real = posixpath.normcase

        def counting(path: Any) -> Any:
            calls.append(path)
            return real(path)

        monkeypatch.setattr(os, "path", posixpath)
        monkeypatch.setattr(posixpath, "normcase", counting)

        names = [f"file{i}.txt" for i in range(50)]
        assert fnmatch.filter(names, "file*.txt") == names
        assert calls == ["file*.txt"]


class TestAPatternIsCompiledOnce:
    """First use of a pattern is `translate()` plus `re.compile()`; the
    matcher is cached for every function but `translate()`."""

    def test_every_matching_function_shares_one_compilation(self, compiles: list[str]) -> None:
        pattern = fresh()
        name = pattern.replace("*", "x")

        assert fnmatch.fnmatchcase(name, pattern)
        assert fnmatch.fnmatchcase(name, pattern)
        assert fnmatch.fnmatch(name, pattern)
        assert fnmatch.filter([name], pattern) == [name]
        if sys.version_info >= (3, 14):
            assert fnmatch.filterfalse([name], pattern) == []

        assert compiles == [fnmatch.translate(pattern)]

    def test_translate_neither_compiles_nor_caches(self, compiles: list[str]) -> None:
        pattern = fresh()

        assert isinstance(fnmatch.translate(pattern), str)
        assert compiles == []

        fnmatch.fnmatchcase("x", pattern)
        assert len(compiles) == 1

    def test_the_cache_holds_its_documented_size(self, monkeypatch: pytest.MonkeyPatch) -> None:
        placeholder = re.compile("(?!)")
        real = re.compile
        compiled: list[str] = []

        def counting(source: Any, flags: Any = 0) -> Any:
            compiled.append(source)
            return placeholder if "filler" in source else real(source, flags)

        monkeypatch.setattr(re, "compile", counting)

        def fill(count: int) -> None:
            tag = uuid.uuid4().hex
            for i in range(count):
                fnmatch.fnmatchcase("", f"filler{tag}{i}")

        kept = fresh("kept")
        fnmatch.fnmatchcase("", kept)
        fill(CACHE_SIZE - 1)
        compiled.clear()
        fnmatch.fnmatchcase("", kept)
        assert compiled == [], f"evicted by {CACHE_SIZE - 1} newer patterns"

        # Least recently used, not first in: a refreshed old entry outlives a newer one
        older, newer = fresh("older"), fresh("newer")
        fnmatch.fnmatchcase("", older)
        fnmatch.fnmatchcase("", newer)
        fnmatch.fnmatchcase("", older)
        fill(CACHE_SIZE - 1)
        compiled.clear()
        fnmatch.fnmatchcase("", older)
        assert compiled == [], "a refreshed entry was evicted"
        fnmatch.fnmatchcase("", newer)
        assert len(compiled) == 1, "the least recently used entry survived"

        evicted = fresh("evicted")
        fnmatch.fnmatchcase("", evicted)
        fill(CACHE_SIZE)
        compiled.clear()
        fnmatch.fnmatchcase("", evicted)
        assert len(compiled) == 1, f"still cached after {CACHE_SIZE} newer patterns"

    @pytest.mark.timing
    def test_first_use_is_linear_in_the_pattern(self) -> None:
        def first_use(length: int) -> float:
            best: float | None = None
            for _ in range(5):
                pattern = uuid.uuid4().hex + "a" * length
                start = time.perf_counter_ns()
                fnmatch.fnmatchcase("", pattern)
                elapsed = time.perf_counter_ns() - start
                best = elapsed if best is None else min(best, elapsed)
            assert best is not None
            return best

        small, large = first_use(1_000), first_use(100_000)
        assert 10 < large / small < 1_000, f"100x the pattern: x{large / small:.1f}"


class TestTranslateIsLinear:
    """`translate()` is O(p) and returns a string."""

    @pytest.mark.timing
    def test_translate_scales_with_the_pattern(self) -> None:
        small, large = "a" * 1_000, "a" * 100_000

        small_ns = best_ns(lambda: fnmatch.translate(small))
        large_ns = best_ns(lambda: fnmatch.translate(large))
        ratio = large_ns / small_ns

        assert 10 < ratio < 1_000, f"100x the pattern: x{ratio:.1f}"


class TestFilterHoldsOnlyTheResult:
    """`filter()` is O(k·n·p) time and O(r) space on POSIX 3.11+ (plus O(p)
    on 3.10), reading `names` once."""

    def test_a_generator_is_read_once_in_order(self) -> None:
        taken: list[str] = []

        def names() -> Iterator[str]:
            for name in ["b.py", "a.txt", "c.py"]:
                taken.append(name)
                yield name

        assert fnmatch.filter(names(), "*.py") == ["b.py", "c.py"]
        assert taken == ["b.py", "a.txt", "c.py"]

    def test_space_follows_the_matches(self) -> None:
        names = [f"file{i}.txt" for i in range(100_000)]
        fnmatch.filter(names[:1], "*.txt")
        fnmatch.filter(names[:1], "*.csv")

        none_peak = peak_bytes(lambda: fnmatch.filter(names, "*.csv"))
        all_peak = peak_bytes(lambda: fnmatch.filter(names, "*.txt"))

        assert none_peak < 10_000, f"no matches peaked at {none_peak} bytes"
        assert all_peak > 400_000, f"100,000 matches peaked at {all_peak} bytes"

    def test_filterfalse_is_the_complement(self) -> None:
        if sys.version_info < (3, 14):
            pytest.skip("version: filterfalse is 3.14+")
        names = ["main.py", "main.pyc", "util.py", "util.pyc"]
        assert fnmatch.filterfalse(names, "*.pyc") == ["main.py", "util.py"]
        assert sorted(fnmatch.filter(names, "*.pyc") + fnmatch.filterfalse(names, "*.pyc")) == (
            sorted(names)
        )


class TestSeveralPatterns:
    """One `filter()` per pattern is a pass per pattern and can list a name
    twice; one `any()` pass reads each name once."""

    def test_one_filter_per_pattern_is_a_pass_per_pattern(self) -> None:
        visits: list[str] = []

        class RecordingNames(list[str]):
            def __iter__(self) -> Iterator[str]:
                for name in super().__iter__():
                    visits.append(name)
                    yield name

        expected = ["test_x_test.py", "a.py"]
        names = RecordingNames(expected)
        patterns = ["test_*.py", "*_test.py"]

        both = [n for p in patterns for n in fnmatch.filter(names, p)]
        assert both == ["test_x_test.py", "test_x_test.py"]
        assert visits == expected + expected

        visits.clear()
        once = [n for n in names if any(fnmatch.fnmatchcase(n, p) for p in patterns)]
        assert once == ["test_x_test.py"]
        assert visits == expected


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
        line, source = next((n, s) for n, s in _blocks() if "len(hits) == 111" in s)
        mutated = source.replace("len(hits) == 111", "len(hits) == 110", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
