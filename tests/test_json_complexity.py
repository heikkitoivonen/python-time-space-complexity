"""Tests for docs/stdlib/json.md.

The page prices both directions as one pass over the text: `dumps()` and
`loads()` are linear in the characters, `dump()` and `iterencode()` hold the
depth and the largest scalar instead of the output and pay depth again in
time, and the options that change a growth class are `sort_keys` and
`indent`. Chunking, laziness and
per-call space are settled by counting writes and by traced allocation; the
hook rows by recording what each hook is handed; the encoder in use by
observing which encoder is built; the error rows by a recording document.

Measurement scope:

* `dumps()` and `loads()` are timed on 2,000 and 32,000 two-field records,
  a 16x step, and asserted under 40x; the excluded shape is quadratic at
  256x. The returned string doubles across 1,000, 2,000 and 4,000 records,
  and the traced peak of `loads()` grows between 2x and 8x from 4,000 to
  16,000 records, where linear predicts 4x and quadratic 16x.
* `dump()` hands a counting sink more than 1,000 chunks for 5,000 records.
  Its traced peak stays within 4x across 1,000, 10,000 and 100,000 records
  while the output grows more than 50x; grows between 5x and 200x from 10
  to 400 levels of empty dictionaries, where linear predicts 40x and
  quadratic 1,600x; grows between 20x and 1,000x from a 10 KB string to a
  1 MB one at a fixed depth of two, where linear predicts 100x and
  quadratic 10,000x; stays within 4x when the same
  megabyte arrives as ten-character strings; and stays within 1.5x when
  400 nested keys grow from one character to 10,000, so an open level does
  not hold its encoded key. `dumps()` peaks above its
  output length where `dump()` peaks below a tenth of it. `dump()` is
  observed to build the pure-Python encoder and `dumps()` not to, and a
  timing test puts `dump()` into a sink at more than 2x the cost of
  `dumps()` on 32,000 records and between 0.5x and 2x on one 10 MB
  string. The d in O(n·d) is a timing test on 20,000
  records placed under 1 and then 100 levels of nesting: `dump()` costs
  more than 3x at the deeper placement while `dumps()` stays under 2x.
  With `indent=2`, the peak of `dump()` above its plain peak grows between
  3x and 6x from 400 to 800 nested dictionaries, where one indentation
  string per open level predicts 4x, a constant per level 2x and a cubic
  term 8x.
* `iterencode()` is observed to call `default` zero times before the first
  `next()`, and its consumed peak stays within 4x from 1,000 to 100,000
  records.
* `sort_keys` is counted in key comparisons through a `str` subclass:
  zero without it, more than one pass with it, and 16x the keys costing
  between 17.5x and 40x the comparisons where linear predicts 16, k log k
  about 23 and quadratic 256. Its space is the traced peak of `dump()`
  into a non-retaining sink with `sort_keys=True` on one object of 20,000
  and then 200,000 keys: between 5x and 40x for 10x the keys, where the
  sorted item list predicts 10x and a quadratic buffer 100x, and more than
  3x the unsorted peak at 200,000 keys, which holds no item list. Both
  sizes sit far above the 2,000-tuple freelist, whose reuse `tracemalloc`
  does not see. `indent=2` output grows between 3x and 6x per doubling of
  depth from 50 to 200 levels, where quadratic predicts 4x and cubic 8x,
  and compact output doubles. `ensure_ascii` is asserted
  by output length on one BMP and one astral code point, and a NUL is
  asserted to escape under both settings. `default` is
  counted at one call per occurrence of a shared object and zero calls for
  an unsupported key, its stand-in is
  asserted in the output, and a stand-in containing the original raises
  `ValueError`; with `check_circular=False` a cycle raises `RecursionError`.
  On 3.13 and later `dumps(indent=2)` is observed not to build the
  pure-Python encoder; before 3.13 it is observed to. `skipkeys` with
  `sort_keys` is asserted to raise `TypeError` on a tuple key.
* `loads()` on `bytes` peaks more than half the text length above `loads()`
  on the same `str`; `load()` peaks more than half the text length above
  `loads()`, and calls `read()` once with no size. `detect_encoding()` on a
  recording `bytes` subclass touches indices below 4 and three `startswith`
  prefixes over an 800 KB UTF-8 blob; the UTF-16 and UTF-32 branches are
  asserted by return value only. Two keys in one document are the same
  object; the same key in a second call is not.
* Each hook is handed what the row says: `object_hook` a four-pair `dict`,
  once per object, innermost first; `object_pairs_hook` the pair list, and
  the `dict` hook is not called when both are given; `parse_int`,
  `parse_float` and `parse_constant` the literal's text. A literal one
  digit over `sys.get_int_max_str_digits()` raises `ValueError` from
  `loads()`, the same number raises from `dumps()`, and `parse_int=float`
  reads it; the test skips where the limit has been disabled.
* `raw_decode()` returns the value and the index after it, walks three
  concatenated documents, and in a timing test costs within 5x with a
  10 MB tail after the value against no tail. `decode()` raises `Extra
  data` on a second document and accepts trailing whitespace.
* `JSONDecodeError` built by the parser calls `count` and `rfind` on the
  document once each over `[0, pos)` and nothing else, keeps the document
  by identity, and carries the five attributes; a direct construction
  agrees, and one with a 100,000-character `msg` carries all of it in
  `str(error)`.
* `dump()` and exhausted `iterencode()` on twice `sys.getrecursionlimit()`
  nested dictionaries raise `RecursionError`; both accept 100 levels.
  The exact failure depth depends on the frames already active, so only
  the bound is asserted. `loads()` and `dumps()` round-trip 100 nested
  arrays, with the decoded depth checked iteratively.
* `python -m json.tool` is run in a subprocess: a second document after the
  first prints nothing and exits 1 by default, and with `--json-lines` it
  prints the first line before failing on a malformed second. Whether it
  reads one line at a time is observed through a pipe held open after the
  first line: before 3.13.14, and on 3.14.0 to 3.14.4, the first line comes
  back while the pipe is open; from 3.13.14 and 3.14.5 nothing comes back
  until the pipe closes. That boundary is the `gh-132631` entry in the
  release notes of those two releases, and CI runs the matrix.
* Every fenced Python block runs in its own subprocess and working
  directory, and a flipped identity assertion in one of them is asserted
  to fail.

Not settled here:

* The C encoder and decoder's recursion guards follow
  `scan_once_unicode` and `encoder_listencode_obj` in CPython 3.10-3.14's
  Modules/_json.c. Their failure depth depends on the version, build and
  available stack; a fixed input depth cannot establish a portable limit.
  These tests do not exhaust the C stack to measure that environment's limit.
* That the remaining `dump()` term is exactly one generator frame per open
  container plus the marker dict is read from Lib/json/encoder.py; the
  tests show the peak follows depth and the largest scalar and not the
  record count. That the d in its time is one `yield from` relay per open
  container is read from the same file; the tests show the cost follows
  depth at a fixed size.
* `raw_decode()` being O(v) on success, rather than merely independent of
  what follows the value, is read from Modules/_json.c's `scanner_call`,
  which starts at `idx` and returns at the value's end; a malformed value
  pays `JSONDecodeError`'s O(p), which the error tests measure.
* `detect_encoding()` reading at most four bytes is read from
  Lib/json/__init__.py; the recording test bounds the indices it touched on
  the UTF-8 input only.
* The 3.10.7 boundary of the integer digit limit is from the CPython
  changelog; every supported interpreter is past it, so no test runs
  without the limit.
* Axes held fixed: scalar kind for the O(d + s) bound (only `str` is
  measured, not a long `int` or `float`); escaping, which lengthens an
  encoded string beyond its source; record shape for the timing tests,
  which use two-field objects only.
* The audit's unclassified names are implementation: the `json.decoder`,
  `json.encoder` and `json.scanner` submodules with their `scanstring`,
  `JSONObject`, `JSONArray`, `make_scanner`, `encode_basestring*` and
  `c_make_encoder` members, and `json.tool.main` and `json.tool.get_theme`.
  None is in the documented API, and the page prices the calls that reach
  them. `detect_encoding`, `item_separator` and `key_separator` are on the
  page.
"""

