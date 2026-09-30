"""Tests for docs/stdlib/getopt.md.

The page prices both parsers by the steps they take: each step slices off the
rest of the argument list, looks a short option up by scanning `shortopts`,
and looks a long option up by testing every entry of `longopts` as a prefix.
Those three costs are settled by observation - a sequence that records how
many elements its slices copy, a `str` subclass that counts index reads, and
option names that count `startswith` calls - so they need no tolerance. One
timing test and one allocation test confirm that a real list behaves as the
recording sequence does. The scanning rules the bounds depend on are settled
by the parsed results.

Measurement scope:

* Slicing: `getopt()` over 1,000 `-a` options copies exactly 1,000·999/2
  elements; over 10 options followed by 990 positional arguments it copies
  the sum of the 10 remainders, 9,945. `gnu_getopt()` over 1,000 positional
  arguments copies 1,000·999/2, and over `-a`, `--` and 998 positional
  arguments, 1,000 in all, it copies 2·1,000 - 3: one slice per step and one
  for the arguments after `--`. `getopt()` returns the arguments from the
  first non-option on without copying them again.
* On real lists, `gnu_getopt()` over 16,000 positional arguments costs more
  than 64x what 1,000 cost (linear predicts 16x, quadratic 256x). Its traced
  peak over 8,000 arguments is under 16x the peak over 1,000 (linear predicts
  8x, a copy retained per step 64x).
* Lookups: one short option placed after 10, 100 and 1,000 other letters of
  `shortopts` costs exactly that many index reads plus one. Each of 5 long
  options against 10, 100 and 1,000 `longopts` entries tests all of them,
  exactly 5·k `startswith` calls.
* Scanning rules: `getopt()` stops at the first non-option and at a bare
  `-`; `gnu_getopt()` scans past positional arguments unless `shortopts`
  starts with `+` or `POSIXLY_CORRECT` is non-empty; an empty
  `POSIXLY_CORRECT` changes nothing, and on 3.14+ a leading `-` overrides
  it. `--` ends processing in both. `POSIXLY_CORRECT` is removed from the
  environment of every other test and of the example subprocesses, since a
  non-empty value makes `gnu_getopt()` stop at the first positional
  argument.
  Unique prefixes match, ambiguous ones raise with `opt` set, and an exact
  match wins over a longer entry. `longopts` given as one string is
  accepted.
* `GetoptError` carries `msg` and `opt`, `str()` of it is `msg`, and
  `getopt.error` is the same class.
* Optional arguments (`::` and `=?`), attached and separate, and the
  in-order mode of a leading `-` are asserted on 3.14+; on earlier versions `o::` is asserted to require an
  argument, so the version boundary is checked from both sides.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* Pricing each argument and option name as O(1) to compare is a cost-model
  assumption. A cluster such as `-abc` re-slices its own remaining letters
  once per letter, which is quadratic in the cluster's length; clusters of a
  few letters are the case the page prices.
* The O(k) space of a long-option lookup is the list of matching entries,
  read from Lib/getopt.py's `long_has_args`; it is k only when every entry
  matches the prefix.
* `do_longs`, `do_shorts`, `long_has_args` and `short_has_arg` are
  undocumented helpers the audit discovers at runtime; the page covers them
  through the lookup rows, not by name.
* The timing and allocation tests vary only the count of positional
  arguments; they do not vary argument length or the mix of options. The k
  and s terms of the space bounds are one copy of `longopts` and, for
  `gnu_getopt()` with a leading `+` or `-`, one slice of `shortopts`, read
  from Lib/getopt.py and not measured.
"""

from __future__ import annotations

import getopt
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable, Iterator
from typing import Any, overload

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "getopt.md"
EXPECTED_BLOCKS = 7


def best_ns(func: Callable[[], Any], repeats: int = 3) -> float:
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


