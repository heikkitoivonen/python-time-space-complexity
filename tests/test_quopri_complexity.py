"""Tests for docs/stdlib/quopri.md.

The page prices all four functions at O(n) time and space in the input's
length, and says the file functions do not stream. Growth class is settled by
timing over three sizes a decade apart, on three input shapes; space and output
size by traced allocation and output length; the file functions by a recording
file object that shows how the input is read and the output written.

Measurement scope:

* `encodestring()` is timed on 10,000, 100,000 and 1,000,000 input bytes of
  plain text, of bytes that all need escaping, and of seeded random bytes, and
  `decodestring()` on the encodings of those inputs, which are longer by a
  factor that depends on the shape but is about the same at every size. Linear
  predicts 10x per step and quadratic 100x; each step is asserted between 3x
  and 30x.
* The traced peak of `encodestring()` on 1,000,000 bytes that all need
  escaping is asserted over 3x and under 7x the input (about 6.2x on 3.14: a
  working buffer the size of the output, then the returned bytes), and ten
  times the input raises the peak between 5x and 20x. `decodestring()` of the
  encodings of 100,000 and 1,000,000 such bytes peaks under 1.5x its own input,
  and the larger peaks between 5x and 20x the smaller.
* Output growth: 1,000 bytes that all need escaping encode to more than 3x and
  under 3.1x their length. Every encoded line is at most 78 characters,
  checked over 200 seeded random inputs with LF and with CRLF line endings, at
  default flags, with `quotetabs`, with `header` and with both; the inputs
  include lines of 60 to 160 characters ending in spaces and tabs. The wrap is
  decided at 76 and a trailing space or tab escaped after it: 75 `x` then a
  tab encode to a 78-character line. Inputs with LF endings and no carriage
  return anywhere are asserted to decode back to themselves.
  `base64.b64encode()` of 3,000 bytes is 4,000 bytes.
* `header=True` writes `a b` as `a_b`, but as `a=20b` with `quotetabs=True`,
  and a trailing space as `=20` either way.
* `encode()` and `decode()` are observed through recording file objects: one
  `read()` with no size argument, no `readline()`, and exactly one `write()`
  carrying the whole result, on an input of 1,000 lines.
* Encoding 1,000 seeded random lines in line-aligned pieces of 1 to 200 lines
  gives the same bytes as encoding them in one call, with LF endings and with
  CRLF endings; the lines include spaces and tabs before the newline, lone
  dots, `=`, bytes above 126 and lines over 76 characters. With mixed
  endings the two differ, since the first newline in each call decides whether
  every line end is written as CRLF.
* The `quopri` codec is asserted to equal `encodestring(quotetabs=True)` on
  seeded random data, and to escape a space `encodestring()` leaves alone.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The pure-Python fallbacks in Lib/quopri.py run only when `binascii` lacks
  `b2a_qp` and `a2b_qp`, which no CPython build does; they are not measured.
* The flags are varied for output shape and round trips, not for timing.
* `encode()` and `decode()` are observed on `io.BytesIO`-like objects; a file
  whose `read()` returns short reads is not exercised.
"""

from __future__ import annotations

import base64
import codecs
import io
import pathlib
import quopri
import random
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "quopri.md"
EXPECTED_BLOCKS = 5
SIZES = (10_000, 100_000, 1_000_000)


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


