"""Tests for docs/stdlib/marshal.md.

The page prices all four functions as linear in the serialized size n, which
counts the objects written and their payload, with two exceptions it names: a
set adds a sort of its elements, and a set nested in a set is written again
for each enclosing set's sort. Growth is settled by timing at three sizes a
decade apart, space by traced allocation, sharing and file handling by direct
observation, and version-dependent behaviour under `sys.version_info` guards.

Measurement scope:

* `dumps()` and `loads()` of a list of 10,000, 100,000 and 1,000,000 short
  strings: each 10x step costs under 30x in time, against 100x for a
  quadratic. Traced peak allocation grows between 5x and 20x from 10,000 to
  100,000 strings, the one step it is measured on, and the `dumps()` peak
  lies between one and four times the output's length.
  `int` payload is varied alone, 100,000 to 10,000,000 bits, with the same
  30x bound per step for both directions.
* `dump()` is observed to make exactly one `write()` call, with bytes equal
  to what `dumps()` returns; its traced peak exceeds the output's length.
* `load()` is observed to take one value from a stream of several, to leave
  the stream just past it, and to raise `EOFError` at the end; its
  `readinto()` calls are at least the item count for lists of 10 and 1,000
  ints. A timing test on a 100,000-int list asserts `load()` of a stream
  costs over twice `loads()` of its bytes. `loads()` ignores trailing bytes
  and raises `EOFError` on empty input and `ValueError` on an unknown type
  code.
* Sharing: a chain of lists each holding the previous one twice, 16 levels
  deep, serializes over 1,000 times larger with version 2 than with the
  default, the default grows under 2.5x from 16 to 32 levels, and the
  round trip keeps `restored[0] is restored[1]`. A list containing itself
  round-trips with identity on versions 3 to `marshal.version` and raises
  `ValueError` on version 2.
* Sets, Python 3.11+: `{8, 0}` and `{0, 8}` iterate in different orders and
  dump to identical bytes, and `{1, 256}` is written with 256 first, the
  order of the elements' serialized forms rather than their values. On 3.10
  the two orders dump differently. A chain of frozensets each holding the
  previous one, 8 against 14 levels, costs over 16x more on 3.11+ where the
  output grows under 2x; on 3.10 the same pair costs under 8x.
* The nesting limit is observed on `dumps()` of nested lists and on `loads()`
  of a hand-built nested list, under a raised `sys.setrecursionlimit()`: 900
  levels pass everywhere, and the exact boundary - 2,000 levels pass, 2,001
  fail - is asserted on Linux and macOS, and 1,000 against 1,001 on Windows.
* Supported types are asserted by round trip; `bytearray`, `memoryview` and
  `array` and a `bytes` subclass come back as `bytes`; subclasses of `dict`,
  `int` and `str`, and a
  plain `object`, raise `ValueError`. `slice` round-trips on 3.14+ and
  raises `ValueError` with version 4, and on earlier versions.
  `marshal.version` is asserted as 5 on 3.14+ and 4 before.
* `allow_code=False` is asserted, on 3.13+, to make each of the four
  functions raise `ValueError` for a code object and to pass plain data.
* A `.pyc` written by `py_compile` is asserted to be a 16-byte header
  followed by a marshalled code object. Compiling 500 small functions is
  asserted to cost over five times unmarshalling the result.
* Every fenced Python block runs in its own subprocess and asserts its own
  result, and a mutated assertion in one of them is asserted to fail.

Not settled here:

* The O(s log s) sort of a set's elements is read from Python/marshal.c
  (`w_complex_object`, set branch, 3.11+), which sorts the pairs of each
  element's serialized form and the element. The tests observe the sorted
  order, which a comparison sort produces, not the comparison count.
* The 1,000-level limit applies on Windows only; it is guarded on
  `sys.platform` and runs on Windows CI, not locally. WASI and iOS builds,
  which the page does not mention, use 1,500.
* That `allow_code=False` does not make malformed data safe, and that a code
  object is only valid on the Python version that wrote it, come from the
  official documentation; neither can be settled by running one interpreter.
* That `importlib` reads `.pyc` files through `marshal.loads()` is read from
  Lib/importlib/_bootstrap_external.py (`_compile_bytecode`).
* Element types beyond `str`, `int` and lists of them, `float` and `complex`
  payloads, and file objects other than `io.BytesIO` are not varied.
"""

