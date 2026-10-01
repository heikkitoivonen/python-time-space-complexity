"""Tests for docs/stdlib/binascii.md.

The page prices every function in the input length n: each encoder and decoder
is linear and produces output at most a fixed multiple of n long, the two
checksums return an int in constant space, and `a2b_uu()` decodes one line
into at most 63 bytes however long the line is. Space is settled by traced
allocation, which separates an output-sized peak from a constant one by orders
of magnitude; time by a three-size timing test; the notes by direct
observation of outputs and exceptions.

Measurement scope:

* Space: every encoder and decoder except the uuencode pair, with the four
  HQX functions included on 3.10, is a `tracemalloc` peak at inputs of 200,000 and
  2,000,000 bytes; the larger peaks more than 5x the smaller, and each peak
  is at least the length of the result and under twice the input plus result
  plus 10,000 bytes, which excludes super-linear growth. `crc32()`,
  `crc_hqx()` and `a2b_uu()` (one encoded line followed by 2,000,000 spaces)
  peak under 1,000 bytes at 2,000,000 bytes of input. Each call is warmed
  once before it is measured; the tests are `serial`, so no xdist thread
  allocates inside the measurement.
* Time: the same operations at 50,000, 500,000 and 5,000,000 bytes, fastest
  of seven runs; each 10x step must cost between 3x and 30x, which excludes a
  constant cost (x1) and a quadratic one (x100). `b2a_uu()` is not measured
  for space or time: its input is capped at 45 bytes, and its output length
  is asserted exactly instead. `hexlify()`, `b2a_base64()` and `a2b_uu()` are
  `builtin_function_or_method` objects, the C implementation the
  introduction names.
* `hexlify()` and `b2a_hex()` give the same output, two digits per byte and
  one separator per `bytes_per_sep` bytes from the right (from the left when
  negative); `unhexlify()` and `a2b_hex()` give the same output, accept an
  ASCII `str`, and raise `binascii.Error` on an odd length and on a non-hex
  digit.
* `b2a_base64()` output is 4·ceil(n/3) characters plus one `\\n`, one line
  at 300,000 bytes, and has no `\\n` with `newline=False`. `a2b_base64()`
  skips a `!` and a newline inside the data; with `strict_mode=True` (3.11+)
  the same input raises `binascii.Error`. Joining encodings of 1,000-byte
  chunks differs from the encoding of the whole; 999-byte chunks match it.
* `b2a_qp()` of 30,000 bytes of 0xFF is lines of 76 characters or fewer, each
  byte escaped as three characters; `a2b_qp()` round-trips it and, with
  `header=True`, decodes `_` as a space.
* `b2a_uu()` output is 2 + 4·ceil(n/3) bytes for every n from 0 to 45, and 46
  bytes raise `binascii.Error`. `a2b_uu()` of a lone length character `_`
  returns 63 bytes; spaces, backticks and line endings after the data are
  accepted and other characters raise "Trailing garbage".
* `crc32()` over 4,096-byte chunks, each fed the previous result, equals
  `crc32()` of the whole and `zlib.crc32()`, and lies in [0, 2**32);
  `crc_hqx()` chains the same way, lies in [0, 2**16), and rejects a call
  without `value`. The check value for b"123456789" is 0xCBF43926 for CRC-32
  and 0x31C3 for `crc_hqx()` from 0 (CRC-CCITT, the XMODEM variant), 0x29B1
  from 0xFFFF.
* `binascii.Error` is a `ValueError` subclass.
* The HQX rows are guarded on `sys.version_info < (3, 11)`; their presence,
  and the `binhex` module's, is asserted to match it on every version. On 3.10 each warns
  `DeprecationWarning`; `a2b_hqx()` returns `(data, 0)` without the
  terminating `:` and `(data, 1)` with it, and raises `binascii.Incomplete`
  when a trailing character is cut; `rlecode_hqx()` leaves a run of three
  alone, codes a run of four as three bytes, splits a run of 300 into codes of
  at most 255, and escapes each 0x90 as two bytes, a run of five included; `rledecode_hqx()` expands 1,000 three-byte
  codes into 255,000 bytes and raises `binascii.Incomplete` on a cut code.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail with an `AssertionError`.

Not settled here:

* That nothing raises `binascii.Incomplete` on 3.11+ is read from
  Modules/binascii.c, v3.11.14 to v3.14.2: the module creates the exception
  and nothing sets it.
* The O(1) rows for `binascii.Error` and `binascii.Incomplete` are
  definitional: naming an exception class is an attribute lookup.
* The Related Modules descriptions summarise the linked pages, whose own
  tests carry those claims.
* Inputs are bytes: for the ASCII decoders, what their encoders produce, and
  for `rledecode_hqx()` codes that each expand to four bytes;
  `str` arguments, other buffer types, and malformed input beyond the cases
  named above are not varied in size. The timing ratios are local evidence
  of the growth class only; CI re-runs them on every supported version.
"""

