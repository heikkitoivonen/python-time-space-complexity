"""Tests for docs/stdlib/xdrlib.md.

The page prices a `Packer` as appends to one growing buffer and an
`Unpacker` as slices of an object it holds by reference. Wire formats,
exceptions and identity are settled by direct observation; the absence of a
copy by identity and traced allocation; the two cost claims a counter cannot
reach - that a held `get_buffer()` result makes the next write copy the
buffer, and that a run of writes is amortized O(1) - by timing ratios. The
module exists on Python 3.10 to 3.12 only, so every runtime test takes the
`xdrlib` fixture, which skips from 3.13; availability is asserted on every
version. Lib/xdrlib.py differs between v3.10.19, v3.11.14 and v3.12.12 only
by the import-time DeprecationWarning that 3.11 adds and a rewrite of the
`unpack_list()` loop that reads the same markers.

Measurement scope:

* Every fixed-width `pack_*` method writes the 4 or 8 big-endian bytes
  `struct` gives for the same value. `pack_int(2**31)`, `pack_int('x')`,
  `pack_uint(-1)`, `pack_uint(2**32)` and `pack_double('x')` raise
  `ConversionError`; `pack_hyper` and `pack_uhyper` are one function that
  writes `-1` and `2**64 + 5` as their values modulo 2**64;
  `pack_float(1e300)` raises `OverflowError`, which is not a
  `ConversionError`. `pack_bool` writes 1 for `[0]` and `'x'` and 0 for `[]`.
* `pack_fstring(3, b'abcdef')` writes `abc` and one zero byte;
  `pack_fstring(6, b'ab')` writes `ab` and six zero bytes; `pack_string`
  writes a length and the padded bytes and raises `TypeError` for a `str`.
  The opaque and bytes spellings are the same functions.
* `pack_list` writes a 1 before each of 0, 1 and 5 items and a 0 after them;
  `pack_array` writes the count and then the items; `pack_farray` writes the
  items alone and raises `ValueError` for a length mismatch. `pack_list`
  calls the item function once per item, in order, and packs a generator.
* `Packer.reset()` empties the buffer, and `get_buf` is `get_buffer`. Two
  calls to `get_buffer()` with nothing packed between them return the same
  object.
* A timing test grows the buffer to 10,000 and to 1,000,000 bytes, takes
  `get_buffer()` and keeps the result, and times only the `pack_int()` that
  follows, fastest of 200: 100x the buffer costs more than 10x, where a
  write that did not copy would cost the same. A second timing test packs 10,000 and 1,000,000
  ints with no `get_buffer()` between them: 100x the values costs under
  1,000x, where a copy per write would be 10,000x.
* `Unpacker(data).get_buffer() is data`, and constructing one over
  1,000,000 bytes peaks under 4,096 traced bytes. `unpack_opaque()` from
  `bytes` returns `bytes` and peaks above the value's 100,000 bytes; from a
  `memoryview` it returns a view on the same object and peaks under 4,096.
  A `bytearray` is accepted by `Unpacker`, and by `pack_string()`.
* Each `unpack_*` method reads back what the matching `pack_*` wrote,
  `unpack_hyper` as signed and `unpack_uhyper` as unsigned; `unpack_bool`
  returns `True` for 1 and 7. `get_position()` advances by 4, 8 and the
  padded string length; `set_position()` accepts an offset past the end
  without complaint; `done()` raises `xdrlib.Error` with
  `msg == 'unextracted data remains'` while bytes remain and returns
  `None` after the last one. A short read raises `EOFError`, and a list
  marker of 2 raises `ConversionError`.
* `ConversionError` subclasses `Error`, which subclasses `Exception`.
* Importing `xdrlib` raises `ModuleNotFoundError` from 3.13; in a
  subprocess it warns on 3.11 and 3.12 and not on 3.10.
* Every fenced Python block runs in its own subprocess on 3.10 to 3.12, and
  a mutated assertion in one of them is asserted to fail.

Not settled here:

* The O(m) of the string rows and the O(k) of the list and array rows follow
  from Lib/xdrlib.py: a slice, a concatenation and one write per string, and
  one loop pass per item. Nothing times them. Integers are packed at small
  widths only; a huge integer passed to `pack_hyper()` costs its shifts and
  masks, which the page's fixed-width model leaves out.
* `get_buffer()` is the `BytesIO.getvalue()` of the buffer, so its O(n) is
  that method's worst case; the first call after packing is not timed apart
  from the next write.
* The deprecation in 3.11 and removal in 3.13 come from the 3.12
  documentation and PEP 594.
* API coverage: the audit on 3.14, where `xdrlib` is gone, checks no names
  for the page. On 3.12 the page names `Packer`, `Unpacker`, `Error`,
  `ConversionError` and every public method of the two classes, and
  reports none missing. `raise_conversion_error`, the decorator the module
  wraps its struct calls in, is listed as needing classification and is not
  on the page: it is not in `__all__`.
"""

