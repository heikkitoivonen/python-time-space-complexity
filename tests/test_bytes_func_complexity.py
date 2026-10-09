"""Tests for docs/builtins/bytes_func.md.

The page prices each source `bytes()` accepts: an exact `bytes` comes back as
itself, a count is n zero bytes, and every other form reads its source once.
Identity and traced allocation settle the O(1) and space claims with no
tolerance; the error rows are settled by what is raised, by traced allocation
and by a recording iterator; the linear rows a counter cannot reach are timed
over a hundredfold step in the source, where a linear row has to cost between
x10 and x1,000 - far from the x1 of a constant and the x10,000 of a square -
and an O(1) row under x3.

Measurement scope:

* `bytes()` and `bytes(0)` are the same object, and traced allocation for
  either is under 10,000 bytes. `bytes(count)` gives that many zero bytes and
  traces a peak of at least 10,000,000 for a count of 10,000,000.
* `bytes(b)` for an exact `bytes` is `b`, and on a 10,000,000-byte `b` traces
  under 10,000 bytes; a hundredfold `b` costs under x3. An instance of a
  `bytes` subclass gives an exact `bytes` that is not the argument and traces
  a full-size peak. A `bytearray`, a `memoryview` and an `array.array` each
  give a copy: the result keeps its value after the source is mutated, a
  10,000,000-byte `bytearray` traces a full-size peak, and copying scales
  over 100,000 to 10,000,000 bytes.
* Iterables: a `list`, a `tuple`, a `range` and a generator give one byte per
  item. Each of the first, second and fourth scales over 10,000 to 1,000,000
  items, and a 1,000,000-item generator traces a peak under three times its
  result.
* Encoding: `bytes(s, enc, errors)` equals `s.encode(enc, errors)` for UTF-8,
  UTF-16, Latin-1 and ASCII with `replace`, and for a `str` subclass whose
  overriding `encode()` is not called, it equals `str.encode()`. It scales over 100,000 to
  10,000,000 characters with UTF-8, and with ASCII under `errors='ignore'` on
  text that emits nothing, which is the "whatever it emits" in its row.
  `bytes.fromhex()`, which the page's encoding example sets beside it,
  scales over the same step in hex digits.
* `__bytes__()`: it is called once, ahead of `__index__` and ahead of a
  buffer (a `bytearray` subclass defining it); a method returning a stored
  10,000,000-byte `bytes` costs `bytes()` under 10,000 traced bytes, so the
  constructor adds nothing of its own; a non-`bytes` result raises
  `TypeError`.
* Errors: a negative count, a `str` without an encoding, `errors` without an
  encoding and an encoding for a 10,000,000-byte `bytes` each raise with
  under 10,000 traced bytes, and the `str` case costs under x3 over a
  hundredfold string. An out-of-range item from a recording generator stops
  the read at that item.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* `bytes(count)` is zero-filled by `calloc` (Objects/bytesobject.c,
  _PyBytes_FromSize, v3.10.19 through v3.14.2). For a large count the
  allocator can hand over pages the operating system has already zeroed, and
  on Linux a count of 10,000,000 then costs no more than one of 1,000,000. So
  the time of that row is asserted only from above (a hundredfold count under
  x1,000); its space is the traced peak.
* That a `list` or `tuple` is sized once while any other iterable grows its
  result geometrically is read from _PyBytes_FromList, _PyBytes_FromTuple and
  _PyBytes_FromIterator; both are linear and only that is asserted.
* The encoding row is scoped to codecs and error handlers whose cost and
  output are proportional to their input. Only UTF-8 and ASCII are timed; a
  registered handler can return a replacement of any length, and a codec
  that rebuilds its result as it goes costs more than its output.
* The O(k) bound on an out-of-range item is the cost up to that item, at
  most the whole source; the time to it is not measured.
* On Windows the timing tests whose larger call builds a fresh buffer above
  about 1 MB are skipped: that step prices newly committed pages rather than
  the copy (see FRESH_PAGES_ON_WINDOWS).
* The examples' annotations on `memoryview()`, `bytearray.append()` and
  `int.to_bytes()` restate rows priced and tested with those pages; here the
  examples only run.
* Timings hold the element values fixed: zeros for counts, buffers and
  iterables, one repeated character for strings.
"""

from __future__ import annotations

import array
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "builtins" / "bytes_func.md"
EXPECTED_BLOCKS = 5