from __future__ import annotations

import binascii
import importlib.util
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import warnings
import zlib
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "binascii.md"
EXPECTED_BLOCKS = 6

HQX_FUNCTIONS = ("a2b_hqx", "b2a_hqx", "rlecode_hqx", "rledecode_hqx")


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


def payload(size: int) -> bytes:
    """`size` bytes cycling through every byte value."""
    return (bytes(range(256)) * (size // 256 + 1))[:size]


def uu_line_padded(size: int) -> bytes:
    """One 45-byte uuencoded line followed by `size` spaces."""
    return binascii.b2a_uu(b"x" * 45).rstrip(b"\n") + b" " * size


# name -> (operation, input of roughly the given size)
LINEAR_OUTPUT: dict[str, tuple[Callable[[bytes], Any], Callable[[int], bytes]]] = {
    "hexlify": (binascii.hexlify, payload),
    "hexlify with sep": (lambda data: binascii.hexlify(data, "-", 2), payload),
    "b2a_hex": (binascii.b2a_hex, payload),
    "unhexlify": (binascii.unhexlify, lambda n: binascii.hexlify(payload(n // 2))),
    "a2b_hex": (binascii.a2b_hex, lambda n: binascii.hexlify(payload(n // 2))),
    "b2a_base64": (binascii.b2a_base64, payload),
    "a2b_base64": (binascii.a2b_base64, lambda n: binascii.b2a_base64(payload(n * 3 // 4))),
    "b2a_qp": (binascii.b2a_qp, payload),
    "a2b_qp": (binascii.a2b_qp, lambda n: binascii.b2a_qp(payload(n // 3))),
}

if sys.version_info < (3, 11):

    def _quiet(name: str) -> Callable[[bytes], Any]:
        def call(data: bytes) -> Any:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                return getattr(binascii, name)(data)

        return call

    LINEAR_OUTPUT.update(
        {
            "b2a_hqx": (_quiet("b2a_hqx"), payload),
            "a2b_hqx": (
                lambda data: _quiet("a2b_hqx")(data)[0],
                lambda n: _quiet("b2a_hqx")(payload(n * 3 // 4 // 3 * 3)),
            ),
            "rlecode_hqx": (_quiet("rlecode_hqx"), payload),
            "rledecode_hqx": (_quiet("rledecode_hqx"), lambda n: b"a\x90\x04" * (n // 3)),
        }
    )

CONSTANT_SPACE: dict[str, tuple[Callable[[bytes], Any], Callable[[int], bytes]]] = {
    "crc32": (binascii.crc32, payload),
    "crc_hqx": (lambda data: binascii.crc_hqx(data, 0), payload),
    "a2b_uu": (binascii.a2b_uu, uu_line_padded),
}


@pytest.mark.serial
class TestOutputSpaceIsLinear:
    """Every encoder and decoder row: O(n) space, the result itself."""

    @pytest.mark.parametrize("name", list(LINEAR_OUTPUT))
    def test_the_peak_grows_with_the_input(self, name: str) -> None:
        operation, make = LINEAR_OUTPUT[name]
        peaks = []
        for size in (200_000, 2_000_000):
            data = make(size)
            result = operation(data)  # warm
            peak = peak_bytes(lambda d=data: operation(d))  # type: ignore[misc]
            assert peak >= len(result), f"{name}: peak {peak} under a {len(result)}-byte result"
            ceiling = 2 * (len(data) + len(result)) + 10_000
            assert peak < ceiling, f"{name}: peak {peak} over {ceiling} for {len(data)} bytes"
            peaks.append(peak)

        assert peaks[1] > peaks[0] * 5, f"{name}: 10x the input peaked at {peaks}"


@pytest.mark.serial
class TestChecksumsAndUuDecodeUseConstantSpace:
    """`crc32`, `crc_hqx` | O(1) space; `a2b_uu` | O(1) space, at most 63 bytes."""

    @pytest.mark.parametrize("name", list(CONSTANT_SPACE))
    def test_the_peak_does_not_follow_the_input(self, name: str) -> None:
        operation, make = CONSTANT_SPACE[name]
        data = make(2_000_000)
        operation(data)  # warm

        peak = peak_bytes(lambda: operation(data))

        assert peak < 1_000, f"{name}: {peak} bytes for a {len(data)}-byte input"


class TestEveryOperationIsLinearInTime:
    """Every row's O(n) time: three sizes in 10x steps, each step x3 to x30."""

    SIZES = (50_000, 500_000, 5_000_000)

    @pytest.mark.timing
    @pytest.mark.parametrize("name", [*LINEAR_OUTPUT, *CONSTANT_SPACE])
    def test_ten_times_the_input_costs_about_ten_times(self, name: str) -> None:
        operation, make = {**LINEAR_OUTPUT, **CONSTANT_SPACE}[name]
        durations = []
        for size in self.SIZES:
            data = make(size)
            operation(data)
            durations.append(best_ns(lambda d=data: operation(d), inner=3))  # type: ignore[misc]

        ratios = [durations[i + 1] / durations[i] for i in range(len(durations) - 1)]
        assert all(3 < ratio < 30 for ratio in ratios), (
            f"{name}: {durations} ns at {self.SIZES} bytes, step ratios {ratios}; "
            "linear gives x10, quadratic x100"
        )


class TestHex:
    """Hex rows: two digits per byte plus separators; the `a2b` side halves it
    and rejects odd lengths and non-hex digits."""

    def test_two_digits_per_byte(self) -> None:
        data = payload(1_000)

        assert binascii.hexlify(data) == data.hex().encode()
        assert binascii.b2a_hex(data) == binascii.hexlify(data)

    def test_separators_are_counted_from_the_right_or_left(self) -> None:
        data = b"\x01\x02\x03\x04\x05"

        assert binascii.hexlify(data, "-", 2) == b"01-0203-0405"
        assert binascii.hexlify(data, b":", -2) == b"0102:0304:05"
        assert binascii.b2a_hex(data, "-") == b"01-02-03-04-05"
        assert len(binascii.hexlify(payload(1_000), "-", 2)) == 2_000 + 499

    def test_decoding_halves_the_length_and_accepts_str(self) -> None:
        assert binascii.unhexlify(b"0102ff") == b"\x01\x02\xff"
        assert binascii.a2b_hex("0A0b") == b"\n\x0b"
        assert binascii.unhexlify("0A0b") == binascii.a2b_hex("0A0b")

    def test_odd_lengths_and_non_hex_digits_raise(self) -> None:
        with pytest.raises(binascii.Error, match="Odd-length"):
            binascii.unhexlify(b"abc")
        with pytest.raises(binascii.Error, match="Non-hexadecimal"):
            binascii.a2b_hex(b"zz")


class TestBase64:
    """`b2a_base64` writes one line of 4·ceil(n/3) characters; `a2b_base64`
    skips what is not base64 unless `strict_mode` is set."""

    @pytest.mark.parametrize("size", [0, 1, 2, 3, 299_999, 300_000])
    def test_four_characters_per_three_bytes_on_one_line(self, size: int) -> None:
        encoded = binascii.b2a_base64(payload(size))

        assert len(encoded) == 4 * -(-size // 3) + 1
        assert encoded.count(b"\n") == 1 and encoded.endswith(b"\n")

    def test_newline_false_drops_the_newline(self) -> None:
        assert binascii.b2a_base64(b"abc", newline=False) == b"YWJj"

    def test_non_alphabet_characters_are_skipped(self) -> None:
        assert binascii.a2b_base64(b"YW!J\nj") == b"abc"
        assert binascii.a2b_base64("YWJj") == b"abc"

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="strict_mode was added in 3.11")
    def test_strict_mode_rejects_them(self) -> None:
        with pytest.raises(binascii.Error, match="Only base64 data"):
            binascii.a2b_base64(b"YW!Jj", strict_mode=True)  # type: ignore[call-arg]

    def test_chunks_must_be_a_multiple_of_three_bytes(self) -> None:
        data = payload(100_000)
        whole = binascii.b2a_base64(data, newline=False)

        def chunked(step: int) -> bytes:
            pieces = (data[i : i + step] for i in range(0, len(data), step))
            return b"".join(binascii.b2a_base64(piece, newline=False) for piece in pieces)

        assert chunked(999) == whole
        assert chunked(1_000) != whole


class TestQuotedPrintable:
    """`b2a_qp`: three characters per escaped byte, lines of at most 76;
    `a2b_qp` reverses it, and `header=True` decodes `_`."""

    def test_escaped_bytes_and_soft_line_breaks(self) -> None:
        data = b"\xff" * 30_000

        encoded = binascii.b2a_qp(data)

        lines = encoded.split(b"\n")
        assert max(len(line) for line in lines) <= 76
        assert b"".join(line.removesuffix(b"=") for line in lines) == b"=FF" * 30_000
        assert binascii.a2b_qp(encoded) == data

    def test_header_mode_decodes_underscores(self) -> None:
        assert binascii.a2b_qp(b"Hello_World", header=True) == b"Hello World"
        assert binascii.a2b_qp(b"Hello_World") == b"Hello_World"


class TestUuencode:
    """`b2a_uu` encodes one line of at most 45 bytes; `a2b_uu` decodes one line
    into at most 63 bytes set by its length character."""

    @pytest.mark.parametrize("size", range(46))
    def test_one_line_of_up_to_45_bytes(self, size: int) -> None:
        encoded = binascii.b2a_uu(payload(size))

        assert len(encoded) == 2 + 4 * -(-size // 3)
        assert binascii.a2b_uu(encoded) == payload(size)

    def test_46_bytes_raise(self) -> None:
        with pytest.raises(binascii.Error, match="45 bytes"):
            binascii.b2a_uu(b"x" * 46)

    def test_the_length_character_fixes_the_output(self) -> None:
        assert binascii.a2b_uu(b"_") == b"\x00" * 63

    def test_only_padding_or_a_line_ending_may_follow(self) -> None:
        line = binascii.b2a_uu(b"hi").rstrip(b"\n")

        assert binascii.a2b_uu(line + b"  ``\r\n") == b"hi"
        with pytest.raises(binascii.Error, match="Trailing garbage"):
            binascii.a2b_uu(line + b"xyz")


class TestChecksums:
    """`crc32` and `crc_hqx` take the previous result, so chunks chain."""

    DATA = payload(100_000)

    def test_crc32_chains_over_chunks(self) -> None:
        running = 0
        for start in range(0, len(self.DATA), 4_096):
            running = binascii.crc32(self.DATA[start : start + 4_096], running)

        assert running == binascii.crc32(self.DATA) == zlib.crc32(self.DATA)
        assert 0 <= running < 2**32

    def test_crc_hqx_chains_and_needs_a_value(self) -> None:
        running = 0
        for start in range(0, len(self.DATA), 4_096):
            running = binascii.crc_hqx(self.DATA[start : start + 4_096], running)

        assert running == binascii.crc_hqx(self.DATA, 0)
        assert 0 <= running < 2**16
        with pytest.raises(TypeError):
            binascii.crc_hqx(self.DATA)  # type: ignore[call-arg]

    def test_check_values(self) -> None:
        assert binascii.crc32(b"123456789") == 0xCBF43926
        assert binascii.crc_hqx(b"123456789", 0) == 0x31C3
        assert binascii.crc_hqx(b"123456789", 0xFFFF) == 0x29B1

    def test_the_functions_are_c(self) -> None:
        for function in (binascii.hexlify, binascii.b2a_base64, binascii.a2b_uu):
            assert type(function).__name__ == "builtin_function_or_method"

    def test_error_is_a_value_error(self) -> None:
        assert issubclass(binascii.Error, ValueError)


class TestHqxFunctionsExistOnlyOn310:
    """BinHex rows: Python 3.10 only, deprecated there."""

    def test_availability_matches_the_version(self) -> None:
        for name in HQX_FUNCTIONS:
            assert hasattr(binascii, name) == (sys.version_info < (3, 11)), name
        has_binhex = importlib.util.find_spec("binhex") is not None
        assert has_binhex == (sys.version_info < (3, 11))

    @pytest.fixture
    def hqx(self) -> Any:
        if sys.version_info >= (3, 11):
            pytest.skip("version: the HQX functions were removed in Python 3.11")
        return binascii

    @pytest.mark.parametrize("name", HQX_FUNCTIONS)
    def test_each_warns(self, hqx: Any, name: str) -> None:
        with pytest.warns(DeprecationWarning, match=name):
            try:
                getattr(hqx, name)(b"abc")
            except (hqx.Error, hqx.Incomplete):
                pass

    def test_a2b_hqx_reports_whether_it_reached_the_colon(self, hqx: Any) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            encoded = hqx.b2a_hqx(b"hello world!")

            assert hqx.a2b_hqx(encoded) == (b"hello world!", 0)
            assert hqx.a2b_hqx(encoded + b":") == (b"hello world!", 1)
            with pytest.raises(hqx.Incomplete):
                hqx.a2b_hqx(encoded[:-1])

    def test_rlecode_codes_runs_of_four_or_more(self, hqx: Any) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)

            assert hqx.rlecode_hqx(b"aaab") == b"aaab"
            assert hqx.rlecode_hqx(b"aaaab") == b"a\x90\x04b"
            assert hqx.rlecode_hqx(b"a" * 300) == b"a\x90\xffa\x90\x2d"
            assert hqx.rlecode_hqx(b"\x90") == b"\x90\x00"
            assert hqx.rlecode_hqx(b"\x90" * 5) == b"\x90\x00" * 5

    def test_rledecode_expands_each_code_up_to_255_bytes(self, hqx: Any) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)

            assert hqx.rledecode_hqx(b"a\x90\xff" * 1_000) == b"a" * 255_000
            with pytest.raises(hqx.Incomplete):
                hqx.rledecode_hqx(b"a\x90")


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
        line, source = next((n, s) for n, s in _blocks() if "assert running == whole" in s)
        mutated = source.replace("assert running == whole", "assert running != whole", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
