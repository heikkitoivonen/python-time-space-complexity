"""Tests to verify documented behaviour of the json module.

All fourteen code blocks on docs/stdlib/json.md run, one of them raising the
exception its own comment names. Four claims did not survive measurement, and
the page had shipped a block that could never have run at all:

* ``'{"items": [1, 2, 3, ..., 10000]}'`` is not JSON. The Space Complexity
  example under Deserialization raised JSONDecodeError on its second line,
  which is where the page demonstrated the memory cost of a parse.
* ``object_hook`` was annotated "O(1) per call". The hook is handed the whole
  decoded object and the page's own example loops over it, so it costs the
  object's key count, not a constant.
* ``json.loads(line)`` in the JSONL loop was annotated "O(1) per line". A line
  costs its own length; the whole point of the JSONL shape is that the length
  is one record rather than the file.
* ``dumps(indent=2, sort_keys=True)`` was called "same complexity, different
  format". indent is linear, but sort_keys sorts each object's keys and is the
  only option here that is not: zero key comparisons without it, k log k with
  it.

The Best Practices block also advised reusing a JSONEncoder without saying
when that helps. dumps() with default options routes through a cached
module-level encoder, so the encoder the block built was the same work as the
dumps() call above it. Reuse only avoids a construction once a non-default
option is passed, which is what the block now shows.

Not settled by execution:

* "d = nesting depth" as the *unit* of dump()'s space bound. Peak memory is
  measured flat in record count, linear in d, and linear in the largest single
  scalar below, which is the claim's content; that the remaining term is exactly
  the generator chain plus the circular-reference marker dict is a source-level
  fact, not an observable one.
* "Reads full file into memory" for load() is asserted here as one read() call
  with no size argument. Whether the OS or the io layer buffered that read in
  pieces is outside what the page claims.

Two bounds were widened after review, both on axes the first version of this
file failed to vary:

* dump() was documented O(d). It builds each encoded scalar whole before
  handing it to write(), so a single large string sets the peak on its own:
  1 MB in one string costs 1,004,139 B, while the same megabyte split into
  ten-character strings costs 4,413 B. The bound is O(d + s) for the largest
  encoded scalar s. The first version varied record count using only short
  strings and varied depth using empty dictionaries, so nothing it measured
  could have caught this.
* dumps(indent=2) was documented O(n) in the input. Indentation repeats each
  level's whitespace, so a chain of d one-key dictionaries prints Theta(d^2)
  from O(d) of input, and both the time and the returned string follow the
  output rather than the input.

Axes still unvaried for the O(d + s) bound: scalar *kind* (only str is
measured, not a long int or a float), and escaping, which can make an encoded
string longer than its source.
"""

import json
import math
import pathlib
import random
import re
import subprocess
import sys
import textwrap
import timeit
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "json.md"

# Every fenced python block on the page, and the one that documents its own
# failure. Both counts are asserted so a broken extractor cannot pass by
# finding nothing.
EXPECTED_BLOCKS = 14
EXPECTED_RAISING_BLOCKS = 1


def per_call(func: Callable[[], Any], number: int = 20) -> float:
    """Seconds per call, taking the best of several runs."""
    return min(timeit.repeat(func, number=number, repeat=3)) / number


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class Sink:
    """A file-like object that counts what json.dump() hands it."""

    def __init__(self) -> None:
        self.writes = 0
        self.chars = 0

    def write(self, chunk: str) -> None:
        self.writes += 1
        self.chars += len(chunk)


def wide(n: int) -> dict[str, Any]:
    """A shallow object with n records."""
    return {"rows": [{"id": i, "name": f"n{i}"} for i in range(n)]}


def deep(d: int) -> dict[str, Any]:
    """A tiny object nested d levels."""
    root: dict[str, Any] = {}
    node = root
    for _ in range(d):
        node["child"] = {}
        node = node["child"]
    return root


