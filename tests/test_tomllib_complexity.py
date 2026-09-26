"""Tests for docs/stdlib/tomllib.md.

The page prices both parsing functions at O(n·d): n characters, and d parts in
the longest key path, a table header's dotted parts plus a dotted key's under
it. Linearity in n is settled by timing, since the parser is one pure-Python
pass and nothing short of a stopwatch separates linear from quadratic across
input shapes. The d factor is settled twice: by traced allocation, which needs
no tolerance, and by timing. Callback, file and error rows are settled by
observation.

Measurement scope:

* Thirteen shapes are each parsed at 1,000, 4,000 and 16,000 units: flat keys,
  `[table]` headers, `[[array]]` headers, three-part dotted keys with distinct
  prefixes, dotted keys sharing a prefix, one long basic string, simple
  escapes, `\\u` escapes, multi-line basic strings with escapes, one array of
  integers, one array of floats, one inline table, and comment lines. Every 4x
  step must cost under 8x, where linear predicts 4x and quadratic 16x.
  Nesting is two further shapes: 200 lines each holding arrays or inline
  tables nested 10, 30 and 90 deep, where each 3x step must cost under 5x
  (linear 3x, quadratic 9x).
* One top-level dotted key: from 100 to 800 parts the traced peak grows more
  than 20x and less than 200x (linear predicts 8x, quadratic 64x, cubic
  512x; x38 to x46 on 3.14.7), and in a timing test from 100 to 900 parts
  time grows more than 20x and less than 250x (linear 9x, quadratic 81x,
  cubic 729x; x46 to x91 on 3.14.7).
* A table header of 100 and of 800 parts over a fixed 2,000 keys, which moves
  the text by under 20%: with two-part keys the traced peak grows more than 3x
  and less than 25x (x5.7 to x5.9 on 3.14.7), and with one-part keys time
  does the same (x6.8 to x7.3); O(n·d) predicts 8x, a d² term 64x.
  Flat keys at 2,000 and 20,000 lines peak under 20x apart for 10x the text.
* A key or table header one part over the recursion limit raises
  `RecursionError` on 3.11.16, 3.12.14, 3.13.14, 3.14.6 and later patch
  releases, and parses on the releases before them; a key exactly at the
  limit parses on both.
* 5,000 nested arrays and 5,000 nested inline tables raise `RecursionError`.
* `parse_float` is a counting callback: it receives each float's text,
  underscores and `inf` included, once per float in keys, arrays and inline
  tables, and is never called for integers, datetimes or quoted strings. A
  callback returning a `dict` raises `ValueError`.
* `load()` is observed to call `read()` once with no size, and to raise
  `TypeError` on a text-mode stream.
* On 3.14+, `TOMLDecodeError(msg, doc, pos)` holds `doc` by identity and
  reports `lineno`, `colno` and `pos`; its construction time grows more than
  50x as `pos` moves from 1,000 to 1,000,000 in one document. Free-form
  arguments warn `DeprecationWarning`. On every version a failed parse raises
  a `ValueError` subclass carrying the line and column in its message.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* That n·d bounds the two together is read from Lib/tomllib/_parser.py:
  `key_value_rule` walks the full path once per container in a dotted key,
  and `Flags.is_` and `NestedDict.get_or_create_nest` walk it once more
  each. The tests move one variable at a time, at key counts of one and
  2,000.
* Dotted keys inside inline tables and table headers are quadratic in their
  parts only through `parse_key` rebuilding the key tuple once per part, read
  from source. Below the key-part cap that term is too small to separate
  from the linear one by timing (for 9x the parts, x16 for a header and x30 for an inline-table key on
  3.14.7), so only
  top-level dotted keys are measured.
* That the `TOMLDecodeError` raised by a failed parse on 3.11 to 3.13 costs
  O(pos) is read from `suffixed_err` in those releases; only the 3.14+
  constructor is timed.
* Integer literals, datetimes, non-ASCII keys, CRLF line endings and invalid
  UTF-8 input are not varied. Nor is a raised recursion limit: the cap is read
  when `tomllib` is imported.
"""

from __future__ import annotations

import io
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import warnings
from collections.abc import Callable
from typing import Any

import pytest

tomllib: Any = pytest.importorskip("tomllib")

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "tomllib.md"
EXPECTED_BLOCKS = 7

# The first patch release of each minor that caps a key's parts.
KEY_PART_CAP = {
    (3, 11): (3, 11, 16),
    (3, 12): (3, 12, 14),
    (3, 13): (3, 13, 14),
    (3, 14): (3, 14, 6),
}


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


def dotted(parts: int, prefix: str = "k") -> str:
    return ".".join(f"{prefix}{index}" for index in range(parts))


