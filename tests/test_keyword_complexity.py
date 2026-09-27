"""Tests for docs/stdlib/keyword.md.

The page prices both checks as hashing the tested string and one set lookup,
and both lists as fixed module attributes. The lookup is settled by
observation: a `str` subclass that counts its `__eq__` calls shows the set
compares nothing for a miss and one entry for a hit, where a scan of the list
compares every entry. The hashing term is settled by timing, and the list
facts by direct checks.

Measurement scope:

* `iskeyword()` and `issoftkeyword()` call a counting `__eq__` zero times for
  a non-keyword and once for a keyword; `s in kwlist` calls it
  `len(kwlist)` times for a non-keyword. That the functions are bound
  `__contains__` methods of frozensets built at import is read from
  Lib/keyword.py and observed: replacing `kwlist` or `softkwlist` with an
  extended list does not change what the checks answer.
* Time is a timing test, for each function, over fresh strings of 10,000
  and 1,000,000 characters, each checked once: 100x the length costs more than 20x. A
  second check of the 1,000,000-character object costs under 3x a check of a
  two-character string, which is the cached hash. Space is a `tracemalloc`
  peak under 1 KB while a 1,000,000-character string is checked.
* The Common Patterns check, `isidentifier()` and then `iskeyword()`, is
  the same timing framing over fresh strings: 100x the length costs more
  than 20x.
* `kwlist` and `softkwlist` are asserted sorted and disjoint; every soft
  keyword is asserted assignable as a name by `compile()`, and `'type'` is
  asserted a soft keyword on 3.12+ and not one before, guarded on
  `sys.version_info`. `tokenize` is asserted to report `if` as a `NAME`
  token.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* That the lists are built once at import is read from Lib/keyword.py; the
  tests observe only that the checks do not read `kwlist` afterwards.
* Only `str` arguments are measured. A `str` subclass with its own
  `__hash__` or `__eq__` adds that cost, and the counting subclass here
  inherits `str.__hash__`.
* The timing tests separate linear from constant time and set no upper
  bound, so they would not catch superlinear growth.
"""

from __future__ import annotations

import io
import keyword
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tokenize
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "keyword.md"
EXPECTED_BLOCKS = 3


def once_ns(func: Callable[[], Any]) -> int:
    """Elapsed nanoseconds for one call."""
    start = time.perf_counter_ns()
    func()
    return time.perf_counter_ns() - start


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class CountingStr(str):
    """A str whose equality comparisons are counted; it hashes like str."""

    calls = 0

    def __eq__(self, other: object) -> bool:
        CountingStr.calls += 1
        return str.__eq__(self, other)

    __hash__ = str.__hash__


def eq_calls(func: Callable[[CountingStr], object], text: str) -> int:
    CountingStr.calls = 0
    func(CountingStr(text))
    return CountingStr.calls


