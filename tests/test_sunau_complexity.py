"""Tests for docs/stdlib/sunau.md.

The page prices the module a call at a time: opening reads only the header,
`readframes()` returns the frames asked for, and `writeframes()` passes its
argument to the file. Those claims are settled by observation rather than
timing: a stream wrapper counts the bytes read and the seeks made, a sink
records the objects it is handed and the seeks it takes, and traced
allocation separates a copy of the frames from none by orders of magnitude.

`sunau` exists on Python 3.10 to 3.12 and is gone from 3.13, so every runtime
test is skipped on 3.13 and later; there, only the availability boundary and
the page's block count are checked. `Lib/sunau.py` differs between v3.10.19,
v3.11.14 and v3.12.12 only in the import-time DeprecationWarning added in
3.11, the warning filter around its `audioop` imports, and `isinstance()` in
place of a `type()` comparison for a file name.

Measurement scope:

* Opening a file the module wrote reads its whole 32-byte header, 24 bytes
  of fixed fields and 8 of padding, whether it holds 1,000 frames or
  1,000,000, and makes no seek; a 40-byte description is read with the
  header. A header size of 101 raises `sunau.Error`, as do a bad magic
  number, each of the six unsupported encodings and zero channels; a file
  ending inside the fixed fields raises `EOFError`. A stream with only
  `read()` reads its frames in order, and `setpos()` and `rewind()` on it
  raise `OSError`.
* `readframes(k)` on 2-channel 16-bit audio peaks within 2 KB of `4·k` bytes
  for k of 1,000, 100,000 and 1,000,000, and `readframes(1000)` peaks below
  6 KB on both a 10,000- and a 2,000,000-frame file, all from `BytesIO`. From
  a file on disk holding 1,000 frames, `readframes(2_500_000)` returns 4,000
  bytes and peaks above 9,000,000: the read buffer is sized for the request.
  At the end of the data it returns fewer frames, then `b''`. A u-law file
  returns twice the bytes it read from the stream; an A-law file returns the
  bytes read, one per sample, while `getsampwidth()` reports 2. A header of
  unknown length gives `getnframes()` `AUDIO_UNKNOWN_SIZE`, and
  `readframes()` of that reads to the end.
* `setpos()` and `rewind()` read nothing and make one seek each; the next
  `readframes(1000)` makes none and reads 4,000 bytes, 999,000 frames into
  the file.
* `writeframes()` hands a `bytes` argument to the file as the same object, and
  its traced peak stays under 100 KB for 10,000,000 bytes, as does that of a
  10,000,000-byte `array.array`; a u-law writer peaks above 4,000,000 bytes
  for the same input, the encoded copy, and writes 5,000,000 bytes. Each patch
  is two seeks, the same at 100 frames and 1,000,000. Without `setnframes()`,
  every `writeframes()` patches, and `close()` once more after three such
  calls, though the header already holds the count; a declared count of 300
  written as three calls of 100 patches each call, and as one call of 300
  never.
  `writeframesraw()` makes no seek, and `close()` then patches once, or not at
  all when the declared count is right. A patched header reads back the
  frames written.
* Building an `Au_write` writes nothing, and its compression type is `'ULAW'`;
  the first frames bring a 32-byte header. Setters other than
  `setcomptype()` raise `sunau.Error` once frames are written; `setcomptype()`
  does not, and the header keeps the first encoding. The setters' value
  checks, the getters' errors before the parameters are set, and `tell()` and
  `getnframes()` counting frames written are asserted directly. A target with
  only `write()` and `flush()` takes a declared count written raw; without
  `flush()` the close raises `AttributeError`, and without a declared count it
  raises `OSError`.
* `open()` is asserted to pick its mode from `file.mode`, to default to
  `'rb'`, and to reject any other mode. `close()` leaves a file object it was
  handed open, for reader and writer, and closes one it opened by name.
* Uncompressed samples are asserted to read back as the bytes stored, which
  the writer is asserted to store as given. u-law samples written in native
  order read back within 1,000 of the original in native order. The writer's
  header encoding is asserted for widths 1 to 4 uncompressed and for u-law.
* The Common Patterns conversion runs on this little-endian host only; that
  `wave` takes native-order samples, so a big-endian host must not swap, is
  read from `Lib/wave.py` at v3.12.12, which swaps on a big-endian host.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* The module is removed from Python 3.13, so no claim on the page is checked
  on 3.13 or 3.14; the removal itself is the availability test.
* What a `seek()` costs is the file object's business and is not measured;
  the page counts one patch as a constant cost.
* `Au_read.getfp()`, `Au_read.initfp()` and `Au_write.initfp()` exist at
  runtime but are not in the official documentation, so the page leaves them
  out. The official documentation names the classes `AU_read` and `AU_write`,
  which the module does not define; the 3.12 audit lists their methods as
  documented but unresolved, and the module's own `Au_read` and `Au_write`
  members as needing classification.
* The O(k·w) cost of `array.array` construction and `byteswap()` in the
  Common Patterns example is priced on docs/stdlib/array.md, and `wave`'s
  costs on docs/stdlib/wave.md. The removal of `aifc` and `audioop` in 3.13,
  named under Related Modules, comes from PEP 594 and the official 3.13
  What's New.
* Channel counts above 2, sample widths 3 and 4 when reading, u-law space at
  other widths, a description field written by the module (it writes none),
  and negative `readframes()` counts are not varied.
* API coverage: the audit on 3.14, where `sunau` is gone, checks no names for
  the page. Run on 3.12.15 it checks `sunau`, `sunau.open` and `sunau.Error`,
  and reports none missing.
"""

