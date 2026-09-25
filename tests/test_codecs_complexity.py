"""Tests for docs/stdlib/codecs.md.

The page prices the standard text codecs as one pass over the input, the
registry as a cache in front of the search functions, and the incremental and
stream classes by the chunk, the tail they keep and the line they build. The
registry, laziness, buffering and error-handler rows are settled by
observation: a counting search function, a recording source or sink, a
counting handler, identity and the undecoded tail itself. Timing is used only
where the claim is a growth class, always as a ratio between two sizes.

Measurement scope:

* `codecs.encode()` and `codecs.decode()` are timed for utf-8, utf-16,
  latin-1, cp1252, utf-7 and unicode_escape at 10,000 and 1,000,000
  characters of mixed Latin-1 text; 100x the input must cost under 1,000x
  (quadratic would be 10,000x). `punycode` is timed at a fixed 2,000
  characters with one distinct non-ASCII character against 2,000 distinct
  ones (over 20x apart), and at 250 against 2,000 distinct characters (8x
  the input, over 25x the time; linear would be 8x, n·u 64x). `punycode`
  decoding of 5,000 against 160,000 repeated `é` must cost over 70x for 32x
  the input; linear would be 32x, and the measured ratio is about 140x.
* `lookup()` is observed through a registered counting search function:
  `My-Codec`, `my codec` and `MY_CODEC` reach it once, as `my_codec`, and
  return one object; an unknown name reaches it on every lookup; after
  `unregister()` of a registered unrelated function a cached name reaches it
  again, and after `unregister()` of a function never registered it does
  not;
  two registered functions are asked in registration order. `getencoder()`
  and the other five helpers are asserted to return the attributes of the
  cached `CodecInfo`.
* Incremental tails are read with `getstate()` while text mixing one- to
  four-byte UTF-8 characters is fed one byte at a time: under 4 bytes for
  utf-8, utf-16 and utf-32 throughout. UTF-7 is fed 10 bytes at a time
  through a 100-character run and keeps all 260 bytes before the run's end
  as its tail, emitting nothing. A timing test decodes 10,000 and 80,000
  CJK characters of UTF-7 in 64-byte chunks: 8x the input costs over 30x
  (linear would be 8x, quadratic 64x). A UTF-7 `StreamReader` reading 500
  and 4,000 such characters 64 bytes at a time costs over 25x for 8x.
* `iterencode()` and `iterdecode()` take nothing from a recording generator
  when called; `iterdecode()` takes one chunk per step while each gives
  output, and three chunks for a first step whose first two give none.
* `StreamWriter.writelines()` is observed to call `encode()` once, with the
  joined text.
* `StreamReader.readline()` is observed through a `str` subclass installed
  as `charbuffertype`, which counts the characters of every `splitlines()`
  on the line being built: 10x the line (200,000 to 2,000,000 characters)
  re-splits over 50x the characters (linear would be 10x, quadratic 100x).
  `io.TextIOWrapper.readline()` is timed on lines of 100,000 and 2,000,000
  characters and must cost under 100x for 20x the line (quadratic would
  be 400x). `read(size)` is observed to advance an ASCII stream by `size`
  bytes and a stream of three-byte characters by three reads of `size`
  bytes, `read(chars=k)` to consume the whole stream, and a second
  `read(chars=1)` over 2,000,000 buffered characters to peak over 1 MB, so
  the buffered characters are a term of the row; `read(2, 5)` to return
  five characters after taking six bytes, so `chars` sets the target and
  `size` the step; a `str` subclass installed as `charbuffertype` counts the
  characters each `+=` copies into the buffer, and `read(100, k)` copies
  over 40x as many for k = 80,000 as for k = 10,000 (linear would be 8x,
  quadratic 64x), against exactly k when `size` equals `chars`; and `readlines(sizehint)` to return every line.
  Iteration is observed to call `readline()` once per line. A one-character
  `readline()` after `read(chars=1)` peaks over 5x higher over 2,000,000
  buffered characters than over 200,000, which is the b term; the L·b cross
  term (one copy of the buffer per refill of a long line) is read from
  Lib/codecs.py and not measured.
* `StreamWriter.write()` and `writelines()` are observed through a recording
  stream: one `write()` each, `writelines()` with the joined text.
* `codecs.open()` is asserted to open the file in binary mode and return
  `'\\r\\n'` untranslated; its `DeprecationWarning` is asserted on 3.14+ and
  asserted absent before.
* A registered handler is counted: one call for a three-character
  unencodable run in ASCII, one call per lone surrogate in UTF-16, one call
  per undecodable byte in UTF-8. The built-in `*_errors` functions are
  asserted by output; each is timed on a one-character slice of a
  10-character and a 10,000,000-character object and must cost under 5x more
  for the large one. `replace`, `backslashreplace` and `xmlcharrefreplace`
  are timed on slices of 1,000 and 1,000,000 characters of one object and
  must cost between 20x and 20,000x more for the long one (measured about
  60x for `replace` and 1,000x for the others; quadratic would be
  1,000,000x).
* Charmap, helper-function and BOM rows are asserted by output. The UTF,
  ASCII, Latin-1, `unicode_escape` and `raw_unicode_escape` helper functions
  are each timed at 10,000 and
  1,000,000 characters and must cost under 1,000x for 100x the input.
  Every small timing repeats the call 50 times and keeps the fastest run.
* Every fenced Python block runs in its own subprocess with warnings raised
  as errors, and a mutated assertion in one of them is asserted to fail.

Not settled here:

* That the space of an encode or decode is O(n) is not traced; it follows
  from the output length, which the examples and tests assert.
* Codecs outside the standard library, and third-party search functions or
  error handlers, cost what they cost; the page prices only the call.
* `bz2_codec` and the CJK multibyte codecs are not timed. Of the Python-level
  codecs only `punycode` and `idna` are exercised, and `idna` only on short
  labels. `punycode` decoding is varied in length on one repeated character,
  not in character diversity.
* The O(1) registry rows treat the name's normalization as O(1): encoding
  names are short, and the name length is not varied. The k term of
  `unregister()` is read from Python/codecs.c, which clears the cache dict;
  it is not timed.
* `namereplace_errors` is not varied in the slice's length.
* `StreamRecoder` is observed to round-trip, not timed; its bounds follow
  from the reader, writer and codec it wraps, read from Lib/codecs.py.
* The Windows-only `mbcs_*`, `oem_*` and `code_page_*` functions are
  exercised by a test guarded on `sys.platform == "win32"`, which no run of
  this project performs; their O(n) bound is read from
  Modules/_codecsmodule.c and is not verified here.
"""