SMALL = 100_000
LARGE = 10_000_000
STEP = LARGE / SMALL  # every scaling measurement below uses this hundredfold step
LINEAR = 10  # a hundredfold input must cost at least this much more
CONSTANT = 3  # ... and at most this much more when the row says O(1)
QUADRATIC = 1_000  # ... and below this, where a quadratic one would be near x10,000
SMALL_PEAK = 10_000  # traced bytes below which nothing proportional was allocated

# The Windows heap hands a block above about 1 MB to VirtualAlloc and returns it
# on free, so each call that allocates one pays for freshly committed,
# zero-filled pages, while a 100 KB result stays cache-resident. An operation
# whose work is one bulk copy into a new buffer then costs x2,000 to x3,900 for
# the 100x step from SMALL to LARGE.
FRESH_PAGES_ON_WINDOWS = pytest.mark.skipif(
    sys.platform == "win32",
    reason="on Windows a new buffer above about 1 MB is freshly committed, zero-filled pages, "
    "so the step crosses from cache-resident to page-faulting memory",
)


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


def growth(small: Callable[[], Any], large: Callable[[], Any], inner: int = 1) -> float:
    """How many times more the large call costs than the small one."""
    return best_ns(large, inner=inner) / best_ns(small, inner=inner)


def assert_linear(name: str, ratio: float) -> None:
    """A hundredfold input costs far more than a constant and far less than a square."""
    assert LINEAR < ratio < QUADRATIC, f"{name}: {STEP:.0f}x the input cost x{ratio:.1f}"


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def raising_peak(func: Callable[[], Any], error: type[BaseException]) -> int:
    """Peak traced allocation while func runs and raises `error`."""

    def call() -> None:
        with pytest.raises(error):
            func()

    return peak_bytes(call)


class TestEmptyAndCount:
    """`bytes()` | O(1) | the shared empty bytes; `bytes(count)` | O(n) | O(n)."""

    def test_the_empty_bytes_is_shared(self) -> None:
        empty = bytes()  # noqa: UP018 - the constructor call is the subject

        assert empty == b""
        assert bytes(0) is empty
        assert peak_bytes(bytes) < SMALL_PEAK
        assert peak_bytes(lambda: bytes(0)) < SMALL_PEAK

    def test_a_count_gives_that_many_zero_bytes(self) -> None:
        assert bytes(5) == b"\x00" * 5
        assert bytes(5) != b"5", "an int is a length, not a value"

    def test_a_count_allocates_all_of_it(self) -> None:
        peak = peak_bytes(lambda: bytes(LARGE))

        assert peak >= LARGE, f"bytes({LARGE}) peaked at {peak} bytes"

    @pytest.mark.timing
    @FRESH_PAGES_ON_WINDOWS
    def test_a_count_costs_no_more_than_linear(self) -> None:
        ratio = growth(lambda: bytes(SMALL), lambda: bytes(LARGE))

        assert ratio < QUADRATIC, f"{STEP:.0f}x the count cost x{ratio:.1f}"


class TestAnExactBytesIsReturnedItself:
    """`bytes(b)` where `b` is a `bytes` | O(1) | O(1) | returns `b`; a
    subclass instance is copied, O(k)."""

    def test_the_argument_comes_back(self) -> None:
        data = bytes(LARGE)

        assert bytes(data) is data
        assert peak_bytes(lambda: bytes(data)) < SMALL_PEAK

    @pytest.mark.timing
    def test_its_size_does_not_change_the_cost(self) -> None:
        small, large = bytes(SMALL), bytes(LARGE)

        ratio = growth(lambda: bytes(small), lambda: bytes(large), inner=1_000)

        assert ratio < CONSTANT, f"{STEP:.0f}x the bytes cost x{ratio:.1f}"

    def test_a_subclass_instance_is_copied(self) -> None:
        class Tagged(bytes):
            pass

        data = Tagged(LARGE)

        result = bytes(data)

        assert type(result) is bytes
        assert result is not data
        assert result == data
        assert peak_bytes(lambda: bytes(data)) >= LARGE


