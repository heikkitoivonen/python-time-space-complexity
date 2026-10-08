"""Tests for docs/stdlib/base64.md.

The page prices every encoder and decoder as linear in its input, returning a
new `bytes` object, so each costs O(n) time and O(n) space; the legacy file
functions hold one line of working memory. Space is settled by traced allocation, which separates
O(n) from O(1) by orders of magnitude with no tolerance to choose; time is
settled by ratios over input sizes a decade apart; behaviour by observation.

Measurement scope:

* Every encoder and decoder on the page has a traced peak between 30x and
  300x larger for a 1,000,000-byte input than for a 10,000-byte one, which
  excludes a constant and a quadratic, and an encoded length within 10 of the
  encoding's ratio times a 30,000-byte input. Inputs are random bytes;
  decoders are given that data encoded. Ascii85 is asserted to write an
  all-zero group as one `z`.
* In a timing test each of those functions is run on 3,000, 30,000 and
  300,000 bytes; each 10x step costs between 4x and 30x, which excludes a
  constant (x1) and a quadratic (x100) at every interval.
* That Base32 and the 85 family loop in Python while Base64 runs in C is
  settled by a timing test on 300,000 random bytes: each of their encoders and
  decoders costs more than 5x `b64encode()` or `b64decode()` on the same data.
  Base16's encoder is held under 5x Base64's, and its decoder under 5x from
  3.14 and under 25x before, where it adds a `re.search()` validation pass.
* `encode()` peaks under 4 KB and within 2x across 10,000 and 1,000,000 input
  bytes, and writes lines of at most 76 characters, identical to
  `encodebytes()`. `decode()` peaks under 4 KB on `encodebytes()` output of
  both sizes and above the input length when the same data is one line.
  `main()` is run in-process on a 10,000-byte and a 1,000,000-byte file, with
  `-d` on their encoded forms, with stdout replaced by a counting sink; its
  peak stays under 512 KB, below the 1,000,000-byte file, and within 2x across
  the two sizes. The open file's buffer is most of that peak.
* `b64decode()` is asserted to discard a space by default, to raise
  `binascii.Error` for it with `validate=True`, and to raise for missing
  padding either way. The decoders except `decodebytes()` are asserted to
  accept an ASCII `str`, and every encoder to refuse one. `b16decode()` is
  asserted to reject lowercase unless `casefold=True`.
* Joining `b64encode()` over 4-byte chunks is asserted to put `=` before the
  end, which `validate=True` rejects.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* That Base64, Base16 and the legacy functions reach `binascii` is read from
  Lib/base64.py; the tests measure the speed gap it produces, not the call.
* `main()` reads a terminal on stdin whole before encoding it on 3.13.10+ and
  3.14.1+; the page prices only file and pipe input, and that path is not run.
* `altchars`, `casefold`, `map01`, `foldspaces`, `wrapcol`, `pad`, `adobe` and
  `validate=True` are checked for behaviour on one short input each; none is
  varied in size.
  Input content is random bytes throughout, so all-zero and all-space input,
  which Ascii85 folds to one character per group, is not measured.
* `z85encode()` and `z85decode()` exist from 3.13; their tests skip before it.
"""

from __future__ import annotations

import base64
import binascii
import io
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from itertools import pairwise
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "base64.md"
EXPECTED_BLOCKS = 7

HAS_Z85 = sys.version_info >= (3, 13)
Z85 = pytest.mark.skipif(not HAS_Z85, reason="z85 was added in 3.13")

# (encoder, decoder, encoded characters per input byte)
PAIRS: list[Any] = [
    pytest.param("b64encode", "b64decode", 4 / 3, id="b64"),
    pytest.param("standard_b64encode", "standard_b64decode", 4 / 3, id="standard_b64"),
    pytest.param("urlsafe_b64encode", "urlsafe_b64decode", 4 / 3, id="urlsafe_b64"),
    pytest.param("b32encode", "b32decode", 8 / 5, id="b32"),
    pytest.param("b32hexencode", "b32hexdecode", 8 / 5, id="b32hex"),
    pytest.param("b16encode", "b16decode", 2, id="b16"),
    pytest.param("a85encode", "a85decode", 5 / 4, id="a85"),
    pytest.param("b85encode", "b85decode", 5 / 4, id="b85"),
    pytest.param("z85encode", "z85decode", 5 / 4, id="z85", marks=Z85),
    pytest.param("encodebytes", "decodebytes", 4 / 3 * 77 / 76, id="encodebytes"),
]

