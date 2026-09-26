"""Tests for docs/stdlib/pickle.md.

The page prices pickling and unpickling in b, the length of the pickle, with
the memo (m distinct memoized objects) and the longest string (s) as the
terms that decide what `dump()` holds in memory. Growth in b is settled by
exact output lengths and a timing test; what `dump()` holds is settled by
traced allocation against a sink that keeps nothing, which separates a
frame-sized peak from a pickle-sized one by orders of magnitude; the hook
rows are settled by counting calls; identity and out-of-band rows by `is`.

Measurement scope:

* Output length: a list of distinct strings grows between 8x and 12x in
  pickle length from 2,000 to 20,000 elements under every protocol 0-5
  (protocol 0 writes memo indexes as decimal text, which adds a digit).
  A timing test has `dumps()` and `loads()` of 2,000, 20,000 and 200,000
  strings and of as many small dicts each cost between 4x and 40x per 10x
  step (linear predicts 10x, quadratic 100x).
* `dump()` into a sink that discards what it is given: 1,000,000 ints peak
  under 200 KB for protocols 4 and 5 and over 3 MB for protocols 0-3, whose
  pickle is written in one call; protocol 5 writes 100,000 ints in several
  calls of under 70,000 bytes each. 200,000 distinct strings peak more than 5x
  higher than 20,000, which is the memo. A 10,000,000-character ASCII string
  and a 10,000,000-byte int each peak over 5 MB, and 10,000,000 bytes under
  100 KB, under protocol 5.
  `dumps()` of 1,000,000 ints peaks above the length of its result, and
  `loads()` of 200,000 strings peaks more than 5x higher than 20,000.
* `load()` is asserted to return two pickles written one after another, from
  a `BytesIO` and from a real file, and to raise `EOFError` after the last.
* Memo: `[text] * 100` for a 10,000-character string pickles under 11,000
  bytes and comes back as one object; a self-referencing dict comes back
  referencing itself. A reused `Pickler` writes a 1,000-string list a second
  time in under 20 bytes, and in full again after `clear_memo()`; the second
  pickle is asserted not to load on its own. The memo of a list of 1,000
  ints, 1,000 floats, `None` and both booleans holds only the list. A
  `__reduce__` callable runs three times loading three objects and once
  loading one object referenced three times. An instance written by a
  `Pickler` survives `del` and a collection until `clear_memo()`, observed by
  weak reference; `[(), (), ""]` leaves two memo entries, and an empty list,
  dict, set and frozenset, a class and a function each take one.
* Hooks, by call counting on protocol 5: `persistent_id` is called 101 times
  for a list of 100 references to one string and for a list of 100 ints;
  `persistent_load` once per ID written; `reducer_override` 101 times for 100
  distinct instances of one class (the instances and the class), twice for
  one instance referenced 100 times, and never for `None`, booleans, ints,
  floats, strings, bytes, bytearrays, lists, tuples, dicts, sets, frozensets
  and `PickleBuffer` objects; a `list` subclass instance is passed to it
  once, and its int element never. `find_class` is called the same number of times for
  100 and for 1,000 instances of one class, under protocols 0 and 5.
  `dispatch_table` is asserted to change one pickler's output and not
  `pickle.dumps()`'s.
* `Pickler.fast`: 100 references to one 1,000-character string produce a
  pickle more than 50x the memoized one and 100 distinct objects after loading, and a cycle
  raises `ValueError`.
* `PickleBuffer`: pickled out of band, a 10,000,000-byte buffer gives a pickle
  under 100 bytes and a traced peak under 50 KB, and `loads(..., buffers=)`
  returns the `bytearray` passed in; a buffer pickled read-only comes back as
  a read-only `memoryview` over a `bytearray` passed in. In band, and with a
  callback that returns `True`, the pickle is longer than the buffer, and
  protocol 4 raises `PicklingError`. `raw()` is a `memoryview`
  over the same object, and `raw()` after `release()` raises `ValueError`;
  wrapping a 10,000,000-byte buffer peaks under 5 KB.
* A structure nested 1,000,000 lists deep raises `RecursionError` on
  `dumps()`.
* Constants and exceptions by value and by `issubclass`: `DEFAULT_PROTOCOL`
  is 4 before 3.14 and 5 from 3.14, a nested function raises
  `PicklingError` from 3.14 and `AttributeError` before, each guarded on
  `sys.version_info`. A module-level lambda raises `PicklingError` and a
  generator `TypeError`; corrupt input raises
  `UnpicklingError`, and some truncations of a valid pickle raise `EOFError`.
* A `Pickler` is built over an object with only `write()`, and an
  `Unpickler` over one with only `read()` and `readline()`.
* Every fenced Python block runs in its own subprocess and working directory,
  and a mutated assertion in one of them is asserted to fail.

Not settled here:

* `clear_memo()` as O(m) is read from Modules/_pickle.c: it walks the whole
  memo table, whose capacity stays at the most entries it has held, and
  releases each reference; clearing is not timed, and the deallocation of
  objects the memo alone kept alive is not priced.
* Hand-crafted pickles are out of scope: a large memo index written by hand
  (`LONG_BINPUT`), or a repeated `GLOBAL`, can make `load()` cost more than
  its length or call `find_class` more than once per name. Only pickles this
  module wrote are measured.
* Protocols 0 and 1 write an int in decimal; beyond
  `sys.get_int_max_str_digits()` digits that raises `ValueError`, so the
  quadratic conversion is bounded by the limit and is not measured.
* Non-contiguous buffers, and the ID `persistent_id` returns (which is
  written without being passed back to it), are not covered.
* `find_class`, `persistent_id` and `persistent_load` as O(1) per call
  exclude the user code they run and any import `find_class` triggers; a
  dotted qualified name adds one attribute lookup per component, not varied.
* The bounds exclude user reduction and reconstruction code, and treat key
  hashing while rebuilding a dict or set as O(1).
* The depth at which `RecursionError` is raised depends on the version's
  recursion or C-stack limit and is not asserted; unpickling a deeply nested
  pickle is not covered.
* `load()` from a file is not measured for memory beyond the rebuilt
  objects; read-ahead and buffering of the file are not varied.
* Not documented on the page: `Pickler.bin`, `Pickler.memo`,
  `Unpickler.memo`, `pickle.compatible_formats`, `pickle.encode_long`,
  `pickle.decode_long` and `pickle.whichmodule`, which are not part of the
  documented API, the opcode constants, and the pure-Python `_Pickler` and
  `_Unpickler`.
"""