class TestBytesLikeSourcesAreCopied:
    """`bytes(bytes_like)` | O(k) | O(k) | copies the buffer of a bytearray,
    memoryview or array.array; the copy keeps its value."""

    def test_each_source_gives_an_independent_copy(self) -> None:
        buffer = bytearray(b"payload")
        source_array = array.array("B", [1, 2])
        sources: list[Any] = [buffer, memoryview(buffer), source_array]

        copies = [bytes(source) for source in sources]
        buffer[0] = ord("P")
        source_array[0] = 9

        assert copies == [b"payload", b"payload", b"\x01\x02"]

    def test_a_view_copies_only_what_it_covers(self) -> None:
        data = bytes(LARGE)
        view = memoryview(data)[:10]

        assert bytes(view) == bytes(10)
        assert bytes(memoryview(data)) is not data
        assert peak_bytes(lambda: bytes(view)) < SMALL_PEAK

    def test_copying_a_bytearray_allocates_its_length(self) -> None:
        source = bytearray(LARGE)

        peak = peak_bytes(lambda: bytes(source))

        assert peak >= LARGE, f"bytes(bytearray of {LARGE}) peaked at {peak} bytes"

    @pytest.mark.timing
    @FRESH_PAGES_ON_WINDOWS
    def test_copying_scales_with_the_source(self) -> None:
        small, large = bytearray(SMALL), bytearray(LARGE)

        assert_linear("bytes(bytearray)", growth(lambda: bytes(small), lambda: bytes(large)))


class TestIterables:
    """`bytes(iterable)` | O(k) | O(k) | one byte per item."""

    def test_each_item_is_one_byte(self) -> None:
        assert bytes([72, 105]) == b"Hi"
        assert bytes((72, 105)) == b"Hi"
        assert bytes(range(3)) == b"\x00\x01\x02"
        assert bytes(value for value in (72, 105)) == b"Hi"

    def test_a_generator_peaks_near_its_result(self) -> None:
        items = SMALL * 10

        peak = peak_bytes(lambda: bytes(0 for _ in range(items)))

        assert items <= peak < 3 * items, f"{items} items peaked at {peak} bytes"

    @pytest.mark.timing
    def test_each_kind_of_iterable_scales_with_its_items(self) -> None:
        small_items, large_items = SMALL // 10, LARGE // 10
        small_list, large_list = [0] * small_items, [0] * large_items
        small_tuple, large_tuple = tuple(small_list), tuple(large_list)

        ratios = {
            "list": growth(lambda: bytes(small_list), lambda: bytes(large_list)),
            "tuple": growth(lambda: bytes(small_tuple), lambda: bytes(large_tuple)),
            "generator": growth(
                lambda: bytes(0 for _ in range(small_items)),
                lambda: bytes(0 for _ in range(large_items)),
            ),
        }

        for name, ratio in ratios.items():
            assert_linear(f"bytes({name})", ratio)


