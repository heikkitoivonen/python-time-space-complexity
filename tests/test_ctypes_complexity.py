"""Tests for docs/stdlib/ctypes.md.

The page prices what `ctypes` itself adds to a C call or a C object: argument
conversion, caches, and copies between C memory and Python objects. Almost all
of it is settled by observation - identity for the caches, a counting
`from_param` for per-argument conversion, mutation through one object seen
from another for sharing - and the copies by traced allocation, which
separates an O(1) view from an O(n) copy by orders of magnitude. Only the
structure-layout bound needs a stopwatch.

Measurement scope:

* Caches are identity checks: `lib.name`, `cdll.<name>`, `c_int * n`,
  `ARRAY()`, `POINTER()` and `CFUNCTYPE()` return the same object twice;
  `lib['name']`, `LoadLibrary()` and `PYFUNCTYPE()` return a new one. Array
  types of 10 and 10,000,000 elements are both built with a traced peak under
  20 KB, where an instance of the larger one peaks over 10 MB.
* Per-argument conversion is a `from_param` counter on a prototype of 1, 4
  and 16 arguments: exactly one call per argument per call, on each of two
  calls. Setting `argtypes` is shown to inspect every entry by placing the
  one without `from_param` sixth. `errcheck` records one result per call.
* `c_char_p(bytes)` keeps the same `bytes` object and its construction peak
  stays under 2 KB for a 1,000,000-byte value; `c_wchar_p(str)` and
  `c_wchar_p.from_param(str)` both peak over 1 MB for a 1,000,000-character
  string, `from_param()` on each of two passes, and under 20 KB for 10
  characters, while `from_param()` of a
  1,000,000-character unicode buffer peaks under 20 KB. `.value` returns an equal but
  new object, with a peak that grows more than 100x from 1,000 to 1,000,000
  bytes; `string_at()` and `.raw` the same.
* Sharing is mutation through one object observed from the other:
  `from_buffer()`, `memoryview_at()` (3.14+), `from_address()`, `cast()`, a
  pointer's `contents`, and array or structure fields and elements; copies
  are the same mutation not observed, for `from_buffer_copy()` and for a
  structure assigned into an array element or a structure field. The
  view-returning operations peak under 20 KB over a 10,000,000-byte object,
  `from_buffer_copy()` over 10 MB. `pointer()`, `cast()` and `c_char_p()`
  record what they keep alive in `_objects`.
* `memmove()` and `memset()` over 10,000,000 bytes peak under 20 KB.
* `resize()` grows `sizeof()` and preserves the old bytes, leaves `len()`
  alone, and raises `ValueError` below the type's size.
* Definition time, with the collector paused, at 500 and 32,000 `c_int`
  fields, a 64x step where linear predicts x64 and quadratic x4096. A
  `Structure` is asserted over x300 before 3.14 and under x300 from 3.14; a
  `Union` under x512 on every version. Locally (aarch64) a `Structure` grows
  x1200 to x1700 on 3.10 to 3.13 and x67 to x72 on 3.14, and a `Union` x68
  to x128 everywhere. The pre-3.14 cost is each field re-copying the growing
  buffer-format string (Modules/_ctypes/stgdict.c). The definition's space is
  its f `CField` descriptors, one per field, asserted by count.
* An anonymous member of 100 fields is asserted to give the outer structure
  a descriptor for each of them.
* `SetPointerType()` completes an incomplete pointer to a self-referencing
  structure; from 3.13 it is asserted to warn `DeprecationWarning`.
* `byref()` is asserted to return something that is not a `_Pointer`, and
  the byte-order classes by the bytes they produce. `CField` attributes
  (3.14+), `_align_` (3.13+), the endian unions (3.11+), `c_time_t` (3.12+)
  and the complex types (3.14+) are guarded on `sys.version_info` or
  `hasattr`.
* `find_library()` is observed, on Linux, to start at least one subprocess
  per call and to start them again on the second call with the same name.
  `dllist()` (3.14+) is asserted to list the C library on Linux.
* `get_errno()` reads the errno a `use_errno=True` call to `close(-1)` left,
  and `set_errno()` returns the previous value.
* Every fenced Python block runs in its own subprocess with warnings as
  errors, and a mutated assertion in one of them is asserted to fail.

Not settled here:

* The dynamic loader's cost in `CDLL()`, `in_dll()` and first attribute
  access, and the cost of the C function a call reaches, are outside every
  bound by definition.
* O(t) for `find_library()` is read from Lib/ctypes/util.py: it reads each
  helper program's whole output and runs one regex over it. The output size
  is not varied. O(d) for `dllist()` is read from the same file: one callback
  per library that `dl_iterate_phdr` reports.
* That `PyDLL` functions keep the GIL, and `CDLL` functions release it, is
  read from the function flags in Lib/ctypes/__init__.py; no test observes
  the GIL. A `PyDLL` call to `PyErr_SetString` is asserted to raise.
* The n term of a call for a structure passed or returned by value is read
  from Modules/_ctypes/callproc.c; only the `str` conversion is measured.
* That a callback costs one Python call per invocation from C is the
  structure of the thunk; the example asserts qsort sorts through it, not how
  many comparisons a particular libc makes.
* Windows-only rows. The tests for `windll` and `WinDLL` caching,
  `WINFUNCTYPE` caching, `set_last_error`, `WinError` and `FormatError` are
  guarded on `sys.platform == "win32"` and skip on every run this project
  performs. `OleDLL`, `oledll`, `HRESULT`, `GetLastError`,
  `get_last_error`, `COMError`, `CopyComPointer`, `DllCanUnloadNow`,
  `DllGetClassObject`, `util.find_msvcrt` and `ctypes.wintypes` are priced
  from the official documentation and Lib/ctypes/__init__.py. None of these
  rows is verified here.
* `ctypes.macholib` is the macOS library-search helper behind
  `find_library()` there, not a documented API, and `ctypes.util.test` is a
  self-test; neither is priced.
* Dimensions held fixed: element types beyond `c_int`, `c_char` and
  `c_uint8`; bit fields; `_pack_` and `_layout_` values; nested structure
  depth; callback argument counts beyond 16.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import gc
import os
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "ctypes.md"
EXPECTED_BLOCKS = 11

POSIX = pytest.mark.skipif(sys.platform == "win32", reason="CDLL(None) is Unix-only")
LINUX = pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux libc and ldconfig")
WINDOWS = pytest.mark.skipif(sys.platform != "win32", reason="Windows-only API")


def best_ns(func: Callable[[], Any], repeats: int = 5) -> float:
    """Fastest of `repeats` runs, in nanoseconds, with the collector paused."""
    best: float | None = None
    for _ in range(repeats):
        gc.collect()
        gc.disable()
        try:
            start = time.perf_counter_ns()
            func()
            elapsed = time.perf_counter_ns() - start
        finally:
            gc.enable()
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


def libc() -> ctypes.CDLL:
    return ctypes.CDLL(None)


class Tracked(ctypes.c_int):
    """A `c_int` whose `from_param` records every conversion."""

    conversions: list[Any] = []

    @classmethod
    def from_param(cls, value: Any) -> ctypes.c_int:
        cls.conversions.append(value)
        return ctypes.c_int(value)


@POSIX
class TestLibrariesAndFunctionsAreCachedByAttribute:
    """`cdll.<name>` and `lib.name` cache; `LoadLibrary()` and `lib['name']`
    build a new object every time."""

    def test_attribute_access_caches_the_function(self) -> None:
        lib = libc()

        assert lib.strlen is lib.strlen

    def test_indexing_builds_a_new_function_each_time(self) -> None:
        lib = libc()

        assert lib["strlen"] is not lib["strlen"]
        assert lib["strlen"].__name__ == "strlen"

    @LINUX
    def test_the_loader_caches_by_attribute_and_indexing(self) -> None:
        loader = ctypes.LibraryLoader(ctypes.CDLL)

        first = loader["libc.so.6"]

        assert loader["libc.so.6"] is first
        assert getattr(loader, "libc.so.6") is first

    @LINUX
    def test_load_library_builds_a_new_one_each_time(self) -> None:
        assert ctypes.cdll.LoadLibrary("libc.so.6") is not ctypes.cdll.LoadLibrary("libc.so.6")

    def test_indexed_functions_keep_their_own_argtypes(self) -> None:
        lib = libc()
        first, second = lib["labs"], lib["labs"]

        first.argtypes = [ctypes.c_long]

        assert second.argtypes is None

    def test_handle_and_name(self) -> None:
        lib = libc()

        assert lib._name is None  # noqa: SLF001
        assert isinstance(lib._handle, int)  # noqa: SLF001

    def test_pythonapi_is_a_pydll(self) -> None:
        function = ctypes.pythonapi.PyLong_FromLong
        function.argtypes = [ctypes.c_long]
        function.restype = ctypes.py_object

        assert isinstance(ctypes.pythonapi, ctypes.PyDLL)
        assert function(12345) == 12345

    def test_a_pydll_raises_the_pending_exception(self) -> None:
        function = ctypes.pythonapi.PyErr_SetString
        function.argtypes = [ctypes.py_object, ctypes.c_char_p]
        function.restype = None

        with pytest.raises(ValueError, match="boom"):
            function(ValueError, b"boom")

    def test_the_mode_flags(self) -> None:
        assert ctypes.DEFAULT_MODE in (ctypes.RTLD_LOCAL, ctypes.RTLD_GLOBAL)
        assert ctypes.RTLD_LOCAL != ctypes.RTLD_GLOBAL


@LINUX
class TestFindLibraryRunsProgramsEveryCall:
    """`find_library(name)` | O(t): it runs helper programs and caches nothing."""

    def test_each_call_starts_a_subprocess(self, monkeypatch: pytest.MonkeyPatch) -> None:
        started: list[Any] = []
        original = subprocess.Popen

        class CountingPopen(original):  # type: ignore[misc, valid-type]
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                started.append(args[0] if args else kwargs.get("args"))
                super().__init__(*args, **kwargs)

        monkeypatch.setattr(subprocess, "Popen", CountingPopen)

        first = ctypes.util.find_library("c")
        after_first = len(started)
        second = ctypes.util.find_library("c")

        assert first == second
        assert after_first >= 1
        assert len(started) > after_first, "the second call started no process"

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="added in 3.14")
    def test_dllist_lists_the_loaded_libraries(self) -> None:
        libraries = ctypes.util.dllist()  # type: ignore[attr-defined]

        assert isinstance(libraries, list)
        assert any("libc" in os.path.basename(name) for name in libraries)


class TestConversionIsPerArgumentPerCall:
    """Calling a foreign function | O(a): each `argtypes` entry's
    `from_param()` runs once on its argument at every call."""

    @pytest.fixture(autouse=True)
    def _clear(self) -> None:
        Tracked.conversions.clear()

    @pytest.mark.parametrize("arity", [1, 4, 16])
    def test_one_conversion_per_argument_per_call(self, arity: int) -> None:
        prototype = ctypes.CFUNCTYPE(ctypes.c_int, *[Tracked] * arity)
        function = prototype(lambda *args: len(args))

        assert function(*range(arity)) == arity
        assert len(Tracked.conversions) == arity
        function(*range(arity))
        assert len(Tracked.conversions) == 2 * arity

    @POSIX
    def test_setting_argtypes_inspects_every_entry(self) -> None:
        class NoConversion:
            pass

        function = libc()["labs"]

        with pytest.raises(TypeError, match="item 6"):
            function.argtypes = [ctypes.c_long] * 5 + [NoConversion]  # type: ignore[assignment]

    @POSIX
    def test_errcheck_runs_once_per_call(self) -> None:
        seen: list[int] = []
        function = libc()["labs"]
        function.argtypes = [ctypes.c_long]
        function.restype = ctypes.c_long

        def check(result: Any, func: Any, args: Any) -> Any:
            seen.append(result)
            return result

        function.errcheck = check  # type: ignore[assignment]

        assert function(-1) == 1
        function(-2)

        assert seen == [1, 2]

    @POSIX
    def test_restype_none_is_void(self) -> None:
        function = libc()["srand"]
        function.restype = None

        assert function(1) is None

    @POSIX
    def test_an_unconvertible_argument_raises_argument_error(self) -> None:
        function = libc()["labs"]
        function.argtypes = [ctypes.c_long]

        with pytest.raises(ctypes.ArgumentError, match="argument 1"):
            function("x")


class TestPrototypeCaching:
    """`CFUNCTYPE` is cached by signature; `PYFUNCTYPE` builds a new class."""

    def test_cfunctype_returns_the_same_class(self) -> None:
        assert ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int) is ctypes.CFUNCTYPE(
            ctypes.c_int, ctypes.c_int
        )

    def test_the_flags_are_part_of_the_key(self) -> None:
        plain = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int)
        with_errno = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int, use_errno=True)

        assert plain is not with_errno

    def test_pyfunctype_returns_a_new_class(self) -> None:
        assert ctypes.PYFUNCTYPE(ctypes.c_int) is not ctypes.PYFUNCTYPE(ctypes.c_int)

    def test_a_callback_calls_python(self) -> None:
        calls: list[int] = []
        callback = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int)(lambda x: calls.append(x) or x)

        assert callback(3) == 3
        assert calls == [3]


class TestStringsCopyOrShare:
    """`c_char_p(bytes)` shares; `c_wchar_p(str)` converts; `.value`,
    `string_at()` and `.raw` build a new object of the bytes they read."""

    def test_c_char_p_keeps_the_bytes_object(self) -> None:
        data = b"x" * 1_000_000

        holder: list[ctypes.c_char_p] = []
        peak = peak_bytes(lambda: holder.append(ctypes.c_char_p(data)))

        assert holder[0]._objects is data  # type: ignore[attr-defined]  # noqa: SLF001
        assert peak < 2_000, f"c_char_p of 1 MB of bytes allocated {peak} bytes"

    def test_c_wchar_p_converts_the_str(self) -> None:
        peaks = [peak_bytes(lambda s=s: ctypes.c_wchar_p(s)) for s in ("x" * 10, "x" * 1_000_000)]

        assert peaks[0] < 20_000
        assert peaks[1] > 1_000_000, f"c_wchar_p peaks: {peaks}"

    def test_a_str_argument_is_converted_at_every_pass(self) -> None:
        text = "x" * 1_000_000

        peaks = [peak_bytes(lambda: ctypes.c_wchar_p.from_param(text)) for _ in range(2)]
        short = peak_bytes(lambda: ctypes.c_wchar_p.from_param("x" * 10))

        assert min(peaks) > 1_000_000, f"from_param(str) peaked at {peaks}"
        assert short < 20_000, f"from_param of 10 characters peaked at {short}"

    @pytest.mark.parametrize(
        "read",
        [
            lambda buffer: ctypes.c_char_p(ctypes.addressof(buffer)).value,
            lambda buffer: ctypes.string_at(buffer),
            lambda buffer: buffer.raw,
            lambda buffer: buffer.value,
        ],
        ids=["c_char_p.value", "string_at", "raw", "value"],
    )
    def test_reading_back_copies_what_it_reads(self, read: Callable[[Any], bytes]) -> None:
        peaks = []
        for size in (1_000, 1_000_000):
            buffer = ctypes.create_string_buffer(b"x" * size)
            assert read(buffer)[:size] == b"x" * size
            peaks.append(peak_bytes(lambda b=buffer: read(b)))

        assert peaks[1] > peaks[0] * 100, f"1,000x the bytes: {peaks}"

    def test_a_unicode_buffer_passes_as_c_wchar_p_without_converting(self) -> None:
        buffer = ctypes.create_unicode_buffer("x" * 1_000_000)

        peak = peak_bytes(lambda: ctypes.c_wchar_p.from_param(buffer))

        assert peak < 20_000, f"from_param(unicode buffer) peaked at {peak}"

    def test_value_is_a_new_object(self) -> None:
        data = b"hello"

        assert ctypes.c_char_p(data).value == data
        assert ctypes.c_char_p(data).value is not data

    def test_value_stops_at_the_nul_and_raw_does_not(self) -> None:
        buffer = ctypes.create_string_buffer(b"ab\x00cd")

        assert buffer.value == b"ab"
        assert buffer.raw == b"ab\x00cd\x00"
        assert ctypes.string_at(buffer) == b"ab"
        assert ctypes.string_at(buffer, 5) == b"ab\x00cd"

    def test_wide_strings(self) -> None:
        buffer = ctypes.create_unicode_buffer("hé")

        assert buffer.value == "hé"
        assert ctypes.wstring_at(buffer) == "hé"
        assert ctypes.c_wchar_p("hé").value == "hé"


class TestSimpleTypes:
    """Simple types are O(1) values; the fixed-width names are aliases."""

    def test_fixed_widths_have_their_width(self) -> None:
        signed = [ctypes.c_byte, ctypes.c_short, ctypes.c_int, ctypes.c_long, ctypes.c_longlong]
        unsigned = [
            ctypes.c_ubyte,
            ctypes.c_ushort,
            ctypes.c_uint,
            ctypes.c_ulong,
            ctypes.c_ulonglong,
        ]
        for kinds, candidates in [
            ((ctypes.c_int8, ctypes.c_int16, ctypes.c_int32, ctypes.c_int64), signed),
            ((ctypes.c_uint8, ctypes.c_uint16, ctypes.c_uint32, ctypes.c_uint64), unsigned),
        ]:
            for kind, size in zip(kinds, (1, 2, 4, 8), strict=True):
                assert ctypes.sizeof(kind) == size
                assert any(kind is candidate for candidate in candidates), kind

    def test_aliases(self) -> None:
        assert ctypes.c_voidp is ctypes.c_void_p
        assert ctypes.c_buffer(b"ab", 4).raw == ctypes.create_string_buffer(b"ab", 4).raw
        assert ctypes.sizeof(ctypes.c_size_t) == ctypes.sizeof(ctypes.c_void_p)
        assert ctypes.sizeof(ctypes.c_ssize_t) == ctypes.sizeof(ctypes.c_void_p)

    def test_values_round_trip(self) -> None:
        number = ctypes.c_int(42)
        number.value = 100

        assert number.value == 100
        assert ctypes.c_double(1.5).value == 1.5
        assert ctypes.c_bool(True).value is True
        assert ctypes.c_char(b"A").value == b"A"
        assert ctypes.c_wchar("é").value == "é"
        assert ctypes.c_double._type_ == "d"  # noqa: SLF001

    def test_py_object_holds_the_object(self) -> None:
        item = object()

        assert ctypes.py_object(item).value is item

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="added in 3.12")
    def test_time_t(self) -> None:
        assert ctypes.sizeof(ctypes.c_time_t) == ctypes.SIZEOF_TIME_T  # type: ignore[attr-defined]

    @pytest.mark.skipif(
        not hasattr(ctypes, "c_double_complex"), reason="3.14+ with libffi complex support"
    )
    def test_complex_types(self) -> None:
        assert ctypes.c_double_complex(1 + 2j).value == 1 + 2j  # type: ignore[attr-defined]
        assert ctypes.c_float_complex(1 + 2j).value == 1 + 2j  # type: ignore[attr-defined]
        assert ctypes.c_longdouble_complex(1 + 2j).value == 1 + 2j  # type: ignore[attr-defined]


class TestArrayTypesAreCachedAndInstancesZeroFilled:
    """`c_int * length` | O(1), cached; an instance is O(n), zero-filled."""

    def test_the_array_type_is_cached(self) -> None:
        kind = ctypes.c_int * 5

        assert ctypes.c_int * 5 is kind
        assert ctypes.ARRAY(ctypes.c_int, 5) is kind  # type: ignore[arg-type]
        assert issubclass(kind, ctypes.Array)
        assert kind._length_ == 5  # noqa: SLF001
        assert kind._type_ is ctypes.c_int  # noqa: SLF001

    def test_the_type_costs_nothing_the_instance_costs_its_bytes(self) -> None:
        small = peak_bytes(lambda: ctypes.c_char * 11)
        large_type = peak_bytes(lambda: ctypes.c_char * 10_000_001)
        kind = ctypes.c_char * 10_000_001
        instance = peak_bytes(kind)

        assert small < 20_000 and large_type < 20_000, (small, large_type)
        assert instance > 10_000_000, f"a 10 MB array instance peaked at {instance}"

    def test_instances_are_zero_filled(self) -> None:
        values = (ctypes.c_int * 5)(10, 20)

        assert list(values) == [10, 20, 0, 0, 0]
        assert bytes(ctypes.create_string_buffer(8)) == b"\x00" * 8

    def test_slices_are_lists_or_bytes(self) -> None:
        assert (ctypes.c_int * 4)(1, 2, 3, 4)[1:3] == [2, 3]
        assert ctypes.create_string_buffer(b"abcd")[1:3] == b"bc"

    def test_create_string_buffer_leaves_room_for_the_nul(self) -> None:
        assert ctypes.sizeof(ctypes.create_string_buffer(b"abc")) == 4
        assert ctypes.sizeof(ctypes.create_string_buffer(b"abc", 10)) == 10
        assert len(ctypes.create_unicode_buffer(7)) == 7


class TestResize:
    """`resize(obj, size)`: grows the memory, keeps the contents, leaves
    `len()` alone, and cannot shrink below the type's size."""

    def test_it_grows_and_keeps_the_contents(self) -> None:
        buffer = ctypes.create_string_buffer(b"abc")

        ctypes.resize(buffer, 1_000)

        assert ctypes.sizeof(buffer) == 1_000
        assert len(buffer) == 4
        assert ctypes.string_at(buffer, 3) == b"abc"

    def test_it_cannot_shrink_below_the_type(self) -> None:
        buffer = ctypes.create_string_buffer(8)

        with pytest.raises(ValueError, match="minimum size"):
            ctypes.resize(buffer, 4)