from __future__ import annotations

import gc
import io
import pathlib
import pickle
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import weakref
from collections.abc import Callable
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "pickle.md"
EXPECTED_BLOCKS = 13


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


class NullSink:
    """A file-like object that keeps nothing it is given."""

    def write(self, data: bytes) -> int:
        return len(data)


class CountingSink:
    """A file-like object that records the size of each write."""

    def __init__(self) -> None:
        self.writes: list[int] = []

    def write(self, data: bytes) -> int:
        self.writes.append(len(data))
        return len(data)


class Point:
    def __init__(self, x: int) -> None:
        self.x = x


MODULE_LAMBDA = lambda: 0  # noqa: E731 - pickled by name, which a lambda does not have


class Items(list[int]):
    pass


class Rebuilt:
    built: list[int] = []

    def __init__(self, x: int) -> None:
        self.x = x
        Rebuilt.built.append(x)

    def __reduce__(self) -> tuple[Any, ...]:
        return (Rebuilt, (self.x,))


def strings(count: int) -> list[str]:
    return [f"s{index:07d}" for index in range(count)]


class TestPickleLengthIsLinear:
    """`dumps` and `loads` | O(b) | O(b): output length for every protocol,
    time for the default one."""

    @pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
    def test_ten_times_the_objects_is_ten_times_the_pickle(self, protocol: int) -> None:
        small = len(pickle.dumps(strings(2_000), protocol=protocol))
        large = len(pickle.dumps(strings(20_000), protocol=protocol))

        assert 8 < large / small < 12, f"protocol {protocol}: {small} -> {large} bytes"

    @pytest.mark.timing
    @pytest.mark.parametrize("shape", ["strings", "dicts"])
    def test_time_grows_linearly(self, shape: str) -> None:
        sizes = (2_000, 20_000, 200_000)
        objects = [
            strings(n) if shape == "strings" else [{"k": i, "v": f"s{i}"} for i in range(n)]
            for n in sizes
        ]
        data = [pickle.dumps(obj) for obj in objects]
        dumps_ns = [best_ns(lambda o=obj: pickle.dumps(o)) for obj in objects]  # type: ignore[misc]
        loads_ns = [best_ns(lambda d=d: pickle.loads(d)) for d in data]  # type: ignore[misc]

        for name, durations in (("dumps", dumps_ns), ("loads", loads_ns)):
            steps = [durations[i + 1] / durations[i] for i in range(2)]
            assert all(4 < step < 40 for step in steps), (
                f"{name} of {shape}: 10x steps cost {[f'x{s:.1f}' for s in steps]} "
                f"({durations} ns); linear predicts x10, quadratic x100"
            )


