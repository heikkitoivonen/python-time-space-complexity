"""Tests for docs/stdlib/wave.md.

The page prices the module a call at a time: opening reads chunk headers up to
`data`, `readframes()` returns the frames asked for, and `writeframes()` passes
its argument to the file. Those claims are settled by observation rather than
timing: a stream wrapper counts the bytes read and the seeks made, a sink
records the objects it is handed, and traced allocation separates a copy of
the frames from none by orders of magnitude.

Measurement scope:

* Opening a file reads 44 bytes whether it holds 1,000 frames or 1,000,000.
  With 10 and 1,000 small chunks ahead of `data`, a seekable stream makes one
  seek per chunk, plus one for `fmt `, and never reads their bodies; an
  unseekable stream reads a 1,000,000-byte chunk ahead of `data` in full, and
  none of the data chunk.
* `readframes(k)` on 2-channel 16-bit audio peaks within 1 KB of `4·k` bytes
  for k of 1,000, 100,000 and 1,000,000, and `readframes(1000)` peaks below
  5 KB on both a 10,000- and a 2,000,000-frame file, so memory follows the
  request, not the file.
  At the end of the data it returns fewer frames, then `b''`.
* `setpos()` and `rewind()` read nothing and seek nothing; the next
  `readframes(1000)` makes at most two seeks and reads 4,000 bytes, 999,000 frames into
  the file. On a stream that cannot seek, that `readframes()` raises `OSError`.
* `writeframes()` hands a `bytes` argument to the file as the same object, and
  its traced peak stays under 100 KB for 10,000,000 bytes, as does that of a
  10,000,000-byte `array.array`. When the frames written so far differ from
  the header's count, each call makes the same three seeks at 100 frames and
  1,000,000; a declared count of 300 written as three calls of 100 costs nine,
  and as one call of 300 none. `writeframesraw()` makes none: to a declared
  count, `close()` makes none either; otherwise it patches the header once.
* Building a `Wave_write` writes nothing; the first frames bring a 44-byte
  header. Setters raise `wave.Error` once frames are written (an empty
  write writes the header and leaves them settable) and for a bad
  value; getters raise it until set, except `getcomptype()`,
  `getcompname()` and so `getparams()`, which raise `AttributeError` until
  `setcomptype()` or `setparams()`; `getnframes()` and `tell()` count frames
  written. Writing a declared length to a write-only object never seeks, and
  a wrong length to a real pipe raises `OSError`.
* `open()` is asserted to pick its mode from `file.mode`, to default to
  `'rb'`, and to reject any other mode; `close()` is asserted to close a file
  it opened by name and to leave a file object open.
* Version notes: a `WAVE_FORMAT_EXTENSIBLE` PCM header reads on 3.12+ and
  raises `wave.Error` before; `getmarkers()` and `getmark()` warn on 3.13+
  and not before. A float (format 3) file and a non-RIFF file raise
  `wave.Error` on every version.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* The big-endian caveat in the size paragraph: on such a host `readframes()`
  and `writeframes()` byte-swap samples wider than a byte into a copy. It is
  read from `_byteswap` in Lib/wave.py (3.11+) and `audioop.byteswap` (3.10);
  the space tests here are skipped on a big-endian host, and no run this
  project performs is on one.
* The per-chunk cost of skipping on a seekable stream is one `seek()`; what
  that `seek()` costs is the file object's business and is not measured.
* `Wave_read.getfp()`, `Wave_read.initfp()`, `Wave_write.initfp()` and
  `Wave_write`'s `getmark()`, `getmarkers()` and `setmark()` exist at runtime
  but are not in the official documentation, so the page leaves them out.
* Sample widths other than 1 and 2 bytes, channel counts above 2,
  odd-sized (padded) chunks, files with chunks after `data`, and negative
  `readframes()` counts are not varied.
"""

from __future__ import annotations

import array
import io
import os
import pathlib
import re
import struct
import subprocess
import sys
import textwrap
import threading
import tracemalloc
import warnings
import wave
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "wave.md"
EXPECTED_BLOCKS = 6