from __future__ import annotations

import array
import io
import marshal
import pathlib
import py_compile
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from functools import partial
from itertools import pairwise
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "marshal.md"
EXPECTED_BLOCKS = 6
# Typeshed's 3.10 signatures have no allow_code and accept only marshallable values.
UNTYPED: Any = marshal


def best_ns(func: Callable[[], Any], repeats: int = 5) -> float:
    """Fastest of `repeats` runs, in nanoseconds."""
    best: float | None = None
    for _ in range(repeats):
        start = time.perf_counter_ns()
        func()
        elapsed = time.perf_counter_ns() - start
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


def nested_lists(levels: int) -> list[Any]:
    """`levels` lists, each the only element of the one around it."""
    value: list[Any] = []
    for _ in range(levels - 1):
        value = [value]
    return value


def marshalled_nested_lists(levels: int) -> bytes:
    """Marshal data for `levels` nested one-element lists, built by hand."""
    return b"[\x01\x00\x00\x00" * (levels - 1) + b"[\x00\x00\x00\x00"


def doubled_chain(levels: int) -> list[Any]:
    """`levels` lists below the outermost, each held twice by the next."""
    value: list[Any] = []
    for _ in range(levels):
        value = [value, value]
    return value


def nested_frozensets(levels: int) -> frozenset[Any]:
    """A chain of frozensets, each holding the previous one and an int."""
    value: frozenset[Any] = frozenset()
    for index in range(levels):
        value = frozenset({value, index})
    return value


class RecordingSink:
    """A binary sink that keeps each object written to it, uncopied."""

    def __init__(self) -> None:
        self.writes: list[bytes] = []

    def write(self, data: bytes) -> int:
        self.writes.append(data)
        return len(data)


class CountingStream(io.BytesIO):
    """A BytesIO that counts its `readinto()` calls."""

    calls = 0

    def readinto(self, buffer: Any) -> int:
        self.calls += 1
        return super().readinto(buffer)


class TestLinearInSerializedSize:
    """`dumps()` and `loads()` | O(n) | O(n).

    Three sizes a decade apart separate linear (10x a step) from quadratic
    (100x a step) with a 30x threshold; traced peaks follow the same steps.
    """

    SIZES = (10_000, 100_000, 1_000_000)

    @staticmethod
    def strings(count: int) -> list[str]:
        return [str(index) for index in range(count)]

    @pytest.mark.timing
    def test_dumps_and_loads_time_grows_linearly(self) -> None:
        dump_ns: list[float] = []
        load_ns: list[float] = []
        for size in self.SIZES:
            value = self.strings(size)
            data = marshal.dumps(value)
            dump_ns.append(best_ns(partial(marshal.dumps, value)))
            load_ns.append(best_ns(partial(marshal.loads, data)))

        for name, times in (("dumps", dump_ns), ("loads", load_ns)):
            steps = [later / earlier for earlier, later in pairwise(times)]
            assert all(step < 30 for step in steps), f"{name} 10x steps cost {steps}"

    def test_space_grows_linearly(self) -> None:
        dump_peaks: list[int] = []
        load_peaks: list[int] = []
        for size in self.SIZES[:2]:
            value = self.strings(size)
            data = marshal.dumps(value)
            dump_peak = peak_bytes(partial(marshal.dumps, value))
            assert len(data) <= dump_peak < 4 * len(data), (
                f"dumps peaked at {dump_peak} bytes for {len(data)} bytes of output"
            )
            dump_peaks.append(dump_peak)
            load_peaks.append(peak_bytes(partial(marshal.loads, data)))

        for name, peaks in (("dumps", dump_peaks), ("loads", load_peaks)):
            step = peaks[1] / peaks[0]
            assert 5 < step < 20, f"{name} peak grew {step:.1f}x for 10x the strings"

    @pytest.mark.timing
    def test_an_int_costs_its_digits(self) -> None:
        dump_ns: list[float] = []
        load_ns: list[float] = []
        for bits in (100_000, 1_000_000, 10_000_000):
            value = (1 << bits) - 1
            data = marshal.dumps(value)
            dump_ns.append(best_ns(partial(marshal.dumps, value)))
            load_ns.append(best_ns(partial(marshal.loads, data)))

        for name, times in (("dumps", dump_ns), ("loads", load_ns)):
            steps = [later / earlier for earlier, later in pairwise(times)]
            assert all(step < 30 for step in steps), f"int {name} 10x steps cost {steps}"