class TestDumpHoldsTheMemoFromProtocol4:
    """`dump` | O(b) | O(m + s) for protocol 4+, O(b) for 0-3.

    The sink keeps nothing, so a traced peak is what the pickler itself holds.
    """

    NUMBERS = list(range(1_000_000))

    @pytest.mark.parametrize("protocol", [4, 5])
    def test_framed_protocols_hold_a_frame_not_the_pickle(self, protocol: int) -> None:
        peak = peak_bytes(lambda: pickle.dump(self.NUMBERS, NullSink(), protocol=protocol))

        assert peak < 200_000, f"protocol {protocol} dump of 1,000,000 ints peaked at {peak}"

    @pytest.mark.parametrize("protocol", [0, 1, 2, 3])
    def test_unframed_protocols_hold_the_whole_pickle(self, protocol: int) -> None:
        sink = CountingSink()

        peak = peak_bytes(lambda: pickle.dump(self.NUMBERS, sink, protocol=protocol))

        assert peak > 3_000_000, f"protocol {protocol} dump of 1,000,000 ints peaked at {peak}"
        assert len(sink.writes) == 1

    def test_framed_output_arrives_in_frame_sized_writes(self) -> None:
        sink = CountingSink()

        pickle.dump(list(range(100_000)), sink, protocol=5)

        assert len(sink.writes) > 1
        assert max(sink.writes) < 70_000, sink.writes

    def test_the_memo_grows_with_memoized_objects(self) -> None:
        small, large = strings(20_000), strings(200_000)

        small_peak = peak_bytes(lambda: pickle.dump(small, NullSink(), protocol=5))
        large_peak = peak_bytes(lambda: pickle.dump(large, NullSink(), protocol=5))

        assert large_peak > small_peak * 5, f"10x the strings: {small_peak} -> {large_peak}"

    def test_strings_and_ints_are_encoded_whole_and_bytes_are_not_copied(self) -> None:
        text = "a" * 10_000_000
        number = 1 << 80_000_000
        blob = b"x" * 10_000_000

        text_peak = peak_bytes(lambda: pickle.dump(text, NullSink(), protocol=5))
        number_peak = peak_bytes(lambda: pickle.dump(number, NullSink(), protocol=5))
        blob_peak = peak_bytes(lambda: pickle.dump(blob, NullSink(), protocol=5))

        assert text_peak > 5_000_000, f"a 10 MB string peaked at {text_peak}"
        assert number_peak > 5_000_000, f"a 10 MB int peaked at {number_peak}"
        assert blob_peak < 100_000, f"10 MB of bytes peaked at {blob_peak}"

    def test_dumps_holds_the_whole_pickle(self) -> None:
        result: list[bytes] = []

        peak = peak_bytes(lambda: result.append(pickle.dumps(self.NUMBERS)))

        assert peak >= len(result[0]) > 4_000_000

    def test_loads_space_follows_the_pickle(self) -> None:
        small, large = pickle.dumps(strings(20_000)), pickle.dumps(strings(200_000))

        small_peak = peak_bytes(lambda: pickle.loads(small))
        large_peak = peak_bytes(lambda: pickle.loads(large))

        assert large_peak > small_peak * 5, f"10x the pickle: {small_peak} -> {large_peak}"


