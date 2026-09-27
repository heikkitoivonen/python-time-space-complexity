"""Tests for docs/stdlib/aifc.md.

The page prices the module a call at a time: opening walks every chunk header
in the file, `readframes()` returns the frames asked for, and `writeframes()`
passes its argument to the file. Those claims are settled by observation
rather than timing: a stream wrapper counts the bytes read and the seeks made,
a sink records the objects it is handed and the seeks it takes, a counting id
records the comparisons a marker lookup makes, and traced allocation separates
a copy of the frames from none by orders of magnitude.

`aifc` exists on Python 3.10 to 3.12 and is gone from 3.13, so every runtime
test is skipped on 3.13 and later; there, only the availability boundary and
the page's block count are checked. The module is identical on 3.11 and 3.12
(`Lib/aifc.py` at v3.11.0 and v3.12.12); 3.10 lacks the deprecation warning
and the `sowt` compression type, both of which are asserted on each side of
the boundary.

Measurement scope:

* Opening a file reads the same number of bytes, under 200, whether it holds
  1,000 frames or 1,000,000. With 10 and 1,000 small chunks after the sound
  data, a seekable stream makes one seek per chunk in the file and reads only
  their 8-byte headers, so the walk runs to the end of the file rather than
  stopping at `SSND`. With 10 and 1,000 markers the bytes read grow by the
  `MARK` chunk's size and `getmarkers()` returns all of them. An unseekable
  stream reads a 4,000,000-byte file in full with a traced peak under 100 KB,
  and the first `readframes()` raises `OSError`.
* `readframes(k)` on 2-channel 16-bit audio peaks within 2 KB of `4·k` bytes
  for k of 1,000, 100,000 and 1,000,000, and `readframes(1000)` peaks below
  6 KB on both a 10,000- and a 2,000,000-frame file. At the end of the data it
  returns fewer frames, then `b''`. A `ulaw` file returns twice the bytes it
  read from the stream, a decoded buffer rather than the bytes read.
* `setpos()` and `rewind()` read nothing and seek nothing; the next
  `readframes(1000)` makes at most two seeks and reads 4,000 bytes, 999,000
  frames into the file.
* `getmark()` and `setmark()` are counted by an `int` subclass whose `__eq__`
  records each call: looking up the last of 10 and 1,000 markers makes 10 and
  1,000 comparisons, the first makes one, and `setmark()` with a new id makes
  one per existing marker. `getmarkers()` returns the same list object on
  every call, reader and writer, and `None` when there are none.
* `writeframes()` hands a `bytes` argument to the file as the same object, and
  its traced peak stays under 100 KB for 10,000,000 bytes, as does that of a
  10,000,000-byte `array.array`; a `ulaw` writer peaks above 4,000,000 bytes
  for the same input, the encoded copy. When the frames written so far differ
  from the header's count, each call makes the same four seeks at 100 frames
  and 1,000,000; a declared count of 300 written as three calls of 100 costs
  twelve, and as one call of 300 none. The first call without a declared
  count, an even number of bytes, sets the header from its own length and
  makes none.
  `writeframesraw()` makes none; `close()` then patches once, or not at all
  when the declared count is right, and always when there are markers.
* Building an `Aifc_write` writes nothing; the first frames bring the header,
  54 bytes after `aiff()` and more for AIFF-C. A file name ending in `.aiff`
  writes `AIFF`, and `.aifc` or `.aif` write `AIFC`. Setters, `aiff()` and
  `aifc()` raise `aifc.Error` once frames are written, and setters for a bad
  value; getters raise until set, `getparams()` until channels, width and
  rate are set, and `writeframes()` with nothing set; `getcomptype()` and `getcompname()` default to `b'NONE'` and
  `b'not compressed'`; `getnframes()` and `tell()` count frames written. A
  declared length written raw to a write-only object never seeks, and markers
  written to one raise at `close()`.
* `open()` is asserted to pick its mode from `file.mode`, to default to
  `'rb'`, and to reject any other mode; `close()` is asserted to close a file
  object it was handed, for reader and writer.
* Uncompressed samples are asserted to read back as the bytes stored, which
  the writer is asserted to store as given. An AIFF file reads back as
  `b'NONE'` and `b'not compressed'`. A file that does not start with
  `FORM`, a `FORM` of another type, one without `SSND` and one with an
  unknown compression type raise `aifc.Error`. `sowt` reads and writes on
  3.11+, storing the samples byte-swapped and returning them as written, and
  raises `aifc.Error` on 3.10; importing warns on 3.11+ and not on
  3.10.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* The module is removed from Python 3.13, so no claim on the page is checked
  on 3.13 or 3.14; the removal itself is the availability test.
* The per-chunk cost of skipping on a seekable stream is one `seek()`; what
  that `seek()` costs is the file object's business and is not measured.
* `Aifc_read.getfp()`, `Aifc_read.initfp()` and `Aifc_write.initfp()` exist
  at runtime but are not in the official documentation, so the page leaves
  them out.
* The byte order of decoded `ulaw`, `alaw` and `G722` samples, which comes
  from `audioop` rather than the file, and the frame count `readframes()`
  returns for `G722`, are not asserted: the page scopes frame counts,
  positions and byte order to uncompressed files. `G722` decodes with state
  that `setpos()` and `rewind()` do not reset.
* The O(k·w) cost of `array.array` construction and `byteswap()` in the
  Common Patterns example is priced on docs/stdlib/array.md, not here. The
  removal of `sunau` and `audioop` in 3.13, named under Related Modules, comes
  from PEP 594 and the official 3.13 What's New.
* Sample widths other than 1 and 2 bytes, channel counts above 2, `alaw` and
  `G722` space, odd-sized chunks, and negative `readframes()` counts are not
  varied.
"""