from __future__ import annotations

import array
import functools
import importlib
import importlib.util
import io
import pathlib
import re
import subprocess
import sys
import textwrap
import tracemalloc
import warnings
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "sunau.md"
EXPECTED_BLOCKS = 8

sunau: Any = None
if sys.version_info < (3, 13):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        sunau = importlib.import_module("sunau")

REQUIRES_SUNAU = pytest.mark.skipif(sunau is None, reason="sunau was removed in Python 3.13")

UNSUPPORTED = ("FLOAT", "DOUBLE", "ADPCM_G721", "ADPCM_G722", "ADPCM_G723_3", "ADPCM_G723_5")


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def header(
    encoding: int = 3,
    data_size: int = 0,
    nchannels: int = 2,
    rate: int = 8000,
    info: bytes = b"",
) -> bytes:
    """An AU header, with `info` padded into it."""
    fields = (0x2E736E64, 24 + len(info), data_size, encoding, rate, nchannels)
    return b"".join(field.to_bytes(4, "big") for field in fields) + info


def au_bytes(nframes: int, nchannels: int = 2, sampwidth: int = 2, comptype: str = "NONE") -> bytes:
    """An AU file of `nframes` silent frames, written by the module."""
    buffer = io.BytesIO()
    out = sunau.open(buffer, "wb")
    out.setparams((nchannels, sampwidth, 8000, nframes, comptype, ""))
    out.writeframes(bytes(nframes * nchannels * sampwidth))
    out.close()
    return buffer.getvalue()


@functools.cache
def million_frames() -> bytes:
    return au_bytes(1_000_000)


class CountingStream(io.RawIOBase):
    """A read stream that counts bytes read and seeks."""

    def __init__(self, data: bytes) -> None:
        self._data = io.BytesIO(data)
        self.bytes_read = 0
        self.seeks = 0

    def readable(self) -> bool:
        return True

    def read(self, size: int | None = -1) -> bytes:
        data = self._data.read(size)
        self.bytes_read += len(data)
        return data

    def seekable(self) -> bool:
        return True

    def seek(self, offset: int, whence: int = 0) -> int:
        self.seeks += 1
        return self._data.seek(offset, whence)

    def tell(self) -> int:
        return self._data.tell()