class TestDumpBuildsTheWholeValue:
    """`dump()` | O(n) | O(n): builds the bytes as `dumps()` does, then one write."""

    def test_one_write_of_the_whole_value(self) -> None:
        value = [str(index) for index in range(10_000)]
        expected = marshal.dumps(value)
        sink = RecordingSink()

        marshal.dump(value, sink)

        assert sink.writes == [expected]

    def test_the_peak_holds_the_whole_output(self) -> None:
        value = [str(index) for index in range(100_000)]
        size = len(marshal.dumps(value))

        peak = peak_bytes(lambda: marshal.dump(value, RecordingSink()))

        assert peak >= size, f"dump peaked at {peak} bytes for {size} bytes of output"


class TestLoadReadsOneValue:
    """`load()` reads exactly one value, with `readinto()` calls for every item;
    `loads()` ignores what follows the value."""

    def test_values_read_back_in_order(self) -> None:
        stream = io.BytesIO()
        marshal.dump({"a": [1, 2]}, stream)
        first_end = stream.tell()
        marshal.dump("second", stream)
        stream.seek(0)

        assert marshal.load(stream) == {"a": [1, 2]}
        assert stream.tell() == first_end
        assert marshal.load(stream) == "second"
        with pytest.raises(EOFError):
            marshal.load(stream)

    def test_readinto_is_called_per_item(self) -> None:
        for count in (10, 1_000):
            stream = CountingStream(marshal.dumps(list(range(count))))
            marshal.load(stream)
            assert stream.calls >= count, f"{stream.calls} readinto calls for {count} items"

    @pytest.mark.timing
    def test_load_costs_more_than_loads_of_the_bytes(self) -> None:
        data = marshal.dumps(list(range(100_000)))

        load_ns = best_ns(lambda: marshal.load(io.BytesIO(data)))
        loads_ns = best_ns(partial(marshal.loads, data))

        assert load_ns > 2 * loads_ns, f"load {load_ns:.0f}ns, loads {loads_ns:.0f}ns"

    def test_loads_ignores_trailing_bytes(self) -> None:
        assert marshal.loads(marshal.dumps((1, "a")) + b"junk") == (1, "a")

    def test_bad_data_raises(self) -> None:
        with pytest.raises(EOFError):
            marshal.loads(b"")
        with pytest.raises(ValueError, match="unknown type code"):
            marshal.loads(b"\x00")


class TestSharedObjects:
    """From version 3 a shared object is written once and the sharing is
    rebuilt; below 3 each path writes it again, and recursion fails."""

    def test_version_2_writes_every_path(self) -> None:
        value = doubled_chain(16)

        compact = marshal.dumps(value)
        expanded = marshal.dumps(value, 2)

        assert len(expanded) > 1_000 * len(compact), (len(expanded), len(compact))

    def test_the_default_grows_with_distinct_objects(self) -> None:
        short = len(marshal.dumps(doubled_chain(16)))
        long = len(marshal.dumps(doubled_chain(32)))

        assert long < 2.5 * short, (short, long)

    def test_sharing_survives_the_round_trip(self) -> None:
        restored = marshal.loads(marshal.dumps(doubled_chain(4)))

        assert restored[0] is restored[1]

    def test_recursive_list_needs_version_3(self) -> None:
        loop: list[Any] = []
        loop.append(loop)

        for version in range(3, marshal.version + 1):
            restored = marshal.loads(marshal.dumps(loop, version))
            assert restored[0] is restored
        with pytest.raises(ValueError, match="deeply nested"):
            marshal.dumps(loop, 2)