from __future__ import annotations

import array
import functools
import importlib
import importlib.util
import io
import pathlib
import re
import struct
import subprocess
import sys
import textwrap
import tracemalloc
import warnings
from collections.abc import Callable
from typing import Any, ClassVar

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "aifc.md"
EXPECTED_BLOCKS = 7

aifc: Any = None
if sys.version_info < (3, 13):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        aifc = importlib.import_module("aifc")

REQUIRES_AIFC = pytest.mark.skipif(aifc is None, reason="aifc was removed in Python 3.13")
NONE = (b"NONE", b"not compressed")


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class KeepOpen(io.BytesIO):
    """A `BytesIO` that survives `close()`, which aifc calls on any file it is given."""

    def close(self) -> None:
        pass


def aifc_bytes(
    nframes: int,
    nchannels: int = 2,
    sampwidth: int = 2,
    comptype: bytes = b"NONE",
    markers: int = 0,
) -> bytes:
    """An AIFF-C file of `nframes` silent frames with `markers` markers."""
    buffer = KeepOpen()
    out = aifc.open(buffer, "wb")
    out.setparams((nchannels, sampwidth, 8000, 0, comptype, b"x"))
    for index in range(markers):
        out.setmark(index + 1, index, b"m")
    out.writeframes(bytes(nframes * nchannels * sampwidth))
    out.close()
    return buffer.getvalue()


@functools.cache
def million_frames() -> bytes:
    return aifc_bytes(1_000_000)


def with_trailing_chunks(raw: bytes, bodies: list[bytes]) -> bytes:
    """Append one chunk per body after the sound data, fixing the FORM size."""
    appended = b"".join(b"junk" + struct.pack(">L", len(body)) + body for body in bodies)
    out = raw + appended
    return out[:4] + struct.pack(">L", len(out) - 8) + out[8:]


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
        self.closed = False
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

    def close(self) -> None:
        self.closed = True

    def forget(self) -> None:
        self.written.clear()