class ReadOnly:
    """Has `read()` and nothing else, like a pipe."""

    def __init__(self, data: bytes) -> None:
        self._data = io.BytesIO(data)

    def read(self, size: int = -1) -> bytes:
        return self._data.read(size)


class RecordingSink:
    """A seekable write target that keeps the objects it is given, not their bytes."""

    def __init__(self) -> None:
        self.position = 0
        self.size = 0
        self.seeks = 0
        self.closed = False
        self.written: list[Any] = []

    def write(self, data: Any) -> int:
        self.written.append(data)
        self.position += len(data)
        self.size = max(self.size, self.position)
        return len(data)

    def tell(self) -> int:
        return self.position

    def seek(self, position: int, whence: int = 0) -> int:
        self.seeks += 1
        self.position = position if whence == 0 else self.size + position
        return self.position

    def flush(self) -> None:
        pass

    def close(self) -> None:
        self.closed = True

    def forget(self) -> None:
        self.written.clear()


class WriteOnly:
    """Accepts writes and flushes and nothing else, like a pipe with no `tell()`."""

    def __init__(self) -> None:
        self.size = 0

    def write(self, data: Any) -> int:
        self.size += len(data)
        return len(data)

    def flush(self) -> None:
        pass


class NoFlush:
    """Accepts writes only."""

    def write(self, data: Any) -> int:
        return len(data)


def stereo_writer(sink: Any, nframes: int | None = None) -> Any:
    """A 2-channel 16-bit uncompressed writer; `None` leaves the count undeclared."""
    out = sunau.open(sink, "wb")
    out.setnchannels(2)
    out.setsampwidth(2)
    out.setframerate(8000)
    out.setcomptype("NONE", "")
    if nframes is not None:
        out.setnframes(nframes)
    return out


class TestAvailability:
    """The page's scope: present on 3.10 to 3.12, removed from 3.13."""

    def test_the_module_exists_only_before_313(self) -> None:
        found = importlib.util.find_spec("sunau") is not None

        assert found == (sys.version_info < (3, 13))

    @REQUIRES_SUNAU
    def test_importing_warns_from_311(self) -> None:
        result = subprocess.run(
            [sys.executable, "-W", "error::DeprecationWarning", "-c", "import sunau"],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )

        if sys.version_info >= (3, 11):
            assert result.returncode != 0
            assert "DeprecationWarning" in result.stderr
        else:
            assert result.returncode == 0, result.stderr