class TestSetOrder:
    """Python 3.11+ writes set elements sorted by their serialized form."""

    def test_the_two_sets_iterate_differently(self) -> None:
        assert list({8, 0}) != list({0, 8})

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="set order is sorted from 3.11")
    def test_equal_sets_give_identical_bytes(self) -> None:
        assert marshal.dumps({8, 0}) == marshal.dumps({0, 8})
        assert marshal.dumps(frozenset({8, 0})) == marshal.dumps(frozenset({0, 8}))

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="set order is sorted from 3.11")
    def test_the_order_is_by_serialized_form(self) -> None:
        data = marshal.dumps({1, 256})
        one = data.index(marshal.dumps(1)[1:])
        two_fifty_six = data.index(marshal.dumps(256)[1:])

        assert marshal.dumps(256) < marshal.dumps(1)
        assert two_fifty_six < one

    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="set order is sorted from 3.11")
    def test_iteration_order_before_3_11(self) -> None:
        assert marshal.dumps({8, 0}) != marshal.dumps({0, 8})

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 11), reason="set order is sorted from 3.11")
    def test_nested_sets_double_per_level(self) -> None:
        shallow, deep = nested_frozensets(8), nested_frozensets(14)

        size_step = len(marshal.dumps(deep)) / len(marshal.dumps(shallow))
        time_step = best_ns(lambda: marshal.dumps(deep)) / best_ns(lambda: marshal.dumps(shallow))

        assert size_step < 2, f"output grew {size_step:.1f}x"
        assert time_step > 16, f"6 more levels cost {time_step:.1f}x"

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="set order is sorted from 3.11")
    def test_nested_sets_are_linear_before_3_11(self) -> None:
        shallow, deep = nested_frozensets(8), nested_frozensets(14)

        time_step = best_ns(lambda: marshal.dumps(deep)) / best_ns(lambda: marshal.dumps(shallow))

        assert time_step < 8, f"6 more levels cost {time_step:.1f}x"


class TestNestingLimit:
    """Nesting is capped by marshal's own limit, not the recursion limit."""

    @pytest.fixture(autouse=True)
    def high_recursion_limit(self) -> Any:
        previous = sys.getrecursionlimit()
        sys.setrecursionlimit(max(previous, 100_000))
        yield
        sys.setrecursionlimit(previous)

    def test_moderate_nesting_passes_both_ways(self) -> None:
        assert marshal.loads(marshal.dumps(nested_lists(900))) == nested_lists(900)
        assert marshal.loads(marshalled_nested_lists(900)) == nested_lists(900)

    def test_deep_nesting_raises_both_ways(self) -> None:
        with pytest.raises(ValueError, match="too deeply nested"):
            marshal.dumps(nested_lists(10_000))
        with pytest.raises(ValueError):
            marshal.loads(marshalled_nested_lists(10_000))

    @pytest.mark.skipif(
        sys.platform not in ("linux", "darwin"),
        reason="marshal's 2,000-level limit is the non-Windows, non-WASI, non-iOS default",
    )
    def test_the_limit_is_2000_levels(self) -> None:
        self.assert_limit(2_000)

    @pytest.mark.skipif(
        sys.platform != "win32", reason="marshal caps nesting at 1,000 levels on Windows builds"
    )
    def test_the_limit_is_1000_levels_on_windows(self) -> None:
        self.assert_limit(1_000)

    @staticmethod
    def assert_limit(levels: int) -> None:
        marshal.dumps(nested_lists(levels))
        marshal.loads(marshalled_nested_lists(levels))
        with pytest.raises(ValueError):
            marshal.dumps(nested_lists(levels + 1))
        with pytest.raises(ValueError):
            marshal.loads(marshalled_nested_lists(levels + 1))