from __future__ import annotations

import codecs
import encodings.cp1252
import io
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import warnings
from collections.abc import Callable, Iterator
from functools import partial
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "codecs.md"
EXPECTED_BLOCKS = 12


def best_ns(func: Callable[[], Any], repeats: int = 5, inner: int = 1) -> float:
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


def growth(small: Callable[[], Any], large: Callable[[], Any]) -> float:
    """How many times `large` costs `small`; the small call is repeated to steady it."""
    return best_ns(large) / best_ns(small, inner=50)


def peak_above_baseline(func: Callable[[], Any]) -> int:
    """Traced peak while func runs, above what was allocated before it."""
    was_tracing = tracemalloc.is_tracing()
    tracemalloc.start()
    tracemalloc.reset_peak()
    try:
        before = tracemalloc.get_traced_memory()[0]
        func()
        return tracemalloc.get_traced_memory()[1] - before
    finally:
        if not was_tracing:
            tracemalloc.stop()


class RecordingStream:
    """A byte sink that records every write."""

    def __init__(self) -> None:
        self.writes: list[bytes] = []

    def write(self, data: bytes) -> int:
        self.writes.append(data)
        return len(data)


class TestEncodingIsLinear:
    """`codecs.encode` / `codecs.decode` | O(n) | O(n) for the standard text
    codecs; `punycode` is O(n·u)."""

    CODECS = ["utf-8", "utf-16", "latin-1", "cp1252", "utf-7", "unicode_escape"]

    def test_round_trips_and_output_lengths(self) -> None:
        text = "Hello, 世界"
        assert codecs.decode(codecs.encode(text), "utf-8") == text
        assert len(codecs.encode(text, "utf-16-le")) == 2 * len(text)
        assert len(codecs.encode(text, "utf-32-le")) == 4 * len(text)

    def test_decode_accepts_any_bytes_like_object(self) -> None:
        data = "é".encode()
        assert codecs.decode(bytearray(data), "utf-8") == "é"
        assert codecs.decode(memoryview(data), "utf-8") == "é"

    def test_a_decompressing_codec_returns_its_decompressed_size(self) -> None:
        packed = codecs.encode(b"a" * 1_000_000, "zlib_codec")

        assert len(packed) < 10_000
        assert len(codecs.decode(packed, "zlib_codec")) == 1_000_000

    @pytest.mark.timing
    @pytest.mark.parametrize("encoding", CODECS)
    def test_a_hundred_times_the_input_is_far_from_quadratic(self, encoding: str) -> None:
        texts = ["héllo wörld " * (size // 12) for size in (10_000, 1_000_000)]
        datas = [codecs.encode(text, encoding) for text in texts]

        ratios = {
            "encode": growth(*(partial(codecs.encode, text, encoding) for text in texts)),
            "decode": growth(*(partial(codecs.decode, data, encoding) for data in datas)),
        }

        for name, ratio in ratios.items():
            assert ratio < 1_000, f"{encoding} {name}: 100x the input cost x{ratio:.1f}"

    @pytest.mark.timing
    def test_punycode_grows_with_distinct_non_ascii_characters(self) -> None:
        one = "é" * 2_000
        distinct = "".join(chr(0x4E00 + index) for index in range(2_000))

        one_ns = best_ns(lambda: codecs.encode(one, "punycode"), 3)
        distinct_ns = best_ns(lambda: codecs.encode(distinct, "punycode"), 3)

        ratio = distinct_ns / one_ns
        assert ratio > 20, f"u = 2,000 against u = 1 at n = 2,000 cost only x{ratio:.1f}"

    @pytest.mark.timing
    def test_punycode_is_quadratic_on_varied_text(self) -> None:
        small = "".join(chr(0x4E00 + index) for index in range(250))
        large = "".join(chr(0x4E00 + index) for index in range(2_000))

        ratio = best_ns(lambda: codecs.encode(large, "punycode"), 3) / best_ns(
            lambda: codecs.encode(small, "punycode"), 3
        )

        assert ratio > 25, f"8x distinct characters cost x{ratio:.1f}; n·u predicts 64"

    @pytest.mark.timing
    def test_punycode_decoding_is_superlinear(self) -> None:
        small, large = (codecs.encode("é" * size, "punycode") for size in (5_000, 160_000))

        ratio = best_ns(partial(codecs.decode, large, "punycode"), 3) / best_ns(
            partial(codecs.decode, small, "punycode"), 3, inner=5
        )

        assert ratio > 70, f"32x the input cost x{ratio:.1f}; linear would be 32"

    def test_punycode_and_idna_outputs(self) -> None:
        assert codecs.encode("bücher", "punycode") == b"bcher-kva"
        assert codecs.decode(b"bcher-kva", "punycode") == "bücher"
        assert codecs.encode("bücher.example", "idna") == b"xn--bcher-kva.example"


class SearchRecorder:
    """A search function that records the names it is asked about."""

    def __init__(self, known: str) -> None:
        self.known = known
        self.asked: list[str] = []

    def __call__(self, name: str) -> codecs.CodecInfo | None:
        self.asked.append(name)
        return codecs.lookup("utf-8") if name == self.known else None


class TestLookupIsCached:
    """`lookup` | O(1) cached by normalized name, O(r) on a first lookup,
    misses never cached; `unregister` empties the cache."""

    @pytest.fixture
    def recorder(self) -> Iterator[SearchRecorder]:
        recorder = SearchRecorder("complexity_test_codec")
        codecs.register(recorder)
        yield recorder
        codecs.unregister(recorder)

    def test_spellings_that_normalize_alike_share_one_entry(self, recorder: SearchRecorder) -> None:
        first = codecs.lookup("Complexity-Test-Codec")

        assert codecs.lookup("complexity test codec") is first
        assert codecs.lookup("COMPLEXITY_TEST_CODEC") is first
        assert recorder.asked == ["complexity_test_codec"]

    def test_a_miss_is_asked_again_every_time(self, recorder: SearchRecorder) -> None:
        for _ in range(3):
            with pytest.raises(LookupError, match="unknown encoding"):
                codecs.lookup("complexity-test-missing")

        assert recorder.asked == ["complexity_test_missing"] * 3

    def test_unregister_empties_the_cache(self, recorder: SearchRecorder) -> None:
        codecs.lookup("complexity_test_codec")
        codecs.lookup("complexity_test_codec")
        assert recorder.asked == ["complexity_test_codec"]

        def unrelated(name: str) -> None:
            return None

        codecs.register(unrelated)
        codecs.unregister(unrelated)
        codecs.lookup("complexity_test_codec")

        assert recorder.asked == ["complexity_test_codec"] * 2

    def test_unregistering_an_unknown_function_keeps_the_cache(
        self, recorder: SearchRecorder
    ) -> None:
        codecs.lookup("complexity_test_codec")

        codecs.unregister(lambda name: None)
        codecs.lookup("complexity_test_codec")

        assert recorder.asked == ["complexity_test_codec"]

    def test_search_functions_are_asked_in_registration_order(self) -> None:
        order: list[str] = []

        def first(name: str) -> None:
            order.append("first")

        def second(name: str) -> None:
            order.append("second")

        codecs.register(first)
        codecs.register(second)
        try:
            with pytest.raises(LookupError):
                codecs.lookup("complexity-test-order")
        finally:
            codecs.unregister(first)
            codecs.unregister(second)

        assert order == ["first", "second"]

    def test_unregistering_removes_the_codec(self) -> None:
        recorder = SearchRecorder("complexity_test_gone")
        codecs.register(recorder)
        codecs.lookup("complexity_test_gone")

        codecs.unregister(recorder)

        with pytest.raises(LookupError):
            codecs.lookup("complexity_test_gone")

    def test_the_helpers_read_the_cached_codecinfo(self) -> None:
        info = codecs.lookup("utf-8")

        assert codecs.lookup("UTF-8") is info
        assert codecs.getencoder("utf-8") is info.encode
        assert codecs.getdecoder("utf-8") is info.decode
        assert codecs.getincrementalencoder("utf-8") is info.incrementalencoder
        assert codecs.getincrementaldecoder("utf-8") is info.incrementaldecoder
        assert codecs.getreader("utf-8") is info.streamreader
        assert codecs.getwriter("utf-8") is info.streamwriter

    def test_a_codec_without_an_incremental_class_raises(self) -> None:
        def search(name: str) -> codecs.CodecInfo | None:
            if name == "complexity_test_plain":
                return codecs.CodecInfo(codecs.utf_8_encode, codecs.utf_8_decode)
            return None

        codecs.register(search)
        try:
            with pytest.raises(LookupError):
                codecs.getincrementalencoder("complexity_test_plain")
            with pytest.raises(LookupError):
                codecs.getincrementaldecoder("complexity_test_plain")
        finally:
            codecs.unregister(search)


class TestCodecInfo:
    """`CodecInfo` unpacks as `(encode, decode, streamreader, streamwriter)`
    and carries the rest as attributes."""

    def test_it_unpacks_as_a_four_tuple(self) -> None:
        info = codecs.lookup("utf-8")

        encode, decode, reader, writer = info

        assert (encode, decode, reader, writer) == (
            info.encode,
            info.decode,
            info.streamreader,
            info.streamwriter,
        )
        assert info.name == "utf-8"

    def test_the_constructor_stores_what_it_is_given(self) -> None:
        info = codecs.CodecInfo(
            codecs.utf_8_encode,
            codecs.utf_8_decode,
            incrementalencoder=codecs.IncrementalEncoder,
            incrementaldecoder=codecs.IncrementalDecoder,
            name="demo",
        )

        assert len(info) == 4
        assert info.name == "demo"
        assert info.incrementalencoder is codecs.IncrementalEncoder
        assert info.incrementaldecoder is codecs.IncrementalDecoder
        assert info.streamreader is None and info.streamwriter is None


class TestCodecBase:
    """`Codec.encode` / `Codec.decode`: stateless, `(output, consumed)`; the
    base raises, and the stream classes subclass it."""

    def test_the_base_class_raises(self) -> None:
        with pytest.raises(NotImplementedError):
            codecs.Codec().encode("a")
        with pytest.raises(NotImplementedError):
            codecs.Codec().decode(b"a")

    def test_the_stream_classes_subclass_it(self) -> None:
        assert issubclass(codecs.StreamWriter, codecs.Codec)
        assert issubclass(codecs.StreamReader, codecs.Codec)
        with pytest.raises(NotImplementedError):
            codecs.StreamWriter(io.BytesIO()).encode("a")
        with pytest.raises(NotImplementedError):
            codecs.StreamReader(io.BytesIO()).decode(b"a")

    def test_a_codec_returns_output_and_length_consumed(self) -> None:
        assert codecs.getencoder("utf-8")("é") == (b"\xc3\xa9", 1)
        assert codecs.getdecoder("utf-8")(b"\xc3\xa9") == ("é", 2)


MIXED = "aé€😀" * 50  # one-, two-, three- and four-byte UTF-8 characters


class TestIncrementalTails:
    """`IncrementalDecoder.decode` | O(t + c): under 4 bytes of tail for the
    UTF-8, UTF-16 and UTF-32 decoders, the whole current run for UTF-7."""

    @pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-32"])
    def test_the_tail_stays_under_four_bytes(self, encoding: str) -> None:
        data = codecs.encode(MIXED, encoding)
        decoder = codecs.getincrementaldecoder(encoding)()
        pieces = []
        largest = 0

        for index in range(len(data)):
            pieces.append(decoder.decode(data[index : index + 1]))
            largest = max(largest, len(decoder.getstate()[0]))
        pieces.append(decoder.decode(b"", final=True))

        assert "".join(pieces) == MIXED
        assert 0 < largest < 4, f"{encoding} kept a {largest}-byte tail"

    def test_utf7_keeps_the_whole_run_as_its_tail(self) -> None:
        data = codecs.encode("世" * 100, "utf-7")
        assert len(data) == 269 and data.startswith(b"+") and data.endswith(b"-")
        decoder = codecs.getincrementaldecoder("utf-7")()

        outputs = [decoder.decode(data[start : start + 10]) for start in range(0, 260, 10)]

        assert set(outputs) == {""}
        assert len(decoder.getstate()[0]) == 260
        assert decoder.decode(data[260:], final=True) == "世" * 100

    @staticmethod
    def _chunked_decode(encoding: str, characters: int) -> Callable[[], str]:
        data = codecs.encode("世" * characters, encoding)
        chunks = [data[index : index + 64] for index in range(0, len(data), 64)]
        return lambda: "".join(codecs.iterdecode(chunks, encoding))

    @pytest.mark.timing
    def test_chunked_utf7_is_quadratic(self) -> None:
        small = best_ns(self._chunked_decode("utf-7", 10_000), 3)
        large = best_ns(self._chunked_decode("utf-7", 80_000), 3)

        ratio = large / small
        assert ratio > 30, f"8x a UTF-7 run in 64-byte chunks cost x{ratio:.1f}"

    @pytest.mark.timing
    def test_a_utf7_stream_reader_is_quadratic_too(self) -> None:
        small, large = (codecs.encode("世" * size, "utf-7") for size in (500, 4_000))

        def read(data: bytes) -> Callable[[], str]:
            return lambda: codecs.getreader("utf-7")(io.BytesIO(data)).read(64)

        ratio = best_ns(read(large), 3) / best_ns(read(small), 3, inner=5)

        assert ratio > 25, f"8x a UTF-7 run read 64 bytes at a time cost x{ratio:.1f}"

    def test_the_final_flag_rejects_an_unfinished_character(self) -> None:
        decoder = codecs.getincrementaldecoder("utf-8")()

        assert decoder.decode(b"\xe2\x82") == ""
        with pytest.raises(UnicodeDecodeError):
            decoder.decode(b"", final=True)

    def test_reset_and_setstate_move_the_tail(self) -> None:
        decoder = codecs.getincrementaldecoder("utf-8")()
        decoder.decode(b"\xe2\x82")
        state = decoder.getstate()

        decoder.reset()
        assert decoder.getstate() == (b"", 0)
        decoder.setstate(state)
        assert decoder.decode(b"\xac") == "€"

    def test_encoding_in_pieces_matches_one_call(self) -> None:
        encoder = codecs.getincrementalencoder("utf-16")()

        pieces = b"".join(encoder.encode(character) for character in MIXED)

        assert pieces + encoder.encode("", final=True) == codecs.encode(MIXED, "utf-16")
        assert encoder.getstate() == 0

    def test_resetting_an_encoder_restarts_it(self) -> None:
        encoder = codecs.getincrementalencoder("utf-16")()
        first = encoder.encode("a")

        encoder.reset()

        assert encoder.encode("a") == first == codecs.encode("a", "utf-16")
        encoder.setstate(0)

    def test_the_base_classes(self) -> None:
        with pytest.raises(NotImplementedError):
            codecs.IncrementalEncoder().encode("a")
        with pytest.raises(NotImplementedError):
            codecs.IncrementalDecoder().decode(b"a")
        assert codecs.IncrementalEncoder().getstate() == 0
        assert codecs.IncrementalDecoder().getstate() == (b"", 0)


class TestBufferedIncrementalClasses:
    """`BufferedIncrementalEncoder` / `BufferedIncrementalDecoder`: the tail
    kept from the last call is joined to the new input; the standard UTF
    decoders are built on the decoder."""

    class KeepLast(codecs.BufferedIncrementalDecoder):
        """Converts all but the last byte until `final`."""

        def _buffer_decode(self, input: Any, errors: str, final: bool) -> tuple[str, int]:
            consumed = len(input) if final else max(len(input) - 1, 0)
            return input[:consumed].decode("latin-1"), consumed

    class KeepLastText(codecs.BufferedIncrementalEncoder):
        """Converts all but the last character until `final`."""

        def _buffer_encode(self, input: str, errors: str, final: bool) -> tuple[bytes, int]:
            consumed = len(input) if final else max(len(input) - 1, 0)
            return input[:consumed].encode("latin-1"), consumed

    def test_the_decoder_joins_its_tail_to_the_input(self) -> None:
        decoder = self.KeepLast()

        assert decoder.decode(b"ab") == "a"
        assert decoder.getstate() == (b"b", 0)
        assert decoder.decode(b"cd") == "bc"
        assert decoder.decode(b"", final=True) == "d"
        decoder.setstate((b"x", 0))
        assert decoder.decode(b"", final=True) == "x"
        decoder.reset()
        assert decoder.getstate() == (b"", 0)

    def test_the_encoder_joins_its_tail_to_the_input(self) -> None:
        encoder = self.KeepLastText()

        assert encoder.encode("ab") == b"a"
        assert encoder.getstate() == "b"
        assert encoder.encode("c", final=True) == b"bc"
        encoder.setstate("z")
        assert encoder.encode("", final=True) == b"z"
        encoder.reset()
        assert encoder.getstate() == 0

    @pytest.mark.parametrize("encoding", ["utf-8", "utf-16", "utf-32", "utf-7"])
    def test_the_standard_utf_decoders_are_built_on_it(self, encoding: str) -> None:
        decoder = codecs.getincrementaldecoder(encoding)()
        assert isinstance(decoder, codecs.BufferedIncrementalDecoder)


class TestIteratingCodecsAreLazy:
    """`iterencode` / `iterdecode`: lazy, taking chunks only until they give
    output."""

    def test_iterdecode_takes_one_chunk_per_step(self) -> None:
        chunks = [b"caf\xc3", b"\xa9 \xe2\x82", b"\xac"]
        taken: list[bytes] = []

        def source() -> Iterator[bytes]:
            for chunk in chunks:
                taken.append(chunk)
                yield chunk

        decoded = codecs.iterdecode(source(), "utf-8")
        assert taken == []

        assert next(decoded) == "caf"
        assert taken == chunks[:1]
        assert next(decoded) == "é "
        assert taken == chunks[:2]
        assert list(decoded) == ["€"]

    def test_iterdecode_takes_chunks_until_they_give_output(self) -> None:
        chunks = [b"\xe2", b"\x82", b"\xac", b"x"]
        taken: list[bytes] = []

        def source() -> Iterator[bytes]:
            for chunk in chunks:
                taken.append(chunk)
                yield chunk

        decoded = codecs.iterdecode(source(), "utf-8")

        assert next(decoded) == "€"
        assert taken == chunks[:3]

    def test_iterencode_takes_one_chunk_per_step(self) -> None:
        taken: list[str] = []

        def source() -> Iterator[str]:
            for chunk in ("a", "é"):
                taken.append(chunk)
                yield chunk

        encoded = codecs.iterencode(source(), "utf-16")
        assert taken == []

        first = next(encoded)
        assert taken == ["a"]
        assert first + b"".join(encoded) == codecs.encode("aé", "utf-16")


class TestStreamReader:
    """`StreamReader`: construction reads nothing, `read(size)` takes `size`
    bytes, `chars` alone takes everything, `readline` is O(L²)."""

    def test_construction_reads_nothing(self) -> None:
        raw = io.BytesIO(b"abc")
        codecs.getreader("utf-8")(raw)
        assert raw.tell() == 0

    def test_read_size_bounds_what_it_takes(self) -> None:
        raw = io.BytesIO(b"x" * 100_000)
        reader = codecs.getreader("utf-8")(raw)

        assert reader.read(4) == "xxxx"
        assert raw.tell() == 4

    def test_read_size_takes_size_bytes_until_it_has_size_characters(self) -> None:
        raw = io.BytesIO(("€" * 100_000).encode())
        reader = codecs.getreader("utf-8")(raw)

        assert reader.read(4) == "€€€€"
        assert raw.tell() == 12

    def test_read_chars_alone_takes_the_whole_stream(self) -> None:
        raw = io.BytesIO(b"x" * 100_000)
        reader = codecs.getreader("utf-8")(raw)

        assert reader.read(chars=2) == "xx"
        assert raw.tell() == 100_000
        assert len(reader.read()) == 99_998

    def test_read_copies_the_characters_already_buffered(self) -> None:
        reader = codecs.getreader("utf-8")(io.BytesIO(b"x" * 2_000_000))
        reader.read(chars=1)

        taken: list[str] = []

        peak = peak_above_baseline(lambda: taken.append(reader.read(chars=1)))

        assert taken == ["x"]
        assert peak > 1_000_000, f"taking one buffered character peaked at {peak} bytes"

    def test_readline_copies_the_characters_already_buffered(self) -> None:
        peaks = []
        for buffered in (200_000, 2_000_000):
            reader = codecs.getreader("utf-8")(io.BytesIO(b"a\nb\n" + b"x" * buffered))
            assert reader.read(chars=1) == "a"
            lines: list[str] = []

            peaks.append(peak_above_baseline(lambda r=reader, out=lines: out.append(r.readline())))

            assert lines == ["\n"]

        assert peaks[1] > peaks[0] * 5, f"10x the buffer, one-character line: peaks {peaks}"

    @staticmethod
    def _characters_gathered(total: int, size: int) -> int:
        """Characters copied into the buffer by one `read(size, total)`."""
        copied = 0

        class Counting(str):
            def __add__(self, other: str) -> Counting:
                nonlocal copied
                result = Counting(str.__add__(self, other))
                copied += len(result)
                return result

        class Reader(codecs.getreader("utf-8")):  # type: ignore[misc]
            charbuffertype = Counting

        assert Reader(io.BytesIO(b"x" * total)).read(size, total) == "x" * total
        return copied

    def test_chars_above_size_re_copies_what_it_gathered(self) -> None:
        small = self._characters_gathered(10_000, 100)
        large = self._characters_gathered(80_000, 100)

        ratio = large / small
        assert ratio > 40, f"8x the characters at size=100 copied x{ratio:.1f}; linear is 8"
        assert self._characters_gathered(80_000, 80_000) == 80_000

    def test_chars_is_the_target_and_size_the_step(self) -> None:
        raw = io.BytesIO(b"abcdefghij")
        reader = codecs.getreader("utf-8")(raw)

        assert reader.read(2, 5) == "abcde"
        assert raw.tell() == 6

    def test_readlines_ignores_sizehint(self) -> None:
        reader = codecs.getreader("utf-8")(io.BytesIO(b"a\nb\nc\n"))
        assert reader.readlines(1) == ["a\n", "b\n", "c\n"]

    def test_iteration_is_one_readline_per_line(self) -> None:
        calls = []
        base = codecs.getreader("utf-8")

        class Counting(base):  # type: ignore[misc, valid-type]
            def readline(self, size: Any = None, keepends: bool = True) -> str:
                calls.append(size)
                return super().readline(size, keepends)

        lines = list(Counting(io.BytesIO(b"a\nb\nc\n")))

        assert lines == ["a\n", "b\n", "c\n"]
        assert len(calls) == 4  # three lines, then the empty read that stops iteration

    def test_reset_and_seek_drop_the_buffers(self) -> None:
        raw = io.BytesIO(b"abcdef")
        reader = codecs.getreader("utf-8")(raw)
        reader.read(chars=1)

        reader.reset()
        assert reader.read() == ""
        reader.seek(0)
        assert reader.read() == "abcdef"

    @staticmethod
    def _characters_split(length: int) -> int:
        """Characters `readline()` re-splits while reading one line of `length`.

        `charbuffertype` seeds the line that `readline()` accumulates, so a
        `str` subclass there sees every `splitlines()` call on it.
        """
        total = 0

        class Counting(str):
            def __add__(self, other: str) -> Counting:
                return Counting(str.__add__(self, other))

            def splitlines(self, keepends: bool = False) -> list[str]:
                nonlocal total
                total += len(self)
                return str.splitlines(self, keepends)

        class Reader(codecs.getreader("utf-8")):  # type: ignore[misc]
            charbuffertype = Counting

        line = Reader(io.BytesIO(b"x" * length + b"\n")).readline()
        assert line == "x" * length + "\n"
        return total

    def test_readline_re_splits_the_line_on_every_refill(self) -> None:
        small = self._characters_split(200_000)
        large = self._characters_split(2_000_000)

        ratio = large / small
        assert ratio > 50, f"10x the line re-split x{ratio:.1f} the characters ({small}, {large})"

    @pytest.mark.timing
    def test_textiowrapper_readline_is_linear(self) -> None:
        datas = [b"x" * size + b"\n" for size in (100_000, 2_000_000)]

        def wrapper(data: bytes) -> Callable[[], str]:
            return lambda: io.TextIOWrapper(io.BytesIO(data), encoding="utf-8").readline()

        ratio = best_ns(wrapper(datas[1]), 5) / best_ns(wrapper(datas[0]), 5)

        assert ratio < 100, f"20x the line cost TextIOWrapper x{ratio:.1f}; quadratic is 400"


class TestStreamWriter:
    """`StreamWriter.write` encodes then writes once; `writelines` joins first."""

    def test_write_is_one_stream_write(self) -> None:
        raw = RecordingStream()
        writer = codecs.getwriter("utf-16-le")(raw)  # type: ignore[arg-type]

        writer.write("hé")

        assert raw.writes == ["hé".encode("utf-16-le")]

    def test_writelines_joins_before_writing(self) -> None:
        raw = RecordingStream()
        encoded: list[str] = []
        base = codecs.getwriter("utf-8")

        class Recording(base):  # type: ignore[misc, valid-type]
            def encode(self, input: str, errors: str = "strict") -> tuple[bytes, int]:
                encoded.append(input)
                return super().encode(input, errors)

        Recording(raw).writelines(["a", "b", "c"])  # type: ignore[arg-type]

        assert encoded == ["abc"]
        assert raw.writes == [b"abc"]

    def test_reset_and_seek(self) -> None:
        raw = io.BytesIO()
        writer = codecs.getwriter("utf-16")(raw)
        writer.write("a")
        writer.seek(0)
        writer.reset()
        writer.write("b")

        assert raw.getvalue().startswith(codecs.BOM_UTF16)


class TestFileWrappers:
    """`codecs.open`, `StreamReaderWriter`, `EncodedFile` and `StreamRecoder`."""

    @pytest.fixture
    def path(self, tmp_path: pathlib.Path) -> pathlib.Path:
        target = tmp_path / "data.txt"
        target.write_bytes(b"one\r\ntwo\r\n")
        return target

    @staticmethod
    def _open(*args: Any, **kwargs: Any) -> Any:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            return codecs.open(*args, **kwargs)

    def test_codecs_open_uses_binary_mode_and_keeps_newlines(self, path: pathlib.Path) -> None:
        with self._open(str(path), encoding="utf-8") as f:
            assert isinstance(f, codecs.StreamReaderWriter)
            assert f.stream.mode == "rb"  # type: ignore[attr-defined]
            assert f.encoding == "utf-8"
            assert f.read() == "one\r\ntwo\r\n"

        with open(path, encoding="utf-8") as f:
            assert f.read() == "one\ntwo\n"

    def test_without_an_encoding_it_is_the_built_in_file(self, path: pathlib.Path) -> None:
        with self._open(str(path)) as f:
            assert isinstance(f, io.TextIOWrapper)

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="deprecated in 3.14")
    def test_codecs_open_is_deprecated(self, path: pathlib.Path) -> None:
        with pytest.warns(DeprecationWarning, match="codecs.open"):
            codecs.open(str(path), encoding="utf-8").close()

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="deprecated in 3.14")
    def test_codecs_open_is_not_deprecated_before_314(self, path: pathlib.Path) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            codecs.open(str(path), encoding="utf-8").close()

    def test_stream_reader_writer_forwards(self, path: pathlib.Path) -> None:
        with self._open(str(path), "r+", encoding="utf-8") as f:
            assert isinstance(f.reader, codecs.StreamReader)
            assert isinstance(f.writer, codecs.StreamWriter)
            assert f.readline() == "one\r\n"
            assert f.readlines() == ["two\r\n"]
            f.write("é")
            f.writelines(["x", "y"])
            f.seek(0)
            assert f.read() == "one\r\ntwo\r\néxy"
            f.reset()

    def test_encoded_file_recodes_both_ways(self) -> None:
        raw = io.BytesIO()
        recoder = codecs.EncodedFile(raw, "utf-8", "utf-16-le")
        assert isinstance(recoder, codecs.StreamRecoder)
        assert (recoder.data_encoding, recoder.file_encoding) == ("utf-8", "utf-16-le")

        recoder.write("é\n".encode())
        recoder.writelines([b"a\n", b"b\n"])
        assert raw.getvalue() == "é\na\nb\n".encode("utf-16-le")

        recoder.seek(0)
        assert recoder.readline() == "é\n".encode()
        assert recoder.read() == b"a\nb\n"
        recoder.seek(0)
        recoder.reset()
        assert recoder.readlines() == ["é\n".encode(), b"a\n", b"b\n"]