@REQUIRES_SUNAU
class TestOpeningReadsOnlyTheHeader:
    """`sunau.open(f, 'rb')` | O(1) | O(1) | reads the header and nothing else;
    needs only `read()`."""

    def test_the_bytes_read_do_not_depend_on_the_audio_length(self) -> None:
        read = {}
        for nframes in (1_000, 1_000_000):
            stream = CountingStream(au_bytes(nframes))

            audio = sunau.open(stream, "rb")

            assert audio.getnframes() == nframes
            assert stream.seeks == 0
            read[nframes] = stream.bytes_read

        assert read[1_000] == read[1_000_000] == 32, "24 fields + 8 bytes of padding"

    def test_a_description_is_read_with_the_header(self) -> None:
        stream = CountingStream(header(data_size=4, info=b"x" * 40) + bytes(4))

        audio = sunau.open(stream, "rb")

        assert stream.bytes_read == 64
        assert audio.readframes(1) == bytes(4)

    def test_a_header_over_100_bytes_raises(self) -> None:
        with pytest.raises(sunau.Error, match="ridiculously large"):
            sunau.open(io.BytesIO(header(info=b"x" * 77) + bytes(4)), "rb")
        sunau.open(io.BytesIO(header(info=b"x" * 76) + bytes(4)), "rb")

    def test_a_file_that_is_not_au_raises(self) -> None:
        with pytest.raises(sunau.Error, match="bad magic number"):
            sunau.open(io.BytesIO(b"RIFF" + bytes(40)), "rb")

    @pytest.mark.parametrize("name", UNSUPPORTED)
    def test_an_unsupported_encoding_raises(self, name: str) -> None:
        encoding = getattr(sunau, f"AUDIO_FILE_ENCODING_{name}")

        with pytest.raises(sunau.Error, match="not \\(yet\\) supported"):
            sunau.open(io.BytesIO(header(encoding=encoding)), "rb")

    def test_zero_channels_raise(self) -> None:
        with pytest.raises(sunau.Error, match="channels"):
            sunau.open(io.BytesIO(header(nchannels=0)), "rb")

    def test_a_header_cut_short_raises_eof_error(self) -> None:
        with pytest.raises(EOFError):
            sunau.open(io.BytesIO(header()[:10]), "rb")

    def test_a_read_only_stream_reads_in_order_but_cannot_seek(self) -> None:
        audio = sunau.open(ReadOnly(au_bytes(100, nchannels=1, sampwidth=1)), "rb")

        assert len(audio.readframes(60)) == 60
        assert len(audio.readframes(60)) == 40
        with pytest.raises(OSError, match="cannot seek"):
            audio.rewind()
        with pytest.raises(OSError, match="cannot seek"):
            audio.setpos(0)

    def test_the_parameters_come_from_the_header(self) -> None:
        audio = sunau.open(io.BytesIO(au_bytes(100)), "rb")

        assert audio.getparams() == (2, 2, 8000, 100, "NONE", "not compressed")
        assert audio.getparams().nframes == audio.getnframes()
        assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (2, 2, 8000)

    @pytest.mark.parametrize(
        ("encoding", "names"),
        [(1, ("ULAW", "CCITT G.711 u-law")), (27, ("ALAW", "CCITT G.711 A-law"))],
    )
    def test_the_compression_names(self, encoding: int, names: tuple[str, str]) -> None:
        audio = sunau.open(io.BytesIO(header(encoding=encoding)), "rb")

        assert (audio.getcomptype(), audio.getcompname()) == names

    def test_there_are_no_markers(self) -> None:
        audio = sunau.open(io.BytesIO(au_bytes(1)), "rb")

        assert audio.getmarkers() is None
        with pytest.raises(sunau.Error):
            audio.getmark(1)