class TestLoadStopsAfterOnePickle:
    """`load` returns one pickle and leaves the file at the next."""

    def test_two_pickles_from_a_stream(self) -> None:
        buffer = io.BytesIO()
        pickle.dump([1, 2, 3], buffer)
        pickle.dump({"x": 1}, buffer)
        buffer.seek(0)

        assert pickle.load(buffer) == [1, 2, 3]
        assert pickle.load(buffer) == {"x": 1}
        with pytest.raises(EOFError):
            pickle.load(buffer)

    def test_two_pickles_from_a_file(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "data.pkl"
        with path.open("wb") as f:
            pickle.dump(strings(50_000), f)
            pickle.dump("second", f)

        with path.open("rb") as f:
            assert pickle.load(f) == strings(50_000)
            assert pickle.load(f) == "second"
            with pytest.raises(EOFError):
                pickle.load(f)

    def test_file_objects_need_only_the_documented_methods(self) -> None:
        class WriteOnly:
            def __init__(self) -> None:
                self.data = bytearray()

            def write(self, chunk: bytes) -> int:
                self.data += chunk
                return len(chunk)

        class ReadOnly:
            def __init__(self, data: bytes) -> None:
                self._stream = io.BytesIO(data)

            def read(self, size: int = -1) -> bytes:
                return self._stream.read(size)

            def readline(self) -> bytes:
                return self._stream.readline()

        sink = WriteOnly()
        pickle.Pickler(sink).dump(["a", 1])

        assert pickle.Unpickler(ReadOnly(bytes(sink.data))).load() == ["a", 1]


class TestTheMemo:
    """Shared and cyclic references are written once; a `Pickler` keeps its
    memo across `dump()` calls until `clear_memo()`."""

    def test_a_shared_object_is_written_once_and_stays_shared(self) -> None:
        text = "x" * 10_000

        data = pickle.dumps([text] * 100)
        restored = pickle.loads(data)

        assert len(data) < 11_000
        assert all(item is restored[0] for item in restored)

    def test_a_cycle_survives(self) -> None:
        node: dict[str, Any] = {"name": "A"}
        node["self"] = node

        again = pickle.loads(pickle.dumps(node))

        assert again["self"] is again

    def test_a_reused_pickler_writes_a_back_reference(self) -> None:
        record = strings(1_000)
        buffer = io.BytesIO()
        pickler = pickle.Pickler(buffer)

        pickler.dump(record)
        first = buffer.tell()
        pickler.dump(record)
        second = buffer.tell() - first
        pickler.clear_memo()
        pickler.dump(record)
        third = buffer.tell() - first - second

        assert second < 20 < first
        assert third == first
        with pytest.raises((pickle.UnpicklingError, KeyError)):
            pickle.loads(buffer.getvalue()[first : first + second])

    def test_a_reused_pickler_keeps_what_it_wrote_alive(self) -> None:
        pickler = pickle.Pickler(io.BytesIO())
        written = Point(1)
        reference = weakref.ref(written)

        pickler.dump(written)
        del written
        gc.collect()
        assert reference() is not None
        pickler.clear_memo()
        gc.collect()
        assert reference() is None

    def test_an_empty_tuple_takes_no_memo_entry(self) -> None:
        pickler = pickle.Pickler(io.BytesIO())

        pickler.dump([(), (), ""])

        assert len(pickler.memo.copy()) == 2  # the list and the string

    def test_empty_containers_classes_and_functions_are_memoized(self) -> None:
        pickler = pickle.Pickler(io.BytesIO())

        items = [[], {}, set(), frozenset(), Point, len]
        pickler.dump(items)

        memoized = [obj for _, obj in pickler.memo.copy().values()]
        assert all(any(obj is item for obj in memoized) for item in [items, *items])

    def test_numbers_none_and_booleans_are_not_memoized(self) -> None:
        pickler = pickle.Pickler(io.BytesIO())
        values = [*range(1_000, 2_000), *(i / 3 for i in range(1_000)), None, True, False]

        pickler.dump(values)

        assert len(pickler.memo.copy()) == 1  # the list only

    def test_a_reduce_callable_runs_once_per_object_not_per_reference(self) -> None:
        distinct = pickle.dumps([Rebuilt(1), Rebuilt(2), Rebuilt(3)])
        shared = pickle.dumps([Rebuilt(4)] * 3)
        Rebuilt.built.clear()

        pickle.loads(distinct)
        assert Rebuilt.built == [1, 2, 3]
        pickle.loads(shared)
        assert Rebuilt.built == [1, 2, 3, 4]

    def test_fast_mode_drops_the_memo(self) -> None:
        text = "x" * 1_000
        memoized = len(pickle.dumps([text] * 100))
        buffer = io.BytesIO()
        pickler = pickle.Pickler(buffer)
        pickler.fast = True

        pickler.dump([text] * 100)
        restored = pickle.loads(buffer.getvalue())

        assert len(buffer.getvalue()) > memoized * 50
        assert len({id(item) for item in restored}) == 100

    def test_fast_mode_rejects_a_cycle(self) -> None:
        cyclic: list[Any] = []
        cyclic.append(cyclic)
        pickler = pickle.Pickler(io.BytesIO())
        pickler.fast = True

        with pytest.raises(ValueError, match="cyclic"):
            pickler.dump(cyclic)

    def test_deep_nesting_raises_recursion_error(self) -> None:
        nested: list[Any] = []
        for _ in range(1_000_000):
            nested = [nested]

        with pytest.raises(RecursionError):
            pickle.dumps(nested)


class TestHooksAreCalledPerReferenceOrPerObject:
    """`persistent_id` once per reference, `reducer_override` once per new
    non-builtin object, `find_class` once per distinct global."""

    @staticmethod
    def persistent_id_calls(obj: Any) -> int:
        calls = 0

        class Counting(pickle.Pickler):
            def persistent_id(self, obj: Any) -> Any:
                nonlocal calls
                calls += 1
                return None

        Counting(io.BytesIO(), protocol=5).dump(obj)
        return calls

    def test_persistent_id_sees_every_reference(self) -> None:
        assert self.persistent_id_calls(["x" * 100] * 100) == 101
        assert self.persistent_id_calls(list(range(100))) == 101

    def test_persistent_load_is_called_once_per_id(self) -> None:
        loaded: list[Any] = []

        class ById(pickle.Pickler):
            def persistent_id(self, obj: Any) -> Any:
                return obj.x if isinstance(obj, Point) else None

        class FromId(pickle.Unpickler):
            def persistent_load(self, pid: Any) -> Any:
                loaded.append(pid)
                return pid * 10

        buffer = io.BytesIO()
        ById(buffer).dump([Point(1), Point(2), "text", Point(3)])
        restored = FromId(io.BytesIO(buffer.getvalue())).load()

        assert loaded == [1, 2, 3]
        assert restored == [10, 20, "text", 30]

    @staticmethod
    def reducer_subjects(obj: Any) -> list[Any]:
        subjects: list[Any] = []

        class Recording(pickle.Pickler):
            def reducer_override(self, obj: Any) -> Any:
                subjects.append(obj)
                return NotImplemented

        Recording(io.BytesIO(), protocol=5).dump(obj)
        return subjects

    @classmethod
    def reducer_calls(cls, obj: Any) -> int:
        return len(cls.reducer_subjects(obj))

    def test_reducer_override_is_called_once_per_new_object(self) -> None:
        assert self.reducer_calls([Point(i) for i in range(100)]) == 101
        assert self.reducer_calls([Point(0)] * 100) == 2

    def test_reducer_override_skips_plain_builtins(self) -> None:
        builtins = [
            *(None, True, False, 1, 1.5, "s", b"b", bytearray(b"a"), [1], (1,)),
            *({"a": 1}, {1}, frozenset({1}), pickle.PickleBuffer(b"p")),
        ]

        assert self.reducer_calls(builtins) == 0

    def test_reducer_override_sees_a_builtin_subclass(self) -> None:
        items = Items([1])

        subjects = self.reducer_subjects(items)

        assert [s for s in subjects if s is items] == [items]
        assert not any(type(s) is int for s in subjects)

    def test_dispatch_table_is_per_pickler(self) -> None:
        def as_tuple(point: Point) -> tuple[Any, ...]:
            return (Point, (point.x * 2,))

        buffer = io.BytesIO()
        pickler = pickle.Pickler(buffer)
        pickler.dispatch_table = {Point: as_tuple}
        pickler.dump(Point(4))

        assert pickle.loads(buffer.getvalue()).x == 8
        assert pickle.loads(pickle.dumps(Point(4))).x == 4

    @staticmethod
    def find_class_calls(data: bytes) -> list[tuple[str, str]]:
        seen: list[tuple[str, str]] = []

        class Counting(pickle.Unpickler):
            def find_class(self, module: str, name: str) -> Any:
                seen.append((module, name))
                return super().find_class(module, name)

        Counting(io.BytesIO(data)).load()
        return seen

    @pytest.mark.parametrize("protocol", [0, 5])
    def test_find_class_is_called_per_distinct_global(self, protocol: int) -> None:
        few = self.find_class_calls(pickle.dumps([Point(i) for i in range(100)], protocol))
        many = self.find_class_calls(pickle.dumps([Point(i) for i in range(1_000)], protocol))

        assert few == many
        assert len(few) <= 3
        assert (Point.__module__, "Point") in few


class TestPickleBuffer:
    """`PickleBuffer` wraps without copying; out of band it is handed over,
    in band it is copied."""

    PAYLOAD = bytearray(10_000_000)

    def test_out_of_band_hands_the_buffer_over(self) -> None:
        buffers: list[pickle.PickleBuffer] = []
        result: list[bytes] = []

        peak = peak_bytes(
            lambda: result.append(
                pickle.dumps(
                    pickle.PickleBuffer(self.PAYLOAD), protocol=5, buffer_callback=buffers.append
                )
            )
        )

        assert len(result[0]) < 100
        assert peak < 50_000, f"out-of-band pickling of 10 MB peaked at {peak}"
        assert len(buffers) == 1
        assert pickle.loads(result[0], buffers=[self.PAYLOAD]) is self.PAYLOAD

    def test_in_band_copies_it(self) -> None:
        data = pickle.dumps(pickle.PickleBuffer(self.PAYLOAD), protocol=5)

        assert len(data) > len(self.PAYLOAD)
        assert pickle.loads(data) == self.PAYLOAD

    def test_a_truthy_callback_result_keeps_it_in_band(self) -> None:
        data = pickle.dumps(
            pickle.PickleBuffer(self.PAYLOAD), protocol=5, buffer_callback=lambda _: True
        )

        assert len(data) > len(self.PAYLOAD)

    def test_a_readonly_buffer_comes_back_as_a_view_over_the_one_passed(self) -> None:
        buffers: list[pickle.PickleBuffer] = []
        data = pickle.dumps(
            pickle.PickleBuffer(bytes(100)), protocol=5, buffer_callback=buffers.append
        )
        replacement = bytearray(100)

        restored = pickle.loads(data, buffers=[replacement])

        assert isinstance(restored, memoryview)
        assert restored.readonly
        assert restored.obj is replacement

    def test_protocols_below_5_refuse_it(self) -> None:
        with pytest.raises(pickle.PicklingError):
            pickle.dumps(pickle.PickleBuffer(self.PAYLOAD), protocol=4)

    def test_wrapping_and_raw_do_not_copy(self) -> None:
        wrapped: list[pickle.PickleBuffer] = []

        peak = peak_bytes(lambda: wrapped.append(pickle.PickleBuffer(self.PAYLOAD)))
        view = wrapped[0].raw()

        assert peak < 5_000
        assert isinstance(view, memoryview)
        assert view.obj is self.PAYLOAD
        assert view.nbytes == len(self.PAYLOAD)
        view.release()

    def test_release_ends_access(self) -> None:
        buffer = pickle.PickleBuffer(bytearray(10))

        buffer.release()

        with pytest.raises(ValueError, match="released"):
            buffer.raw()


class TestConstantsAndExceptions:
    """Protocol constants by value, and which exception each failure raises."""

    def test_protocol_constants(self) -> None:
        assert pickle.HIGHEST_PROTOCOL == 5
        assert pickle.DEFAULT_PROTOCOL == (5 if sys.version_info >= (3, 14) else 4)

    def test_exception_hierarchy(self) -> None:
        assert issubclass(pickle.PicklingError, pickle.PickleError)
        assert issubclass(pickle.UnpicklingError, pickle.PickleError)

    def test_a_module_level_lambda_raises_pickling_error(self) -> None:
        with pytest.raises(pickle.PicklingError):
            pickle.dumps(MODULE_LAMBDA)

    def test_an_unpicklable_instance_raises_type_error(self) -> None:
        with pytest.raises(TypeError, match="generator"):
            pickle.dumps(x for x in range(3))

    @staticmethod
    def nested() -> Callable[[], None]:
        def inner() -> None:
            pass

        return inner

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="PicklingError from 3.14")
    def test_a_nested_function_raises_pickling_error(self) -> None:
        with pytest.raises(pickle.PicklingError):
            pickle.dumps(self.nested())

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="AttributeError before 3.14")
    def test_a_nested_function_raises_attribute_error(self) -> None:
        with pytest.raises(AttributeError):
            pickle.dumps(self.nested())

    def test_corrupt_and_truncated_input(self) -> None:
        with pytest.raises(pickle.UnpicklingError):
            pickle.loads(b"not a pickle")

        data = pickle.dumps([1, 2, 3, "abc"], protocol=0)
        raised: set[type[BaseException]] = set()
        for cut in range(1, len(data)):
            try:
                pickle.loads(data[:cut])
            except Exception as error:  # noqa: BLE001 - collecting the types raised
                raised.add(type(error))
        assert pickle.UnpicklingError in raised
        assert EOFError in raised


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
    """Each block runs in its own subprocess and working directory, so the
    classes it defines live in its own `__main__`, and asserts its own
    result."""

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
        line, source = next((n, s) for n, s in _blocks() if "restored is payload" in s)
        mutated = source.replace("restored is payload", "restored is not payload", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