class TestErrorHandlers:
    """A registered handler is called once per reported error; the built-in
    `*_errors` functions cost the slice they replace."""

    @pytest.fixture
    def calls(self) -> list[tuple[int, int]]:
        recorded: list[tuple[int, int]] = []

        def handler(error: UnicodeError) -> tuple[str, int]:
            assert isinstance(error, (UnicodeEncodeError, UnicodeDecodeError))
            recorded.append((error.start, error.end))
            return "?", error.end

        codecs.register_error("complexity_test_counter", handler)
        assert codecs.lookup_error("complexity_test_counter") is handler
        return recorded

    def test_one_call_per_unencodable_run(self, calls: list[tuple[int, int]]) -> None:
        assert codecs.encode("héé€x", "ascii", "complexity_test_counter") == b"h?x"
        assert calls == [(1, 4)]

    def test_one_call_per_undecodable_byte(self, calls: list[tuple[int, int]]) -> None:
        assert codecs.decode(b"a\xff\xfeb", "utf-8", "complexity_test_counter") == "a??b"
        assert calls == [(1, 2), (2, 3)]

    def test_utf16_reports_each_lone_surrogate(self, calls: list[tuple[int, int]]) -> None:
        encoded = codecs.encode("\ud800\ud801", "utf-16-le", "complexity_test_counter")

        assert encoded == b"?\x00?\x00"
        assert calls == [(0, 1), (1, 2)]

    def test_an_unknown_name_raises(self) -> None:
        with pytest.raises(LookupError):
            codecs.lookup_error("complexity-test-no-such-handler")

    def test_the_built_in_functions(self) -> None:
        error = UnicodeEncodeError("ascii", "aé€b", 1, 3, "ordinal not in range(128)")

        assert codecs.xmlcharrefreplace_errors(error) == ("&#233;&#8364;", 3)
        assert codecs.backslashreplace_errors(error) == ("\\xe9\\u20ac", 3)
        assert codecs.namereplace_errors(error) == (
            "\\N{LATIN SMALL LETTER E WITH ACUTE}\\N{EURO SIGN}",
            3,
        )
        assert codecs.replace_errors(error) == ("??", 3)
        assert codecs.ignore_errors(error) == ("", 3)
        with pytest.raises(UnicodeEncodeError) as raised:
            codecs.strict_errors(error)
        assert raised.value is error
        assert codecs.lookup_error("strict") is codecs.strict_errors

    def test_replace_writes_one_character_for_a_decoding_slice(self) -> None:
        error = UnicodeDecodeError("utf-8", b"a\xff\xfe\xfdb", 1, 4, "invalid")

        assert codecs.replace_errors(error) == ("�", 4)
        assert codecs.backslashreplace_errors(error) == ("\\xff\\xfe\\xfd", 4)

    @pytest.mark.parametrize("name", ["xmlcharrefreplace", "namereplace"])
    def test_two_handle_encoding_errors_only(self, name: str) -> None:
        error = UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid")

        with pytest.raises(TypeError):
            getattr(codecs, f"{name}_errors")(error)

    @pytest.mark.timing
    @pytest.mark.parametrize(
        "name", ["replace", "backslashreplace", "xmlcharrefreplace", "namereplace", "ignore"]
    )
    def test_the_cost_follows_the_slice_not_the_object(self, name: str) -> None:
        handler = getattr(codecs, f"{name}_errors")
        small = UnicodeEncodeError("ascii", "é" * 10, 0, 1, "x")
        large = UnicodeEncodeError("ascii", "é" * 10_000_000, 0, 1, "x")

        ratio = best_ns(lambda: handler(large), inner=200) / best_ns(
            lambda: handler(small), inner=200
        )

        assert ratio < 5, f"{name}: a 10,000,000-character object cost x{ratio:.1f}"

    @pytest.mark.timing
    @pytest.mark.parametrize("name", ["replace", "backslashreplace", "xmlcharrefreplace"])
    def test_the_cost_grows_with_the_slice(self, name: str) -> None:
        handler = getattr(codecs, f"{name}_errors")
        text = "é" * 1_000_000
        short = UnicodeEncodeError("ascii", text, 0, 1_000, "x")
        long = UnicodeEncodeError("ascii", text, 0, 1_000_000, "x")

        ratio = best_ns(lambda: handler(long)) / best_ns(lambda: handler(short), inner=50)

        assert 20 < ratio < 20_000, f"{name}: 1,000x the slice cost x{ratio:.1f}"


