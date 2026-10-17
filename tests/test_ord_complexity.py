"""Tests for docs/builtins/ord.md.

ord() is builtin_ord in Python/bltinmodule.c. For a bytes, str or bytearray
argument (subclasses included) it reads the stored length, and if it is 1
reads the one byte or character; any other length, and any other type, raises
TypeError. Nothing in it loops, so a single call is O(1) by construction; the
function is the same in the v3.11.14, v3.12.12, v3.13.11, v3.14.2 and
v3.15.0rc3 tags apart from a PyUnicode_READY call that 3.13 removed, which is
a no-op for every string those versions create.

The rows are settled by observation where a value or an exception decides
them, and by a stopwatch where they are about cost: a rejected long string
and a bulk conversion.

Measurement scope:

* every code point from 0 to 0x10FFFF round-trips through chr() and ord(),
  surrogates included; every byte value round-trips through a one-byte bytes
  and bytearray; a str subclass is accepted.
* wrong length: '', 'ab', b'' and bytearray(b'ab') raise TypeError naming the
  length, and a 10,000,000-character string raises TypeError in under x3
  the time of a two-character one, where counting its characters would cost
  about x5,000,000.
* wrong type: int, float, memoryview and a list raise TypeError naming the
  type, and an object with a counting `__index__` raises with the counter at
  zero.
* bulk conversion: `[ord(c) for c in s]` over 10,000, 100,000 and 1,000,000
  characters costs between x3 and x30 for each tenfold step; linear predicts
  x10 and quadratic x100.
* bytes: `data[i]` is an int, ord() of it raises TypeError, and `list(data)`
  equals ord() of each one-byte slice.
* `str.isascii()` on 10,000,000 ASCII characters costs under x3 what it
  costs on 1,000, where a scan predicts x10,000.
* sorting: for 2,000 code points drawn with a fixed seed from the whole
  range, `sorted(chars)` and `sorted(chars, key=ord)` are equal.
* every fenced block runs in its own subprocess and asserts its own results,
  and a mutated assertion in one is asserted to fail.

Not settled here:

* That a one-character call does not depend on the code point is read from
  builtin_ord, which reads one character whatever the string's storage
  width; it is not timed, since there is no size to vary.
"""

from __future__ import annotations

import pathlib
import random
import re
import subprocess
import sys
import textwrap
import time
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "ord.md"
EXPECTED_BLOCKS = 8


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


class TestOneCharacter:
    """`ord(c)` on a one-character str gives any code point from 0 to
    0x10FFFF, and on a one-byte bytes or bytearray a value from 0 to 255."""

    def test_every_code_point_round_trips(self) -> None:
        assert all(ord(chr(code)) == code for code in range(0x110000))

    def test_every_byte_round_trips(self) -> None:
        for value in range(256):
            assert ord(bytes([value])) == value
            assert ord(bytearray([value])) == value

    def test_a_str_subclass_is_accepted(self) -> None:
        class Letter(str):
            pass

        assert ord(Letter("a")) == 97


class TestWrongLengthIsRejectedInConstantTime:
    """`ord(s)` with `len(s) != 1` raises TypeError after reading the length,
    so a long string is rejected as fast as a short one."""

    @pytest.mark.parametrize(
        "bad", ["", "ab", b"", bytearray(b"ab")], ids=["empty", "two", "bytes", "bytearray"]
    )
    def test_the_error_names_the_length(self, bad: Any) -> None:
        with pytest.raises(TypeError, match=f"string of length {len(bad)} found"):
            ord(bad)

    @pytest.mark.timing
    def test_a_long_string_fails_as_fast_as_a_short_one(self) -> None:
        short = "ab"
        long = "x" * 10_000_000

        def reject(text: str) -> None:
            try:
                ord(text)
            except TypeError:
                pass
            else:
                raise AssertionError("expected TypeError")

        short_ns = best_ns(lambda: reject(short), inner=1_000)
        long_ns = best_ns(lambda: reject(long), inner=1_000)

        ratio = long_ns / short_ns
        assert ratio < 3, (
            f"rejecting 10,000,000 characters cost x{ratio:.2f} rejecting 2 "
            f"({short_ns:.0f}ns to {long_ns:.0f}ns); counting them predicts x5,000,000"
        )


class TestWrongType:
    """`ord(x)` on any other type raises TypeError, and `__index__` is not
    consulted."""

    @pytest.mark.parametrize(
        "bad", [120, 1.5, memoryview(b"a"), ["a"]], ids=["int", "float", "memoryview", "list"]
    )
    def test_other_types_raise(self, bad: Any) -> None:
        with pytest.raises(TypeError, match=f"but {type(bad).__name__} found"):
            ord(bad)

    def test_index_is_not_called(self) -> None:
        calls = 0

        class Code:
            def __index__(self) -> int:
                nonlocal calls
                calls += 1
                return 97

        with pytest.raises(TypeError):
            ord(Code())  # pyright: ignore[reportArgumentType]
        assert calls == 0


class TestBulkConversionIsLinear:
    """`[ord(c) for c in s]` is O(n): one O(1) call per character."""

    @pytest.mark.timing
    def test_each_tenfold_step_costs_about_tenfold(self) -> None:
        texts = ["abcdéπ中😀" * (size // 8) for size in (10_000, 100_000, 1_000_000)]
        costs = [best_ns(lambda text=text: [ord(c) for c in text], repeats=5) for text in texts]

        for smaller, larger in zip(costs, costs[1:], strict=False):
            ratio = larger / smaller
            assert 3 < ratio < 30, (
                f"10x the characters cost x{ratio:.1f} ({smaller:.0f}ns to {larger:.0f}ns); "
                "linear predicts x10 and quadratic x100"
            )


class TestBytesAreAlreadyInts:
    """Indexing or iterating bytes yields ints, so ord() is not needed and
    `ord(data[i])` raises."""

    def test_indexing_gives_an_int_that_ord_rejects(self) -> None:
        data = b"hello"
        assert data[0] == 104
        with pytest.raises(TypeError, match="but int found"):
            ord(data[0])  # pyright: ignore[reportArgumentType]

    def test_iterating_matches_ord_of_each_slice(self) -> None:
        data = bytes(range(256))
        assert list(data) == [ord(data[i : i + 1]) for i in range(len(data))]


class TestIsasciiReadsAFlag:
    """`str.isascii()` checks a whole string in O(1), where `ord()` on every
    character is O(n)."""

    @pytest.mark.timing
    def test_it_does_not_grow_with_the_string(self) -> None:
        short = "a" * 1_000
        long = "a" * 10_000_000

        short_ns = best_ns(short.isascii, inner=1_000)
        long_ns = best_ns(long.isascii, inner=1_000)

        ratio = long_ns / short_ns
        assert ratio < 3, (
            f"isascii() on 10,000,000 characters cost x{ratio:.2f} its cost on 1,000 "
            f"({short_ns:.0f}ns to {long_ns:.0f}ns); a scan predicts x10,000"
        )
        assert not ("a" * 1_000 + "é").isascii()


class TestSortingByCodePoint:
    """Strings compare by code point, so single characters sort the same with
    and without `key=ord`."""

    def test_key_ord_does_not_change_the_order(self) -> None:
        rng = random.Random(1234)
        chars = [chr(rng.randrange(0x110000)) for _ in range(2_000)]

        assert sorted(chars) == sorted(chars, key=ord)


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
        encoding="utf-8",
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and asserts its own results."""

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
        line, source = next((n, s) for n, s in _blocks() if "ord('😀') == 128512" in s)
        mutated = source.replace("ord('😀') == 128512", "ord('😀') == 128513", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