def plain_text(size: int) -> bytes:
    return (b"hello world. " * (size // 13 + 1))[:size]


def all_escaped(size: int) -> bytes:
    return bytes([200]) * size


def random_bytes(size: int) -> bytes:
    return random.Random(size).randbytes(size)


SHAPES: dict[str, Callable[[int], bytes]] = {
    "plain text": plain_text,
    "all escaped": all_escaped,
    "random bytes": random_bytes,
}


def random_lines(rng: random.Random, count: int, ending: bytes) -> list[bytes]:
    """Lines mixing the cases the encoder treats specially."""
    pieces = [b"word", b" ", b"\t", b"=", b".", b"\xe9", b"\xff", b"_", b"x" * 90]
    lines: list[bytes] = []
    for _ in range(count):
        kind = rng.random()
        if kind < 0.1:
            body = b"."
        elif kind < 0.2:
            body = b"trailing" + rng.choice([b" ", b"\t", b" \t "])
        elif kind < 0.3:
            body = b"x" * rng.randrange(60, 160) + rng.choice([b" ", b"\t", b"\t "])
        else:
            body = b"".join(rng.choice(pieces) for _ in range(rng.randrange(0, 12)))
        lines.append(body + ending)
    return lines


class RecordingReader(io.BytesIO):
    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.reads: list[tuple[Any, ...]] = []
        self.readline_calls = 0

    def read(self, *args: Any) -> bytes:
        self.reads.append(args)
        return super().read(*args)

    def readline(self, *args: Any) -> bytes:
        self.readline_calls += 1
        return super().readline(*args)


class RecordingWriter:
    def __init__(self) -> None:
        self.writes: list[bytes] = []

    def write(self, data: bytes) -> int:
        self.writes.append(bytes(data))
        return len(data)


@pytest.mark.timing
class TestConversionIsLinear:
    """`encodestring()` and `decodestring()` | O(n) | O(n).

    Three sizes a decade apart: linear predicts 10x per step, quadratic 100x.
    """

    @pytest.mark.parametrize("shape", SHAPES)
    def test_encoding_grows_linearly(self, shape: str) -> None:
        inputs = [SHAPES[shape](size) for size in SIZES]
        times = [best_ns(lambda data=data: quopri.encodestring(data)) for data in inputs]

        steps = [later / earlier for earlier, later in zip(times, times[1:], strict=False)]
        assert all(3 < step < 30 for step in steps), f"{shape}: {times} ns, steps {steps}"

    @pytest.mark.parametrize("shape", SHAPES)
    def test_decoding_grows_linearly(self, shape: str) -> None:
        inputs = [quopri.encodestring(SHAPES[shape](size)) for size in SIZES]
        times = [best_ns(lambda data=data: quopri.decodestring(data)) for data in inputs]

        steps = [later / earlier for earlier, later in zip(times, times[1:], strict=False)]
        assert all(3 < step < 30 for step in steps), f"{shape}: {times} ns, steps {steps}"


class TestSpaceFollowsTheOutput:
    """O(n) space for both directions, on the input shape that grows most."""

    def test_encoding_peak_is_a_multiple_of_the_input(self) -> None:
        small = all_escaped(100_000)
        large = all_escaped(1_000_000)

        small_peak = peak_bytes(lambda: quopri.encodestring(small))
        large_peak = peak_bytes(lambda: quopri.encodestring(large))

        assert 3 * len(large) < large_peak < 7 * len(large), large_peak
        assert 5 < large_peak / small_peak < 20, (small_peak, large_peak)

    def test_decoding_peak_is_linear_and_under_its_input_and_a_half(self) -> None:
        small = quopri.encodestring(all_escaped(100_000))
        large = quopri.encodestring(all_escaped(1_000_000))

        small_peak = peak_bytes(lambda: quopri.decodestring(small))
        large_peak = peak_bytes(lambda: quopri.decodestring(large))

        assert small_peak < 1.5 * len(small), (small_peak, len(small))
        assert large_peak < 1.5 * len(large), (large_peak, len(large))
        assert 5 < large_peak / small_peak < 20, (small_peak, large_peak)


class TestFlags:
    """`header` writes an embedded space as `_` when `quotetabs` is off."""

    def test_header_writes_a_space_as_an_underscore(self) -> None:
        assert quopri.encodestring(b"a b", header=True) == b"a_b"

    def test_quotetabs_overrides_it(self) -> None:
        assert quopri.encodestring(b"a b", header=True, quotetabs=True) == b"a=20b"

    @pytest.mark.parametrize("quotetabs", [False, True])
    def test_a_trailing_space_is_escaped_either_way(self, quotetabs: bool) -> None:
        assert quopri.encodestring(b"a ", header=True, quotetabs=quotetabs) == b"a=20"


class TestOutputGrowth:
    """An escaped byte becomes three, so the output is up to about three times
    n, and encoded lines stay short however long the input line is."""

    def test_escaping_everything_triples_the_input(self) -> None:
        data = all_escaped(1_000)

        encoded = quopri.encodestring(data)

        assert 3 * len(data) < len(encoded) < 3.1 * len(data), len(encoded)

    @pytest.mark.parametrize("ending", [b"\n", b"\r\n"])
    @pytest.mark.parametrize(
        "flags",
        [{}, {"quotetabs": True}, {"header": True}, {"quotetabs": True, "header": True}],
        ids=["default", "quotetabs", "header", "both"],
    )
    def test_no_encoded_line_exceeds_78_characters(
        self, ending: bytes, flags: dict[str, bool]
    ) -> None:
        rng = random.Random(76)
        for _ in range(200):
            data = b"".join(random_lines(rng, rng.randrange(1, 20), ending))
            data += rng.randbytes(rng.randrange(0, 300))

            encoded = quopri.encodestring(data, **flags)

            longest = max(len(line.rstrip(b"\r")) for line in encoded.split(b"\n"))
            assert longest <= 78, (data, encoded)
            decoded = quopri.decodestring(encoded, header=flags.get("header", False))
            if ending == b"\n" and b"\r" not in data:
                assert decoded == data

    def test_a_trailing_tab_after_the_wrap_reaches_78(self) -> None:
        encoded = quopri.encodestring(b"x" * 75 + b"\t\n")

        assert encoded == b"x" * 75 + b"=09\n"

    def test_base64_adds_a_third(self) -> None:
        assert len(base64.b64encode(bytes(3_000))) == 4_000


class TestFileFunctionsDoNotStream:
    """`encode()` and `decode()` read all of `input`, then make one
    `output.write()`."""

    DATA = b"".join(b"line %d with caf\xc3\xa9 \n" % index for index in range(1_000))

    def test_encode_reads_everything_then_writes_once(self) -> None:
        source = RecordingReader(self.DATA)
        target = RecordingWriter()

        quopri.encode(source, target, quotetabs=False)

        assert source.reads == [()], source.reads
        assert source.readline_calls == 0
        assert target.writes == [quopri.encodestring(self.DATA)]

    def test_decode_reads_everything_then_writes_once(self) -> None:
        encoded = quopri.encodestring(self.DATA)
        source = RecordingReader(encoded)
        target = RecordingWriter()

        quopri.decode(source, target)

        assert source.reads == [()], source.reads
        assert source.readline_calls == 0
        assert target.writes == [self.DATA]


class TestPiecesEncodeIndependently:
    """In a file with one line-ending style, pieces that end on a newline
    encode independently; with mixed endings they do not."""

    @staticmethod
    def _in_pieces(lines: list[bytes], rng: random.Random) -> bytes:
        out: list[bytes] = []
        index = 0
        while index < len(lines):
            step = rng.randrange(1, 201)
            out.append(quopri.encodestring(b"".join(lines[index : index + step])))
            index += step
        return b"".join(out)

    @pytest.mark.parametrize("ending", [b"\n", b"\r\n"], ids=["LF", "CRLF"])
    def test_line_aligned_pieces_match_one_call(self, ending: bytes) -> None:
        rng = random.Random(1_000)
        for _ in range(20):
            lines = random_lines(rng, 1_000, ending)

            assert self._in_pieces(lines, rng) == quopri.encodestring(b"".join(lines))

    def test_mixed_line_endings_break_it(self) -> None:
        whole = b"a\r\nb\nc\n"

        in_pieces = quopri.encodestring(b"a\r\n") + quopri.encodestring(b"b\nc\n")

        assert quopri.encodestring(whole) == b"a\r\nb\r\nc\r\n"
        assert in_pieces != quopri.encodestring(whole)


class TestTheCodecQuotesTabs:
    """The `quopri` codec encodes as `encodestring(quotetabs=True)` does."""

    def test_codec_matches_encodestring_with_quotetabs(self) -> None:
        rng = random.Random(3)
        for _ in range(50):
            data = b"".join(random_lines(rng, 20, b"\n"))

            assert codecs.encode(data, "quopri") == quopri.encodestring(data, quotetabs=True)
            assert codecs.decode(codecs.encode(data, "quopri"), "quopri") == data

    def test_codec_escapes_a_space_encodestring_leaves(self) -> None:
        assert quopri.encodestring(b"a b") == b"a b"
        assert codecs.encode(b"a b", "quopri") == b"a=20b"


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
        line, source = next((n, s) for n, s in _blocks() if "== 3 * len(binary)" in s)
        mutated = source.replace("== 3 * len(binary)", "== 2 * len(binary)", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