class TestSupportedTypes:
    """The supported built-in types round-trip; anything else raises."""

    def test_supported_values_round_trip(self) -> None:
        values: list[Any] = [
            None, True, False, 0, -(10**50), 1.5, 2 - 3j, "text", b"bytes",
            (1, "a"), [1, [2]], {"k": (1,)}, {1, 2}, frozenset({"x"}),
        ]  # fmt: skip
        for value in values:
            assert marshal.loads(marshal.dumps(value)) == value
        assert marshal.loads(marshal.dumps(...)) is ...
        assert marshal.loads(marshal.dumps(StopIteration)) is StopIteration

    def test_bytes_like_objects_come_back_as_bytes(self) -> None:
        class Raw(bytes):
            pass

        for value in (bytearray(b"ab"), memoryview(b"ab"), array.array("B", b"ab"), Raw(b"ab")):
            restored = marshal.loads(marshal.dumps(value))
            assert type(restored) is bytes and restored == b"ab"

    def test_subclasses_and_other_objects_raise(self) -> None:
        class Mapping(dict[str, int]):
            pass

        class Number(int):
            pass

        class Text(str):
            pass

        for value in (Mapping(a=1), Number(1), Text("a"), object()):
            with pytest.raises(ValueError, match="unmarshallable"):
                UNTYPED.dumps(value)

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="version 5 adds slice in 3.14")
    def test_slice_needs_version_5(self) -> None:
        assert marshal.version == 5
        assert marshal.loads(UNTYPED.dumps(slice(1, None, 2))) == slice(1, None, 2)
        with pytest.raises(ValueError):
            UNTYPED.dumps(slice(1, 2), 4)

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="version 5 adds slice in 3.14")
    def test_slice_is_unsupported_before_3_14(self) -> None:
        assert marshal.version == 4
        with pytest.raises(ValueError):
            UNTYPED.dumps(slice(1, 2))


@pytest.mark.skipif(sys.version_info < (3, 13), reason="allow_code is new in 3.13")
class TestAllowCode:
    """`allow_code=False` rejects code objects in all four functions."""

    CODE = compile("x * 2", "<expr>", "eval")

    def test_writing_code_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="disallowed"):
            UNTYPED.dumps(self.CODE, allow_code=False)
        with pytest.raises(ValueError, match="disallowed"):
            UNTYPED.dump(self.CODE, io.BytesIO(), allow_code=False)

    def test_reading_code_is_rejected(self) -> None:
        data = marshal.dumps(self.CODE)
        with pytest.raises(ValueError, match="disallowed"):
            UNTYPED.loads(data, allow_code=False)
        with pytest.raises(ValueError, match="disallowed"):
            UNTYPED.load(io.BytesIO(data), allow_code=False)

    def test_plain_data_passes(self) -> None:
        data = UNTYPED.dumps([1, "a"], allow_code=False)
        stream = io.BytesIO()
        UNTYPED.dump([1, "a"], stream, allow_code=False)
        assert stream.getvalue() == data
        assert UNTYPED.loads(data, allow_code=False) == [1, "a"]
        assert UNTYPED.load(io.BytesIO(data), allow_code=False) == [1, "a"]


class TestCompiledCode:
    """A `.pyc` is a header and a marshalled code object, and unmarshalling
    code is cheaper than compiling it."""

    SOURCE = "\n".join(f"def f{i}(a, b):\n    return a * {i} + b - {i}\n" for i in range(500))

    def test_a_pyc_is_a_header_and_a_marshalled_code_object(self, tmp_path: pathlib.Path) -> None:
        source = tmp_path / "module.py"
        source.write_text("VALUE = 42\n", encoding="utf-8")
        compiled = py_compile.compile(str(source), cfile=str(tmp_path / "m.pyc"))
        assert compiled is not None

        code = marshal.loads(pathlib.Path(compiled).read_bytes()[16:])
        namespace: dict[str, Any] = {}
        exec(code, namespace)

        assert namespace["VALUE"] == 42

    @pytest.mark.timing
    def test_loading_code_beats_compiling_it(self) -> None:
        data = marshal.dumps(compile(self.SOURCE, "<module>", "exec"))

        compile_ns = best_ns(lambda: compile(self.SOURCE, "<module>", "exec"))
        load_ns = best_ns(partial(marshal.loads, data))

        assert compile_ns > 5 * load_ns, f"compile {compile_ns:.0f}ns, loads {load_ns:.0f}ns"


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
        line, source = next((n, s) for n, s in _blocks() if "restored[0] is restored[1]" in s)
        mutated = source.replace("restored[0] is restored[1]", "restored[0] is not restored[1]")

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
