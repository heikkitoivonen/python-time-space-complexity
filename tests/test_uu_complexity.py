"""Tests for docs/stdlib/uu.md.

The page prices both functions as streams: `encode()` reads 45 bytes and
writes one line per read, and `decode()` reads a line at a time through the
`end` line, holding the line it is on and the parsed header. Those bounds are
settled by observation - a recording stream counts every read and write,
`tell()` shows where reading stopped, and a traced peak that stays under a
fixed ceiling, and does not double, while the input grows a hundredfold
separates O(1) from O(n). The module exists on
Python 3.10 to 3.12 only, so every runtime test takes the `uu` fixture, which
skips from 3.13; availability is asserted on every version. Lib/uu.py is the
same file at v3.10.19, v3.11.14 and v3.12.12 apart from the import-time
DeprecationWarning that 3.11 adds.

Measurement scope:

* `encode()` of 0, 44, 45, 46, 1,000, 10,000 and 100,000 bytes from a recording stream calls
  `read(45)` exactly ceil(n/45) + 1 times and writes ceil(n/45) + 2 times:
  the header, one line per read, and the footer. Its traced peak, encoding
  100,000, 1,000,000 and 10,000,000 bytes from a `BytesIO` into a sink that
  keeps nothing, stays under 4,096 bytes at every size, and the largest peak
  is under twice the smallest.
* `decode()` of the same three encodings, from a counting stream into the
  same sink, calls `readline()` once per line through `end` and peaks under
  4,096 bytes at every size, the largest under twice the smallest; preceded by one line of 1,000,000 bytes, its peak
  exceeds 1,000,000. Each data line `encode()` writes for a full 45 bytes is
  62 bytes, newline included. With text after the `end` line, the stream is left
  at the first byte after it. Input with no `begin` line raises `uu.Error`
  with the stream at its end.
* The header: `begin 644 data.bin` for an explicit name and mode, `begin 666
  -` for a file object with neither, and the base name and permission bits of
  the input path otherwise; a mode is written masked to `0o777`. The footer
  is ` \\nend\\n`, or `` `\\nend\\n `` with `backtick=True`, which also writes
  zero bytes as `` ` `` rather than spaces.
* Paths: `encode()` and `decode()` given path strings open and close their
  files; file objects passed in are left open. `'-'` is standard input and
  output, run in a subprocess with bytes on stdin.
* A text-mode file raises `TypeError` as `encode()`'s output and as
  `decode()`'s input, given data to pass through it; empty input is not
  tried.
* Without `out_file`, `decode()` writes the header's name relative to the
  working directory, and `os.chmod()` gives it the header's mode or the
  `mode` argument; a file object output gets no `os.chmod()` call. A header
  name of `-` writes to standard output, run in a subprocess. A name that
  exists, one starting with `/` and one containing `../` raise `uu.Error`
  with the name in the message, and no new file appears.
* Input that stops before `end` raises `uu.Error` after the decoded bytes
  are written. A line with non-space characters past its length decodes to that
  length and writes a warning to standard error, and nothing at all with
  `quiet=True`; a full-length line with characters outside the alphabet
  within its length raises `binascii.Error`.
  `uu.Error` is an `Exception` subclass.
* Importing `uu` raises `ModuleNotFoundError` from 3.13; in a subprocess it
  warns on 3.11 and 3.12 and not on 3.10.
* Every fenced Python block runs in its own subprocess and working directory
  on 3.10 to 3.12, and a mutated assertion in one of them is asserted to fail.

Not settled here:

* The O(n) and O(m) times are read from the counted calls and Lib/uu.py:
  each `encode()` read is at most 45 bytes and goes through one
  `b2a_uu()`; `decode()` skips lines before `begin` with a prefix check and
  passes each data line to `a2b_uu()`, twice for a line it recovers, whose
  per-line cost is priced on the binascii page. Nothing is timed. The
  measurements use one byte pattern per size; data content does not change
  the code path, and the header name is held short.
* `decode()`'s refusal of a name starting with a separator or containing
  `../` is in v3.10.12 and v3.11.4 onwards and in every 3.12 release (`git
  tag --contains` on the backports of gh-99889); earlier patch releases are
  not installed here. On Windows `os.sep` is `\\` and `os.altsep` adds `/`,
  and a drive-qualified name such as `C:x` is not refused; the tests run on
  Linux, the only platform CI runs 3.10 to 3.12 on.
* The deprecation in 3.11 and removal in 3.13 come from the 3.12
  documentation and PEP 594.
* API coverage: the audit on 3.14, where `uu` is gone, checks no names for
  the page. Run on 3.12.15 it checks `uu`, `encode`, `decode` and `Error`
  and reports none missing; `uu.test()`, the command-line entry point that
  reads `sys.argv`, is listed as needing classification and is not on the
  page.
"""