class TestCharmaps:
    """Charmap tables are built in O(m) and used one lookup per unit."""

    def test_build_encode_and_decode(self) -> None:
        table = codecs.charmap_build("abc")

        assert codecs.charmap_encode("cab", "strict", table) == (b"\x02\x00\x01", 3)
        decoded = codecs.charmap_decode(b"\x02\x00", "strict", "abc")  # type: ignore[arg-type]
        assert decoded == ("ca", 2)

    def test_a_single_byte_code_page_is_a_charmap(self) -> None:
        assert len(encodings.cp1252.decoding_table) == 256
        rebuilt = codecs.charmap_build(encodings.cp1252.decoding_table)
        assert type(rebuilt) is type(encodings.cp1252.encoding_table)
        assert codecs.charmap_encode("€", "strict", rebuilt) == (b"\x80", 1)

    def test_identity_and_encoding_maps(self) -> None:
        # Neither helper is in the typeshed stubs.
        identity = codecs.make_identity_dict(range(3))  # type: ignore[attr-defined]
        encoding_map = codecs.make_encoding_map(  # type: ignore[attr-defined]
            {0x41: 0x41, 0x42: 0x41, 0x43: 0x43}
        )

        assert identity == {0: 0, 1: 1, 2: 2}
        assert encoding_map == {0x41: None, 0x43: 0x43}
        assert codecs.charmap_encode("C", "strict", encoding_map) == (b"C", 1)
        with pytest.raises(UnicodeEncodeError):
            codecs.charmap_encode("A", "strict", encoding_map)