class Point(ctypes.Structure):
    _fields_ = [("x", ctypes.c_int), ("y", ctypes.c_int)]


class TestStructures:
    """Definition is O(f); an instance is O(n); a field is O(1) and an
    aggregate field is a view."""

    @staticmethod
    def define(fields: list[tuple[str, Any]]) -> type:
        return type("S", (ctypes.Structure,), {"_fields_": fields})

    def test_every_field_gets_a_descriptor(self) -> None:
        kind = self.define([(f"f{index}", ctypes.c_int) for index in range(1_000)])

        descriptors = [getattr(kind, f"f{index}") for index in range(1_000)]

        assert len({id(d) for d in descriptors}) == 1_000
        assert descriptors[999].offset == 999 * ctypes.sizeof(ctypes.c_int)

    @staticmethod
    def definition_ns(base: type, fields: int) -> float:
        names = [(f"f{index}", ctypes.c_int) for index in range(fields)]
        return best_ns(lambda: type("S", (base,), {"_fields_": names}), repeats=3)

    @classmethod
    def growth(cls, base: type) -> tuple[float, list[float]]:
        """Definition time at 32,000 fields over 500: x64 if linear, x4096 if quadratic."""
        durations = [cls.definition_ns(base, fields) for fields in (500, 32_000)]
        return durations[1] / durations[0], durations

    @pytest.mark.timing
    def test_structure_definition_is_quadratic_before_314_and_linear_after(self) -> None:
        ratio, durations = self.growth(ctypes.Structure)

        if sys.version_info >= (3, 14):
            assert ratio < 300, f"64x the fields: {durations} ns, x{ratio:.0f}"
        else:
            assert ratio > 300, f"64x the fields: {durations} ns, only x{ratio:.0f}"

    @pytest.mark.timing
    def test_union_definition_is_linear_in_fields(self) -> None:
        ratio, durations = self.growth(ctypes.Union)

        assert ratio < 512, f"64x the fields: {durations} ns, x{ratio:.0f}"

    def test_an_instance_is_zero_filled_and_costs_its_bytes(self) -> None:
        big = self.define([("data", ctypes.c_char * 10_000_000)])
        small = self.define([("data", ctypes.c_char * 10)])

        assert bytes(small()) == b"\x00" * 10
        assert peak_bytes(big) > 10_000_000
        assert peak_bytes(small) < 20_000

    def test_arguments_fill_fields_in_order(self) -> None:
        point = Point(3, y=4)

        assert (point.x, point.y) == (3, 4)

    def test_an_array_field_is_a_view(self) -> None:
        kind = self.define([("data", ctypes.c_int * 2_500_000)])
        instance = kind()

        views: list[Any] = []
        peak = peak_bytes(lambda: views.append(instance.data))
        views[0][0] = 7

        assert instance.data[0] == 7
        assert views[0]._b_base_ is instance  # noqa: SLF001
        assert peak < 20_000, f"reading a 10 MB array field allocated {peak} bytes"

    def test_a_char_array_field_reads_as_bytes(self) -> None:
        kind = self.define([("name", ctypes.c_char * 8)])
        instance = kind(b"abc")

        assert instance.name == b"abc"
        assert isinstance(instance.name, bytes)

    def test_assigning_an_aggregate_copies_it(self) -> None:
        points = (Point * 2)()
        source = Point(1, 2)
        holder = self.define([("point", Point)])()

        points[0] = source
        holder.point = source
        source.x = 9

        assert points[0].x == 1
        assert holder.point.x == 1

    def test_array_elements_of_structures_are_views(self) -> None:
        points = (Point * 3)()

        element = points[1]
        element.x = 5

        assert points[1].x == 5
        assert element._b_base_ is points  # noqa: SLF001
        assert points._b_needsfree_ == 1  # noqa: SLF001
        assert element._b_needsfree_ == 0  # noqa: SLF001

    def test_a_union_puts_every_field_at_offset_zero(self) -> None:
        class Either(ctypes.Union):
            _fields_ = [("small", ctypes.c_uint8), ("large", ctypes.c_uint64)]

        class Padded(ctypes.Union):
            _fields_ = [("text", ctypes.c_char * 9), ("number", ctypes.c_uint64)]

        either = Either(large=0x0102)

        assert Either.small.offset == Either.large.offset == 0
        assert ctypes.sizeof(Padded) >= 9
        assert ctypes.sizeof(Padded) % ctypes.alignment(ctypes.c_uint64) == 0
        assert either.small == (0x02 if sys.byteorder == "little" else 0x00)

    def test_an_anonymous_member_adds_a_descriptor_per_field(self) -> None:
        inner = self.define([(f"f{index}", ctypes.c_int) for index in range(100)])

        class Outer(ctypes.Structure):
            _fields_ = [("inner", inner)]
            _anonymous_ = ("inner",)

        assert all(hasattr(Outer, f"f{index}") for index in range(100))
        assert not hasattr(Point, "f0")

    def test_anonymous_fields_are_reached_directly(self) -> None:
        class Outer(ctypes.Structure):
            _fields_ = [("inner", Point), ("z", ctypes.c_int)]
            _anonymous_ = ("inner",)

        outer = Outer(Point(1, 2), 3)

        assert (outer.x, outer.y, outer.z) == (1, 2, 3)

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="added in 3.13")
    def test_align_raises_the_alignment(self) -> None:
        class Aligned(ctypes.Structure):
            _fields_ = [("x", ctypes.c_int)]
            _align_ = 16

        assert ctypes.alignment(Aligned) == 16

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="added in 3.14")
    def test_cfield_attributes(self) -> None:
        field = Point.y

        assert isinstance(field, ctypes.CField)  # type: ignore[attr-defined]
        assert (field.name, field.type) == ("y", ctypes.c_int)  # type: ignore[attr-defined]
        assert field.byte_offset == field.offset == 4  # type: ignore[attr-defined]
        assert field.byte_size == field.size == 4  # type: ignore[attr-defined]
        assert (field.bit_offset, field.bit_size) == (0, 32)  # type: ignore[attr-defined]
        assert not field.is_bitfield and not field.is_anonymous  # type: ignore[attr-defined]