from __future__ import annotations

import io
import json
import json.encoder
import math
import pathlib
import random
import re
import select
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "json.md"
EXPECTED_BLOCKS = 11


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


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class CountingSink:
    """A file-like object that counts what json.dump() hands it."""

    def __init__(self) -> None:
        self.writes = 0
        self.chars = 0

    def write(self, chunk: str) -> None:
        self.writes += 1
        self.chars += len(chunk)


def wide(n: int) -> dict[str, Any]:
    """A shallow object with n two-field records."""
    return {"rows": [{"id": i, "name": f"n{i}"} for i in range(n)]}


def deep(d: int) -> dict[str, Any]:
    """An empty dictionary nested d levels."""
    root: dict[str, Any] = {}
    node = root
    for _ in range(d):
        node["child"] = {}
        node = node["child"]
    return root


def at_depth(n: int, d: int) -> dict[str, Any]:
    """n two-field records placed under d levels of nesting."""
    root = deep(d)
    node = root
    for _ in range(d):
        node = node["child"]
    node["rows"] = wide(n)["rows"]
    return root


class TestEncodingAndDecodingAreOnePass:
    """`dumps()` | O(n) | O(n) and `loads()` | O(n) | O(n); `encode()` and
    `decode()` are the same work under the class names."""

    @pytest.mark.timing
    def test_dumps_is_linear_in_the_object(self) -> None:
        """16x the records costs about 16x, not 256x; the threshold is 40."""
        small, large = wide(2_000), wide(32_000)

        small_ns = best_ns(lambda: json.dumps(small))
        large_ns = best_ns(lambda: json.dumps(large))

        ratio = large_ns / small_ns
        assert ratio < 40, (
            f"16x the records cost x{ratio:.1f} ({small_ns:.0f}ns to {large_ns:.0f}ns)"
        )

    def test_dumps_output_grows_with_the_object(self) -> None:
        lengths = [len(json.dumps(wide(n))) for n in (1_000, 2_000, 4_000)]

        for shorter, longer in zip(lengths, lengths[1:], strict=False):
            assert 1.9 < longer / shorter < 2.2, f"output is not tracking n: {lengths}"

    @pytest.mark.timing
    def test_loads_is_linear_in_the_text(self) -> None:
        small, large = json.dumps(wide(2_000)), json.dumps(wide(32_000))

        small_ns = best_ns(lambda: json.loads(small))
        large_ns = best_ns(lambda: json.loads(large))

        ratio = large_ns / small_ns
        assert ratio < 40, f"16x the text cost x{ratio:.1f} ({small_ns:.0f}ns to {large_ns:.0f}ns)"

    def test_loads_result_grows_with_the_text(self) -> None:
        small_text, large_text = json.dumps(wide(4_000)), json.dumps(wide(16_000))

        small_peak = peak_bytes(lambda: json.loads(small_text))
        large_peak = peak_bytes(lambda: json.loads(large_text))

        ratio = large_peak / small_peak
        assert 2 < ratio < 8, f"4x the text built {small_peak} then {large_peak} B, x{ratio:.1f}"

    def test_encode_and_decode_are_dumps_and_loads(self) -> None:
        obj = wide(50)

        encoded = json.JSONEncoder().encode(obj)

        assert encoded == json.dumps(obj)
        assert json.JSONDecoder().decode(encoded) == obj

    def test_the_constructors_store_their_options(self) -> None:
        encoder = json.JSONEncoder(sort_keys=True, indent=3, skipkeys=True)
        decoder = json.JSONDecoder(strict=False, parse_int=float)

        assert (encoder.sort_keys, encoder.indent, encoder.skipkeys) == (True, 3, True)
        assert (decoder.strict, decoder.parse_int) == (False, float)