class TestEncoding:
    """`bytes(string, encoding, errors='strict')` | O(k) | O(k) | the encoder
    `string.encode()` runs; k = characters, walked whatever it emits."""

    def test_it_matches_str_encode(self) -> None:
        text = "café"

        for encoding, errors in [
            ("utf-8", "strict"),
            ("utf-16", "strict"),
            ("latin-1", "strict"),
            ("ascii", "replace"),
        ]:
            assert bytes(text, encoding, errors) == text.encode(encoding, errors)

    def test_it_runs_str_encode_not_an_override(self) -> None:
        class Loud(str):
            def encode(self, encoding: str = "utf-8", errors: str = "strict") -> bytes:
                return b"override"

        text = Loud("café")

        assert text.encode("utf-8") == b"override"
        assert bytes(text, "utf-8") == str.encode(text, "utf-8") == b"caf\xc3\xa9"

    def test_strict_errors_raise(self) -> None:
        with pytest.raises(UnicodeEncodeError) as caught:
            bytes("café", "ascii")

        assert caught.value.start == 3

    @pytest.mark.timing
    @FRESH_PAGES_ON_WINDOWS
    def test_it_scales_with_the_characters(self) -> None:
        small, large = "é" * SMALL, "é" * LARGE

        assert_linear(
            "bytes(str, 'utf-8')",
            growth(lambda: bytes(small, "utf-8"), lambda: bytes(large, "utf-8")),
        )

    @pytest.mark.timing
    @FRESH_PAGES_ON_WINDOWS
    def test_fromhex_scales_with_the_digits(self) -> None:
        small, large = "ab" * (SMALL // 2), "ab" * (LARGE // 2)

        assert bytes.fromhex("63 61 66") == b"caf"
        assert_linear(
            "bytes.fromhex()",
            growth(lambda: bytes.fromhex(small), lambda: bytes.fromhex(large)),
        )

    @pytest.mark.timing
    def test_it_walks_characters_that_emit_nothing(self) -> None:
        small, large = "é" * SMALL, "é" * LARGE

        assert bytes(large, "ascii", "ignore") == b""
        assert_linear(
            "bytes(str, 'ascii', 'ignore')",
            growth(
                lambda: bytes(small, "ascii", "ignore"),
                lambda: bytes(large, "ascii", "ignore"),
            ),
        )


class TestDunderBytes:
    """`bytes(obj)` where obj defines `__bytes__()` | O(f) | O(f) | takes
    precedence over the other forms; a non-bytes result raises TypeError."""

    def test_it_is_called_once_and_its_result_returned(self) -> None:
        stored = bytes(LARGE)
        calls: list[None] = []

        class Holder:
            def __bytes__(self) -> bytes:
                calls.append(None)
                return stored

        holder = Holder()

        assert bytes(holder) is stored
        assert len(calls) == 1
        assert peak_bytes(lambda: bytes(holder)) < SMALL_PEAK

    def test_it_comes_before_a_count(self) -> None:
        class Both:
            def __bytes__(self) -> bytes:
                return b"bytes"

            def __index__(self) -> int:
                return 3

        assert bytes(Both()) == b"bytes"

    def test_it_comes_before_a_buffer(self) -> None:
        class Buffer(bytearray):
            def __bytes__(self) -> bytes:
                return b"method"

        assert bytes(Buffer(b"buffer")) == b"method"

    def test_a_result_that_is_not_bytes_raises(self) -> None:
        class Wrong:
            def __bytes__(self) -> Any:
                return bytearray(b"x")

        with pytest.raises(TypeError, match="non-bytes"):
            bytes(Wrong())


class TestErrors:
    """The error rows: a negative count, a `str` without an encoding and an
    encoding for a non-str raise in O(1); an out-of-range item stops the read."""

    def test_a_negative_count_raises_before_allocating(self) -> None:
        with pytest.raises(ValueError, match="negative count"):
            bytes(-1)
        assert raising_peak(lambda: bytes(-LARGE), ValueError) < SMALL_PEAK

    def test_a_string_without_an_encoding_is_not_read(self) -> None:
        text = "é" * LARGE

        with pytest.raises(TypeError, match="without an encoding"):
            bytes(text)  # type: ignore[call-overload]
        with pytest.raises(TypeError, match="without an encoding"):
            bytes(text, errors="strict")  # type: ignore[call-overload]
        assert raising_peak(lambda: bytes(text), TypeError) < SMALL_PEAK  # type: ignore[call-overload]
        assert (
            raising_peak(lambda: bytes(text, errors="strict"), TypeError)  # type: ignore[call-overload]
            < SMALL_PEAK
        )

    @pytest.mark.timing
    def test_a_string_without_an_encoding_costs_the_same_at_any_length(self) -> None:
        small, large = "é" * SMALL, "é" * LARGE

        def rejected(text: str) -> Callable[[], None]:
            def call() -> None:
                try:
                    bytes(text)  # type: ignore[call-overload]
                except TypeError:
                    pass

            return call

        ratio = growth(rejected(small), rejected(large), inner=1_000)

        assert ratio < CONSTANT, f"{STEP:.0f}x the string cost x{ratio:.1f}"

    def test_an_encoding_for_a_non_str_is_rejected_unread(self) -> None:
        data = bytes(LARGE)

        with pytest.raises(TypeError, match="encoding without a string"):
            bytes(data, "utf-8")  # type: ignore[call-overload]
        with pytest.raises(TypeError, match="errors without a string"):
            bytes(5, errors="strict")  # type: ignore[call-overload]
        assert raising_peak(lambda: bytes(data, "utf-8"), TypeError) < SMALL_PEAK  # type: ignore[call-overload]

    def test_an_item_out_of_range_stops_the_read(self) -> None:
        taken: list[int] = []

        def items() -> Iterator[int]:
            for value in (65, 66, 256, 67, 68):
                taken.append(value)
                yield value

        with pytest.raises(ValueError, match="range\\(0, 256\\)"):
            bytes(items())
        with pytest.raises(ValueError, match="range\\(0, 256\\)"):
            bytes([-1])

        assert taken == [65, 66, 256]


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
        line, source = next((n, s) for n, s in _blocks() if "assert frozen ==" in s)
        mutated = source.replace('assert frozen == b"payload"', 'assert frozen == b"Payload"', 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