class TestByteOrder:
    """The endian variants store fields in a fixed byte order."""

    def test_big_endian_structure(self) -> None:
        class Header(ctypes.BigEndianStructure):
            _fields_ = [("magic", ctypes.c_uint16), ("length", ctypes.c_uint16)]

        header = Header(0x0102, 5)

        assert bytes(header) == b"\x01\x02\x00\x05"
        assert header.length == 5

    def test_little_endian_structure(self) -> None:
        class Header(ctypes.LittleEndianStructure):
            _fields_ = [("magic", ctypes.c_uint16)]

        assert bytes(Header(0x0102)) == b"\x02\x01"

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="added in 3.11")
    def test_endian_unions(self) -> None:
        class Big(ctypes.BigEndianUnion):  # type: ignore[name-defined, misc]
            _fields_ = [("value", ctypes.c_uint16)]

        class Little(ctypes.LittleEndianUnion):  # type: ignore[name-defined, misc]
            _fields_ = [("value", ctypes.c_uint16)]

        assert bytes(Big(0x0102)) == b"\x01\x02"
        assert bytes(Little(0x0102)) == b"\x02\x01"


class TestPointers:
    """`POINTER` is cached; `pointer`, `cast` and `contents` share memory and
    keep their target alive; `byref` builds no pointer."""

    def test_pointer_types_are_cached(self) -> None:
        assert ctypes.POINTER(ctypes.c_int) is ctypes.POINTER(ctypes.c_int)
        assert ctypes.POINTER(ctypes.c_int)._type_ is ctypes.c_int  # type: ignore[misc]  # noqa: SLF001

    def test_pointer_writes_through_and_keeps_the_target(self) -> None:
        value = ctypes.c_int(42)
        pointer = ctypes.pointer(value)

        pointer.contents.value = 100
        pointer[0] += 1

        assert value.value == 101
        assert value in pointer._objects.values()  # type: ignore[union-attr]  # noqa: SLF001

    def test_contents_is_a_new_object_over_the_same_memory(self) -> None:
        value = ctypes.c_int(1)
        pointer = ctypes.pointer(value)

        assert pointer.contents is not pointer.contents
        assert ctypes.addressof(pointer.contents) == ctypes.addressof(value)

    def test_byref_builds_no_pointer(self) -> None:
        reference = ctypes.byref(ctypes.c_int(1))

        assert not isinstance(reference, ctypes._Pointer)  # noqa: SLF001

    def test_cast_shares_the_address_and_keeps_the_source(self) -> None:
        value = ctypes.c_int(0x01020304)
        pointer = ctypes.pointer(value)

        as_bytes = ctypes.cast(pointer, ctypes.POINTER(ctypes.c_ubyte))

        assert ctypes.addressof(as_bytes.contents) == ctypes.addressof(value)
        assert pointer in as_bytes._objects.values()  # type: ignore[union-attr]  # noqa: SLF001

    def test_sizes_and_alignment(self) -> None:
        assert ctypes.sizeof(ctypes.c_int * 10) == 10 * ctypes.sizeof(ctypes.c_int)
        assert ctypes.alignment(ctypes.c_double) == ctypes.sizeof(ctypes.c_double)