def key_parts_are_capped() -> bool:
    release = KEY_PART_CAP.get(sys.version_info[:2])
    return release is None or sys.version_info[:3] >= release


SHAPES: dict[str, Callable[[int], str]] = {
    "flat keys": lambda n: "\n".join(f"k{i} = {i}" for i in range(n)),
    "table headers": lambda n: "\n".join(f"[t{i}]\nk = {i}" for i in range(n)),
    "array-of-table headers": lambda n: "\n".join(f"[[t]]\nk = {i}" for i in range(n)),
    "distinct dotted keys": lambda n: "\n".join(f"a{i}.b.c = {i}" for i in range(n)),
    "shared dotted prefix": lambda n: "\n".join(f"a.b.c{i} = {i}" for i in range(n)),
    "long string": lambda n: 'k = "' + "x" * (n * 10) + '"',
    "escapes": lambda n: 'k = "' + "\\n" * (n * 5) + '"',
    "unicode escapes": lambda n: 'k = "' + "\\u00e9" * (n * 2) + '"',
    "multi-line escapes": lambda n: 'k = """' + "a\\n" * (n * 3) + '"""',
    "integer array": lambda n: "k = [" + ",".join(str(i) for i in range(n)) + "]",
    "float array": lambda n: "k = [" + ",".join(f"{i}.5" for i in range(n)) + "]",
    "inline table": lambda n: "k = {" + ",".join(f"a{i} = {i}" for i in range(n)) + "}",
    "comments": lambda n: "\n".join(f"# comment {i}" for i in range(n)),
}

NESTED: dict[str, Callable[[int], str]] = {
    "nested arrays": lambda depth: "\n".join(
        f"k{i} = " + "[" * depth + "1" + "]" * depth for i in range(200)
    ),
    "nested inline tables": lambda depth: "\n".join(
        f"k{i} = " + "{a = " * depth + "1" + "}" * depth for i in range(200)
    ),
}


class TestParsingIsLinearInTheText:
    """`loads(s)` | O(n·d), O(n) for ordinary documents, and nesting arrays
    and inline tables adds nothing beyond their characters.

    Each 4x step in the input would cost 16x if any shape were quadratic.
    """

    @pytest.mark.parametrize("shape", list(SHAPES))
    def test_every_shape_parses(self, shape: str) -> None:
        result = tomllib.loads(SHAPES[shape](10))

        assert isinstance(result, dict) and (result or shape == "comments")

    @pytest.mark.timing
    @pytest.mark.parametrize("shape", list(SHAPES))
    def test_four_times_the_text_costs_about_four_times(self, shape: str) -> None:
        documents = [SHAPES[shape](units) for units in (1_000, 4_000, 16_000)]
        durations = [best_ns(lambda s=text: tomllib.loads(s)) for text in documents]
        ratios = [durations[i + 1] / durations[i] for i in range(2)]

        assert all(ratio < 8 for ratio in ratios), (
            f"{shape}: {[len(s) for s in documents]} characters took {durations} ns, "
            f"steps {ratios}; linear predicts 4x a step, quadratic 16x"
        )

    @pytest.mark.parametrize("shape", list(NESTED))
    def test_nesting_parses_to_the_same_depth(self, shape: str) -> None:
        value = tomllib.loads(NESTED[shape](30))["k0"]
        depth = 0
        while isinstance(value, (list, dict)):
            value = value[0] if isinstance(value, list) else value["a"]
            depth += 1

        assert (depth, value) == (30, 1)

    @pytest.mark.timing
    @pytest.mark.parametrize("shape", list(NESTED))
    def test_three_times_the_depth_costs_about_three_times(self, shape: str) -> None:
        documents = [NESTED[shape](depth) for depth in (10, 30, 90)]
        durations = [best_ns(lambda s=text: tomllib.loads(s)) for text in documents]
        ratios = [durations[i + 1] / durations[i] for i in range(2)]

        assert all(ratio < 5 for ratio in ratios), (
            f"{shape}: depths 10, 30, 90 took {durations} ns, steps {ratios}; "
            "linear predicts 3x a step, quadratic 9x"
        )

    def test_flat_keys_allocate_in_proportion_to_the_text(self) -> None:
        small, large = SHAPES["flat keys"](2_000), SHAPES["flat keys"](20_000)
        tomllib.loads(small)

        peaks = [peak_bytes(lambda: tomllib.loads(small)), peak_bytes(lambda: tomllib.loads(large))]

        assert peaks[1] < peaks[0] * 20, f"10x the text peaked at {peaks}"