LITTLE_ENDIAN = pytest.mark.skipif(
    sys.byteorder != "little", reason="big-endian hosts byte-swap into a copy"
)


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def wav_bytes(nframes: int, nchannels: int = 2, sampwidth: int = 2) -> bytes:
    """A canonical 44-byte-header PCM file of `nframes` silent frames."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(nchannels)
        out.setsampwidth(sampwidth)
        out.setframerate(8000)
        out.writeframes(bytes(nframes * nchannels * sampwidth))
    return buffer.getvalue()


def with_chunks_before_data(raw: bytes, bodies: list[bytes]) -> bytes:
    """Insert one chunk per body between `fmt ` and `data`, fixing the RIFF size."""
    index = raw.index(b"data")
    inserted = b"".join(b"junk" + struct.pack("<L", len(body)) + body for body in bodies)
    out = raw[:index] + inserted + raw[index:]
    return out[:4] + struct.pack("<L", len(out) - 8) + out[8:]


def fmt_file(format_tag: int, extension: bytes = b"") -> bytes:
    """A one-frame mono 16-bit file with the given format tag and fmt extension."""
    fmt = struct.pack("<HHLLHH", format_tag, 1, 8000, 16000, 2, 16) + extension
    body = b"WAVE" + b"fmt " + struct.pack("<L", len(fmt)) + fmt + b"data" + struct.pack("<L", 2)
    body += b"\x00\x00"
    return b"RIFF" + struct.pack("<L", len(body)) + body


class CountingStream(io.RawIOBase):
    """A read stream that counts bytes read and seeks, and can refuse to seek."""

    def __init__(self, data: bytes, seekable: bool = True) -> None:
        self._data = io.BytesIO(data)
        self._seekable = seekable
        self.bytes_read = 0
        self.seeks = 0

    def readable(self) -> bool:
        return True

    def read(self, size: int | None = -1) -> bytes:
        data = self._data.read(size)
        self.bytes_read += len(data)
        return data

    def seekable(self) -> bool:
        return self._seekable

    def seek(self, offset: int, whence: int = 0) -> int:
        if not self._seekable:
            raise io.UnsupportedOperation("seek")
        self.seeks += 1
        return self._data.seek(offset, whence)

    def tell(self) -> int:
        if not self._seekable:
            raise io.UnsupportedOperation("tell")
        return self._data.tell()


class RecordingSink:
    """A seekable write target that keeps the objects it is given, not their bytes."""

    def __init__(self) -> None:
        self.position = 0
        self.seeks = 0
        self.written: list[Any] = []

    def write(self, data: Any) -> int:
        self.written.append(data)
        self.position += len(data)
        return len(data)

    def tell(self) -> int:
        return self.position

    def seek(self, position: int, whence: int = 0) -> int:
        self.seeks += 1
        self.position = position
        return position

    def flush(self) -> None:
        pass

    def forget(self) -> None:
        self.written.clear()


def open_read(stream: Any) -> wave.Wave_read:
    """`wave.open(stream, 'rb')` for a file-like object the stubs do not accept."""
    return wave.open(stream, "rb")


def open_write(sink: Any) -> wave.Wave_write:
    """`wave.open(sink, 'wb')` for a file-like object the stubs do not accept."""
    return wave.open(sink, "wb")


def stereo_writer(sink: Any, nframes: int = 0) -> wave.Wave_write:
    out = open_write(sink)
    out.setnchannels(2)
    out.setsampwidth(2)
    out.setframerate(8000)
    out.setnframes(nframes)
    return out


class TestOpeningReadsOnlyTheHeader:
    """`wave.open(file, 'rb')` | O(c) | O(1) | reads chunk headers up to
    `data`; an unseekable stream reads through them, O(c + s)."""

    @pytest.mark.parametrize("nframes", [1_000, 1_000_000])
    def test_the_bytes_read_do_not_depend_on_the_file_length(self, nframes: int) -> None:
        stream = CountingStream(wav_bytes(nframes))

        wav = open_read(stream)

        assert wav.getnframes() == nframes
        assert stream.bytes_read == 44

    def test_a_seekable_stream_seeks_once_per_chunk_ahead_of_data(self) -> None:
        seeks = {}
        for chunks in (10, 1_000):
            raw = with_chunks_before_data(wav_bytes(10), [b"x" * 100] * chunks)
            stream = CountingStream(raw)

            assert open_read(stream).getnframes() == 10
            assert stream.bytes_read == 44 + 8 * chunks, "a chunk body was read"
            seeks[chunks] = stream.seeks

        assert seeks == {10: 11, 1_000: 1_001}, "one per chunk, plus the fmt chunk"

    def test_an_unseekable_stream_reads_through_them(self) -> None:
        raw = with_chunks_before_data(wav_bytes(10), [b"x" * 1_000_000])
        stream = CountingStream(raw, seekable=False)

        assert open_read(stream).getnframes() == 10
        assert stream.bytes_read == 44 + 8 + 1_000_000

    def test_the_parameters_come_from_the_header(self) -> None:
        wav = wave.open(io.BytesIO(wav_bytes(100)), "rb")

        assert wav.getparams() == (2, 2, 8000, 100, "NONE", "not compressed")
        assert wav.getparams().nframes == wav.getnframes()
        assert (wav.getcomptype(), wav.getcompname()) == ("NONE", "not compressed")


class TestReadframesFollowsTheRequest:
    """`readframes(n)` | O(k·w) | O(k·w) | k = frames returned."""

    @LITTLE_ENDIAN
    @pytest.mark.parametrize("frames", [1_000, 100_000, 1_000_000])
    def test_the_peak_is_the_block_returned(self, frames: int) -> None:
        wav = wave.open(io.BytesIO(wav_bytes(1_000_000)), "rb")
        wav.readframes(1)  # settle the initial seek

        peak = peak_bytes(lambda: wav.readframes(frames))

        assert abs(peak - 4 * frames) < 1_000, f"readframes({frames}) peaked at {peak}"

    @LITTLE_ENDIAN
    def test_the_peak_does_not_depend_on_the_file(self) -> None:
        peaks = []
        for nframes in (10_000, 2_000_000):
            wav = wave.open(io.BytesIO(wav_bytes(nframes)), "rb")
            wav.readframes(1)
            peaks.append(peak_bytes(lambda w=wav: w.readframes(1_000)))  # type: ignore[misc]

        assert max(peaks) < 5_000, peaks

    def test_it_returns_fewer_at_the_end_then_nothing(self) -> None:
        wav = wave.open(io.BytesIO(wav_bytes(10)), "rb")

        assert len(wav.readframes(7)) == 7 * 4
        assert len(wav.readframes(7)) == 3 * 4
        assert wav.readframes(7) == b""
        assert wav.tell() == 10


class TestSeekingIsDeferred:
    """`setpos(pos)`, `rewind()` | O(1) | O(1) | the next `readframes()` seeks,
    and raises `OSError` if the stream cannot seek."""

    def test_setpos_reads_and_seeks_nothing_until_the_next_read(self) -> None:
        stream = CountingStream(wav_bytes(1_000_000))
        wav = open_read(stream)
        read, seeks = stream.bytes_read, stream.seeks

        wav.setpos(999_000)

        assert (stream.bytes_read, stream.seeks) == (read, seeks)
        assert wav.tell() == 999_000

        assert len(wav.readframes(1_000)) == 4_000
        assert stream.bytes_read - read == 4_000
        assert 1 <= stream.seeks - seeks <= 2

    def test_rewind_is_deferred_too(self) -> None:
        stream = CountingStream(wav_bytes(1_000))
        wav = open_read(stream)
        wav.readframes(500)
        read, seeks = stream.bytes_read, stream.seeks

        wav.rewind()

        assert (stream.bytes_read, stream.seeks) == (read, seeks)
        assert wav.tell() == 0
        assert wav.readframes(1) == bytes(4)
        assert 1 <= stream.seeks - seeks <= 2

    def test_setpos_rejects_a_position_past_the_end(self) -> None:
        wav = wave.open(io.BytesIO(wav_bytes(10)), "rb")

        wav.setpos(10)
        with pytest.raises(wave.Error, match="not in range"):
            wav.setpos(11)

    def test_an_unseekable_stream_reads_forward_but_cannot_jump(self) -> None:
        wav = open_read(CountingStream(wav_bytes(10), seekable=False))

        assert len(wav.readframes(5)) == 20
        wav.setpos(0)
        with pytest.raises(OSError):
            wav.readframes(1)


class TestWriteframesDoesNotCopy:
    """`writeframes(data)` | O(k·w) | O(1): written as given; a wrong header
    frame count costs a constant patch per call."""

    @LITTLE_ENDIAN
    def test_bytes_reach_the_file_as_the_same_object(self) -> None:
        sink = RecordingSink()
        out = stereo_writer(sink)
        data = bytes(4 * 1_000)

        out.writeframes(data)

        assert sink.written[-1] is data

    @LITTLE_ENDIAN
    @pytest.mark.parametrize("kind", ["bytes", "array"])
    def test_ten_megabytes_are_written_without_a_copy(self, kind: str) -> None:
        sink = RecordingSink()
        out = stereo_writer(sink)
        out.writeframes(bytes(4))  # the header is written outside the measurement
        size = 10_000_000
        data: Any = bytes(size) if kind == "bytes" else array.array("h", bytes(size))
        sink.forget()

        peak = peak_bytes(lambda: out.writeframes(data))

        assert peak < 100_000, f"writeframes({kind} of {size} bytes) peaked at {peak}"
        assert out.tell() == 1 + size // 4

    def test_one_call_matching_the_declared_count_needs_no_seek(self) -> None:
        sink = RecordingSink()
        out = stereo_writer(sink, nframes=300)

        out.writeframes(bytes(4 * 300))
        out.close()

        assert sink.seeks == 0

    def test_a_declared_count_written_in_parts_is_patched_every_call(self) -> None:
        sink = RecordingSink()
        out = stereo_writer(sink, nframes=300)

        for _ in range(3):
            out.writeframes(bytes(4 * 100))

        assert sink.seeks == 9

    def test_writeframesraw_to_a_declared_count_needs_no_seek(self) -> None:
        sink = RecordingSink()
        out = stereo_writer(sink, nframes=300)

        for _ in range(3):
            out.writeframesraw(bytes(4 * 100))
        out.close()

        assert sink.seeks == 0

    @pytest.mark.parametrize("frames", [100, 1_000_000])
    def test_a_wrong_header_costs_the_same_patch_per_call(self, frames: int) -> None:
        sink = RecordingSink()
        out = stereo_writer(sink)
        out.writeframes(bytes(4))
        data = bytes(4 * frames)

        before = sink.seeks
        out.writeframes(data)

        assert sink.seeks - before == 3

    def test_writeframesraw_leaves_the_patch_to_close(self) -> None:
        sink = RecordingSink()
        out = stereo_writer(sink)
        out.writeframesraw(bytes(4))
        out.writeframesraw(bytes(4 * 100))

        assert sink.seeks == 0
        out.close()
        assert sink.seeks == 3

    def test_the_patched_header_reads_back(self) -> None:
        buffer = io.BytesIO()
        out = stereo_writer(buffer)
        out.writeframes(bytes(4 * 100))
        out.writeframes(bytes(4 * 100))
        out.close()

        buffer.seek(0)
        assert wave.open(buffer, "rb").getnframes() == 200


class TestWriterParameters:
    """`Wave_write(file)` | O(1) writes nothing; setters raise once frames are
    written; getters raise until set; `tell()`/`getnframes()` count frames written."""

    def test_building_a_writer_writes_nothing(self) -> None:
        sink = RecordingSink()

        out = stereo_writer(sink)

        assert sink.written == []
        out.writeframes(bytes(4))
        assert sink.position == 44 + 4
        assert sink.written[0] == b"RIFF"
        out.close()

    def test_close_without_frames_writes_the_header(self) -> None:
        sink = RecordingSink()

        stereo_writer(sink).close()

        assert sink.position == 44

    @pytest.mark.parametrize(
        "setter",
        [
            lambda w: w.setnchannels(1),
            lambda w: w.setsampwidth(1),
            lambda w: w.setframerate(16000),
            lambda w: w.setnframes(5),
            lambda w: w.setcomptype("NONE", "not compressed"),
            lambda w: w.setparams((1, 1, 8000, 0, "NONE", "not compressed")),
        ],
    )
    def test_every_setter_raises_once_frames_are_written(self, setter: Any) -> None:
        out = stereo_writer(RecordingSink())
        out.writeframes(bytes(4))

        with pytest.raises(wave.Error, match="cannot change parameters"):
            setter(out)

    def test_an_empty_write_leaves_parameters_settable(self) -> None:
        sink = RecordingSink()
        out = stereo_writer(sink)

        out.writeframes(b"")
        out.setnchannels(1)

        assert sink.position == 44
        out.close()

    def test_getparams_needs_no_frame_count(self) -> None:
        out = open_write(RecordingSink())
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(8000)
        out.setcomptype("NONE", "not compressed")

        assert out.getparams() == (2, 2, 8000, 0, "NONE", "not compressed")
        out.close()

    def test_setters_reject_bad_values(self) -> None:
        out = open_write(RecordingSink())

        with pytest.raises(wave.Error):
            out.setnchannels(0)
        with pytest.raises(wave.Error):
            out.setsampwidth(5)
        with pytest.raises(wave.Error):
            out.setframerate(0)
        with pytest.raises(wave.Error):
            out.setcomptype("ULAW", "u-law")
        out.setparams((1, 1, 8000, 0, "NONE", "not compressed"))
        out.close()

    def test_getters_raise_until_set(self) -> None:
        out = open_write(RecordingSink())

        for getter in (out.getnchannels, out.getsampwidth, out.getframerate, out.getparams):
            with pytest.raises(wave.Error):
                getter()
        out.setparams((1, 1, 8000, 0, "NONE", "not compressed"))
        out.close()

    def test_tell_and_getnframes_count_frames_written(self) -> None:
        out = stereo_writer(RecordingSink(), nframes=1_000)
        out.setcomptype("NONE", "not compressed")

        assert (out.tell(), out.getnframes()) == (0, 0)
        out.writeframes(bytes(4 * 30))
        assert (out.tell(), out.getnframes()) == (30, 30)
        assert out.getparams().nframes == 1_000
        assert (out.getcomptype(), out.getcompname()) == ("NONE", "not compressed")

    def test_the_compression_getters_need_setcomptype(self) -> None:
        out = stereo_writer(RecordingSink())

        for getter in (out.getcomptype, out.getcompname, out.getparams):
            with pytest.raises(AttributeError):
                getter()
        out.setparams((2, 2, 8000, 0, "NONE", "not compressed"))
        assert out.getparams().comptype == "NONE"


class TestUnseekableOutput:
    """A declared frame count needs no seek; a wrong one cannot be patched."""

    def test_a_declared_length_writes_to_a_write_only_object(self) -> None:
        class WriteOnly:
            def __init__(self) -> None:
                self.size = 0

            def write(self, data: Any) -> int:
                self.size += len(data)
                return len(data)

            def flush(self) -> None:
                pass

        sink = WriteOnly()
        with stereo_writer(sink, nframes=200) as out:
            out.writeframesraw(bytes(4 * 100))
            out.writeframesraw(bytes(4 * 100))

        assert sink.size == 44 + 800

    def test_a_wrong_length_on_a_pipe_raises(self) -> None:
        read_fd, write_fd = os.pipe()
        received = bytearray()

        def drain() -> None:
            with open(read_fd, "rb") as reader:
                while chunk := reader.read(4096):
                    received.extend(chunk)

        thread = threading.Thread(target=drain)
        thread.start()
        try:
            with open(write_fd, "wb") as pipe:
                out = stereo_writer(pipe)
                out.writeframes(bytes(4))
                with pytest.raises(OSError):
                    out.writeframes(bytes(4 * 10))
                with pytest.raises(OSError):
                    out.close()
        finally:
            thread.join(timeout=10)

        assert received[:4] == b"RIFF"


class TestOpenAndClose:
    """`wave.open(file, mode=None)`: the mode comes from `file.mode`, else
    `'rb'`; `close()` closes only a file it opened by name."""

    def test_the_mode_comes_from_the_file(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "a.wav"
        path.write_bytes(wav_bytes(3))

        with open(path, "rb") as handle:
            assert isinstance(wave.open(handle), wave.Wave_read)
        with open(tmp_path / "b.wav", "wb") as handle:
            writer = wave.open(handle)
            assert isinstance(writer, wave.Wave_write)
            writer.setparams((1, 1, 8000, 0, "NONE", "not compressed"))
            writer.close()

    def test_without_a_mode_attribute_it_reads(self) -> None:
        assert isinstance(wave.open(io.BytesIO(wav_bytes(3))), wave.Wave_read)

    def test_an_unknown_mode_raises(self) -> None:
        with pytest.raises(wave.Error, match="mode must be"):
            wave.open(io.BytesIO(), "ab")

    def test_close_closes_only_a_file_it_opened(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "a.wav"
        path.write_bytes(wav_bytes(3))
        handle = open(path, "rb")  # noqa: SIM115

        wave.open(handle).close()
        assert not handle.closed
        handle.close()

        wav = wave.open(str(path))
        opened = wav._i_opened_the_file  # type: ignore[attr-defined]  # noqa: SLF001
        wav.close()
        assert opened.closed


class TestFormats:
    """Only PCM is supported; `WAVE_FORMAT_EXTENSIBLE` PCM reads from 3.12."""

    EXTENSIBLE_PCM = fmt_file(
        0xFFFE,
        struct.pack("<HHL", 22, 16, 4)
        + b"\x01\x00\x00\x00\x00\x00\x10\x00\x80\x00\x00\xaa\x008\x9bq",
    )

    def test_a_float_file_raises(self) -> None:
        with pytest.raises(wave.Error, match="unknown format"):
            wave.open(io.BytesIO(fmt_file(3)), "rb")

    def test_a_non_riff_file_raises(self) -> None:
        with pytest.raises(wave.Error, match="RIFF"):
            wave.open(io.BytesIO(b"OggS" + bytes(40)), "rb")

    def test_the_pcm_fixture_reads(self) -> None:
        assert wave.open(io.BytesIO(fmt_file(1)), "rb").getnframes() == 1

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="read from 3.12")
    def test_extensible_pcm_reads(self) -> None:
        wav = wave.open(io.BytesIO(self.EXTENSIBLE_PCM), "rb")

        assert (wav.getnframes(), wav.getsampwidth()) == (1, 2)

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="read from 3.12")
    def test_extensible_pcm_raises_before_312(self) -> None:
        with pytest.raises(wave.Error, match="unknown format"):
            wave.open(io.BytesIO(self.EXTENSIBLE_PCM), "rb")


class TestMarkerStubs:
    """`getmarkers()`, `getmark(id)` | O(1) | return `None` and raise;
    deprecated from 3.13."""

    def wav(self) -> wave.Wave_read:
        return wave.open(io.BytesIO(wav_bytes(1)), "rb")

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="deprecated in 3.13")
    def test_they_warn_from_313(self) -> None:
        wav = self.wav()

        with pytest.warns(DeprecationWarning):
            assert wav.getmarkers() is None
        with pytest.warns(DeprecationWarning), pytest.raises(wave.Error, match="no marks"):
            wav.getmark(1)

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="deprecated in 3.13")
    def test_they_do_not_warn_before_313(self) -> None:
        wav = self.wav()

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert wav.getmarkers() is None
            with pytest.raises(wave.Error, match="no marks"):
                wav.getmark(1)


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
        [sys.executable, "-W", "error::DeprecationWarning", str(script)],
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
        line, source = next((n, s) for n, s in _blocks() if "frames == 10_000" in s)
        mutated = source.replace("frames == 10_000", "frames == 9_999", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