from __future__ import annotations

import binascii
import importlib
import importlib.util
import io
import os
import pathlib
import re
import stat
import subprocess
import sys
import textwrap
import tracemalloc
import warnings
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "uu.md"
EXPECTED_BLOCKS = 4
PEAK_LIMIT = 4096


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def payload(size: int) -> bytes:
    return bytes(range(256)) * (size // 256) + bytes(range(size % 256))


def lines_for(size: int) -> int:
    return -(-size // 45)


class Sink:
    """A binary output that keeps nothing and counts its writes."""

    def __init__(self) -> None:
        self.writes = 0

    def write(self, data: bytes) -> int:
        self.writes += 1
        return len(data)


class CountingReader(io.BytesIO):
    """A `BytesIO` that records each `read()` size and counts `readline()`."""

    def __init__(self, data: bytes) -> None:
        super().__init__(data)
        self.reads: list[int] = []
        self.lines_read = 0

    def read(self, size: int | None = -1, /) -> bytes:
        self.reads.append(-1 if size is None else size)
        return super().read(size)

    def readline(self, size: int | None = -1, /) -> bytes:
        self.lines_read += 1
        return super().readline(size)


@pytest.fixture
def uu() -> Iterator[Any]:
    if sys.version_info >= (3, 13):
        pytest.skip("version: uu was removed in Python 3.13")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        yield importlib.import_module("uu")


def encode(uu: Any, data: bytes, **kwargs: Any) -> bytes:
    out = io.BytesIO()
    uu.encode(io.BytesIO(data), out, **kwargs)
    return out.getvalue()


class TestAvailability:
    """`import uu` warns on 3.11 and 3.12 and fails from 3.13."""

    def test_the_module_exists_only_before_3_13(self) -> None:
        assert (importlib.util.find_spec("uu") is not None) == (sys.version_info < (3, 13))

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="uu exists before 3.13")
    def test_importing_it_from_3_13_raises(self) -> None:
        with pytest.raises(ModuleNotFoundError) as caught:
            importlib.import_module("uu")
        assert caught.value.name == "uu"

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="uu was removed in 3.13")
    def test_importing_it_warns_from_3_11(self) -> None:
        result = subprocess.run(
            [sys.executable, "-I", "-W", "error::DeprecationWarning", "-c", "import uu"],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        if sys.version_info >= (3, 11):
            assert result.returncode != 0
            assert "'uu' is deprecated" in result.stderr
        else:
            assert result.returncode == 0, result.stderr


class TestEncodeStreams:
    """`uu.encode()` | O(n) | O(1): reads 45 bytes at a time and writes one
    line per read. A whole-input read would show as one `read()` call, and a
    buffered output as a peak that grows with n."""

    @pytest.mark.parametrize("size", [0, 44, 45, 46, 1_000, 10_000, 100_000])
    def test_it_reads_45_bytes_and_writes_one_line_per_read(self, uu: Any, size: int) -> None:
        source = CountingReader(payload(size))
        sink = Sink()
        uu.encode(source, sink)

        assert source.reads == [45] * (lines_for(size) + 1)
        assert sink.writes == lines_for(size) + 2

    def test_memory_does_not_grow_with_the_input(self, uu: Any) -> None:
        peaks = {}
        for size in (100_000, 1_000_000, 10_000_000):
            source = io.BytesIO(payload(size))
            peaks[size] = peak_bytes(lambda source=source: uu.encode(source, Sink()))

        assert all(peak < PEAK_LIMIT for peak in peaks.values()), peaks
        assert max(peaks.values()) < 2 * min(peaks.values()), peaks

    def test_a_full_line_is_61_characters_and_a_newline(self, uu: Any) -> None:
        lines = encode(uu, payload(450)).split(b"\n")
        assert len(lines[1]) == 61
        assert lines[1][:1] == b"M"
        assert all(len(line) + 1 == 62 for line in lines[1:11])


class TestEncodeHeader:
    """The `name`, `mode` and `backtick` defaults in the encode row."""

    def test_explicit_name_and_a_mode_masked_to_0o777(self, uu: Any) -> None:
        encoded = encode(uu, b"x", name="data.bin", mode=0o100644)
        assert encoded.startswith(b"begin 644 data.bin\n")

    def test_a_file_object_defaults_to_dash_and_0o666(self, uu: Any) -> None:
        assert encode(uu, b"x").startswith(b"begin 666 -\n")

    def test_a_path_supplies_its_base_name_and_mode(self, uu: Any, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "input.bin"
        source.write_bytes(b"data")
        source.chmod(0o640)
        out = io.BytesIO()
        uu.encode(str(source), out)

        mode = stat.S_IMODE(source.stat().st_mode)
        assert out.getvalue().startswith(f"begin {mode:o} input.bin\n".encode())

    def test_backtick_replaces_spaces_in_data_and_footer(self, uu: Any) -> None:
        plain = encode(uu, bytes(3))
        ticked = encode(uu, bytes(3), backtick=True)

        assert plain.endswith(b"\n \nend\n")
        assert ticked.endswith(b"\n`\nend\n")
        assert plain.split(b"\n")[1] == b"#    "
        assert ticked.split(b"\n")[1] == b"#````"


class TestFilesAndPaths:
    """Both files are binary; a path is opened and closed for you, and `'-'`
    is standard input or output."""

    def test_paths_are_opened_and_closed(self, uu: Any, tmp_path: pathlib.Path) -> None:
        opened: list[Any] = []
        real_open = open

        def recording_open(*args: Any, **kwargs: Any) -> Any:
            handle = real_open(*args, **kwargs)
            opened.append(handle)
            return handle

        source, encoded, decoded = (tmp_path / name for name in ("in", "uu", "out"))
        source.write_bytes(payload(1000))
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr("builtins.open", recording_open)
            uu.encode(str(source), str(encoded))
            uu.decode(str(encoded), str(decoded))

        assert len(opened) == 4
        assert all(handle.closed for handle in opened)
        assert decoded.read_bytes() == payload(1000)

    def test_file_objects_passed_in_are_left_open(self, uu: Any) -> None:
        source, out = io.BytesIO(b"data"), io.BytesIO()
        uu.encode(source, out)
        assert not source.closed and not out.closed

        out.seek(0)
        decoded = io.BytesIO()
        uu.decode(out, decoded)
        assert not out.closed and not decoded.closed

    def test_dash_is_standard_input_and_output(self, uu: Any) -> None:
        def run(code: str, data: bytes) -> bytes:
            result = subprocess.run(
                [sys.executable, "-I", "-W", "ignore::DeprecationWarning", "-c", code],
                input=data,
                capture_output=True,
                timeout=60,
                check=False,
            )
            assert result.returncode == 0, result.stderr
            return result.stdout

        encoded = run("import uu; uu.encode('-', '-')", payload(100))
        assert encoded == encode(uu, payload(100))
        assert run("import uu; uu.decode('-', '-')", encoded) == payload(100)

    def test_text_mode_files_raise_type_error(self, uu: Any) -> None:
        with pytest.raises(TypeError):
            uu.encode(io.BytesIO(b"data"), io.StringIO())
        with pytest.raises(TypeError):
            uu.decode(io.StringIO("begin 644 x\n"), io.BytesIO())


class TestDecodeStreams:
    """`uu.decode()` | O(m) | O(l): one `readline()` per line through `end`,
    nothing after it, and only the current line held. A whole-input read would
    leave the stream at its end; a buffered result would grow the peak with n."""

    @pytest.mark.parametrize("size", [1_000, 10_000, 100_000])
    def test_it_reads_one_line_at_a_time_through_end(self, uu: Any, size: int) -> None:
        encoded = encode(uu, payload(size))
        source = CountingReader(b"preamble\n" * 5 + encoded + b"trailer\n")
        sink = Sink()
        uu.decode(source, sink)

        assert source.lines_read == 5 + 1 + lines_for(size) + 1 + 1
        assert source.reads == []
        assert sink.writes == lines_for(size) + 1  # the space line decodes to b""
        assert source.read() == b"trailer\n"

    def test_memory_does_not_grow_with_the_input(self, uu: Any) -> None:
        peaks = {}
        for size in (100_000, 1_000_000, 10_000_000):
            source = io.BytesIO(encode(uu, payload(size)))
            peaks[size] = peak_bytes(lambda source=source: uu.decode(source, Sink()))

        assert all(peak < PEAK_LIMIT for peak in peaks.values()), peaks
        assert max(peaks.values()) < 2 * min(peaks.values()), peaks

    def test_a_long_line_before_begin_is_held_whole(self, uu: Any) -> None:
        source = io.BytesIO(b"x" * 1_000_000 + b"\n" + encode(uu, b"data"))
        peak = peak_bytes(lambda: uu.decode(source, Sink()))
        assert peak > 1_000_000

    def test_no_begin_line_reads_everything_then_raises(self, uu: Any) -> None:
        data = b"not uuencoded\n" * 100
        source = io.BytesIO(data)
        with pytest.raises(uu.Error, match="No valid begin line"):
            uu.decode(source, io.BytesIO())
        assert source.tell() == len(data)

    def test_a_begin_line_needs_an_octal_mode_and_a_name(self, uu: Any) -> None:
        encoded = encode(uu, b"data", name="f")
        decoded = io.BytesIO()
        uu.decode(io.BytesIO(b"begin here\nbegin 9 f\n" + encoded), decoded)
        assert decoded.getvalue() == b"data"


class TestDecodeToTheHeaderName:
    """Without `out_file`, the header's name relative to the working
    directory; `mode` or the header's is applied only to a path output; an
    existing, separator-led or `../` name raises `uu.Error` before writing;
    `-` is standard output."""

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows chmod sets only read-only")
    def test_the_header_names_the_file_and_its_mode(
        self, uu: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(tmp_path)
        uu.decode(io.BytesIO(encode(uu, b"data", name="out.bin", mode=0o604)))
        assert (tmp_path / "out.bin").read_bytes() == b"data"
        assert stat.S_IMODE((tmp_path / "out.bin").stat().st_mode) == 0o604

        uu.decode(io.BytesIO(encode(uu, b"data", name="two.bin", mode=0o604)), mode=0o640)
        assert stat.S_IMODE((tmp_path / "two.bin").stat().st_mode) == 0o640

    def test_a_file_object_output_gets_no_chmod(
        self, uu: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[tuple[Any, ...]] = []
        monkeypatch.setattr(uu.os, "chmod", lambda *args: calls.append(args))
        uu.decode(io.BytesIO(encode(uu, b"data", mode=0o600)), io.BytesIO(), mode=0o644)
        assert calls == []

    def test_a_dash_header_name_is_standard_output(self, uu: Any, tmp_path: pathlib.Path) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-W",
                "ignore::DeprecationWarning",
                "-c",
                "import sys, uu; uu.decode(sys.stdin.buffer)",
            ],
            input=encode(uu, b"data"),
            capture_output=True,
            cwd=tmp_path,
            timeout=60,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout == b"data"
        assert list(tmp_path.iterdir()) == []

    @pytest.mark.parametrize("kind", ["existing", "separator", "parent"])
    def test_unsafe_names_are_refused_before_writing(
        self, uu: Any, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, kind: str
    ) -> None:
        work = tmp_path / "work"
        work.mkdir()
        monkeypatch.chdir(work)
        (work / "existing.bin").write_bytes(b"keep")
        name = {
            "existing": "existing.bin",
            "separator": os.sep + "separator.bin",
            "parent": "../parent.bin",
        }[kind]

        with pytest.raises(uu.Error) as caught:
            uu.decode(io.BytesIO(encode(uu, b"data", name=name)))
        assert name in str(caught.value)
        assert sorted(path.name for path in tmp_path.rglob("*")) == ["existing.bin", "work"]
        assert (work / "existing.bin").read_bytes() == b"keep"


class TestMalformedInput:
    """`uu.Error` for a missing `end` after writing what was decoded; a
    broken encoder's long line recovered with a warning unless `quiet`; a
    character outside the alphabet raises `binascii.Error`."""

    def test_a_truncated_input_raises_after_writing(self, uu: Any) -> None:
        encoded = encode(uu, payload(1000))
        truncated = encoded[: encoded.rindex(b" \nend\n")]
        decoded = io.BytesIO()
        with pytest.raises(uu.Error, match="Truncated"):
            uu.decode(io.BytesIO(truncated), decoded)
        assert decoded.getvalue() == payload(1000)

    @pytest.mark.parametrize("quiet", [False, True])
    def test_a_padded_line_decodes_with_a_warning_unless_quiet(
        self, uu: Any, capsys: pytest.CaptureFixture[str], quiet: bool
    ) -> None:
        line = binascii.b2a_uu(b"hi").rstrip(b"\n") + b"xyz\n"
        decoded = io.BytesIO()
        uu.decode(io.BytesIO(b"begin 644 f\n" + line + b" \nend\n"), decoded, quiet=quiet)

        assert decoded.getvalue() == b"hi"
        err = capsys.readouterr().err
        if quiet:
            assert err == ""
        else:
            assert err.startswith("Warning:")

    def test_a_character_outside_the_alphabet_raises_binascii_error(self, uu: Any) -> None:
        corrupt = b"begin 644 f\nM" + b"\x7f" * 60 + b"\n \nend\n"
        with pytest.raises(binascii.Error):
            uu.decode(io.BytesIO(corrupt), io.BytesIO())

    def test_error_is_an_exception(self, uu: Any) -> None:
        assert issubclass(uu.Error, Exception)
        assert not issubclass(uu.Error, binascii.Error)


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
        [sys.executable, "-I", "-W", "ignore::DeprecationWarning", str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and working directory on the
    versions that still have the module, and asserts its own result."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        assert all("import uu" in source for _, source in blocks)

    def test_every_block_runs(self, uu: Any, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")
            assert os.listdir(workdir) == ["block.py"], line

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    def test_the_runner_notices_a_broken_assertion(self, uu: Any, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "b'begin 644 data.bin'" in s)
        mutated = source.replace("b'begin 644 data.bin'", "b'begin 600 data.bin'", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