class WriteOnly:
    """Accepts writes and nothing else, like a pipe with no `tell()`."""

    def __init__(self) -> None:
        self.size = 0

    def write(self, data: Any) -> int:
        self.size += len(data)
        return len(data)

    def close(self) -> None:
        pass


class CountingId(int):
    """A marker id that counts the equality tests made against it."""

    calls: ClassVar[int] = 0

    def __eq__(self, other: object) -> bool:
        CountingId.calls += 1
        return int(self) == other

    __hash__ = int.__hash__


def stereo_writer(sink: Any, nframes: int = 0) -> Any:
    out = aifc.open(sink, "wb")
    out.setparams((2, 2, 8000, nframes, *NONE))
    return out


class TestAvailability:
    """The page's scope: present on 3.10 to 3.12, removed from 3.13."""

    def test_the_module_exists_only_before_313(self) -> None:
        found = importlib.util.find_spec("aifc") is not None

        assert found == (sys.version_info < (3, 13))

    @REQUIRES_AIFC
    def test_importing_warns_from_311(self) -> None:
        result = subprocess.run(
            [sys.executable, "-W", "error::DeprecationWarning", "-c", "import aifc"],
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


@REQUIRES_AIFC
class TestOpeningWalksEveryChunkHeader:
    """`aifc.open(file, 'rb')` | O(c + m) | O(m) | reads every chunk header to
    the end of the file, seeking past the bodies, and keeps the markers."""

    def test_the_bytes_read_do_not_depend_on_the_audio_length(self) -> None:
        read = {}
        for nframes in (1_000, 1_000_000):
            stream = CountingStream(aifc_bytes(nframes))

            audio = aifc.open(stream, "rb")

            assert audio.getnframes() == nframes
            read[nframes] = stream.bytes_read

        assert read[1_000] == read[1_000_000] < 200

    def test_a_seekable_stream_seeks_once_per_chunk_to_the_end(self) -> None:
        base = CountingStream(aifc_bytes(10))
        aifc.open(base, "rb")
        seeks = {}
        for chunks in (10, 1_000):
            raw = with_trailing_chunks(aifc_bytes(10), [b"x" * 100] * chunks)
            stream = CountingStream(raw)

            assert aifc.open(stream, "rb").getnframes() == 10
            assert stream.bytes_read == base.bytes_read + 8 * chunks, "a chunk body was read"
            seeks[chunks] = stream.seeks - base.seeks

        assert seeks == {10: 10, 1_000: 1_000}

    def test_the_markers_are_parsed_and_kept(self) -> None:
        read = {}
        for markers in (10, 1_000):
            stream = CountingStream(aifc_bytes(10, markers=markers))

            audio = aifc.open(stream, "rb")

            assert len(audio.getmarkers()) == markers
            assert audio.getmark(markers) == (markers, markers - 1, b"m")
            read[markers] = stream.bytes_read

        assert read[1_000] - read[10] == 990 * 8

    def test_an_unseekable_stream_is_read_to_the_end_and_cannot_be_read_from(self) -> None:
        raw = aifc_bytes(1_000_000)
        stream = CountingStream(raw, seekable=False)
        opened: list[Any] = []

        peak = peak_bytes(lambda: opened.append(aifc.open(stream, "rb")))

        assert stream.bytes_read == len(raw) > 4_000_000
        assert peak < 100_000, f"opening an unseekable stream peaked at {peak}"
        with pytest.raises(OSError):
            opened[0].readframes(1)

    def test_the_parameters_come_from_the_header(self) -> None:
        audio = aifc.open(io.BytesIO(aifc_bytes(100)), "rb")

        assert audio.getparams() == (2, 2, 8000, 100, b"NONE", b"x")
        assert audio.getparams().nframes == audio.getnframes()
        assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (2, 2, 8000)
        assert (audio.getcomptype(), audio.getcompname()) == (b"NONE", b"x")

    def test_an_aiff_file_reports_no_compression(self) -> None:
        sink = KeepOpen()
        out = stereo_writer(sink)
        out.aiff()
        out.writeframes(bytes(4))
        out.close()

        audio = aifc.open(io.BytesIO(sink.getvalue()), "rb")

        assert sink.getvalue()[8:12] == b"AIFF"
        assert (audio.getcomptype(), audio.getcompname()) == NONE


@REQUIRES_AIFC
class TestReadframesFollowsTheRequest:
    """`readframes(nframes)` | O(k·w) | O(k·w) | k = frames returned."""

    @pytest.mark.parametrize("frames", [1_000, 100_000, 1_000_000])
    def test_the_peak_is_the_block_returned(self, frames: int) -> None:
        audio = aifc.open(io.BytesIO(million_frames()), "rb")
        audio.setpos(0)
        held: list[bytes] = []

        peak = peak_bytes(lambda: held.append(audio.readframes(frames)))

        assert len(held[0]) == 4 * frames
        assert abs(peak - 4 * frames) < 2_000, f"readframes({frames}) peaked at {peak}"

    def test_the_peak_does_not_depend_on_the_file(self) -> None:
        peaks = []
        for nframes in (10_000, 2_000_000):
            audio = aifc.open(io.BytesIO(aifc_bytes(nframes)), "rb")
            audio.readframes(1)
            peaks.append(peak_bytes(lambda a=audio: a.readframes(1_000)))

        assert max(peaks) < 6_000, peaks

    def test_it_returns_fewer_at_the_end_then_nothing(self) -> None:
        audio = aifc.open(io.BytesIO(aifc_bytes(10)), "rb")

        assert len(audio.readframes(7)) == 7 * 4
        assert len(audio.readframes(7)) == 3 * 4
        assert audio.readframes(7) == b""
        assert audio.tell() == 10

    def test_a_compressed_file_is_decoded_into_a_new_buffer(self) -> None:
        stream = CountingStream(aifc_bytes(1_000, nchannels=1, comptype=b"ulaw"))
        audio = aifc.open(stream, "rb")
        before = stream.bytes_read

        block = audio.readframes(100)

        assert audio.getsampwidth() == 2
        assert len(block) == 2 * (stream.bytes_read - before - 8) == 200, "8: the SSND offsets"

    def test_uncompressed_samples_come_back_as_stored(self) -> None:
        stored = b"\x00\x01\xff\xfe\x12\x34"
        buffer = KeepOpen()
        with aifc.open(buffer, "wb") as out:
            out.setparams((1, 2, 8000, 0, *NONE))
            out.writeframes(stored)

        assert stored in buffer.getvalue()
        assert aifc.open(io.BytesIO(buffer.getvalue()), "rb").readframes(3) == stored


@REQUIRES_AIFC
class TestSeekingIsDeferred:
    """`setpos(pos)`, `rewind()` | O(1) | O(1) | the next `readframes()` seeks."""

    def test_setpos_reads_and_seeks_nothing_until_the_next_read(self) -> None:
        stream = CountingStream(aifc_bytes(1_000_000))
        audio = aifc.open(stream, "rb")
        read, seeks = stream.bytes_read, stream.seeks

        audio.setpos(999_000)

        assert (stream.bytes_read, stream.seeks) == (read, seeks)
        assert audio.tell() == 999_000

        assert len(audio.readframes(1_000)) == 4_000
        assert stream.bytes_read - read - 8 == 4_000, "only the frames and the SSND offsets"
        assert 1 <= stream.seeks - seeks <= 2

    def test_rewind_is_deferred_too(self) -> None:
        stream = CountingStream(aifc_bytes(1_000))
        audio = aifc.open(stream, "rb")
        audio.readframes(500)
        read, seeks = stream.bytes_read, stream.seeks

        audio.rewind()

        assert (stream.bytes_read, stream.seeks) == (read, seeks)
        assert audio.tell() == 0
        assert audio.readframes(1) == bytes(4)
        assert 1 <= stream.seeks - seeks <= 2

    def test_setpos_rejects_a_position_past_the_end(self) -> None:
        audio = aifc.open(io.BytesIO(aifc_bytes(10)), "rb")

        audio.setpos(10)
        assert audio.readframes(1) == b""
        with pytest.raises(aifc.Error, match="not in range"):
            audio.setpos(11)


@REQUIRES_AIFC
class TestMarkers:
    """`getmark(id)`, `setmark(id, pos, name)` | O(m) | scan the markers in
    order; `getmarkers()` | O(1) | the list itself, or `None`."""

    @staticmethod
    def comparisons(call: Callable[[], Any]) -> int:
        CountingId.calls = 0
        call()
        return CountingId.calls

    @pytest.mark.parametrize("markers", [10, 1_000])
    def test_the_reader_scans_to_the_match(self, markers: int) -> None:
        audio = aifc.open(io.BytesIO(aifc_bytes(10, markers=markers)), "rb")

        assert self.comparisons(lambda: audio.getmark(CountingId(markers))) == markers
        assert self.comparisons(lambda: audio.getmark(CountingId(1))) == 1
        with pytest.raises(aifc.Error, match="does not exist"):
            audio.getmark(markers + 1)

    @pytest.mark.parametrize("markers", [10, 1_000])
    def test_the_writer_scans_to_set_and_to_look_up(self, markers: int) -> None:
        out = stereo_writer(RecordingSink())
        for index in range(1, markers + 1):
            out.setmark(index, index, b"m")

        assert self.comparisons(lambda: out.setmark(CountingId(markers + 1), 0, b"n")) == markers
        assert self.comparisons(lambda: out.getmark(CountingId(markers))) == markers
        assert len(out.getmarkers()) == markers + 1
        with pytest.raises(aifc.Error, match="does not exist"):
            out.getmark(markers + 2)
        out.close()

    def test_setting_an_existing_id_replaces_it(self) -> None:
        out = stereo_writer(RecordingSink())
        out.setmark(1, 0, b"a")
        out.setmark(2, 5, b"b")
        out.setmark(1, 9, b"c")

        assert out.getmarkers() == [(1, 9, b"c"), (2, 5, b"b")]
        out.close()

    def test_getmarkers_returns_the_list_itself(self) -> None:
        audio = aifc.open(io.BytesIO(aifc_bytes(10, markers=3)), "rb")
        out = stereo_writer(RecordingSink())
        out.setmark(1, 0, b"a")

        assert audio.getmarkers() is audio.getmarkers()
        assert out.getmarkers() is out.getmarkers()
        assert aifc.open(io.BytesIO(aifc_bytes(10)), "rb").getmarkers() is None
        assert stereo_writer(RecordingSink()).getmarkers() is None
        out.close()

    def test_setmark_rejects_bad_markers(self) -> None:
        out = stereo_writer(RecordingSink())

        for bad in ((0, 1, b"x"), (1, -1, b"x"), (1, 1, "x")):
            with pytest.raises(aifc.Error):
                out.setmark(*bad)
        out.close()

    def test_close_writes_every_marker(self) -> None:
        sizes = {}
        for markers in (10, 1_000):
            sink = RecordingSink()
            out = stereo_writer(sink)
            out.writeframes(bytes(4))
            for index in range(1, markers + 1):
                out.setmark(index, index, b"m")
            before = sink.position

            out.close()

            sizes[markers] = sink.position - before
        assert sizes[1_000] - sizes[10] == 990 * 8


@REQUIRES_AIFC
class TestWriteframesDoesNotCopy:
    """`writeframes(data)` | O(k·w) | O(1), O(k·w) compressed: written as
    given; a wrong header frame count costs a constant patch per call."""

    def test_bytes_reach_the_file_as_the_same_object(self) -> None:
        sink = RecordingSink()
        out = stereo_writer(sink)
        data = bytes(4 * 1_000)

        out.writeframes(data)

        assert sink.written[-1] is data
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

    def test_a_compressed_writer_copies(self) -> None:
        sink = RecordingSink()
        out = aifc.open(sink, "wb")
        out.setparams((2, 2, 8000, 0, b"ulaw", b"u-law"))
        out.writeframes(bytes(4))
        data = bytes(10_000_000)
        sink.forget()

        peak = peak_bytes(lambda: out.writeframes(data))

        assert peak > 4_000_000, f"a ulaw writeframes of 10 MB peaked at only {peak}"
        assert max(map(len, sink.written)) == 5_000_000
        out.close()

    def test_one_call_matching_the_declared_count_needs_no_seek(self) -> None:
        sink = RecordingSink()
        out = stereo_writer(sink, nframes=300)

        out.writeframes(bytes(4 * 300))
        out.close()

        assert sink.seeks == 0

    def test_the_first_call_without_a_declared_count_needs_no_seek(self) -> None:
        sink = RecordingSink()
        out = stereo_writer(sink)

        out.writeframes(bytes(4 * 300))
        out.close()

        assert sink.seeks == 0

    def test_a_declared_count_written_in_parts_is_patched_every_call(self) -> None:
        sink = RecordingSink()
        out = stereo_writer(sink, nframes=300)

        for _ in range(3):
            out.writeframes(bytes(4 * 100))

        assert sink.seeks == 12
        out.close()
        assert sink.seeks == 12

    @pytest.mark.parametrize("frames", [100, 1_000_000])
    def test_a_wrong_header_costs_the_same_patch_per_call(self, frames: int) -> None:
        sink = RecordingSink()
        out = stereo_writer(sink)
        out.writeframes(bytes(4))
        data = bytes(4 * frames)

        before = sink.seeks
        out.writeframes(data)

        assert sink.seeks - before == 4
        out.close()

    def test_writeframesraw_leaves_the_patch_to_close(self) -> None:
        sink = RecordingSink()
        out = stereo_writer(sink)
        out.writeframesraw(bytes(4))
        out.writeframesraw(bytes(4 * 100))

        assert sink.seeks == 0
        out.close()
        assert sink.seeks == 4

    def test_writeframesraw_to_a_declared_count_needs_no_seek(self) -> None:
        sink = RecordingSink()
        out = stereo_writer(sink, nframes=300)

        for _ in range(3):
            out.writeframesraw(bytes(4 * 100))
        out.close()

        assert sink.seeks == 0

    def test_markers_always_cost_a_patch(self) -> None:
        sink = RecordingSink()
        out = stereo_writer(sink, nframes=300)
        out.setmark(1, 0, b"a")

        out.writeframesraw(bytes(4 * 300))
        assert sink.seeks == 0
        out.close()

        assert sink.seeks == 4

    def test_the_patched_header_reads_back(self) -> None:
        buffer = KeepOpen()
        out = stereo_writer(buffer)
        out.writeframes(bytes(4 * 100))
        out.writeframes(bytes(4 * 100))
        out.close()

        assert aifc.open(io.BytesIO(buffer.getvalue()), "rb").getnframes() == 200


@REQUIRES_AIFC
class TestWriterParameters:
    """`Aifc_write(file)` | O(1) writes nothing; setters raise once frames are
    written; getters raise until set; `tell()`/`getnframes()` count frames written."""

    def test_building_a_writer_writes_nothing(self) -> None:
        sink = RecordingSink()

        out = stereo_writer(sink)

        assert sink.written == []
        out.writeframes(bytes(4))
        assert sink.written[0] == b"FORM"
        out.close()

    def test_aiff_writes_a_54_byte_header_and_aifc_a_longer_one(self) -> None:
        sizes = {}
        for form in ("aiff", "aifc"):
            sink = RecordingSink()
            out = stereo_writer(sink)
            getattr(out, form)()
            out.close()
            sizes[form] = sink.position

        assert sizes["aiff"] == 54
        assert sizes["aifc"] > 54

    @pytest.mark.parametrize(
        ("name", "form"), [("a.aiff", b"AIFF"), ("a.aifc", b"AIFC"), ("a.aif", b"AIFC")]
    )
    def test_the_file_name_picks_the_form(
        self, tmp_path: pathlib.Path, name: str, form: bytes
    ) -> None:
        path = tmp_path / name
        out = aifc.open(str(path), "wb")
        out.setparams((1, 2, 8000, 0, *NONE))
        out.close()

        assert path.read_bytes()[8:12] == form

    @pytest.mark.parametrize(
        "setter",
        [
            lambda w: w.aiff(),
            lambda w: w.aifc(),
            lambda w: w.setnchannels(1),
            lambda w: w.setsampwidth(1),
            lambda w: w.setframerate(16000),
            lambda w: w.setnframes(5),
            lambda w: w.setcomptype(*NONE),
            lambda w: w.setparams((1, 1, 8000, 0, *NONE)),
        ],
    )
    def test_every_setter_raises_once_frames_are_written(self, setter: Any) -> None:
        out = stereo_writer(RecordingSink())
        out.writeframes(bytes(4))

        with pytest.raises(aifc.Error, match="cannot change parameters"):
            setter(out)
        out.close()

    def test_setters_reject_bad_values(self) -> None:
        out = aifc.open(RecordingSink(), "wb")

        with pytest.raises(aifc.Error):
            out.setnchannels(0)
        with pytest.raises(aifc.Error):
            out.setsampwidth(5)
        with pytest.raises(aifc.Error):
            out.setframerate(0)
        with pytest.raises(aifc.Error):
            out.setcomptype(b"MP3 ", b"mp3")
        out.setnframes(-1)
        out.setparams((1, 1, 8000, 0, *NONE))
        out.close()

    def test_getters_raise_until_set(self) -> None:
        out = aifc.open(RecordingSink(), "wb")

        for getter in (out.getnchannels, out.getsampwidth, out.getframerate, out.getparams):
            with pytest.raises(aifc.Error):
                getter()
        with pytest.raises(aifc.Error, match="not specified"):
            out.writeframes(bytes(4))
        assert (out.getcomptype(), out.getcompname()) == NONE
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(8000)
        assert out.getparams() == (1, 2, 8000, 0, *NONE)
        out.close()

    def test_tell_and_getnframes_count_frames_written(self) -> None:
        out = stereo_writer(RecordingSink(), nframes=1_000)

        assert (out.tell(), out.getnframes()) == (0, 0)
        out.writeframesraw(bytes(4 * 30))
        assert (out.tell(), out.getnframes()) == (30, 30)
        assert out.getparams().nframes == 1_000
        out.close()


@REQUIRES_AIFC
class TestUnseekableOutput:
    """A declared frame count needs no seek; markers always need one."""

    def test_a_declared_length_writes_to_a_write_only_object(self) -> None:
        sink = WriteOnly()
        with aifc.open(sink, "wb") as out:
            out.aiff()
            out.setparams((2, 2, 8000, 200, *NONE))
            out.writeframesraw(bytes(4 * 100))
            out.writeframesraw(bytes(4 * 100))

        assert sink.size == 54 + 800

    def test_markers_cannot_be_written_to_one(self) -> None:
        out = aifc.open(WriteOnly(), "wb")
        out.setparams((2, 2, 8000, 1, *NONE))
        out.setmark(1, 0, b"a")
        out.writeframesraw(bytes(4))

        with pytest.raises((AttributeError, OSError)):
            out.close()


@REQUIRES_AIFC
class TestOpenAndClose:
    """`aifc.open(file, mode=None)`: the mode comes from `file.mode`, else
    `'rb'`; `close()` closes the file, including one passed in."""

    def test_the_mode_comes_from_the_file(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "a.aiff"
        path.write_bytes(aifc_bytes(3))

        with open(path, "rb") as handle:
            assert isinstance(aifc.open(handle), aifc.Aifc_read)
        with open(tmp_path / "b.aiff", "wb") as handle:
            writer = aifc.open(handle)
            assert isinstance(writer, aifc.Aifc_write)
            writer.setparams((1, 1, 8000, 0, *NONE))
            writer.close()

    def test_without_a_mode_attribute_it_reads(self) -> None:
        assert isinstance(aifc.open(io.BytesIO(aifc_bytes(3))), aifc.Aifc_read)
        assert isinstance(aifc.open(io.BytesIO(aifc_bytes(3)), "r"), aifc.Aifc_read)

    def test_an_unknown_mode_raises(self) -> None:
        with pytest.raises(aifc.Error, match="mode must be"):
            aifc.open(io.BytesIO(), "ab")

    def test_close_closes_a_file_object_it_was_handed(self) -> None:
        source = io.BytesIO(aifc_bytes(3))
        aifc.open(source, "rb").close()
        target = io.BytesIO()
        writer = aifc.open(target, "w")
        writer.setparams((1, 1, 8000, 0, *NONE))
        writer.close()

        assert source.closed
        assert target.closed


@REQUIRES_AIFC
class TestFormats:
    """`aifc.Error` for a file the module cannot read; `sowt` from 3.11."""

    def test_a_file_that_is_not_form_raises(self) -> None:
        with pytest.raises(aifc.Error, match="FORM"):
            aifc.open(io.BytesIO(b"RIFF" + bytes(40)), "rb")

    def test_a_form_of_another_type_raises(self) -> None:
        with pytest.raises(aifc.Error, match="not an AIFF"):
            aifc.open(io.BytesIO(b"FORM" + struct.pack(">L", 4) + b"WAVE"), "rb")

    def test_a_file_without_sound_data_raises(self) -> None:
        raw = aifc_bytes(0)
        ssnd = raw.index(b"SSND")
        truncated = raw[:ssnd]
        truncated = truncated[:4] + struct.pack(">L", len(truncated) - 8) + truncated[8:]

        with pytest.raises(aifc.Error, match="SSND chunk missing"):
            aifc.open(io.BytesIO(truncated), "rb")

    def test_an_unknown_compression_type_raises(self) -> None:
        raw = aifc_bytes(1).replace(b"NONE", b"MP3 ", 1)

        with pytest.raises(aifc.Error, match="unsupported compression type"):
            aifc.open(io.BytesIO(raw), "rb")

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="sowt from 3.11")
    def test_sowt_reads_and_writes_from_311(self) -> None:
        buffer = KeepOpen()
        with aifc.open(buffer, "wb") as out:
            out.setparams((1, 2, 8000, 0, b"sowt", b""))
            out.writeframes(b"\x00\x01\x02\x03")

        audio = aifc.open(io.BytesIO(buffer.getvalue()), "rb")

        assert buffer.getvalue().endswith(b"\x01\x00\x03\x02")
        assert audio.getcomptype() == b"sowt"
        assert audio.readframes(2) == b"\x00\x01\x02\x03"

    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="sowt from 3.11")
    def test_sowt_raises_before_311(self) -> None:
        out = aifc.open(RecordingSink(), "wb")
        with pytest.raises(aifc.Error, match="unsupported compression type"):
            out.setcomptype(b"sowt", b"")
        raw = aifc_bytes(1, nchannels=1).replace(b"NONE", b"sowt", 1)
        with pytest.raises(aifc.Error, match="unsupported compression type"):
            aifc.open(io.BytesIO(raw), "rb")
        out.setparams((1, 1, 8000, 0, *NONE))
        out.close()


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

    @REQUIRES_AIFC
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

    @REQUIRES_AIFC
    def test_the_runner_notices_a_broken_assertion(self, tmp_path: pathlib.Path) -> None:
        line, source = next((n, s) for n, s in _blocks() if "frames == 10_000" in s)
        mutated = source.replace("frames == 10_000", "frames == 9_999", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