class TestFunctionTable:
    """The six rows of the page's Functions table."""

    @pytest.mark.timing
    def test_dumps_is_linear_in_the_object(self) -> None:
        """A 16x object costs about 16x, not 256x.

        The shape being excluded is quadratic, so the threshold sits far from
        both: linear predicts 16, the assertion allows 40.
        """
        small, large = wide(2_000), wide(32_000)

        small_time = per_call(lambda: json.dumps(small))
        large_time = per_call(lambda: json.dumps(large))

        ratio = large_time / small_time
        assert ratio < 40, (
            f"dumps() does not look linear: 16x the object cost {ratio:.1f}x "
            f"({small_time:.2e}s vs {large_time:.2e}s)"
        )

    def test_dumps_output_grows_with_the_object(self) -> None:
        """O(n) space for dumps() is the output string itself."""
        lengths = [len(json.dumps(wide(n))) for n in (1_000, 2_000, 4_000)]

        for shorter, longer in zip(lengths, lengths[1:], strict=False):
            assert 1.9 < longer / shorter < 2.2, f"output is not tracking n: {lengths}"

    @pytest.mark.timing
    def test_loads_is_linear_in_the_text(self) -> None:
        small, large = json.dumps(wide(2_000)), json.dumps(wide(32_000))

        small_time = per_call(lambda: json.loads(small))
        large_time = per_call(lambda: json.loads(large))

        ratio = large_time / small_time
        assert ratio < 40, (
            f"loads() does not look linear: 16x the text cost {ratio:.1f}x "
            f"({small_time:.2e}s vs {large_time:.2e}s)"
        )

    def test_loads_result_grows_with_the_text(self) -> None:
        """O(n) space for loads() is the object tree it builds."""
        small_text, large_text = json.dumps(wide(4_000)), json.dumps(wide(16_000))

        peaks = [
            peak_bytes(lambda: json.loads(small_text)),
            peak_bytes(lambda: json.loads(large_text)),
        ]

        assert peaks[1] > 2 * peaks[0], (
            f"a 4x document should build a much larger result: {peaks} bytes"
        )

    def test_encoder_and_decoder_round_trip(self) -> None:
        """JSONEncoder.encode() and JSONDecoder.decode() are the same work."""
        obj = wide(50)

        encoded = json.JSONEncoder().encode(obj)

        assert encoded == json.dumps(obj)
        assert json.JSONDecoder().decode(encoded) == obj