class TestSharingAndCopying:
    """`from_buffer`, `from_address`, `memoryview_at` share; the `_copy`
    form and `string_at` copy; `memmove` and `memset` allocate nothing."""

    SIZE = 10_000_000

    def test_from_buffer_shares(self) -> None:
        raw = bytearray(self.SIZE)
        kind = ctypes.c_uint8 * self.SIZE

        holder: list[Any] = []
        peak = peak_bytes(lambda: holder.append(kind.from_buffer(raw)))
        raw[0] = 9

        assert holder[0][0] == 9
        assert holder[0]._objects is not None  # noqa: SLF001
        assert peak < 20_000, f"from_buffer over 10 MB allocated {peak}"

    def test_from_buffer_copy_copies(self) -> None:
        raw = bytearray(self.SIZE)
        kind = ctypes.c_uint8 * self.SIZE

        holder: list[Any] = []
        peak = peak_bytes(lambda: holder.append(kind.from_buffer_copy(raw)))
        raw[0] = 9

        assert holder[0][0] == 0
        assert peak > self.SIZE

    def test_from_address_shares(self) -> None:
        value = ctypes.c_int(5)

        alias = ctypes.c_int.from_address(ctypes.addressof(value))
        alias.value = 6

        assert value.value == 6

    @POSIX
    def test_in_dll_reads_the_library_variable(self) -> None:
        exception = ctypes.py_object.in_dll(ctypes.pythonapi, "PyExc_ValueError")

        assert exception.value is ValueError

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="added in 3.14")
    def test_memoryview_at_shares(self) -> None:
        buffer = ctypes.create_string_buffer(self.SIZE)

        views: list[memoryview] = []
        peak = peak_bytes(
            lambda: views.append(ctypes.memoryview_at(buffer, self.SIZE))  # type: ignore[attr-defined]
        )
        views[0][0] = ord("Z")

        assert buffer.raw[0:1] == b"Z"
        assert peak < 20_000, f"memoryview_at over 10 MB allocated {peak}"

        readonly = ctypes.memoryview_at(buffer, 4, readonly=True)  # type: ignore[attr-defined]
        assert readonly.readonly

    def test_memmove_and_memset_allocate_nothing(self) -> None:
        source = ctypes.create_string_buffer(b"a" * (self.SIZE - 1))
        target = ctypes.create_string_buffer(self.SIZE)

        moved = peak_bytes(lambda: ctypes.memmove(target, source, self.SIZE))
        assert target.raw[:3] == b"aaa"
        filled = peak_bytes(lambda: ctypes.memset(target, ord("z"), self.SIZE))
        assert target.raw[-3:] == b"zzz"

        assert moved < 20_000 and filled < 20_000, (moved, filled)