class TestDumpStreams:
    """`dump()` | O(n·d) | O(d + s): one chunk per scalar through the
    pure-Python encoder, so the peak follows depth and the largest scalar
    and every chunk is relayed through each open container."""

    def test_dump_writes_many_small_chunks(self) -> None:
        sink = CountingSink()

        json.dump(wide(5_000), sink)

        assert sink.chars == len(json.dumps(wide(5_000)))
        assert sink.writes > 1_000, f"dump() handed over {sink.writes} chunks"

    def test_dump_peak_is_flat_in_the_record_count(self) -> None:
        objects = [wide(n) for n in (1_000, 10_000, 100_000)]
        outputs = [len(json.dumps(obj)) for obj in objects]

        peaks = [peak_bytes(lambda obj=obj: json.dump(obj, CountingSink())) for obj in objects]

        assert outputs[-1] > 50 * outputs[0], f"the inputs did not spread: {outputs}"
        assert max(peaks) < 4 * min(peaks), f"peaks {peaks} for outputs {outputs}"

    def test_dump_peak_grows_with_depth(self) -> None:
        shallow, nested = deep(10), deep(400)

        shallow_peak = peak_bytes(lambda: json.dump(shallow, CountingSink()))
        nested_peak = peak_bytes(lambda: json.dump(nested, CountingSink()))

        ratio = nested_peak / shallow_peak
        assert 5 < ratio < 200, f"40x the depth: {shallow_peak} to {nested_peak} B, x{ratio:.1f}"

    def test_dump_peak_tracks_the_largest_scalar(self) -> None:
        """Depth is fixed at two, so d cannot explain the growth."""
        peaks = [
            peak_bytes(lambda obj={"a": {"b": "x" * s}}: json.dump(obj, CountingSink()))
            for s in (10_000, 100_000, 1_000_000)
        ]

        ratio = peaks[-1] / peaks[0]
        assert 20 < ratio < 1_000, (
            f"peaks {peaks} B for 10 KB, 100 KB and 1 MB strings, x{ratio:.0f}"
        )

    def test_dump_peak_ignores_total_size_when_scalars_are_small(self) -> None:
        """The control: the same characters, split up, do not raise the peak."""
        objects = [
            {"a": {f"k{i}": "x" * 10 for i in range(total // 10)}} for total in (10_000, 1_000_000)
        ]
        outputs = [len(json.dumps(obj)) for obj in objects]

        peaks = [peak_bytes(lambda obj=obj: json.dump(obj, CountingSink())) for obj in objects]

        assert outputs[-1] > 50 * outputs[0], f"the documents did not spread: {outputs}"
        assert max(peaks) < 4 * min(peaks), f"peaks {peaks} for outputs {outputs}"

    def test_an_open_level_does_not_hold_its_encoded_key(self) -> None:
        """Key length at a fixed depth of 400: retained keys would add 4 MB."""

        def chain(key: str) -> dict[str, Any]:
            root: dict[str, Any] = {}
            node = root
            for _ in range(400):
                node[key] = {}
                node = node[key]
            return root

        short, long = chain("k"), chain("k" * 10_000)

        short_peak = peak_bytes(lambda: json.dump(short, CountingSink()))
        long_peak = peak_bytes(lambda: json.dump(long, CountingSink()))

        assert long_peak < 1.5 * short_peak, f"peaks {short_peak} and {long_peak} B"

    def test_dumps_holds_the_whole_string(self) -> None:
        obj = wide(20_000)
        output_size = len(json.dumps(obj))

        dump_peak = peak_bytes(lambda: json.dump(obj, CountingSink()))
        dumps_peak = peak_bytes(lambda: json.dumps(obj))

        assert dumps_peak > output_size
        assert dump_peak < output_size / 10, (
            f"dump() peaked at {dump_peak} B for {output_size} chars"
        )

    def test_dump_builds_the_python_encoder_and_dumps_does_not(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        built: list[str] = []
        original = json.encoder._make_iterencode  # type: ignore[attr-defined]  # noqa: SLF001

        def spy(*args: Any, **kwargs: Any) -> Any:
            built.append("python")
            return original(*args, **kwargs)

        monkeypatch.setattr(json.encoder, "_make_iterencode", spy)

        json.dumps(wide(3))
        assert built == [], "dumps() should use the C encoder"
        json.dump(wide(3), CountingSink())
        assert built == ["python"], "dump() should use the pure-Python encoder"

    @pytest.mark.timing
    def test_dump_costs_more_per_element_than_dumps(self) -> None:
        obj = wide(32_000)
        sink = CountingSink()

        dumps_ns = best_ns(lambda: sink.write(json.dumps(obj)))
        dump_ns = best_ns(lambda: json.dump(obj, sink))

        ratio = dump_ns / dumps_ns
        assert ratio > 2, (
            f"dump() cost x{ratio:.2f} of dumps() ({dumps_ns:.0f}ns to {dump_ns:.0f}ns)"
        )

    @pytest.mark.timing
    def test_a_lone_large_string_costs_the_same_either_way(self) -> None:
        """The control: with one scalar there is nothing per element to save."""
        text = "x" * 10_000_000
        sink = CountingSink()

        dumps_ns = best_ns(lambda: sink.write(json.dumps(text)))
        dump_ns = best_ns(lambda: json.dump(text, sink))

        ratio = dump_ns / dumps_ns
        assert 0.5 < ratio < 2, f"dump() cost x{ratio:.2f} of dumps() on one 10 MB string"

    @pytest.mark.timing
    def test_dump_cost_grows_with_depth_at_a_fixed_size(self) -> None:
        """The d in O(n·d): the same records cost more the deeper they sit.

        Linear in n predicts 1x for both; the relay through 100 open
        generators is what separates `dump()` from `dumps()` here.
        """
        shallow, nested = at_depth(20_000, 1), at_depth(20_000, 100)
        sink = CountingSink()

        dump_ratio = best_ns(lambda: json.dump(nested, sink)) / best_ns(
            lambda: json.dump(shallow, sink)
        )
        dumps_ratio = best_ns(lambda: json.dumps(nested)) / best_ns(lambda: json.dumps(shallow))

        assert dumps_ratio < 2, f"dumps() should not care about depth: x{dumps_ratio:.2f}"
        assert dump_ratio > 3, f"dump() at 100 levels cost only x{dump_ratio:.2f} of 1 level"

    def test_indent_makes_dump_hold_each_level_s_indentation(self) -> None:
        """The indentation held above the plain peak quadruples per doubling
        of depth; a constant per open level would only double it."""
        overheads = []
        for depth in (400, 800):
            chain = deep(depth)
            plain = peak_bytes(lambda chain=chain: json.dump(chain, CountingSink()))
            indented = peak_bytes(lambda chain=chain: json.dump(chain, CountingSink(), indent=2))
            overheads.append(indented - plain)

        assert overheads[0] > 0, f"indentation held over 400 then 800 levels: {overheads} B"
        ratio = overheads[1] / overheads[0]
        assert 3 < ratio < 6, (
            f"indentation held over 400 then 800 levels: {overheads} B, x{ratio:.1f}"
        )


class TestIterencodeIsLazy:
    """`iterencode()` | O(n·d) to exhaust | O(d + s): a generator that encodes
    nothing until it is iterated."""

    def test_nothing_is_encoded_before_the_first_next(self) -> None:
        calls: list[Any] = []

        class Encoder(json.JSONEncoder):
            def default(self, o: Any) -> Any:
                calls.append(o)
                return "stand-in"

        chunks = Encoder().iterencode({"x": object()})

        assert calls == []
        assert "".join(chunks) == '{"x": "stand-in"}'
        assert len(calls) == 1

    def test_consuming_it_peaks_like_dump(self) -> None:
        objects = [wide(n) for n in (1_000, 100_000)]

        def consume(obj: dict[str, Any]) -> None:
            for _ in json.JSONEncoder().iterencode(obj):
                pass

        peaks = [peak_bytes(lambda obj=obj: consume(obj)) for obj in objects]

        assert max(peaks) < 4 * min(peaks), f"peaks {peaks} B for 1,000 and 100,000 records"


class CountingStr(str):
    """A dict key that counts the comparisons a sort makes on it.

    The counter is not called `count`: str already has that method.
    """

    comparisons = 0

    def __lt__(self, other: str) -> bool:
        CountingStr.comparisons += 1
        return str.__lt__(self, other)

    def __gt__(self, other: str) -> bool:
        CountingStr.comparisons += 1
        return str.__gt__(self, other)


class TestSortKeys:
    """`sort_keys=True` | O(k log k) per object. Counted in key comparisons,
    which are deterministic for a fixed key order; only the shape is asserted."""

    @staticmethod
    def _comparisons(k: int, *, sort_keys: bool) -> int:
        keys = [f"k{i:07d}" for i in range(k)]
        random.Random(1).shuffle(keys)
        obj = {CountingStr(key): 1 for key in keys}

        CountingStr.comparisons = 0
        json.dumps(obj, sort_keys=sort_keys)
        return CountingStr.comparisons

    def test_without_sort_keys_no_key_is_compared(self) -> None:
        assert self._comparisons(2_048, sort_keys=False) == 0

    def test_sort_keys_compares_keys(self) -> None:
        count = self._comparisons(2_048, sort_keys=True)

        assert count > 2_048, f"sorting 2048 keys should cost more than one pass: {count}"

    def test_sort_keys_cost_is_superlinear(self) -> None:
        """Linear predicts 16.0, k log k about 23 and quadratic 256."""
        small = self._comparisons(512, sort_keys=True)
        large = self._comparisons(8_192, sort_keys=True)

        ratio = large / small
        predicted = 16 * math.log2(8_192) / math.log2(512)
        assert 17.5 < ratio < 40, (
            f"16x the keys cost x{ratio:.1f} ({small} to {large} comparisons; "
            f"k log k predicts {predicted:.1f}, quadratic 256)"
        )

    def test_sorted_output(self) -> None:
        assert json.dumps({"b": 1, "a": 2}, sort_keys=True) == '{"a": 2, "b": 1}'

    def test_the_sort_holds_one_item_list_per_object(self) -> None:
        """O(k) space: the sorted item list, measured through a sink that
        keeps nothing, grows about 10x for 10x the keys and dwarfs the
        unsorted peak, which holds no such list."""
        objects = [{f"k{i:07d}": 1 for i in range(k)} for k in (20_000, 200_000)]

        sorted_peaks = [
            peak_bytes(lambda obj=obj: json.dump(obj, CountingSink(), sort_keys=True))
            for obj in objects
        ]
        plain_peak = peak_bytes(lambda: json.dump(objects[1], CountingSink()))

        ratio = sorted_peaks[1] / sorted_peaks[0]
        assert 5 < ratio < 40, f"10x the keys peaked at {sorted_peaks} B, x{ratio:.1f}"
        assert sorted_peaks[1] > 3 * plain_peak, (
            f"sorted {sorted_peaks[1]} B against unsorted {plain_peak} B at 200,000 keys"
        )


class TestIndentIsOutputSensitive:
    """`indent` makes n grow: each level repeats its whitespace, and before
    3.13 `dumps()` takes the pure-Python path for it."""

    def test_indented_output_is_quadratic_in_depth(self) -> None:
        lengths = [len(json.dumps(deep(d), indent=2)) for d in (50, 100, 200)]

        for shorter, longer in zip(lengths, lengths[1:], strict=False):
            assert 3.0 < longer / shorter < 6.0, f"indented output per doubling: {lengths}"

    def test_unindented_output_is_linear_in_depth(self) -> None:
        """The control: without indent the same objects double, not quadruple."""
        lengths = [len(json.dumps(deep(d))) for d in (50, 100, 200)]

        for shorter, longer in zip(lengths, lengths[1:], strict=False):
            assert 1.9 < longer / shorter < 2.2, f"plain output should track input: {lengths}"

    def test_indent_uses_the_c_encoder_from_313(self, monkeypatch: pytest.MonkeyPatch) -> None:
        built: list[str] = []
        original = json.encoder._make_iterencode  # type: ignore[attr-defined]  # noqa: SLF001

        def spy(*args: Any, **kwargs: Any) -> Any:
            built.append("python")
            return original(*args, **kwargs)

        monkeypatch.setattr(json.encoder, "_make_iterencode", spy)

        pretty = json.dumps(deep(3), indent=2)

        assert json.loads(pretty) == deep(3)
        if sys.version_info >= (3, 13):
            assert built == [], "3.13+ should pretty-print in the C encoder"
        else:
            assert built == ["python"], "before 3.13 indent should build the Python encoder"

    def test_separators_change_only_the_text_between_elements(self) -> None:
        data = {"key": "value", "nested": {"a": 1}}

        assert json.dumps(data, separators=(",", ":")) == '{"key":"value","nested":{"a":1}}'
        assert json.dumps(data, indent=2).count("\n") == 5

    def test_item_and_key_separator_attributes(self) -> None:
        assert (json.JSONEncoder.item_separator, json.JSONEncoder.key_separator) == (", ", ": ")

        plain = json.JSONEncoder()
        indented = json.JSONEncoder(indent=2)
        custom = json.JSONEncoder(separators=(",", ":"))

        assert (plain.item_separator, plain.key_separator) == (", ", ": ")
        assert (indented.item_separator, indented.key_separator) == (",", ": ")
        assert (custom.item_separator, custom.key_separator) == (",", ":")


class TestEscaping:
    """`ensure_ascii=True` | six output characters per BMP code point, twelve
    beyond it; `ensure_ascii=False` writes the code point itself."""

    def test_output_length_per_code_point(self) -> None:
        assert json.dumps("é") == '"\\u00e9"'
        assert len(json.dumps("é")) == 8
        assert json.dumps("😀") == '"\\ud83d\\ude00"'
        assert len(json.dumps("😀")) == 14
        assert json.dumps("😀", ensure_ascii=False) == '"😀"'
        assert json.loads('"\\ud83d\\ude00"') == "😀"

    def test_control_characters_escape_under_both_settings(self) -> None:
        assert json.dumps("\x00") == '"\\u0000"'
        assert json.dumps("\x00", ensure_ascii=False) == '"\\u0000"'
        assert json.dumps('a"b\\', ensure_ascii=False) == '"a\\"b\\\\"'


class TestDefaultAndCycles:
    """`default=fn` | O(h) per unsupported object, once per occurrence, its
    stand-in encoded in place; `check_circular=False` turns a cycle into
    `RecursionError`."""

    def test_default_is_called_once_per_occurrence(self) -> None:
        seen: list[str] = []

        def default(obj: Any) -> Any:
            seen.append(type(obj).__name__)
            return [1, 2]

        shared = object()

        assert json.dumps([shared, shared], default=default) == "[[1, 2], [1, 2]]"
        assert seen == ["object", "object"]

    def test_default_is_never_offered_a_key(self) -> None:
        seen: list[Any] = []

        with pytest.raises(TypeError, match="keys must be str"):
            json.dumps({object(): 1}, default=seen.append)
        assert json.dumps({object(): 1}, default=seen.append, skipkeys=True) == "{}"
        assert seen == []

    def test_the_stand_in_is_encoded_in_place(self) -> None:
        class Encoder(json.JSONEncoder):
            def default(self, o: Any) -> Any:
                if isinstance(o, set):
                    return sorted(o)
                return super().default(o)

        assert json.dumps({"tags": {"b", "a"}}, cls=Encoder) == '{"tags": ["a", "b"]}'

    def test_the_base_default_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="not JSON serializable"):
            json.JSONEncoder().default(object())
        with pytest.raises(TypeError, match="not JSON serializable"):
            json.dumps(object())

    def test_a_stand_in_containing_the_original_is_a_cycle(self) -> None:
        with pytest.raises(ValueError, match="Circular reference detected"):
            json.dumps(object(), default=lambda o: {"node": o})

    def test_a_cycle_is_a_value_error_by_default(self) -> None:
        first: dict[str, Any] = {"name": "A"}
        second: dict[str, Any] = {"name": "B", "ref": first}
        first["ref"] = second

        with pytest.raises(ValueError, match="Circular reference detected"):
            json.dumps(first)

    def test_without_check_circular_a_cycle_is_a_recursion_error(self) -> None:
        first: dict[str, Any] = {"name": "A"}
        first["ref"] = first

        with pytest.raises(RecursionError):
            json.dumps(first, check_circular=False)
        with pytest.raises(RecursionError):
            json.dump(first, CountingSink(), check_circular=False)


class TestKeyAndFloatOptions:
    """`skipkeys=True` drops unsupported keys; `allow_nan=False` rejects
    `nan` and `inf`."""

    def test_skipkeys(self) -> None:
        with pytest.raises(TypeError, match="keys must be str"):
            json.dumps({(1, 2): 1})

        assert json.dumps({(1, 2): 1, "a": 2}, skipkeys=True) == '{"a": 2}'

    def test_skipkeys_does_not_protect_a_sort(self) -> None:
        with pytest.raises(TypeError, match="not supported between"):
            json.dumps({(1, 2): 1, "a": 2}, skipkeys=True, sort_keys=True)

    def test_allow_nan(self) -> None:
        assert json.dumps([float("nan"), float("inf")]) == "[NaN, Infinity]"
        assert json.loads("[NaN, -Infinity]")[1] == float("-inf")

        for value in (float("nan"), float("inf"), float("-inf")):
            with pytest.raises(ValueError, match="not JSON compliant"):
                json.dumps(value, allow_nan=False)


class TestLoadsHoldsTheTree:
    """`loads()` | O(n) | O(n) with a copy for `bytes`; `load()` reads the
    file once and holds the text beside the tree; `detect_encoding()` looks
    at the first four bytes; keys repeat by identity within a document."""

    TEXT = json.dumps(wide(20_000))

    def test_bytes_are_decoded_to_a_str_first(self) -> None:
        text = self.TEXT
        data = text.encode()

        str_peak = peak_bytes(lambda: json.loads(text))
        bytes_peak = peak_bytes(lambda: json.loads(data))

        assert bytes_peak - str_peak > len(text) / 2, (
            f"bytes input peaked at {bytes_peak} B against {str_peak} for {len(text)} characters"
        )

    def test_load_holds_the_text_and_the_tree_together(self) -> None:
        text = self.TEXT
        stream = io.StringIO(text)

        loads_peak = peak_bytes(lambda: json.loads(text))
        load_peak = peak_bytes(lambda: json.load(stream))

        assert load_peak - loads_peak > len(text) / 2, (
            f"load() peaked at {load_peak} B against {loads_peak} for {len(text)} characters"
        )

    def test_load_reads_the_file_in_one_unsized_call(self) -> None:
        class CountingReader:
            def __init__(self, text: str) -> None:
                self.text = text
                self.calls: list[tuple[Any, ...]] = []

            def read(self, *args: Any) -> str:
                self.calls.append(args)
                return self.text

        reader = CountingReader(json.dumps(wide(1_000)))

        json.load(reader)

        assert reader.calls == [()], f"load() should read once, unsized: {reader.calls}"

    def test_detect_encoding_touches_only_the_first_bytes(self) -> None:
        touched: list[Any] = []

        class Recording(bytes):
            def __getitem__(self, index: Any) -> Any:
                touched.append(index)
                return bytes.__getitem__(self, index)

            def startswith(self, *args: Any) -> bool:
                touched.append(("startswith", args))
                return bytes.startswith(self, *args)

        blob = Recording(b'{"a": 1}' * 100_000)

        assert json.detect_encoding(blob) == "utf-8"
        indices = [item for item in touched if isinstance(item, int)]
        assert indices and max(indices) < 4, f"detect_encoding touched {touched}"
        assert len([item for item in touched if isinstance(item, tuple)]) == 3

    def test_detect_encoding_by_prefix(self) -> None:
        assert json.detect_encoding(b"\xff\xfe" + '{"a": 1}'.encode("utf-16-le")) == "utf-16"
        assert json.detect_encoding('{"a": 1}'.encode("utf-16-be")) == "utf-16-be"
        assert json.detect_encoding('{"a": 1}'.encode("utf-32-le")) == "utf-32-le"
        assert json.detect_encoding(b"\xef\xbb\xbf{}") == "utf-8-sig"
        assert json.loads('{"a": 1}'.encode("utf-16")) == {"a": 1}

    def test_repeated_keys_in_one_document_are_one_object(self) -> None:
        records = json.loads('[{"identifier": 1}, {"identifier": 2}]')
        first, second = (next(iter(record)) for record in records)

        assert first is second

        other = next(iter(json.loads('{"identifier": 3}')))
        assert other == first
        assert other is not first, "the memo lives for one call, not across calls"


class TestDecodingHooks:
    """`object_hook` sees each finished dict, innermost first;
    `object_pairs_hook` sees the pair list and takes priority; the number
    hooks see the literal's text; `strict=False` admits control characters."""

    def test_object_hook_receives_every_key_of_each_object(self) -> None:
        seen: list[int] = []

        def hook(dct: dict[str, Any]) -> dict[str, Any]:
            seen.append(len(dct))
            return dct

        json.loads('{"a":1,"b":2,"c":3,"d":4}', object_hook=hook)

        assert seen == [4]

    def test_object_hook_runs_once_per_object_innermost_first(self) -> None:
        calls: list[list[str]] = []

        def hook(dct: dict[str, Any]) -> dict[str, Any]:
            calls.append(list(dct))
            return dct

        json.loads('{"outer":{"a":1,"b":2},"other":{"c":3}}', object_hook=hook)

        assert calls == [["a", "b"], ["c"], ["outer", "other"]]

    def test_object_pairs_hook_receives_pairs_and_wins(self) -> None:
        pairs_seen: list[list[tuple[str, Any]]] = []
        dict_calls: list[dict[str, Any]] = []

        def pairs_hook(pairs: list[tuple[str, Any]]) -> Any:
            pairs_seen.append(pairs)
            return pairs

        result = json.loads(
            '{"b": 1, "a": 2}', object_hook=dict_calls.append, object_pairs_hook=pairs_hook
        )

        assert result == [("b", 1), ("a", 2)]
        assert pairs_seen == [[("b", 1), ("a", 2)]]
        assert dict_calls == []

    def test_number_hooks_receive_the_literal_text(self) -> None:
        ints: list[str] = []
        floats: list[str] = []
        constants: list[str] = []

        json.loads(
            "[1, 2.5, -3e2, NaN, Infinity]",
            parse_int=lambda text: ints.append(text),
            parse_float=lambda text: floats.append(text),
            parse_constant=lambda text: constants.append(text),
        )

        assert (ints, floats, constants) == (["1"], ["2.5", "-3e2"], ["NaN", "Infinity"])

    def test_an_integer_past_the_digit_limit_raises_in_both_directions(self) -> None:
        limit = sys.get_int_max_str_digits()
        if limit == 0:
            pytest.skip("the integer digit limit is disabled in this interpreter")
        literal = "1" * (limit + 1)

        with pytest.raises(ValueError, match="Exceeds the limit"):
            json.loads(literal)
        with pytest.raises(ValueError, match="Exceeds the limit"):
            json.dumps(int("1" * limit) * 10 + 1)

        assert json.loads(literal, parse_int=float) == float(literal)
        assert json.loads("1" * limit) == int("1" * limit)

    def test_strict_controls_control_characters(self) -> None:
        with pytest.raises(json.JSONDecodeError, match="Invalid control character"):
            json.loads('"a\tb"')

        assert json.JSONDecoder(strict=False).decode('"a\tb"') == "a\tb"
        assert json.loads('"a\tb"', strict=False) == "a\tb"


class TestRawDecodeStopsAtTheValue:
    """`raw_decode()` | O(v): parses one value and returns the index after it;
    `decode()` rejects a second document."""

    def test_it_returns_the_value_and_where_it_ended(self) -> None:
        decoder = json.JSONDecoder()

        assert decoder.raw_decode('{"a": 1} trailing', 0) == ({"a": 1}, 8)
        assert decoder.raw_decode('xx{"a": 1}', 2) == ({"a": 1}, 10)

    def test_it_walks_concatenated_documents(self) -> None:
        decoder = json.JSONDecoder()
        stream = '{"id": 1}{"id": 2}[3]'
        documents = []
        position = 0

        while position < len(stream):
            value, position = decoder.raw_decode(stream, position)
            documents.append(value)

        assert documents == [{"id": 1}, {"id": 2}, [3]]

    def test_decode_rejects_a_second_document_and_accepts_whitespace(self) -> None:
        decoder = json.JSONDecoder()

        with pytest.raises(json.JSONDecodeError, match="Extra data") as info:
            decoder.decode('{"id": 1}{"id": 2}')
        assert info.value.pos == 9
        assert decoder.decode('  {"id": 1}  \n') == {"id": 1}

    @pytest.mark.timing
    def test_a_tail_after_the_value_costs_nothing(self) -> None:
        decoder = json.JSONDecoder()
        value = '{"a": 1}'
        with_tail = value + " " * 10_000_000

        bare_ns = best_ns(lambda: decoder.raw_decode(value, 0), inner=200)
        tail_ns = best_ns(lambda: decoder.raw_decode(with_tail, 0), inner=200)

        ratio = tail_ns / bare_ns
        assert ratio < 5, f"a 10 MB tail cost x{ratio:.2f} ({bare_ns:.0f}ns to {tail_ns:.0f}ns)"


class RecordingDoc(str):
    """A document that records the scans an error makes over it."""

    calls: list[tuple[str, tuple[Any, ...]]] = []

    def count(self, *args: Any) -> int:
        RecordingDoc.calls.append(("count", args))
        return str.count(self, *args)

    def rfind(self, *args: Any) -> int:
        RecordingDoc.calls.append(("rfind", args))
        return str.rfind(self, *args)


class TestDecodeErrorCostsItsPosition:
    """`JSONDecodeError(msg, doc, pos)` | O(p + len(msg)) | O(len(msg)):
    counts the newlines before `pos`, formats `msg` into the message, and
    keeps `doc` by reference."""

    def test_the_parser_scans_the_document_up_to_pos_once(self) -> None:
        doc = RecordingDoc("[1, 2,\n 3, oops]")
        RecordingDoc.calls = []

        with pytest.raises(json.JSONDecodeError) as info:
            json.loads(doc)

        error = info.value
        assert error.pos == 11
        assert RecordingDoc.calls == [("count", ("\n", 0, 11)), ("rfind", ("\n", 0, 11))]
        assert error.doc is doc
        assert (error.msg, error.lineno, error.colno) == ("Expecting value", 2, 5)
        assert isinstance(error, ValueError)

    def test_a_direct_construction_agrees(self) -> None:
        doc = "a\nb\ncd"

        error = json.JSONDecodeError("bad", doc, 5)

        assert (error.msg, error.pos, error.lineno, error.colno) == ("bad", 5, 3, 2)
        assert error.doc is doc
        assert str(error) == "bad: line 3 column 2 (char 5)"

    def test_the_message_is_copied_into_the_formatted_text(self) -> None:
        msg = "m" * 100_000

        error = json.JSONDecodeError(msg, "", 0)

        assert str(error) == msg + ": line 1 column 1 (char 0)"


class TestNestingIsBoundedByRecursion:
    """Python encoders obey `sys.getrecursionlimit()`; the C paths round-trip
    moderate nesting without asserting a platform-specific failure depth."""

    def test_c_paths_preserve_nested_arrays(self) -> None:
        text = "[" * 100 + "]" * 100
        value = json.loads(text)

        assert json.dumps(value) == text
        for _ in range(99):
            assert isinstance(value, list) and len(value) == 1
            value = value[0]
        assert value == []

    @pytest.mark.parametrize("operation", ["dump", "iterencode"])
    def test_python_encoder_raises_within_twice_the_recursion_limit(self, operation: str) -> None:
        def encode(value: Any) -> None:
            if operation == "dump":
                json.dump(value, CountingSink())
            else:
                for _ in json.JSONEncoder().iterencode(value):
                    pass

        encode(deep(100))

        with pytest.raises(RecursionError, match="recursion"):
            encode(deep(sys.getrecursionlimit() * 2))


READS_ALL_LINES_FIRST = sys.version_info >= (3, 14, 5) or (3, 13, 14) <= sys.version_info < (3, 14)


class TestJsonTool:
    """`python -m json.tool` parses the whole input before writing; with
    `--json-lines` it parses and prints one line at a time, reading the
    lines one at a time before 3.13.14 and 3.14.5 and all at once after."""

    @staticmethod
    def _run(stdin: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "json.tool", *args],
            input=stdin,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

    def test_it_pretty_prints_with_four_spaces(self) -> None:
        result = self._run('{"b": 1, "a": [1, 2]}\n')

        assert result.returncode == 0
        assert result.stdout == '{\n    "b": 1,\n    "a": [\n        1,\n        2\n    ]\n}\n'

    def test_a_second_document_prints_nothing_by_default(self) -> None:
        result = self._run('{"a": 1}\n{"b": 2}\n')

        assert result.returncode == 1
        assert result.stdout == ""
        assert "Extra data" in result.stderr

    def test_json_lines_prints_a_line_before_failing_on_the_next(self) -> None:
        result = self._run('{"a": 1}\n{"b": oops}\n', "--json-lines", "--no-indent")

        assert result.returncode == 1
        assert result.stdout == '{"a": 1}\n'
        assert "Expecting value" in result.stderr

    def test_whether_json_lines_reads_one_line_at_a_time(self) -> None:
        """A pipe held open after the first line separates the two readers:
        a line-at-a-time reader prints the first line while the pipe is open,
        a `readlines()` reader prints nothing until it closes. `-u` keeps the
        child's stdout from buffering the evidence."""
        process = subprocess.Popen(
            [sys.executable, "-u", "-m", "json.tool", "--json-lines", "--no-indent"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert process.stdin is not None and process.stdout is not None
        try:
            process.stdin.write('{"a": 1}\n')
            process.stdin.flush()

            if READS_ALL_LINES_FIRST:
                ready, _, _ = select.select([process.stdout], [], [], 5)
                assert not ready, "this release should read every line before printing one"
                first = ""
            else:
                ready, _, _ = select.select([process.stdout], [], [], 60)
                assert ready, "no output within 60s of the first line; the tool waited for more"
                first = process.stdout.readline()
                assert first == '{"a": 1}\n'

            stdout, stderr = process.communicate(input='{"b": 2}\n', timeout=60)
        finally:
            process.kill()

        assert (first + stdout, stderr, process.returncode) == ('{"a": 1}\n{"b": 2}\n', "", 0)


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
    """Each block runs in its own subprocess and working directory and
    asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "assert first is second" in s)
        mutated = source.replace("assert first is second", "assert first is not second", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