class TestDumpStreams:
    """`json.dump(obj, fp)` | O(n) | O(d) | writes incrementally."""

    def test_dump_writes_many_small_chunks(self) -> None:
        sink = Sink()

        json.dump(wide(5_000), sink)

        assert sink.chars == len(json.dumps(wide(5_000)))
        assert sink.writes > 1_000, (
            f"dump() should stream, not hand over one string: {sink.writes} writes"
        )

    def test_dump_peak_is_flat_in_n(self) -> None:
        """The O(d) claim's content: peak does not track the output size.

        Output grows 100x across these three; the peak must not.
        """
        objects = [wide(n) for n in (1_000, 10_000, 100_000)]
        outputs = [len(json.dumps(obj)) for obj in objects]

        peaks = [peak_bytes(lambda obj=obj: json.dump(obj, Sink())) for obj in objects]

        assert outputs[-1] > 50 * outputs[0], f"the inputs did not spread: {outputs}"
        assert max(peaks) < 4 * min(peaks), (
            f"dump() peak should not track output size: peaks {peaks} for outputs {outputs}"
        )

    def test_dump_peak_grows_with_depth(self) -> None:
        """The other half of O(d): depth is what the peak does track."""
        shallow, nested = deep(10), deep(400)

        shallow_peak = peak_bytes(lambda: json.dump(shallow, Sink()))
        nested_peak = peak_bytes(lambda: json.dump(nested, Sink()))

        assert nested_peak > 5 * shallow_peak, (
            f"40x the depth should cost far more: {shallow_peak} B vs {nested_peak} B"
        )

    def test_dump_peak_tracks_the_largest_scalar(self) -> None:
        """The s in O(d + s): a chunk is built whole before it is written.

        Depth is fixed at 2 here, so d cannot explain the growth. The control
        below rules out total document size, which would predict the same
        peak for both.
        """
        peaks = [
            peak_bytes(lambda obj={"a": {"b": "x" * s}}: json.dump(obj, Sink()))
            for s in (10_000, 100_000, 1_000_000)
        ]

        assert peaks[-1] > 20 * peaks[0], (
            f"peak should follow the largest scalar: {peaks} bytes for 10 KB, 100 KB, 1 MB"
        )

    def test_dump_peak_ignores_total_size_when_scalars_are_small(self) -> None:
        """The control: the same characters, split up, cost nothing extra."""
        objects = [
            {"a": {f"k{i}": "x" * 10 for i in range(total // 10)}} for total in (10_000, 1_000_000)
        ]
        outputs = [len(json.dumps(obj)) for obj in objects]

        peaks = [peak_bytes(lambda obj=obj: json.dump(obj, Sink())) for obj in objects]

        assert outputs[-1] > 50 * outputs[0], f"the documents did not spread: {outputs}"
        assert max(peaks) < 4 * min(peaks), (
            f"many short strings should not raise the peak: {peaks} for outputs {outputs}"
        )

    def test_dumps_holds_the_whole_string(self) -> None:
        """The contrast the table draws: dumps() is O(n) where dump() is O(d)."""
        obj = wide(20_000)
        output_size = len(json.dumps(obj))

        dump_peak = peak_bytes(lambda: json.dump(obj, Sink()))
        dumps_peak = peak_bytes(lambda: json.dumps(obj))

        assert dumps_peak > output_size
        assert dump_peak < output_size / 10, (
            f"dump() should not hold the output: {dump_peak} B against {output_size} chars"
        )


class TestLoadReadsEverything:
    """`json.load(fp)` | O(n) | O(n) | Reads full file into memory."""

    def test_load_reads_the_file_in_one_call(self) -> None:
        class CountingReader:
            def __init__(self, text: str) -> None:
                self.text = text
                self.calls: list[tuple[Any, ...]] = []

            def read(self, *args: Any) -> str:
                self.calls.append(args)
                return self.text

        reader = CountingReader(json.dumps(wide(1_000)))

        json.load(reader)

        assert reader.calls == [()], (
            f"load() should read the whole file once, unsized: {reader.calls}"
        )


class CountingStr(str):
    """A dict key that counts the comparisons a sort makes on it.

    The counter is not called `count`: str already has that method, and
    shadowing it on a str subclass is a type error rather than a rename.
    """

    comparisons = 0

    def __lt__(self, other: str) -> bool:
        CountingStr.comparisons += 1
        return str.__lt__(self, other)

    def __gt__(self, other: str) -> bool:
        CountingStr.comparisons += 1
        return str.__gt__(self, other)


class TestSortKeys:
    """sort_keys is the one dumps() option that is not linear.

    Counted exactly rather than timed: the comparison count is deterministic
    for a fixed key order, so there is no threshold to flake on. The counts
    themselves are Timsort's and may shift between releases; only the shape is
    asserted.
    """

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
        """16x the keys costs more than 16x the comparisons.

        Linear predicts 16.0 and k log k predicts about 23, so the threshold
        sits between them with room on both sides. Measured 22.9 on 3.11.
        """
        small = self._comparisons(512, sort_keys=True)
        large = self._comparisons(8_192, sort_keys=True)

        ratio = large / small
        predicted = 16 * math.log2(8_192) / math.log2(512)
        assert ratio > 17.5, (
            f"sort_keys looks linear: 16x the keys cost {ratio:.1f}x "
            f"({small} vs {large} comparisons, k log k predicts {predicted:.1f})"
        )


class TestIndentIsOutputSensitive:
    """indent repeats each level's whitespace, so output outgrows input."""

    def test_indented_output_is_quadratic_in_depth(self) -> None:
        """Doubling the depth roughly quadruples the pretty-printed output."""
        lengths = [len(json.dumps(deep(d), indent=2)) for d in (50, 100, 200)]

        for shorter, longer in zip(lengths, lengths[1:], strict=False):
            assert longer / shorter > 3.0, (
                f"indented output should grow faster than the input: {lengths}"
            )

    def test_unindented_output_is_linear_in_depth(self) -> None:
        """The control: without indent the same objects grow 2x, not 4x."""
        lengths = [len(json.dumps(deep(d))) for d in (50, 100, 200)]

        for shorter, longer in zip(lengths, lengths[1:], strict=False):
            assert 1.9 < longer / shorter < 2.2, f"plain output should track input: {lengths}"


class TestEncoderReuse:
    """dumps() caches an encoder only while every option is left alone."""

    def test_default_options_route_through_the_cached_encoder(self) -> None:
        marker = object()

        class Marker:
            def encode(self, obj: Any) -> Any:
                return marker

        original = json._default_encoder  # type: ignore[attr-defined]
        json._default_encoder = Marker()  # type: ignore[attr-defined]
        try:
            cached = json.dumps({"a": 1})
            with_option = json.dumps({"a": 1}, sort_keys=True)
        finally:
            json._default_encoder = original  # type: ignore[attr-defined]

        assert cached is marker, "dumps() with no options should reuse the module encoder"
        assert with_option == '{"a": 1}', "an option should bypass the cached encoder"

    def test_an_option_builds_a_fresh_encoder_per_call(self) -> None:
        class SpyEncoder(json.JSONEncoder):
            inits = 0

            def __init__(self, **kwargs: Any) -> None:
                SpyEncoder.inits += 1
                super().__init__(**kwargs)

        SpyEncoder.inits = 0
        for _ in range(20):
            json.dumps({"a": 1}, cls=SpyEncoder)

        assert SpyEncoder.inits == 20, (
            f"each dumps() with options should build its own encoder: {SpyEncoder.inits}"
        )

        encoder = SpyEncoder()
        SpyEncoder.inits = 0
        for _ in range(20):
            encoder.encode({"a": 1})

        assert SpyEncoder.inits == 0, "a held encoder should not be rebuilt"


class TestObjectHook:
    """The hook is handed whole objects, so it cannot be O(1) by inspection."""

    def test_hook_receives_every_key_of_each_object(self) -> None:
        seen: list[int] = []

        def hook(dct: dict[str, Any]) -> dict[str, Any]:
            seen.append(len(dct))
            return dct

        json.loads('{"a":1,"b":2,"c":3,"d":4}', object_hook=hook)

        assert seen == [4], f"the hook should see the whole object at once: {seen}"

    def test_hook_runs_once_per_object_not_once_per_key(self) -> None:
        calls: list[int] = []

        def hook(dct: dict[str, Any]) -> dict[str, Any]:
            calls.append(len(dct))
            return dct

        json.loads('{"outer":{"a":1,"b":2},"other":{"c":3}}', object_hook=hook)

        assert sorted(calls) == [1, 2, 2], f"one call per object, innermost first: {calls}"


class TestCircularReferences:
    """The Common Issues block documents the exception it raises."""

    def test_circular_reference_raises_value_error(self) -> None:
        first: dict[str, Any] = {"name": "A"}
        second: dict[str, Any] = {"name": "B", "ref": first}
        first["ref"] = second

        with pytest.raises(ValueError, match="Circular reference detected"):
            json.dumps(first)


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


def _expected_exception(source: str) -> str | None:
    """The exception a block's own comment says it raises, if any."""
    match = re.search(r"#\s*([A-Z]\w*(?:Error|Exception))\b", source)
    return match.group(1) if match else None


def _run(source: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "_block.py"
    script.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, script.name],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=120,
        stdin=subprocess.DEVNULL,
        check=False,
    )


@pytest.fixture
def page_workspace(tmp_path: pathlib.Path) -> pathlib.Path:
    """A directory holding the files the page's examples assume exist.

    'huge.json' and 'data.jsonl' are named by the Memory Efficiency block but
    never created by it; 'data.json' is written by the dump() block and read
    by the load() block that follows, so the blocks run in page order here.
    """
    (tmp_path / "huge.json").write_text(json.dumps(wide(10)), encoding="utf-8")
    (tmp_path / "data.jsonl").write_text('{"a": 1}\n{"b": 2}\n', encoding="utf-8")
    return tmp_path


class TestDocumentedExamples:
    """Every block runs, and the one that raises raises what it claims."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )
        raising = [line for line, source in blocks if _expected_exception(source)]
        assert len(raising) == EXPECTED_RAISING_BLOCKS, (
            f"expected {EXPECTED_RAISING_BLOCKS} block documenting an exception, found {raising}"
        )

    def test_every_block_behaves_as_the_page_says(self, page_workspace: pathlib.Path) -> None:
        failures: list[str] = []

        for line, source in _blocks():
            expected = _expected_exception(source)
            result = _run(source, page_workspace)

            if expected is None:
                if result.returncode != 0:
                    failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()}")
            elif result.returncode == 0:
                failures.append(f"{PAGE.name}:{line} claims {expected} but succeeded")
            elif expected not in result.stderr:
                failures.append(
                    f"{PAGE.name}:{line} claims {expected}, raised: {result.stderr.strip()}"
                )

        assert not failures, "\n".join(failures)

    def test_the_runner_catches_a_broken_block(self, page_workspace: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = _blocks()[0][1]
        broken = original + "\njson.loads('{\"items\": [1, 2, ..., 3]}')\n"
        assert broken != original, "the mutation did not change the block"

        result = _run(broken, page_workspace)

        assert result.returncode != 0
        assert "JSONDecodeError" in result.stderr