class TestKeyDepthMultipliesTheCost:
    """`loads(s)` | O(n·d) | O(n·d): a dotted key with p parts pays O(p²), and
    every key under a deep header pays for the header's parts.

    Allocation separates the shapes without tolerance; timing confirms that
    time moves with it.
    """

    @staticmethod
    def one_key(parts: int) -> str:
        return dotted(parts) + " = 1"

    @staticmethod
    def under_header(header_parts: int, key: str) -> str:
        keys = "\n".join(key.format(i) for i in range(2_000))
        return f"[{dotted(header_parts)}]\n{keys}"

    def test_one_dotted_key_parses_to_nested_tables(self) -> None:
        value = tomllib.loads(self.one_key(50))
        for index in range(49):
            value = value[f"k{index}"]

        assert value == {"k49": 1}

    def test_a_dotted_key_allocates_with_its_parts_squared(self) -> None:
        small, large = self.one_key(100), self.one_key(800)

        peaks = [peak_bytes(lambda: tomllib.loads(small)), peak_bytes(lambda: tomllib.loads(large))]

        assert peaks[0] * 20 < peaks[1] < peaks[0] * 200, (
            f"8x the parts peaked at {peaks}; linear predicts 8x, quadratic 64x, cubic 512x"
        )

    @pytest.mark.timing
    def test_a_dotted_key_costs_its_parts_squared(self) -> None:
        small, large = self.one_key(100), self.one_key(900)

        durations = [
            best_ns(lambda: tomllib.loads(small), inner=5),
            best_ns(lambda: tomllib.loads(large), inner=5),
        ]
        ratio = durations[1] / durations[0]

        assert 20 < ratio < 250, (
            f"9x the parts took {durations} ns, x{ratio:.1f}; linear predicts 9x, quadratic 81x"
        )

    def test_a_deep_header_multiplies_what_its_keys_allocate(self) -> None:
        shallow = self.under_header(100, "x{}.y = 1")
        deep = self.under_header(800, "x{}.y = 1")
        assert len(deep) < len(shallow) * 1.2

        peaks = [
            peak_bytes(lambda: tomllib.loads(shallow)),
            peak_bytes(lambda: tomllib.loads(deep)),
        ]

        assert peaks[0] * 3 < peaks[1] < peaks[0] * 25, (
            f"8x the header parts at one key count peaked at {peaks}; O(n·d) predicts 8x"
        )

    @pytest.mark.timing
    def test_a_deep_header_multiplies_what_its_keys_cost(self) -> None:
        shallow = self.under_header(100, "x{} = 1")
        deep = self.under_header(800, "x{} = 1")
        assert len(deep) < len(shallow) * 1.2

        durations = [best_ns(lambda: tomllib.loads(shallow)), best_ns(lambda: tomllib.loads(deep))]
        ratio = durations[1] / durations[0]

        assert 3 < ratio < 25, (
            f"8x the header parts under 2,000 plain keys took {durations} ns, x{ratio:.1f}"
        )

    def test_a_header_and_dotted_keys_build_the_same_tables(self) -> None:
        headed = tomllib.loads("[server.http]\nport = 80\nhost = 'a'\n")
        spelled = tomllib.loads("server.http.port = 80\nserver.http.host = 'a'\n")

        assert headed == spelled == {"server": {"http": {"port": 80, "host": "a"}}}

    def test_a_table_cannot_be_declared_twice(self) -> None:
        with pytest.raises(tomllib.TOMLDecodeError, match="Cannot declare"):
            tomllib.loads("[server]\nport = 80\n[server]\nhost = 'a'\n")


class TestKeyPartsAreCappedOnPatchedReleases:
    """Version Notes: from 3.11.16, 3.12.14, 3.13.14 and 3.14.6, a key or
    table header with more dotted parts than the recursion limit raises
    `RecursionError`; earlier releases parse it."""

    @pytest.fixture
    def limit(self) -> int:
        limit = sys.getrecursionlimit()
        if key_parts_are_capped():
            assert tomllib._parser.MAX_KEY_PARTS == limit  # noqa: SLF001
        return limit

    def test_a_key_at_the_limit_parses(self, limit: int) -> None:
        assert tomllib.loads(dotted(limit) + " = 1")
        assert tomllib.loads(f"[{dotted(limit)}]")

    @pytest.mark.parametrize("template", ["{} = 1", "[{}]"])
    def test_one_part_over_the_limit(self, limit: int, template: str) -> None:
        document = template.format(dotted(limit + 1))

        if key_parts_are_capped():
            with pytest.raises(RecursionError, match="parts"):
                tomllib.loads(document)
        else:
            assert tomllib.loads(document)


class TestDeepNestingRaises:
    """Arrays and inline tables are parsed recursively; nesting past the
    recursion limit raises `RecursionError`."""

    @pytest.mark.parametrize("opening, closing", [("[", "]"), ("{a = ", "}")])
    def test_five_thousand_levels_raise(self, opening: str, closing: str) -> None:
        document = "k = " + opening * 5_000 + "1" + closing * 5_000

        with pytest.raises(RecursionError):
            tomllib.loads(document)