@POSIX
class TestErrno:
    """`get_errno()` reads the copy saved after a `use_errno=True` call, and
    `set_errno()` returns the previous value."""

    def test_errno_is_captured_after_the_call(self) -> None:
        lib = ctypes.CDLL(None, use_errno=True)
        ctypes.set_errno(0)

        assert lib.close(-1) == -1
        assert ctypes.get_errno() != 0

    def test_set_errno_returns_the_old_value(self) -> None:
        ctypes.set_errno(7)

        assert ctypes.set_errno(0) == 7
        assert ctypes.get_errno() == 0


class TestSetPointerType:
    """`SetPointerType(pointer, cls)` completes an incomplete pointer type,
    and is deprecated from 3.13."""

    @staticmethod
    def incomplete(name: str) -> Any:
        if sys.version_info >= (3, 14):
            return type(f"LP_{name}", (ctypes._Pointer,), {})  # noqa: SLF001
        return ctypes.POINTER(name)  # type: ignore[arg-type]

    @staticmethod
    def complete(pointer: Any) -> type:
        class Node(ctypes.Structure):
            _fields_ = [("value", ctypes.c_int), ("next", pointer)]

        ctypes.SetPointerType(pointer, Node)
        return Node

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="deprecated from 3.13")
    def test_it_completes_the_type(self) -> None:
        pointer = self.incomplete("NodeA")

        node = self.complete(pointer)

        assert pointer._type_ is node  # noqa: SLF001

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="deprecated from 3.13")
    def test_it_warns_and_completes_the_type(self) -> None:
        pointer = self.incomplete("NodeB")

        with pytest.warns(DeprecationWarning, match="SetPointerType"):
            node = self.complete(pointer)

        assert pointer._type_ is node  # noqa: SLF001