class TestChecksAreSetLookups:
    """`iskeyword(s)` and `issoftkeyword(s)` | O(n) | O(1) | hashes `s`, then
    one set lookup. A scan of the list compares every entry for a miss; the
    set compares none."""

    def test_a_miss_compares_no_entry(self) -> None:
        assert eq_calls(keyword.iskeyword, "variable") == 0
        assert eq_calls(keyword.issoftkeyword, "variable") == 0

    def test_a_hit_compares_one_entry(self) -> None:
        assert eq_calls(keyword.iskeyword, "if") == 1
        assert eq_calls(keyword.issoftkeyword, "match") == 1

    def test_membership_in_kwlist_compares_every_entry(self) -> None:
        count = eq_calls(lambda s: s in keyword.kwlist, "variable")
        assert count == len(keyword.kwlist) > 30

    def test_the_checks_do_not_read_the_lists(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(keyword, "kwlist", [*keyword.kwlist, "variable"])
        monkeypatch.setattr(keyword, "softkwlist", [*keyword.softkwlist, "variable"])

        assert not keyword.iskeyword("variable")
        assert not keyword.issoftkeyword("variable")

    def test_checks_are_exact_and_case_sensitive(self) -> None:
        assert keyword.iskeyword("None")
        assert not keyword.iskeyword("If")
        assert not keyword.iskeyword("print")
        assert not keyword.iskeyword("if ")

    def test_checking_a_long_string_allocates_under_a_kilobyte(self) -> None:
        text = "x" * 1_000_000
        keyword.iskeyword("warm")
        keyword.issoftkeyword("warm")

        peak = peak_bytes(lambda: (keyword.iskeyword(text), keyword.issoftkeyword(text)))

        assert peak < 1_000, f"checking a 1,000,000-character string peaked at {peak} bytes"

    @pytest.mark.timing
    @pytest.mark.parametrize("check", [keyword.iskeyword, keyword.issoftkeyword])
    def test_a_fresh_string_costs_its_length_to_hash(self, check: Callable[[str], bool]) -> None:
        def fastest(length: int) -> int:
            fresh = [("x" * length) + str(index) for index in range(7)]
            return min(once_ns(lambda s=s: check(s)) for s in fresh)

        short_ns = fastest(10_000)
        long_ns = fastest(1_000_000)

        ratio = long_ns / short_ns
        assert ratio > 20, (
            f"100x the length cost x{ratio:.1f} ({short_ns}ns to {long_ns}ns); "
            "hashing is linear, so about x100 is expected and a constant x1"
        )

    @pytest.mark.timing
    def test_the_same_string_again_uses_its_cached_hash(self) -> None:
        text = "x" * 1_000_000
        keyword.iskeyword(text)
        short = "ab"
        keyword.iskeyword(short)

        cached_ns = min(once_ns(lambda: keyword.iskeyword(text)) for _ in range(21))
        short_ns = min(once_ns(lambda: keyword.iskeyword(short)) for _ in range(21))

        assert cached_ns < short_ns * 3, (
            f"a repeat check of a 1,000,000-character string cost {cached_ns}ns against "
            f"{short_ns}ns for two characters; a cached hash makes them equal"
        )


class TestKeywordLists:
    """`keyword.kwlist` and `keyword.softkwlist` | O(1) | O(1) | the hard and
    soft keywords, sorted and disjoint."""

    def test_the_lists_are_sorted(self) -> None:
        assert keyword.kwlist == sorted(keyword.kwlist)
        assert keyword.softkwlist == sorted(keyword.softkwlist)

    def test_the_lists_are_disjoint_and_match_the_checks(self) -> None:
        assert not set(keyword.kwlist) & set(keyword.softkwlist)
        assert all(keyword.iskeyword(word) for word in keyword.kwlist)
        assert all(keyword.issoftkeyword(word) for word in keyword.softkwlist)
        assert not any(keyword.iskeyword(word) for word in keyword.softkwlist)

    def test_soft_keywords_can_be_assigned(self) -> None:
        for word in keyword.softkwlist:
            compile(f"{word} = 1", "<soft>", "exec")

    def test_hard_keywords_cannot_be_assigned(self) -> None:
        with pytest.raises(SyntaxError):
            compile("class = 1", "<hard>", "exec")

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="'type' is soft from 3.12")
    def test_type_is_a_soft_keyword(self) -> None:
        assert keyword.issoftkeyword("type")

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="'type' is soft from 3.12")
    def test_type_is_not_a_soft_keyword_before_3_12(self) -> None:
        assert not keyword.issoftkeyword("type")

    def test_tokenize_reports_a_keyword_as_a_name(self) -> None:
        tokens = list(tokenize.generate_tokens(io.StringIO("if x: pass\n").readline))

        assert tokens[0].type == tokenize.NAME
        assert tokens[0].string == "if"


class TestValidatingANameIsLinear:
    """`s.isidentifier() and not keyword.iskeyword(s)  # O(n)` in Common
    Patterns, measured on fresh strings with identifier syntax, where both
    checks run and neither has a cached result."""

    @pytest.mark.timing
    def test_a_hundred_times_the_length_costs_far_more(self) -> None:
        def fastest(length: int) -> int:
            fresh = [("x" * length) + str(index) for index in range(7)]
            return min(
                once_ns(lambda s=s: s.isidentifier() and not keyword.iskeyword(s)) for s in fresh
            )

        short_ns = fastest(10_000)
        long_ns = fastest(1_000_000)

        ratio = long_ns / short_ns
        assert ratio > 20, (
            f"100x the length cost x{ratio:.1f} ({short_ns}ns to {long_ns}ns); "
            "a linear check gives about x100 and a constant one x1"
        )


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
        line, source = next((n, s) for n, s in _blocks() if "iskeyword('If')" in s)
        mutated = source.replace(
            "assert not keyword.iskeyword('If')", "assert keyword.iskeyword('If')", 1
        )

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