from __future__ import annotations

import importlib
import importlib.util
import pathlib
import re
import struct
import subprocess
import sys
import textwrap
import time
import tracemalloc
import warnings
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "xdrlib.md"
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


def fastest_ns(func: Callable[[], Any], number: int, repeat: int = 7) -> float:
    """Fastest per-call time over `repeat` runs of `number` calls."""
    best = float("inf")
    for _ in range(repeat):
        start = time.perf_counter_ns()
        for _ in range(number):
            func()
        best = min(best, (time.perf_counter_ns() - start) / number)
    return best


@pytest.fixture
def xdrlib() -> Iterator[Any]:
    if sys.version_info >= (3, 13):
        pytest.skip("version: xdrlib was removed in Python 3.13")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        yield importlib.import_module("xdrlib")


def packed(xdrlib: Any, method: str, *args: Any) -> bytes:
    p = xdrlib.Packer()
    getattr(p, method)(*args)
    return p.get_buffer()


class TestAvailability:
    """`import xdrlib` warns on 3.11 and 3.12 and fails from 3.13."""

    def test_the_module_exists_only_before_3_13(self) -> None:
        assert (importlib.util.find_spec("xdrlib") is not None) == (sys.version_info < (3, 13))

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="xdrlib exists before 3.13")
    def test_importing_it_from_3_13_raises(self) -> None:
        with pytest.raises(ModuleNotFoundError) as caught:
            importlib.import_module("xdrlib")
        assert caught.value.name == "xdrlib"

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="xdrlib was removed in 3.13")
    def test_importing_it_warns_from_3_11(self) -> None:
        result = subprocess.run(
            [sys.executable, "-I", "-W", "error::DeprecationWarning", "-c", "import xdrlib"],
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        if sys.version_info >= (3, 11):
            assert result.returncode != 0
            assert "'xdrlib' is deprecated" in result.stderr
        else:
            assert result.returncode == 0, result.stderr


class TestFixedWidthPacking:
    """The int, uint, enum, bool, hyper, float and double rows: 4 or 8
    bytes each, `ConversionError` outside the 32-bit ranges, wrapping for
    hyper, and `OverflowError` for a float too large for single precision."""

    @pytest.mark.parametrize(
        ("method", "value", "fmt"),
        [
            ("pack_int", -5, ">l"),
            ("pack_enum", 3, ">l"),
            ("pack_uint", 2**32 - 1, ">L"),
            ("pack_hyper", -(2**63), ">q"),
            ("pack_uhyper", 2**64 - 1, ">Q"),
            ("pack_float", 1.5, ">f"),
            ("pack_double", 1.5, ">d"),
        ],
    )
    def test_each_writes_the_struct_bytes(
        self, xdrlib: Any, method: str, value: Any, fmt: str
    ) -> None:
        assert packed(xdrlib, method, value) == struct.pack(fmt, value)

    @pytest.mark.parametrize(
        ("method", "value"),
        [
            ("pack_int", 2**31),
            ("pack_int", "x"),
            ("pack_uint", -1),
            ("pack_uint", 2**32),
            ("pack_double", "x"),
        ],
    )
    def test_a_value_that_does_not_fit_raises_conversion_error(
        self, xdrlib: Any, method: str, value: Any
    ) -> None:
        with pytest.raises(xdrlib.ConversionError):
            packed(xdrlib, method, value)

    def test_hyper_is_reduced_modulo_2_64(self, xdrlib: Any) -> None:
        assert xdrlib.Packer.pack_hyper is xdrlib.Packer.pack_uhyper
        assert packed(xdrlib, "pack_hyper", -1) == b"\xff" * 8
        assert packed(xdrlib, "pack_uhyper", 2**64 + 5) == struct.pack(">Q", 5)

    def test_float_overflow_is_not_a_conversion_error(self, xdrlib: Any) -> None:
        with pytest.raises(OverflowError) as caught:
            packed(xdrlib, "pack_float", 1e300)
        assert not isinstance(caught.value, xdrlib.ConversionError)

    @pytest.mark.parametrize(("value", "expected"), [([0], 1), ("x", 1), ([], 0)])
    def test_bool_writes_one_for_any_true_value(
        self, xdrlib: Any, value: Any, expected: int
    ) -> None:
        assert packed(xdrlib, "pack_bool", value) == struct.pack(">L", expected)


class TestStringPacking:
    """`pack_fstring` cuts or zero-pads to n and then to a multiple of 4,
    with no length; `pack_string` writes the length first and needs bytes."""

    def test_fstring_cuts_and_pads(self, xdrlib: Any) -> None:
        assert packed(xdrlib, "pack_fstring", 3, b"abcdef") == b"abc\0"
        assert packed(xdrlib, "pack_fstring", 6, b"ab") == b"ab" + b"\0" * 6
        assert xdrlib.Packer.pack_fopaque is xdrlib.Packer.pack_fstring

    def test_string_writes_its_length_then_padded_bytes(self, xdrlib: Any) -> None:
        assert packed(xdrlib, "pack_string", b"hello") == b"\0\0\0\5hello\0\0\0"
        assert xdrlib.Packer.pack_opaque is xdrlib.Packer.pack_string
        assert xdrlib.Packer.pack_bytes is xdrlib.Packer.pack_string

    def test_a_bytearray_is_accepted(self, xdrlib: Any) -> None:
        assert packed(xdrlib, "pack_string", bytearray(b"abc")) == b"\0\0\0\3abc\0"

    def test_a_str_raises_type_error(self, xdrlib: Any) -> None:
        with pytest.raises(TypeError):
            packed(xdrlib, "pack_string", "abc")


class TestListsAndArrays:
    """`pack_list` writes 1 before each item and 0 after, `pack_array` the
    count then the items, `pack_farray` the items alone; the item function
    runs once per item, and the unpacking side reads the same layouts."""

    @pytest.mark.parametrize("count", [0, 1, 5])
    def test_list_markers_surround_each_item(self, xdrlib: Any, count: int) -> None:
        p = xdrlib.Packer()
        calls: list[int] = []

        def pack_item(item: int) -> None:
            calls.append(item)
            p.pack_uint(item)

        p.pack_list(list(range(10, 10 + count)), pack_item)
        expected = b"".join(struct.pack(">LL", 1, 10 + i) for i in range(count))
        assert p.get_buffer() == expected + struct.pack(">L", 0)
        assert calls == list(range(10, 10 + count))

        u = xdrlib.Unpacker(p.get_buffer())
        assert u.unpack_list(u.unpack_uint) == calls
        u.done()

    def test_a_list_can_come_from_a_generator(self, xdrlib: Any) -> None:
        p = xdrlib.Packer()
        p.pack_list((i for i in range(3)), p.pack_uint)
        assert p.get_buffer() == struct.pack(">7L", 1, 0, 1, 1, 1, 2, 0)

    def test_array_writes_the_count_and_farray_does_not(self, xdrlib: Any) -> None:
        p = xdrlib.Packer()
        p.pack_array([7, 8], p.pack_uint)
        assert p.get_buffer() == struct.pack(">LLL", 2, 7, 8)
        p.reset()
        p.pack_farray(2, [7, 8], p.pack_uint)
        assert p.get_buffer() == struct.pack(">LL", 7, 8)

        u = xdrlib.Unpacker(struct.pack(">LLL", 2, 7, 8))
        assert u.unpack_array(u.unpack_uint) == [7, 8]
        u.reset(struct.pack(">LL", 7, 8))
        assert u.unpack_farray(2, u.unpack_uint) == [7, 8]
        u.done()

    def test_farray_rejects_a_length_mismatch(self, xdrlib: Any) -> None:
        p = xdrlib.Packer()
        with pytest.raises(ValueError, match="wrong array size"):
            p.pack_farray(3, [1, 2], p.pack_uint)

    def test_a_list_marker_other_than_0_or_1_raises(self, xdrlib: Any) -> None:
        u = xdrlib.Unpacker(struct.pack(">LL", 2, 0))
        with pytest.raises(xdrlib.ConversionError, match="0 or 1 expected"):
            u.unpack_list(u.unpack_uint)


class TestPackerBuffer:
    """`Packer()` and `reset()` start an empty buffer; `get_buffer()` is
    O(n), and a result still referenced makes the next write copy the whole
    buffer, while writes with no snapshot between them are amortized O(1)."""

    def test_reset_empties_the_buffer(self, xdrlib: Any) -> None:
        p = xdrlib.Packer()
        assert p.get_buffer() == b""
        p.pack_int(1)
        p.reset()
        assert p.get_buffer() == b""
        assert xdrlib.Packer.get_buf is xdrlib.Packer.get_buffer

    def test_a_second_get_buffer_with_no_write_is_the_same_object(self, xdrlib: Any) -> None:
        p = xdrlib.Packer()
        p.pack_fopaque(100_000, b"x" * 100_000)
        assert p.get_buffer() is p.get_buffer()

    @pytest.mark.timing
    def test_a_held_result_makes_the_next_write_copy_the_buffer(self, xdrlib: Any) -> None:
        costs = {}
        for size in (10_000, 1_000_000):
            p = xdrlib.Packer()
            p.pack_fopaque(size, b"x" * size)
            best = float("inf")
            for _ in range(200):
                held = p.get_buffer()
                start = time.perf_counter_ns()
                p.pack_int(1)
                best = min(best, time.perf_counter_ns() - start)
                del held
            costs[size] = best

        ratio = costs[1_000_000] / costs[10_000]
        assert ratio > 10, costs

    @pytest.mark.timing
    def test_writes_with_no_snapshot_are_amortized_constant(self, xdrlib: Any) -> None:
        def pack(count: int) -> None:
            p = xdrlib.Packer()
            pack_int = p.pack_int
            for i in range(count):
                pack_int(i)

        small = fastest_ns(lambda: pack(10_000), number=1, repeat=5)
        large = fastest_ns(lambda: pack(1_000_000), number=1, repeat=3)
        assert large / small < 1_000, (small, large)


class TestUnpackerHoldsTheData:
    """`Unpacker(data)` and its `get_buffer()` are O(1): the object passed in,
    no copy; string slices copy from `bytes` and are views from a
    `memoryview`."""

    def test_the_data_is_held_by_reference(self, xdrlib: Any) -> None:
        data = bytes(1_000_000)
        assert xdrlib.Unpacker(data).get_buffer() is data
        assert peak_bytes(lambda: xdrlib.Unpacker(data)) < PEAK_LIMIT

    def test_opaque_from_bytes_is_a_copy(self, xdrlib: Any) -> None:
        data = packed(xdrlib, "pack_opaque", b"x" * 100_000)
        u = xdrlib.Unpacker(data)
        result: list[Any] = []
        peak = peak_bytes(lambda: result.append(u.unpack_opaque()))
        assert type(result[0]) is bytes
        assert peak > 100_000

    def test_opaque_from_a_memoryview_is_a_view(self, xdrlib: Any) -> None:
        data = packed(xdrlib, "pack_opaque", b"x" * 100_000)
        u = xdrlib.Unpacker(memoryview(data))
        result: list[Any] = []
        peak = peak_bytes(lambda: result.append(u.unpack_opaque()))
        assert type(result[0]) is memoryview
        assert result[0].obj is data
        assert peak < PEAK_LIMIT

    def test_a_bytearray_is_accepted(self, xdrlib: Any) -> None:
        u = xdrlib.Unpacker(bytearray(struct.pack(">l", -3)))
        assert u.unpack_int() == -3


class TestUnpackerReads:
    """The fixed-width and string unpack rows, positions, `done()` and the
    `EOFError` on a short read."""

    def test_each_value_reads_back(self, xdrlib: Any) -> None:
        p = xdrlib.Packer()
        p.pack_int(-5)
        p.pack_uint(2**32 - 1)
        p.pack_enum(3)
        p.pack_bool(True)
        p.pack_hyper(-1)
        p.pack_uhyper(2**64 - 1)
        p.pack_float(1.5)
        p.pack_double(2.25)
        p.pack_string(b"hello")
        p.pack_fstring(3, b"abc")
        u = xdrlib.Unpacker(p.get_buffer())

        assert u.unpack_int() == -5
        assert u.unpack_uint() == 2**32 - 1
        assert u.unpack_enum() == 3
        assert u.get_position() == 12
        assert u.unpack_bool() is True
        assert u.unpack_hyper() == -1
        assert u.unpack_uhyper() == 2**64 - 1
        assert u.get_position() == 32
        assert u.unpack_float() == 1.5
        assert u.unpack_double() == 2.25
        assert u.unpack_bytes() == b"hello"
        assert u.get_position() == 56
        assert u.unpack_fopaque(3) == b"abc"
        assert u.done() is None

    def test_spellings_share_functions(self, xdrlib: Any) -> None:
        unpacker = xdrlib.Unpacker
        assert unpacker.unpack_enum is unpacker.unpack_int
        assert unpacker.unpack_opaque is unpacker.unpack_string
        assert unpacker.unpack_bytes is unpacker.unpack_string
        assert unpacker.unpack_fopaque is unpacker.unpack_fstring

    def test_any_nonzero_bool_is_true(self, xdrlib: Any) -> None:
        assert xdrlib.Unpacker(struct.pack(">l", 7)).unpack_bool() is True
        assert xdrlib.Unpacker(struct.pack(">l", 0)).unpack_bool() is False

    def test_done_raises_while_bytes_remain(self, xdrlib: Any) -> None:
        u = xdrlib.Unpacker(bytes(8))
        u.unpack_int()
        with pytest.raises(xdrlib.Error) as caught:
            u.done()
        assert caught.value.msg == "unextracted data remains"
        u.unpack_int()
        u.done()

    def test_set_position_is_not_checked(self, xdrlib: Any) -> None:
        u = xdrlib.Unpacker(bytes(8))
        u.set_position(100)
        assert u.get_position() == 100
        with pytest.raises(EOFError):
            u.unpack_int()

    @pytest.mark.parametrize("method", ["unpack_int", "unpack_uint", "unpack_double"])
    def test_a_short_read_raises_eof_error(self, xdrlib: Any, method: str) -> None:
        with pytest.raises(EOFError):
            getattr(xdrlib.Unpacker(b"\0\0"), method)()

    def test_a_short_string_raises_eof_error(self, xdrlib: Any) -> None:
        with pytest.raises(EOFError):
            xdrlib.Unpacker(struct.pack(">L", 10) + b"abc").unpack_string()


class TestExceptions:
    """`ConversionError` is an `Error`, and `Error` an `Exception`."""

    def test_hierarchy(self, xdrlib: Any) -> None:
        error = xdrlib.Error("m")
        assert error.msg == "m"
        assert issubclass(xdrlib.ConversionError, xdrlib.Error)
        assert issubclass(xdrlib.Error, Exception)


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
    """Each block runs in its own subprocess on the versions that still have
    the module, and asserts its own result."""

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()
        assert len(blocks) == EXPECTED_BLOCKS
        assert all("import xdrlib" in source for _, source in blocks)

    def test_every_block_runs(self, xdrlib: Any, tmp_path: pathlib.Path) -> None:
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

    def test_the_runner_notices_a_broken_assertion(
        self, xdrlib: Any, tmp_path: pathlib.Path
    ) -> None:
        line, source = next((n, s) for n, s in _blocks() if "unpack_int() == 42" in s)
        mutated = source.replace("unpack_int() == 42", "unpack_int() == 43", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        result = _run_block(mutated, tmp_path)
        assert result.returncode != 0
        assert "AssertionError" in result.stderr