SLOW = ["b32", "b32hex", "a85", "b85"] + (["z85"] if HAS_Z85 else [])
DECODERS_TAKING_STR = [
    "b64decode",
    "standard_b64decode",
    "urlsafe_b64decode",
    "b32decode",
    "b32hexdecode",
    "b16decode",
    "a85decode",
    "b85decode",
] + (["z85decode"] if HAS_Z85 else [])
ENCODERS = [
    "b64encode",
    "standard_b64encode",
    "urlsafe_b64encode",
    "b32encode",
    "b32hexencode",
    "b16encode",
    "a85encode",
    "b85encode",
    "encodebytes",
] + (["z85encode"] if HAS_Z85 else [])


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


def coder(name: str) -> Callable[[Any], bytes]:
    return getattr(base64, name)


class CountingSink:
    """A binary file-like object that keeps only a running byte count."""

    def __init__(self) -> None:
        self.written = 0

    def write(self, data: bytes) -> int:
        self.written += len(data)
        return len(data)


class TestEveryFunctionIsLinear:
    """Every encoder and decoder row: O(n) time, O(n) space, and an output that
    is a fixed multiple of the input."""

    @pytest.mark.parametrize(("encoder", "decoder", "ratio"), PAIRS)
    def test_round_trip_and_output_length(self, encoder: str, decoder: str, ratio: float) -> None:
        data = os.urandom(30_000)

        encoded = coder(encoder)(data)

        assert abs(len(encoded) - len(data) * ratio) < 10
        assert coder(decoder)(encoded) == data

    @pytest.mark.parametrize(("encoder", "decoder", "ratio"), PAIRS)
    def test_the_peak_follows_the_input(self, encoder: str, decoder: str, ratio: float) -> None:
        del ratio
        for name in (encoder, decoder):
            peaks = []
            for size in (10_000, 1_000_000):
                data = os.urandom(size)
                subject = data if name == encoder else coder(encoder)(data)
                coder(name)(subject)  # build lazy tables outside the measurement
                peaks.append(peak_bytes(lambda n=name, s=subject: coder(n)(s)))  # type: ignore[misc]

            assert peaks[0] * 30 < peaks[1] < peaks[0] * 300, (
                f"{name}: 100x the input peaked at {peaks}"
            )

    @pytest.mark.timing
    @pytest.mark.parametrize(("encoder", "decoder", "ratio"), PAIRS)
    def test_each_tenfold_step_costs_about_tenfold(
        self, encoder: str, decoder: str, ratio: float
    ) -> None:
        del ratio
        for name in (encoder, decoder):
            durations = []
            for size in (3_000, 30_000, 300_000):
                data = os.urandom(size)
                subject = data if name == encoder else coder(encoder)(data)
                function = coder(name)
                function(subject)
                inner = max(1, 300_000 // size)
                durations.append(best_ns(lambda f=function, s=subject: f(s), inner=inner))  # type: ignore[misc]

            steps = [later / earlier for earlier, later in pairwise(durations)]
            assert all(4 < step < 30 for step in steps), (
                f"{name}: 3,000 / 30,000 / 300,000 bytes took {durations} ns, steps {steps}"
            )


class TestPythonLoopsAreSlowerThanBinascii:
    """Base32 and the 85 family loop over groups in Python; Base64 and Base16
    run in C. Same O(n), a wide gap per byte."""

    DATA = os.urandom(300_000)

    @staticmethod
    def _ns(name: str, subject: bytes) -> float:
        function = coder(name)
        function(subject)
        return best_ns(lambda: function(subject), repeats=5)

    @pytest.mark.timing
    @pytest.mark.parametrize("family", SLOW)
    def test_the_python_loops_cost_more_than_five_times_base64(self, family: str) -> None:
        encoded = coder(f"{family}encode")(self.DATA)
        b64_encoded = base64.b64encode(self.DATA)

        encode_ratio = self._ns(f"{family}encode", self.DATA) / self._ns("b64encode", self.DATA)
        decode_ratio = self._ns(f"{family}decode", encoded) / self._ns("b64decode", b64_encoded)

        assert encode_ratio > 5, f"{family}encode is only x{encode_ratio:.1f} b64encode"
        assert decode_ratio > 5, f"{family}decode is only x{decode_ratio:.1f} b64decode"

    @pytest.mark.timing
    def test_base16_stays_close_to_base64(self) -> None:
        """Before 3.14, `b16decode()` validates with `re.search()` before
        `unhexlify()`: a second C pass, measured at x6.5-x12.3 `b64decode()`
        on 3.10-3.13, where the Python-loop decoders measured x35 and up."""
        encoded = base64.b16encode(self.DATA)
        b64_encoded = base64.b64encode(self.DATA)
        decode_bound = 5 if sys.version_info >= (3, 14) else 25

        encode_ratio = self._ns("b16encode", self.DATA) / self._ns("b64encode", self.DATA)
        decode_ratio = self._ns("b16decode", encoded) / self._ns("b64decode", b64_encoded)

        assert encode_ratio < 5, f"b16encode is x{encode_ratio:.1f} b64encode"
        assert decode_ratio < decode_bound, f"b16decode is x{decode_ratio:.1f} b64decode"


class TestInputTypes:
    """Encoders take bytes-like objects; the decoders except `decodebytes()`
    also take an ASCII `str`."""

    @pytest.mark.parametrize("name", DECODERS_TAKING_STR)
    def test_decoders_accept_an_ascii_str(self, name: str) -> None:
        encoded = coder(name.replace("decode", "encode"))(b"Hello, World!")

        assert coder(name)(encoded.decode("ascii")) == b"Hello, World!"

    def test_decodebytes_refuses_a_str(self) -> None:
        with pytest.raises(TypeError, match="bytes-like"):
            base64.decodebytes("SGVsbG8=")  # type: ignore[arg-type]

    @pytest.mark.parametrize("name", ENCODERS)
    def test_encoders_refuse_a_str(self, name: str) -> None:
        with pytest.raises(TypeError):
            coder(name)("Hello")

    @pytest.mark.parametrize("name", ENCODERS)
    def test_encoders_take_any_bytes_like_object(self, name: str) -> None:
        assert coder(name)(memoryview(b"Hello")) == coder(name)(b"Hello")


class TestDecodingIsLenientByDefault:
    """`b64decode()` discards characters outside the alphabet unless
    `validate=True`, and never repairs missing padding."""

    def test_a_space_is_discarded(self) -> None:
        assert base64.b64decode(b"SGVs bG8=") == b"Hello"

    def test_validate_rejects_it(self) -> None:
        with pytest.raises(binascii.Error):
            base64.b64decode(b"SGVs bG8=", validate=True)

    @pytest.mark.parametrize("validate", [False, True])
    def test_missing_padding_raises(self, validate: bool) -> None:
        with pytest.raises(binascii.Error):
            base64.b64decode(b"SGVsbG8", validate=validate)

    def test_altchars_and_the_urlsafe_alphabet(self) -> None:
        data = b"\xfb\xff"

        assert base64.b64encode(data) == b"+/8="
        assert base64.b64encode(data, altchars=b"-_") == base64.urlsafe_b64encode(data) == b"-_8="
        assert base64.b64decode(b"-_8=", altchars=b"-_") == data

    def test_b16decode_needs_casefold_for_lowercase(self) -> None:
        with pytest.raises(binascii.Error):
            base64.b16decode(b"48656c6c6f")

        assert base64.b16decode(b"48656c6c6f", casefold=True) == b"Hello"

    def test_b32decode_map01_reads_the_digits_as_letters(self) -> None:
        assert base64.b32decode(b"0L======", map01=b"L") == base64.b32decode(b"OL======")

    def test_ascii85_options(self) -> None:
        assert base64.a85encode(b"\0" * 8) == b"zz"
        assert base64.a85encode(b"    ", foldspaces=True) == b"y"
        assert base64.a85decode(b"y", foldspaces=True) == b"    "
        assert base64.a85encode(b"x" * 20, wrapcol=10).split(b"\n") == [b"G^+IXG^+IX"] * 2 + [
            b"G^+IX"
        ]
        assert base64.a85encode(b"x") == b"GQ"
        assert base64.a85encode(b"x", pad=True) == b"GQ7^D"
        assert base64.a85encode(b"Hello", adobe=True) == b"<~87cURDZ~>"
        assert base64.a85decode(b"<~87cURDZ~>", adobe=True) == b"Hello"

    def test_joined_chunks_put_padding_in_the_middle(self) -> None:
        joined = b"".join(base64.b64encode(b"x" * 4) for _ in range(2))

        assert b"=" in joined[:-2], joined
        with pytest.raises(binascii.Error):
            base64.b64decode(joined, validate=True)


class TestLegacyFunctionsHoldOneLine:
    """`encode()` | O(n) | O(1), `decode()` | O(n) | O(L), and `main()` streams
    through them from a file."""

    @staticmethod
    def _encode_peak(size: int) -> int:
        source = io.BytesIO(os.urandom(size))
        return peak_bytes(lambda: base64.encode(source, CountingSink()))

    def test_encode_peak_does_not_follow_the_file(self) -> None:
        self._encode_peak(1_000)  # warm
        small, large = self._encode_peak(10_000), self._encode_peak(1_000_000)

        assert large < 4_000, f"encode() over 1,000,000 bytes peaked at {large}"
        assert large < small * 2, f"100x the file moved the peak from {small} to {large}"

    def test_encode_writes_the_lines_encodebytes_returns(self) -> None:
        data = os.urandom(10_000)
        output = io.BytesIO()

        base64.encode(io.BytesIO(data), output)

        assert output.getvalue() == base64.encodebytes(data)
        assert max(len(line) for line in output.getvalue().splitlines()) == 76

    def test_decode_peak_follows_the_line_not_the_file(self) -> None:
        peaks = []
        for size in (10_000, 1_000_000):
            source = io.BytesIO(base64.encodebytes(os.urandom(size)))
            peaks.append(peak_bytes(lambda s=source: base64.decode(s, CountingSink())))  # type: ignore[misc]

        assert max(peaks) < 4_000, f"decode() of 76-character lines peaked at {peaks}"

    def test_decode_holds_a_single_long_line(self) -> None:
        data = os.urandom(1_000_000)
        source = io.BytesIO(base64.b64encode(data))
        sink = CountingSink()

        peak = peak_bytes(lambda: base64.decode(source, sink))

        assert sink.written == len(data)
        assert peak > len(data), f"one 1,333,336-character line peaked at only {peak}"

    @staticmethod
    def _main_peak(
        monkeypatch: pytest.MonkeyPatch, path: pathlib.Path, *flags: str
    ) -> tuple[int, int]:
        sink = CountingSink()

        class Stdout:
            buffer = sink

        monkeypatch.setattr(sys, "argv", ["base64", *flags, str(path)])
        monkeypatch.setattr(sys, "stdout", Stdout())
        peak = peak_bytes(base64.main)  # type: ignore[attr-defined]  # absent from typeshed
        monkeypatch.undo()
        return peak, sink.written

    @pytest.mark.parametrize("flags", [(), ("-d",)], ids=["encode", "decode"])
    def test_main_streams_a_file(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path, flags: tuple[str, ...]
    ) -> None:
        peaks = []
        for size in (10_000, 1_000_000):
            data = os.urandom(size)
            path = tmp_path / f"{size}.bin"
            path.write_bytes(base64.encodebytes(data) if flags else data)
            self._main_peak(monkeypatch, path, *flags)  # warm
            peak, written = self._main_peak(monkeypatch, path, *flags)
            assert written == (size if flags else len(base64.encodebytes(data)))
            peaks.append(peak)

        assert peaks[1] < 512_000, f"main {flags} peaked at {peaks}"
        assert peaks[1] < peaks[0] * 2, f"100x the file moved main {flags} from {peaks}"


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
        line, source = next((n, s) for n, s in _blocks() if "== 136" in s)
        mutated = source.replace("== 136", "== 137", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