@pytest.fixture(autouse=True)
def _no_posixly_correct(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("POSIXLY_CORRECT", raising=False)


class SliceLog:
    copied = 0


class RecordingArgs:
    """An argument sequence that records how many elements its slices copy."""

    def __init__(self, items: list[str], log: SliceLog) -> None:
        self._items = items
        self._log = log

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    @overload
    def __getitem__(self, key: int) -> str: ...
    @overload
    def __getitem__(self, key: slice) -> RecordingArgs: ...
    def __getitem__(self, key: int | slice) -> str | RecordingArgs:
        if isinstance(key, slice):
            part = self._items[key]
            self._log.copied += len(part)
            return RecordingArgs(part, self._log)
        return self._items[key]


def copied_by(parse: Callable[..., Any], items: list[str], *options: Any) -> int:
    log = SliceLog()
    parse(RecordingArgs(items, log), *options)
    return log.copied


class CountingShortopts(str):
    """A shortopts string that counts index reads."""

    reads = 0

    def __getitem__(self, key: Any) -> str:  # type: ignore[override]
        self.reads += 1
        return str.__getitem__(self, key)


class StartswithLog:
    calls = 0


class CountingName(str):
    """A longopts entry that counts prefix tests against it."""

    log: StartswithLog

    def startswith(self, *args: Any) -> bool:  # type: ignore[override]
        self.log.calls += 1
        return str.startswith(self, *args)


def counting_longopts(k: int, log: StartswithLog) -> list[str]:
    names: list[str] = []
    for i in range(k):
        name = CountingName(f"option{i}")
        name.log = log
        names.append(name)
    return names


class TestEveryStepSlicesTheRest:
    """`getopt()` and `gnu_getopt()` are O((p + 1)·(n + s + k)): each of the
    p steps replaces the remaining arguments with a slice. A recording sequence counts
    the copied elements exactly, which separates a quadratic scan from a
    linear one with no tolerance."""

    def test_getopt_copies_the_remainder_at_every_option(self) -> None:
        n = 1_000
        assert copied_by(getopt.getopt, ["-a"] * n, "a") == n * (n - 1) // 2

    def test_getopt_takes_no_step_for_positional_arguments(self) -> None:
        n, p = 1_000, 10
        items = ["-a"] * p + ["file"] * (n - p)
        assert copied_by(getopt.getopt, items, "a") == sum(n - i for i in range(1, p + 1))

    def test_gnu_getopt_steps_over_every_positional_argument(self) -> None:
        n = 1_000
        assert copied_by(getopt.gnu_getopt, ["file"] * n, "a") == n * (n - 1) // 2

    def test_a_double_dash_hands_the_rest_over_in_one_slice(self) -> None:
        n = 1_000
        items = ["-a", "--"] + ["file"] * (n - 2)
        assert copied_by(getopt.gnu_getopt, items, "a") == 2 * n - 3

    @pytest.mark.timing
    def test_positional_arguments_cost_quadratic_time_on_a_real_list(self) -> None:
        small = ["file"] * 1_000
        large = ["file"] * 16_000
        small_ns = best_ns(lambda: getopt.gnu_getopt(small, "a"))
        large_ns = best_ns(lambda: getopt.gnu_getopt(large, "a"))
        ratio = large_ns / small_ns
        assert ratio > 64, (
            f"16x the arguments cost x{ratio:.1f} ({small_ns:.0f}ns -> {large_ns:.0f}ns); "
            "linear predicts 16x and quadratic 256x"
        )

    def test_space_stays_linear(self) -> None:
        small = ["file"] * 1_000
        large = ["file"] * 8_000
        small_peak = peak_bytes(lambda: getopt.gnu_getopt(small, "a"))
        large_peak = peak_bytes(lambda: getopt.gnu_getopt(large, "a"))
        ratio = large_peak / small_peak
        assert ratio < 16, (
            f"8x the arguments raised the peak x{ratio:.1f} ({small_peak} -> {large_peak} "
            "bytes); linear predicts 8x, a slice retained per step 64x"
        )


class TestShortOptionLookupScansShortopts:
    """The "Looking up one short option | O(s)" row: the option's letter is found by
    reading `shortopts` from the start, so its position sets the cost."""

    @pytest.mark.parametrize("before", [10, 100, 1_000])
    def test_reads_every_letter_before_the_option(self, before: int) -> None:
        letters = "".join(chr(0x100 + i) for i in range(before))
        shortopts = CountingShortopts(letters + "a")
        opts, _ = getopt.getopt(["-a"], shortopts)
        assert opts == [("-a", "")]
        assert shortopts.reads == before + 1

    def test_an_unknown_letter_reads_all_of_shortopts(self) -> None:
        shortopts = CountingShortopts("abcdefghij")
        with pytest.raises(getopt.GetoptError):
            getopt.getopt(["-z"], shortopts)
        assert shortopts.reads == 10


class TestLongOptionLookupTestsEveryEntry:
    """The "Looking up one long option | O(k)" row: every entry of `longopts` is tested
    as a prefix match, even when the first one matches exactly."""

    @pytest.mark.parametrize("k", [10, 100, 1_000])
    def test_each_long_option_tests_all_k_entries(self, k: int) -> None:
        log = StartswithLog()
        longopts = counting_longopts(k, log)
        opts, _ = getopt.getopt(["--option0"] * 5, "", longopts)
        assert opts == [("--option0", "")] * 5
        assert log.calls == 5 * k


class TestWhereScanningStops:
    """The scanning rules that decide p: `getopt()` stops at the first
    non-option, `gnu_getopt()` does not unless told to, and `--` ends both."""

    def test_getopt_stops_at_the_first_non_option(self) -> None:
        opts, args = getopt.getopt(["-a", "file", "-b"], "ab")
        assert opts == [("-a", "")]
        assert args == ["file", "-b"]

    def test_a_bare_dash_is_a_non_option(self) -> None:
        opts, args = getopt.getopt(["-a", "-", "-b"], "ab")
        assert opts == [("-a", "")]
        assert args == ["-", "-b"]

    def test_gnu_getopt_scans_past_positional_arguments(self) -> None:
        opts, args = getopt.gnu_getopt(["-a", "file", "-b", "-"], "ab")
        assert opts == [("-a", ""), ("-b", "")]
        assert args == ["file", "-"]

    def test_a_leading_plus_stops_gnu_getopt_at_the_first_non_option(self) -> None:
        opts, args = getopt.gnu_getopt(["-a", "file", "-b"], "+ab")
        assert opts == [("-a", "")]
        assert args == ["file", "-b"]

    def test_posixly_correct_stops_gnu_getopt_too(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("POSIXLY_CORRECT", "1")
        opts, args = getopt.gnu_getopt(["-a", "file", "-b"], "ab")
        assert opts == [("-a", "")]
        assert args == ["file", "-b"]

    def test_an_empty_posixly_correct_changes_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("POSIXLY_CORRECT", "")
        opts, args = getopt.gnu_getopt(["-a", "file", "-b"], "ab")
        assert opts == [("-a", ""), ("-b", "")]
        assert args == ["file"]

    def test_double_dash_ends_processing_in_both(self) -> None:
        for parse in (getopt.getopt, getopt.gnu_getopt):
            opts, args = parse(["-a", "--", "-b"], "ab")
            assert opts == [("-a", "")]
            assert args == ["-b"]


class TestLongOptionPrefixes:
    """A unique prefix matches, an ambiguous one raises, an exact match wins."""

    def test_a_unique_prefix_matches(self) -> None:
        opts, _ = getopt.getopt(["--fr", "--lev=3"], "", ["frob", "level="])
        assert opts == [("--frob", ""), ("--level", "3")]

    def test_an_ambiguous_prefix_raises(self) -> None:
        with pytest.raises(getopt.GetoptError) as caught:
            getopt.getopt(["--f"], "", ["foo", "frob"])
        assert caught.value.opt == "f"
        assert "not a unique prefix" in caught.value.msg

    def test_an_exact_match_wins_over_a_longer_entry(self) -> None:
        opts, _ = getopt.getopt(["--foo"], "", ["foo", "foobar"])
        assert opts == [("--foo", "")]

    def test_longopts_may_be_one_string(self) -> None:
        opts, _ = getopt.getopt(["--verbose"], "", "verbose")
        assert opts == [("--verbose", "")]


class TestGetoptError:
    """`GetoptError(msg, opt='')` carries both, and `error` is an alias."""

    def test_msg_and_opt(self) -> None:
        with pytest.raises(getopt.GetoptError) as caught:
            getopt.getopt(["--size"], "", ["size="])
        assert caught.value.opt == "size"
        assert caught.value.msg == "option --size requires argument"
        assert str(caught.value) == caught.value.msg

    def test_an_argument_to_an_option_that_takes_none_raises(self) -> None:
        with pytest.raises(getopt.GetoptError) as caught:
            getopt.getopt(["--quiet=yes"], "", ["quiet"])
        assert caught.value.opt == "quiet"

    def test_opt_defaults_to_empty(self) -> None:
        assert getopt.GetoptError("message").opt == ""

    def test_error_is_the_same_class(self) -> None:
        assert getopt.error is getopt.GetoptError


class TestOptionalArguments:
    """Python 3.14+: `::` and `=?` make an argument optional, and a leading `-`
    makes `gnu_getopt()` report positional arguments in order."""

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="version: optional arguments are 3.14+")
    def test_an_optional_argument_must_be_attached(self) -> None:
        opts, args = getopt.getopt(["-ow", "-o", "value"], "o::")
        assert opts == [("-o", "w"), ("-o", "")]
        assert args == ["value"]
        opts, args = getopt.getopt(["--color=red", "--color", "blue"], "", ["color=?"])
        assert opts == [("--color", "red"), ("--color", "")]
        assert args == ["blue"]

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="version: in-order mode is 3.14+")
    def test_a_leading_dash_keeps_arguments_in_order(self) -> None:
        opts, args = getopt.gnu_getopt(["a", "-x", "b", "--y", "c"], "-x", ["y"])
        assert opts == [(None, ["a"]), ("-x", ""), (None, ["b"]), ("--y", "")]
        assert args == ["c"]

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="version: in-order mode is 3.14+")
    def test_a_leading_dash_overrides_posixly_correct(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("POSIXLY_CORRECT", "1")
        opts, args = getopt.gnu_getopt(["a", "-x", "b"], "-x")
        assert opts == [(None, ["a"]), ("-x", "")]
        assert args == ["b"]

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="version: 3.14 added `::`")
    def test_before_3_14_a_double_colon_still_requires_an_argument(self) -> None:
        with pytest.raises(getopt.GetoptError, match="requires argument"):
            getopt.getopt(["-o"], "o::")


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
    env = {key: value for key, value in os.environ.items() if key != "POSIXLY_CORRECT"}
    return subprocess.run(
        [sys.executable, str(script)],
        env=env,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and asserts its own result. The
    optional-argument and in-order blocks need Python 3.14, the pinned
    interpreter the suite runs examples on."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    @pytest.mark.skipif(
        sys.version_info < (3, 14), reason="version: two examples need 3.14 optional arguments"
    )
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
        line, source = next((n, s) for n, s in _blocks() if "args == ['file1', 'file2']" in s)
        mutated = source.replace("args == ['file1', 'file2']", "args == ['file1']", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