HELPERS = [
    ("ascii", "ab"),
    ("latin_1", "aé"),
    ("utf_7", "a€"),
    ("utf_8", "a€"),
    ("utf_16", "a€"),
    ("utf_16_le", "a€"),
    ("utf_16_be", "a€"),
    ("utf_32", "a😀"),
    ("utf_32_le", "a😀"),
    ("utf_32_be", "a😀"),
    ("unicode_escape", "a\n€"),
    ("raw_unicode_escape", "a€"),
]


class TestHelperFunctions:
    """The undocumented `<codec>_encode` / `<codec>_decode` functions return
    `(output, length consumed)` and are linear."""

    @pytest.mark.parametrize(("name", "text"), HELPERS)
    def test_they_round_trip(self, name: str, text: str) -> None:
        encode = getattr(codecs, f"{name}_encode")
        decode = getattr(codecs, f"{name}_decode")

        encoded, consumed = encode(text)
        assert consumed == len(text)
        assert decode(encoded)[:2] == (text, len(encoded))

    def test_escape_and_readbuffer(self) -> None:
        assert codecs.escape_encode(b"a\n") == (b"a\\n", 2)
        assert codecs.escape_decode(b"a\\n") == (b"a\n", 3)
        assert codecs.readbuffer_encode(b"abc") == (b"abc", 3)
        assert codecs.readbuffer_encode("é") == (b"\xc3\xa9", 2)

    def test_the_ex_decoders_report_the_byte_order(self) -> None:
        assert codecs.utf_16_ex_decode(codecs.BOM_UTF16_LE + b"a\x00") == ("a", 4, -1)
        assert codecs.utf_16_ex_decode(codecs.BOM_UTF16_BE + b"\x00a") == ("a", 4, 1)
        assert codecs.utf_32_ex_decode(codecs.BOM_UTF32_LE + b"a\x00\x00\x00") == ("a", 8, -1)

    @pytest.mark.skipif(sys.platform != "win32", reason="Windows-only functions")
    def test_the_windows_code_page_functions(self) -> None:
        for name in ("mbcs", "oem"):
            encoded, consumed = getattr(codecs, f"{name}_encode")("abc")
            assert (encoded, consumed) == (b"abc", 3)
            assert getattr(codecs, f"{name}_decode")(b"abc")[:2] == ("abc", 3)
        encode, decode = (getattr(codecs, f"code_page_{op}") for op in ("encode", "decode"))
        assert encode(1252, "\u20ac") == (b"\x80", 1)
        assert decode(1252, b"\x80")[:2] == ("\u20ac", 1)

    @pytest.mark.timing
    @pytest.mark.parametrize(("name", "text"), HELPERS)
    def test_a_hundred_times_the_input_is_far_from_quadratic(self, name: str, text: str) -> None:
        encode = getattr(codecs, f"{name}_encode")
        decode = getattr(codecs, f"{name}_decode")
        inputs = [text * (size // len(text)) for size in (10_000, 1_000_000)]
        outputs = [encode(value)[0] for value in inputs]

        encode_ratio = growth(*(partial(encode, value) for value in inputs))
        decode_ratio = growth(*(partial(decode, value) for value in outputs))

        assert encode_ratio < 1_000, f"{name}_encode: 100x the input cost x{encode_ratio:.1f}"
        assert decode_ratio < 1_000, f"{name}_decode: 100x the input cost x{decode_ratio:.1f}"


class TestConstants:
    """The BOM constants: fixed-order ones, native-order ones, older names."""

    def test_the_fixed_order_marks(self) -> None:
        assert codecs.BOM_UTF8 == b"\xef\xbb\xbf"
        assert codecs.BOM_UTF16_LE == b"\xff\xfe"
        assert codecs.BOM_UTF16_BE == b"\xfe\xff"
        assert codecs.BOM_UTF32_LE == b"\xff\xfe\x00\x00"
        assert codecs.BOM_UTF32_BE == b"\x00\x00\xfe\xff"

    def test_the_native_order_marks(self) -> None:
        little = sys.byteorder == "little"
        utf16 = codecs.BOM_UTF16_LE if little else codecs.BOM_UTF16_BE
        utf32 = codecs.BOM_UTF32_LE if little else codecs.BOM_UTF32_BE

        assert codecs.BOM == codecs.BOM_UTF16 == utf16
        assert codecs.BOM_UTF32 == utf32
        assert codecs.BOM_BE == codecs.BOM_UTF16_BE
        assert codecs.BOM_LE == codecs.BOM_UTF16_LE

    def test_the_older_names(self) -> None:
        assert codecs.BOM32_BE == codecs.BOM_UTF16_BE
        assert codecs.BOM32_LE == codecs.BOM_UTF16_LE
        assert codecs.BOM64_BE == codecs.BOM_UTF32_BE
        assert codecs.BOM64_LE == codecs.BOM_UTF32_LE


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
        [sys.executable, "-W", "error", str(script)],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


class TestDocumentedExamples:
    """Each block runs in its own subprocess, so registered search functions
    and error handlers cannot leak between them, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "assert calls == [(1, 4)]" in s)
        mutated = source.replace("assert calls == [(1, 4)]", "assert calls == [(1, 2)]", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