@WINDOWS
class TestWindowsOnly:
    """The Windows rows. They skip everywhere this project runs."""

    def test_windll_caches_and_windll_functions_cache(self) -> None:
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

        assert ctypes.windll.kernel32 is kernel32  # type: ignore[attr-defined]
        assert kernel32.GetTickCount is kernel32.GetTickCount
        assert isinstance(kernel32, ctypes.WinDLL)  # type: ignore[attr-defined]

    def test_winfunctype_is_cached(self) -> None:
        winfunctype = ctypes.WINFUNCTYPE  # type: ignore[attr-defined]

        assert winfunctype(ctypes.c_int) is winfunctype(ctypes.c_int)

    def test_last_error(self) -> None:
        ctypes.set_last_error(5)  # type: ignore[attr-defined]

        assert ctypes.set_last_error(0) == 5  # type: ignore[attr-defined]
        assert isinstance(ctypes.WinError(5), OSError)  # type: ignore[attr-defined]
        assert ctypes.FormatError(5)  # type: ignore[attr-defined]


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


@POSIX
class TestDocumentedExamples:
    """Each block runs in its own subprocess, with warnings as errors, and
    asserts its own result. The blocks load the C library with `CDLL(None)`,
    so they run on Unix only."""

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
        line, source = next((n, s) for n, s in _blocks() if "assert shared[0] == 9" in s)
        mutated = source.replace("assert shared[0] == 9", "assert shared[0] == 0", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