class TestParseFloatIsCalledOncePerFloat:
    """`parse_float` | O(f) per float: once per float value, with its text as
    written, never for an integer; a `dict` or `list` result raises."""

    def test_it_sees_each_float_once_and_nothing_else(self) -> None:
        calls: list[str] = []

        def record(text: str) -> float:
            calls.append(text)
            return float(text)

        result = tomllib.loads(
            "a = 1_000.5\n"
            "b = [1.0, 2e3, inf, -nan, 7]\n"
            "c = {x = +inf, y = 3}\n"
            "d = 1979-05-27T07:32:00Z\n"
            "e = 0x1F\n"
            "f = '1.5'\n",
            parse_float=record,
        )

        assert calls == ["1_000.5", "1.0", "2e3", "inf", "-nan", "+inf"]
        assert result["a"] == 1000.5 and result["e"] == 31 and result["f"] == "1.5"

    def test_the_call_count_follows_the_floats(self) -> None:
        calls: list[str] = []
        document = "k = [" + ",".join(f"{i}.5" for i in range(1_000)) + "]"

        tomllib.loads(document, parse_float=lambda text: calls.append(text) or 0.0)

        assert len(calls) == 1_000

    @pytest.mark.parametrize("bad", [{}, []])
    def test_a_container_result_raises(self, bad: object) -> None:
        with pytest.raises(ValueError, match="must not return dicts or lists"):
            tomllib.loads("a = 1.5", parse_float=lambda _text: bad)


class TestLoadReadsTheWholeFile:
    """`load(fp)`: one `read()` of the whole binary file, then `loads()`; a
    text-mode file raises `TypeError`."""

    def test_one_read_with_no_size(self) -> None:
        sizes: list[object] = []

        class Recording(io.BytesIO):
            def read(self, size: int | None = -1, /) -> bytes:
                sizes.append(size)
                return super().read(size)

        assert tomllib.load(Recording(b"a = 1\nb = 'x'\n")) == {"a": 1, "b": "x"}
        assert sizes == [-1]

    def test_it_matches_loads_on_the_decoded_text(self) -> None:
        data = "name = 'café'\n[t]\nk = [1, 2]\n".encode()

        assert tomllib.load(io.BytesIO(data)) == tomllib.loads(data.decode())

    def test_a_text_mode_file_raises(self) -> None:
        with pytest.raises(TypeError, match="binary mode"):
            tomllib.load(io.StringIO("a = 1"))


class TestDecodeError:
    """`TOMLDecodeError(msg, doc, pos)` | O(pos) | O(1): a `ValueError`
    subclass whose message carries the position; on 3.14+ it keeps `doc` by
    reference and exposes the position as attributes."""

    DOCUMENT = "name = 'myapp'\nversion = \n"

    def test_a_failed_parse_raises_a_value_error_with_the_position(self) -> None:
        with pytest.raises(tomllib.TOMLDecodeError) as caught:
            tomllib.loads(self.DOCUMENT)

        assert isinstance(caught.value, ValueError)
        assert "line 2, column 11" in str(caught.value)

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="attributes added in 3.14")
    def test_the_attributes(self) -> None:
        with pytest.raises(tomllib.TOMLDecodeError) as caught:
            tomllib.loads(self.DOCUMENT)
        error = caught.value

        assert error.doc is self.DOCUMENT, "no CRLF, so the document itself is kept"
        assert (error.msg, error.lineno, error.colno) == ("Invalid value", 2, 11)
        assert error.pos == self.DOCUMENT.index("\n", 15)

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="signature added in 3.14")
    def test_free_form_arguments_are_deprecated(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            tomllib.TOMLDecodeError("m", "doc", 1)
        with pytest.warns(DeprecationWarning, match="Free-form arguments"):
            tomllib.TOMLDecodeError("free form")

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 14), reason="signature added in 3.14")
    def test_construction_counts_lines_up_to_pos(self) -> None:
        document = ("x" * 49 + "\n") * 20_000

        durations = [
            best_ns(lambda: tomllib.TOMLDecodeError("m", document, 1_000), inner=20),
            best_ns(lambda: tomllib.TOMLDecodeError("m", document, 999_000), inner=20),
        ]
        ratio = durations[1] / durations[0]

        assert ratio > 50, f"1,000x the position took {durations} ns, x{ratio:.1f}"


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
        line, source = next((n, s) for n, s in _blocks() if "calls == [" in s)
        mutated = source.replace("'2e3', 'inf']", "'2e3']", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr, result.stderr