@REQUIRES_SUNAU
class TestReadframesFollowsTheRequest:
    """`readframes(nframes)` | O(k·w) | O(k·w), O(nframes·w) from a file on
    disk | k = frames returned."""

    @pytest.mark.parametrize("frames", [1_000, 100_000, 1_000_000])
    def test_the_peak_is_the_block_returned(self, frames: int) -> None:
        audio = sunau.open(io.BytesIO(million_frames()), "rb")
        held: list[bytes] = []

        peak = peak_bytes(lambda: held.append(audio.readframes(frames)))

        assert len(held[0]) == 4 * frames
        assert abs(peak - 4 * frames) < 2_000, f"readframes({frames}) peaked at {peak}"

    def test_the_peak_does_not_depend_on_the_file(self) -> None:
        peaks = []
        for nframes in (10_000, 2_000_000):
            audio = sunau.open(io.BytesIO(au_bytes(nframes)), "rb")
            audio.readframes(1)
            peaks.append(peak_bytes(lambda a=audio: a.readframes(1_000)))

        assert max(peaks) < 6_000, peaks

    def test_a_file_on_disk_sizes_the_buffer_for_the_request(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "short.au"
        path.write_bytes(au_bytes(1_000))
        held: list[bytes] = []

        with sunau.open(str(path), "rb") as audio:
            peak = peak_bytes(lambda: held.append(audio.readframes(2_500_000)))

        assert len(held[0]) == 4_000
        assert peak > 9_000_000, f"readframes(2,500,000) of 1,000 frames peaked at {peak}"

    def test_it_returns_fewer_at_the_end_then_nothing(self) -> None:
        audio = sunau.open(io.BytesIO(au_bytes(10)), "rb")

        assert len(audio.readframes(7)) == 7 * 4
        assert len(audio.readframes(7)) == 3 * 4
        assert audio.readframes(7) == b""
        assert audio.tell() == 10

    def test_u_law_is_decoded_into_a_new_buffer(self) -> None:
        stream = CountingStream(au_bytes(1_000, nchannels=1, comptype="ULAW"))
        audio = sunau.open(stream, "rb")
        before = stream.bytes_read

        block = audio.readframes(100)

        assert audio.getsampwidth() == 2
        assert stream.bytes_read - before == 100
        assert len(block) == 200

    def test_a_law_is_returned_undecoded(self) -> None:
        stored = bytes(range(10))
        audio = sunau.open(io.BytesIO(header(encoding=27, data_size=10, nchannels=1) + stored))

        assert audio.getsampwidth() == 2
        assert audio.getnframes() == 10
        assert audio.readframes(10) == stored

    def test_an_unknown_length_reads_to_the_end(self) -> None:
        unknown = sunau.AUDIO_UNKNOWN_SIZE
        audio = sunau.open(io.BytesIO(header(data_size=unknown, nchannels=1) + bytes(2 * 300)))

        assert unknown == 0xFFFFFFFF
        assert audio.getnframes() == unknown
        assert len(audio.readframes(audio.getnframes())) == 600

    def test_uncompressed_samples_come_back_as_stored(self) -> None:
        stored = b"\x00\x01\xff\xfe\x12\x34"
        buffer = io.BytesIO()
        with sunau.open(buffer, "wb") as out:
            out.setparams((1, 2, 8000, 0, "NONE", ""))
            out.writeframes(stored)

        assert buffer.getvalue().endswith(stored)
        assert sunau.open(io.BytesIO(buffer.getvalue()), "rb").readframes(3) == stored


@REQUIRES_SUNAU
class TestSeekingIsImmediate:
    """`setpos(pos)`, `rewind()` | O(1) | O(1) | seek at once, reading nothing."""

    def test_setpos_seeks_once_and_reads_nothing(self) -> None:
        stream = CountingStream(au_bytes(1_000_000))
        audio = sunau.open(stream, "rb")
        read = stream.bytes_read

        audio.setpos(999_000)

        assert (stream.bytes_read, stream.seeks) == (read, 1)
        assert audio.tell() == 999_000

        assert len(audio.readframes(1_000)) == 4_000
        assert stream.bytes_read - read == 4_000
        assert stream.seeks == 1

    def test_rewind_seeks_once_and_reads_nothing(self) -> None:
        stream = CountingStream(au_bytes(1_000))
        audio = sunau.open(stream, "rb")
        audio.readframes(500)
        read = stream.bytes_read

        audio.rewind()

        assert (stream.bytes_read, stream.seeks) == (read, 1)
        assert audio.tell() == 0
        assert audio.readframes(1) == bytes(4)

    def test_setpos_rejects_a_position_past_the_end(self) -> None:
        audio = sunau.open(io.BytesIO(au_bytes(10)), "rb")

        audio.setpos(10)
        assert audio.readframes(1) == b""
        with pytest.raises(sunau.Error, match="not in range"):
            audio.setpos(11)


@REQUIRES_SUNAU
class TestWriteframesDoesNotCopy:
    """`writeframes(data)` | O(k·w) | O(1), O(k·w) u-law: written as given;
    a wrong header count costs a constant patch per call."""

    def test_bytes_reach_the_file_as_the_same_object(self) -> None:
        sink = RecordingSink()
        out = stereo_writer(sink)
        data = bytes(4 * 1_000)

        out.writeframes(data)

        assert any(item is data for item in sink.written)
        out.close()

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
        out.close()

    def test_a_u_law_writer_copies(self) -> None:
        sink = RecordingSink()
        out = sunau.open(sink, "wb")
        out.setparams((2, 2, 8000, 0, "ULAW", ""))
        out.writeframes(bytes(4))
        data = bytes(10_000_000)
        sink.forget()

        peak = peak_bytes(lambda: out.writeframes(data))

        assert peak > 4_000_000, f"a u-law writeframes of 10 MB peaked at only {peak}"
        assert max(map(len, sink.written)) == 5_000_000
        out.close()

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

        assert sink.seeks == 6
        out.close()
        assert sink.seeks == 6

    def test_an_undeclared_count_is_patched_every_call(self) -> None:
        sink = RecordingSink()
        out = stereo_writer(sink)

        for _ in range(3):
            out.writeframes(bytes(4 * 100))

        assert sink.seeks == 6
        out.close()
        assert sink.seeks == 8

    @pytest.mark.parametrize("frames", [100, 1_000_000])
    def test_a_wrong_header_costs_the_same_patch_per_call(self, frames: int) -> None:
        sink = RecordingSink()
        out = stereo_writer(sink)
        out.writeframes(bytes(4))
        data = bytes(4 * frames)

        before = sink.seeks
        out.writeframes(data)

        assert sink.seeks - before == 2
        out.close()

    def test_writeframesraw_leaves_the_patch_to_close(self) -> None:
        sink = RecordingSink()
        out = stereo_writer(sink)
        out.writeframesraw(bytes(4))
        out.writeframesraw(bytes(4 * 100))

        assert sink.seeks == 0
        out.close()
        assert sink.seeks == 2

    def test_writeframesraw_to_a_declared_count_needs_no_seek(self) -> None:
        sink = RecordingSink()
        out = stereo_writer(sink, nframes=300)

        for _ in range(3):
            out.writeframesraw(bytes(4 * 100))
        out.close()

        assert sink.seeks == 0

    def test_the_patched_header_reads_back(self) -> None:
        buffer = io.BytesIO()
        out = stereo_writer(buffer)
        out.writeframes(bytes(4 * 100))
        out.writeframes(bytes(4 * 100))
        out.close()

        assert sunau.open(io.BytesIO(buffer.getvalue()), "rb").getnframes() == 200


@REQUIRES_SUNAU
class TestWriterParameters:
    """`Au_write(f)` | O(1) writes nothing and starts as u-law; setters other
    than `setcomptype()` raise once frames are written; getters raise until set."""

    def test_building_a_writer_writes_nothing(self) -> None:
        sink = RecordingSink()

        out = sunau.open(sink, "wb")

        assert sink.written == []
        assert (out.getcomptype(), out.getcompname()) == ("ULAW", "CCITT G.711 u-law")
        out.setparams((2, 2, 8000, 0, "NONE", ""))
        out.writeframes(bytes(4))
        assert sink.written[0] == b".snd"
        out.close()

    def test_the_header_is_32_bytes(self) -> None:
        sink = RecordingSink()
        out = stereo_writer(sink)

        out.close()

        assert sink.size == 32

    @pytest.mark.parametrize(
        "setter",
        [
            lambda w: w.setnchannels(1),
            lambda w: w.setsampwidth(1),
            lambda w: w.setframerate(16000),
            lambda w: w.setnframes(5),
            lambda w: w.setparams((1, 1, 8000, 0, "NONE", "")),
        ],
    )
    def test_every_setter_but_setcomptype_raises_once_frames_are_written(self, setter: Any) -> None:
        out = stereo_writer(RecordingSink())
        out.writeframes(bytes(4))

        with pytest.raises(sunau.Error, match="cannot change parameters"):
            setter(out)
        out.close()

    def test_setcomptype_is_not_refused_but_the_header_keeps_the_first(self) -> None:
        buffer = io.BytesIO()
        out = stereo_writer(buffer)
        out.writeframes(bytes(4))

        out.setcomptype("ULAW", "")

        assert out.getcomptype() == "ULAW"
        out.writeframes(bytes(4))
        out.close()
        assert int.from_bytes(buffer.getvalue()[12:16], "big") == 3  # LINEAR_16
        assert len(buffer.getvalue()) == 32 + 4 + 2, "the second call was u-law encoded"

    def test_setters_reject_bad_values(self) -> None:
        out = sunau.open(RecordingSink(), "wb")

        with pytest.raises(sunau.Error):
            out.setnchannels(3)
        with pytest.raises(sunau.Error):
            out.setsampwidth(5)
        with pytest.raises(sunau.Error):
            out.setnframes(-1)
        for bad in ("ALAW", b"NONE"):
            with pytest.raises(sunau.Error, match="unknown compression type"):
                out.setcomptype(bad, "")
        for channels in (1, 2, 4):
            out.setnchannels(channels)
        for width in (1, 2, 3, 4):
            out.setsampwidth(width)
        out.setcomptype("NONE", "ignored")
        assert out.getcompname() == "not compressed"
        out.setparams((1, 1, 8000, 0, "NONE", ""))
        out.close()

    def test_getters_raise_until_set(self) -> None:
        out = sunau.open(RecordingSink(), "wb")

        for getter in (out.getnchannels, out.getsampwidth, out.getframerate, out.getparams):
            with pytest.raises(sunau.Error):
                getter()
        with pytest.raises(sunau.Error, match="not specified"):
            out.writeframes(bytes(4))
        out.setsampwidth(2)
        with pytest.raises(sunau.Error, match="sample width not specified"):
            out.getsampwidth()
        out.setframerate(8000)
        assert out.getsampwidth() == 2
        out.setnchannels(1)
        assert out.getparams() == (1, 2, 8000, 0, "ULAW", "CCITT G.711 u-law")
        out.setcomptype("NONE", "")
        out.close()

    def test_getparams_needs_channels_and_rate_only(self) -> None:
        out = sunau.open(RecordingSink(), "wb")
        out.setnchannels(1)
        out.setframerate(8000)

        assert out.getparams().sampwidth == 0
        out.setsampwidth(1)
        out.setcomptype("NONE", "")
        out.close()

    def test_tell_and_getnframes_count_frames_written(self) -> None:
        out = stereo_writer(RecordingSink(), nframes=1_000)

        assert (out.tell(), out.getnframes()) == (0, 0)
        out.writeframesraw(bytes(4 * 30))
        assert (out.tell(), out.getnframes()) == (30, 30)
        out.close()

    @pytest.mark.parametrize(
        ("sampwidth", "comptype", "encoding"),
        [(1, "NONE", 2), (2, "NONE", 3), (3, "NONE", 4), (4, "NONE", 5), (2, "ULAW", 1)],
    )
    def test_the_header_names_the_encoding(
        self, sampwidth: int, comptype: str, encoding: int
    ) -> None:
        buffer = io.BytesIO()
        with sunau.open(buffer, "wb") as out:
            out.setparams((1, sampwidth, 8000, 0, comptype, ""))

        assert int.from_bytes(buffer.getvalue()[12:16], "big") == encoding


@REQUIRES_SUNAU
class TestUnseekableOutput:
    """A declared frame count written raw needs only `write()` and `flush()`."""

    def test_a_declared_length_writes_to_a_write_only_object(self) -> None:
        sink = WriteOnly()
        with sunau.open(sink, "wb") as out:
            out.setparams((2, 2, 8000, 200, "NONE", ""))
            out.writeframesraw(bytes(4 * 100))
            out.writeframesraw(bytes(4 * 100))

        assert sink.size == 32 + 800

    def test_close_needs_flush(self) -> None:
        out = sunau.open(NoFlush(), "wb")
        out.setparams((2, 2, 8000, 1, "NONE", ""))
        out.writeframesraw(bytes(4))

        with pytest.raises(AttributeError, match="flush"):
            out.close()

    def test_an_undeclared_length_cannot_be_patched(self) -> None:
        out = sunau.open(WriteOnly(), "wb")
        out.setparams((2, 2, 8000, 0, "NONE", ""))
        out.writeframesraw(bytes(4))

        with pytest.raises(OSError, match="cannot seek"):
            out.close()


@REQUIRES_SUNAU
class TestOpenAndClose:
    """`sunau.open(f, mode=None)`: the mode comes from `f.mode`, else `'rb'`;
    `close()` closes only a file opened by name."""

    def test_the_mode_comes_from_the_file(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "a.au"
        path.write_bytes(au_bytes(3))

        with open(path, "rb") as handle:
            assert isinstance(sunau.open(handle), sunau.Au_read)
        with open(tmp_path / "b.au", "wb") as handle:
            writer = sunau.open(handle)
            assert isinstance(writer, sunau.Au_write)
            writer.setparams((1, 1, 8000, 0, "NONE", ""))
            writer.close()

    def test_without_a_mode_attribute_it_reads(self) -> None:
        assert isinstance(sunau.open(io.BytesIO(au_bytes(3))), sunau.Au_read)
        assert isinstance(sunau.open(io.BytesIO(au_bytes(3)), "r"), sunau.Au_read)
        assert isinstance(sunau.Au_read(io.BytesIO(au_bytes(3))), sunau.Au_read)

    def test_an_unknown_mode_raises(self) -> None:
        with pytest.raises(sunau.Error, match="mode must be"):
            sunau.open(io.BytesIO(), "ab")

    def test_close_leaves_a_file_object_it_was_handed_open(self) -> None:
        source = io.BytesIO(au_bytes(3))
        sunau.open(source, "rb").close()
        target = io.BytesIO()
        writer = sunau.open(target, "w")
        writer.setparams((1, 1, 8000, 0, "NONE", ""))
        writer.close()

        assert not source.closed
        assert not target.closed

    def test_close_closes_a_file_it_opened(self, tmp_path: pathlib.Path) -> None:
        path = str(tmp_path / "a.au")
        writer = sunau.open(path, "wb")
        written = writer._file
        writer.setparams((1, 1, 8000, 0, "NONE", ""))
        writer.close()
        reader = sunau.open(path, "rb")
        read = reader.getfp()
        reader.close()

        assert written.closed
        assert read.closed


@REQUIRES_SUNAU
class TestByteOrderAndConstants:
    """Uncompressed samples are stored as given; u-law converts from and to
    native order. The constants' values."""

    def test_u_law_round_trips_in_native_order(self) -> None:
        samples = array.array("h", [0, 1000, -1000, 32000])
        buffer = io.BytesIO()
        with sunau.open(buffer, "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(8000)
            out.writeframes(samples)

        decoded = array.array("h", sunau.open(io.BytesIO(buffer.getvalue())).readframes(4))

        assert len(buffer.getvalue()) == 32 + 4
        assert decoded != samples
        assert all(abs(a - b) < 1_000 for a, b in zip(decoded, samples, strict=True))

    def test_the_magic_is_snd(self) -> None:
        assert sunau.AUDIO_FILE_MAGIC == int.from_bytes(b".snd", "big")

    def test_the_supported_encodings_open(self) -> None:
        for name in ("MULAW_8", "LINEAR_8", "LINEAR_16", "LINEAR_24", "LINEAR_32", "ALAW_8"):
            encoding = getattr(sunau, f"AUDIO_FILE_ENCODING_{name}")
            assert sunau.open(io.BytesIO(header(encoding=encoding))).getnframes() == 0


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
        [sys.executable, "-W", "ignore::DeprecationWarning", str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess and asserts its own result, on
    the versions that still have the module."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        assert len(_blocks()) == EXPECTED_BLOCKS

    @REQUIRES_SUNAU
    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []
        ran = 0
        for line, source in _blocks():
            ran += 1
            workdir = tmp_path / f"block{line}"
            workdir.mkdir()
            result = _run_block(source, workdir)
            if result.returncode != 0 or result.stderr:
                failures.append(f"{PAGE.name}:{line}\n{result.stderr.strip()}")

        assert ran == EXPECTED_BLOCKS
        assert not failures, "\n\n".join(failures)

    @REQUIRES_SUNAU
    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "frames == 10_000" in s)
        mutated = source.replace("frames == 10_000", "frames == 9_999", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
