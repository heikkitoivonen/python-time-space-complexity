"""Tests for docs/stdlib/copyreg.md.

The page prices every `copyreg` operation as O(1) apart from
`clear_extension_cache()`, which empties a dict. Those bounds follow from
Lib/copyreg.py, where each function does a callability check, builds a
reduction tuple, or makes a fixed number of registry lookups, insertions and
deletions; what
the tests settle is the behaviour the page builds on them - which objects
`pickle` and `copy` look up, how often a reducer runs, and what an extension
code changes in a pickle - by observation: call counters, identity checks and
`pickletools` opcodes, none of which needs a tolerance. The one timing test is
the O(c) clear.

Measurement scope:

* `copyreg.pickle()` stores the function itself under the exact type and
  raises `TypeError` for a non-callable; `constructor()` leaves
  `dispatch_table` unchanged and raises `TypeError` for a non-callable.
  `copy` imports the same `dispatch_table` object, and an entry assigned to
  the dict directly is used by `pickle.dumps()` and removed by `del`.
* A counting reducer runs once for a list holding one instance 1,000 times
  and 1,000 times for 1,000 distinct instances, on every pickle protocol.
  `copy.copy()` calls it once, and `copy.deepcopy()` once for the repeated
  instance, whose reducer builds a fresh object; a class's own `__copy__` or
  `__deepcopy__`, which `copy` tries first, is not exercised.
* The lookup is by exact type: a subclass instance does not call its base's
  reducer. A `Pickler` whose `dispatch_table` is an empty dict does not call
  the global one. Reducers registered for `int`, `str`, `list` and `dict` are
  never called by `pickle.dumps()`, `copy.copy()` or `copy.deepcopy()`.
* An extension code replaces a global's module and name with an `EXT1`
  opcode on protocols 2 to the highest, giving a shorter pickle, and is not
  used on protocols 0 and 1. A counting `Unpickler.find_class` is called once
  for the first load of a code and not for the second; after
  `clear_extension_cache()` it is called again; `remove_extension()` empties
  the cached entry and a later load raises `ValueError`.
* `add_extension()` raises `ValueError` for codes 0 and 2**31, for a key
  already holding another code and for a code already holding another key,
  and accepts the identical pair twice. `remove_extension()` raises
  `ValueError` for a pair that is not registered.
* `clear_extension_cache()` over 1,000 and 100,000 cached entries: the larger
  costs more than 10x the smaller, where a constant-time clear predicts 1x
  and a linear one 100x; it allocates under 1 KB at 100,000 entries. The
  cache is refilled outside each timed call.
* `pickle_complex()` returns `(complex, (real, imag))`; `pickle_union()`
  returns the union's own `__args__` object as its last argument, and a union
  round-trips through `pickle`. Both are registered in `dispatch_table`. `pickle_super` exists on 3.14+ and
  round-trips a `super` object through `pickle` and `copy.copy()`; before
  3.14 it is absent, pickling a `super` object raises, and `copy.copy()`
  either raises or returns something other than a `super` object.
* Every fenced Python block runs in its own subprocess, so registrations
  cannot leak between them, and a mutated assertion is asserted to fail.

Not settled here:

* The O(1) bounds of `pickle()`, `add_extension()` and `remove_extension()`
  are dict operations read from Lib/copyreg.py; registry size is not varied.
* That codes 240 to 255 are reserved for private use is the allocation table
  in Lib/copyreg.py's closing comment, a convention rather than behaviour.
* A reducer's own cost is the caller's; only reducers that return at once are
  used here.
"""

from __future__ import annotations

import copy
import copyreg
import io
import pathlib
import pickle
import pickletools
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections import OrderedDict
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "copyreg.md"
EXPECTED_BLOCKS = 4

# A code from the private-use range; TestExtensionCodes asserts nothing else holds it.
CODE = 241


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


@pytest.fixture(autouse=True)
def _restore_registries() -> Iterator[None]:
    """Put every copyreg registry back as it was, mutating rather than rebinding,
    because `pickle` holds references to these exact dicts."""
    registries: list[dict[Any, Any]] = [
        copyreg.dispatch_table,
        copyreg._extension_registry,  # type: ignore[attr-defined]  # noqa: SLF001
        copyreg._inverted_registry,  # type: ignore[attr-defined]  # noqa: SLF001
        copyreg._extension_cache,  # type: ignore[attr-defined]  # noqa: SLF001
    ]
    saved = [dict(registry) for registry in registries]
    yield
    for registry, contents in zip(registries, saved, strict=True):
        registry.clear()
        registry.update(contents)


class Point:
    def __init__(self, x: int) -> None:
        self.x = x


class SubPoint(Point):
    pass


class CountingReducer:
    """A reduction function that records each object it is asked to reduce."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, obj: Point) -> tuple[type[Point], tuple[int]]:
        self.calls += 1
        return Point, (obj.x,)


class CountingUnpickler(pickle.Unpickler):
    """Counts the global lookups an unpickle makes."""

    lookups = 0

    def find_class(self, module: str, name: str) -> Any:
        CountingUnpickler.lookups += 1
        return super().find_class(module, name)


def load_counting(data: bytes) -> tuple[Any, int]:
    CountingUnpickler.lookups = 0
    result = CountingUnpickler(io.BytesIO(data)).load()
    return result, CountingUnpickler.lookups


class TestRegisteringIsOneEntry:
    """`pickle(type, function)` | O(1) | one `dispatch_table` entry;
    `constructor(object)` only checks that its argument is callable."""

    def test_pickle_stores_the_function_under_the_exact_type(self) -> None:
        reducer = CountingReducer()

        copyreg.pickle(Point, reducer)

        assert copyreg.dispatch_table[Point] is reducer
        assert SubPoint not in copyreg.dispatch_table

    def test_pickle_rejects_a_non_callable(self) -> None:
        with pytest.raises(TypeError, match="must be callable"):
            copyreg.pickle(Point, 42)  # type: ignore[arg-type]
        assert Point not in copyreg.dispatch_table

    def test_constructor_registers_nothing(self) -> None:
        before = dict(copyreg.dispatch_table)

        copyreg.constructor(Point)  # type: ignore[arg-type]

        assert copyreg.dispatch_table == before
        with pytest.raises(TypeError, match="must be callable"):
            copyreg.constructor(42)  # type: ignore[arg-type]

    def test_copy_reads_the_same_dict(self) -> None:
        assert copy.dispatch_table is copyreg.dispatch_table  # type: ignore[attr-defined]

    def test_editing_the_dict_registers_and_unregisters(self) -> None:
        reducer = CountingReducer()

        copyreg.dispatch_table[Point] = reducer
        pickle.dumps(Point(1))
        del copyreg.dispatch_table[Point]
        pickle.dumps(Point(1))

        assert reducer.calls == 1


class TestReducerRunsOncePerDistinctObject:
    """`pickle` adds one reducer call per distinct object, because it memoizes
    an object it has already written; `copy` consults the same table."""

    @pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
    def test_a_repeated_instance_is_reduced_once(self, protocol: int) -> None:
        reducer = CountingReducer()
        copyreg.pickle(Point, reducer)
        point = Point(1)

        restored = pickle.loads(pickle.dumps([point] * 1_000, protocol))

        assert reducer.calls == 1
        assert all(item is restored[0] for item in restored)

    @pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
    def test_distinct_instances_are_each_reduced(self, protocol: int) -> None:
        reducer = CountingReducer()
        copyreg.pickle(Point, reducer)

        pickle.dumps([Point(index) for index in range(1_000)], protocol)

        assert reducer.calls == 1_000

    def test_copy_calls_the_registered_reducer(self) -> None:
        reducer = CountingReducer()
        copyreg.pickle(Point, reducer)
        point = Point(1)

        clone = copy.copy(point)

        assert reducer.calls == 1
        assert clone is not point and clone.x == 1

    def test_deepcopy_reduces_a_repeated_instance_once(self) -> None:
        reducer = CountingReducer()
        copyreg.pickle(Point, reducer)
        point = Point(1)

        clone = copy.deepcopy([point, point])

        assert reducer.calls == 1
        assert clone[0] is clone[1] and clone[0] is not point


class TestWhatTheRegistryDoesNotReach:
    """Exact-type lookup, a private `Pickler.dispatch_table` replacing the
    global one, and the types `pickle` writes directly."""

    def test_a_subclass_is_not_looked_up_under_its_base(self) -> None:
        reducer = CountingReducer()
        copyreg.pickle(Point, reducer)

        pickle.dumps(SubPoint(1))
        copy.copy(SubPoint(1))

        assert reducer.calls == 0

    def test_a_private_dispatch_table_replaces_the_global_one(self) -> None:
        reducer = CountingReducer()
        copyreg.pickle(Point, reducer)
        pickler = pickle.Pickler(io.BytesIO())
        pickler.dispatch_table = {}

        pickler.dump(Point(1))

        assert reducer.calls == 0
        pickle.dumps(Point(1))
        assert reducer.calls == 1, "the global entry is live; only the pickler bypassed it"

    @pytest.mark.parametrize(
        ("kind", "value"), [(int, 5), (str, "s"), (list, [1, 2]), (dict, {"a": 1})]
    )
    def test_types_written_directly_ignore_the_table(self, kind: type, value: object) -> None:
        calls: list[object] = []

        def reducer(obj: Any) -> tuple[Any, tuple[Any, ...]]:
            calls.append(obj)
            return kind, (value,)

        copyreg.pickle(kind, reducer)

        assert pickle.loads(pickle.dumps(value)) == value
        copy.copy(value)
        copy.deepcopy(value)

        assert calls == []


class TestExtensionCodes:
    """`add_extension` | O(1); a registered global is written as its code on
    protocol 2+, resolved once per code and then cached."""

    @pytest.fixture(autouse=True)
    def _code_is_free(self) -> None:
        registry = copyreg._extension_registry  # type: ignore[attr-defined]  # noqa: SLF001
        inverted = copyreg._inverted_registry  # type: ignore[attr-defined]  # noqa: SLF001
        cache = copyreg._extension_cache  # type: ignore[attr-defined]  # noqa: SLF001
        assert CODE not in inverted and CODE not in cache, f"code {CODE} is in use elsewhere"
        assert ("collections", "OrderedDict") not in registry, "OrderedDict already has a code"
        assert ("collections", "deque") not in registry, "deque already has a code"

    @staticmethod
    def opcodes(data: bytes) -> list[str]:
        return [opcode.name for opcode, _, _ in pickletools.genops(data)]

    @pytest.mark.parametrize("protocol", range(2, pickle.HIGHEST_PROTOCOL + 1))
    def test_a_registered_global_is_written_as_its_code(self, protocol: int) -> None:
        by_name = pickle.dumps(OrderedDict, protocol)

        copyreg.add_extension("collections", "OrderedDict", CODE)
        by_code = pickle.dumps(OrderedDict, protocol)

        assert "EXT1" in self.opcodes(by_code)
        assert len(by_code) < len(by_name)
        assert pickle.loads(by_code) is OrderedDict

    @pytest.mark.parametrize("protocol", [0, 1])
    def test_protocols_before_2_ignore_it(self, protocol: int) -> None:
        copyreg.add_extension("collections", "OrderedDict", CODE)

        data = pickle.dumps(OrderedDict, protocol)

        assert not any(name.startswith("EXT") for name in self.opcodes(data))
        assert b"OrderedDict" in data

    def test_a_code_is_looked_up_once_then_cached(self) -> None:
        copyreg.add_extension("collections", "OrderedDict", CODE)
        data = pickle.dumps(OrderedDict, 2)

        first, first_lookups = load_counting(data)
        second, second_lookups = load_counting(data)

        assert first is second is OrderedDict
        assert (first_lookups, second_lookups) == (1, 0)

    def test_clearing_the_cache_forces_a_new_lookup(self) -> None:
        copyreg.add_extension("collections", "OrderedDict", CODE)
        data = pickle.dumps(OrderedDict, 2)
        load_counting(data)

        copyreg.clear_extension_cache()

        assert CODE not in copyreg._extension_cache  # type: ignore[attr-defined]  # noqa: SLF001
        assert load_counting(data) == (OrderedDict, 1)

    def test_removing_drops_the_cached_object_and_the_code(self) -> None:
        copyreg.add_extension("collections", "OrderedDict", CODE)
        data = pickle.dumps(OrderedDict, 2)
        pickle.loads(data)

        copyreg.remove_extension("collections", "OrderedDict", CODE)

        assert CODE not in copyreg._extension_cache  # type: ignore[attr-defined]  # noqa: SLF001
        with pytest.raises(ValueError, match="unregistered extension code"):
            pickle.loads(data)

    def test_registration_errors(self) -> None:
        for bad in (0, 2**31):
            with pytest.raises(ValueError, match="out of range"):
                copyreg.add_extension("collections", "OrderedDict", bad)
        copyreg.add_extension("collections", "OrderedDict", CODE)
        copyreg.add_extension("collections", "OrderedDict", CODE)  # identical: no-op

        with pytest.raises(ValueError, match="already registered"):
            copyreg.add_extension("collections", "OrderedDict", CODE + 1)
        with pytest.raises(ValueError, match="already in use"):
            copyreg.add_extension("collections", "deque", CODE)
        with pytest.raises(ValueError, match="not registered"):
            copyreg.remove_extension("collections", "deque", CODE)

    def test_the_bounds_of_the_code_range_are_accepted(self) -> None:
        for code in (1, 2**31 - 1):
            copyreg.add_extension("tests.bounds", f"name{code}", code)
            copyreg.remove_extension("tests.bounds", f"name{code}", code)


class TestClearingTheCacheIsLinear:
    """`clear_extension_cache()` | O(c) | O(1) | c = cached objects."""

    CACHE: dict[int, Any] = copyreg._extension_cache  # type: ignore[attr-defined]  # noqa: SLF001

    def fill(self, size: int) -> None:
        self.CACHE.update(dict.fromkeys(range(1_000_000, 1_000_000 + size), OrderedDict))

    def clear_ns(self, size: int) -> float:
        best: float | None = None
        for _ in range(7):
            self.fill(size)
            start = time.perf_counter_ns()
            copyreg.clear_extension_cache()
            elapsed = time.perf_counter_ns() - start
            best = elapsed if best is None else min(best, elapsed)
        assert best is not None
        return best

    def test_it_empties_the_cache_without_allocating(self) -> None:
        self.fill(100_000)

        peak = peak_bytes(copyreg.clear_extension_cache)

        assert self.CACHE == {}
        assert peak < 1_000, f"clearing 100,000 entries allocated {peak} bytes"

    @pytest.mark.timing
    def test_a_hundred_times_the_entries_costs_far_more(self) -> None:
        small = self.clear_ns(1_000)
        large = self.clear_ns(100_000)

        ratio = large / small
        assert ratio > 10, (
            f"100x the cached entries cost x{ratio:.1f} ({small:.0f}ns to {large:.0f}ns); "
            "a constant-time clear would give x1"
        )


class TestBuiltInReducers:
    """`pickle_complex`, `pickle_union` and, on 3.14+, `pickle_super`: each
    O(1), each registered for its type."""

    def test_pickle_complex(self) -> None:
        pickle_complex = copyreg.pickle_complex  # type: ignore[attr-defined]

        assert copyreg.dispatch_table[complex] is pickle_complex
        assert pickle_complex(1 + 2j) == (complex, (1.0, 2.0))

    def test_pickle_union_returns_the_union_s_own_arguments(self) -> None:
        union = int | str

        reduced = copyreg.pickle_union(union)  # type: ignore[attr-defined]

        assert copyreg.dispatch_table[type(union)] is copyreg.pickle_union  # type: ignore[attr-defined]
        assert reduced[1][-1] is union.__args__
        assert pickle.loads(pickle.dumps(union)) == union

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="pickle_super was added in 3.14")
    def test_super_round_trips_on_314(self) -> None:
        bound = super(SubPoint, SubPoint(1))

        assert copyreg.dispatch_table[super] is copyreg.pickle_super  # type: ignore[attr-defined]
        for clone in (pickle.loads(pickle.dumps(bound)), copy.copy(bound)):
            assert type(clone) is super
            assert clone.__thisclass__ is SubPoint  # type: ignore[attr-defined]
            assert type(clone.__self__) is SubPoint  # type: ignore[attr-defined]

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="pickle_super exists from 3.14")
    def test_super_does_not_round_trip_before_314(self) -> None:
        bound = super(SubPoint, SubPoint(1))

        assert not hasattr(copyreg, "pickle_super")
        with pytest.raises(pickle.PicklingError):
            pickle.dumps(bound)
        try:
            clone = copy.copy(bound)
        except Exception:  # noqa: BLE001 - failing outright is also not copying
            pass
        else:
            assert type(clone) is not super


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
    """Each block runs in its own subprocess, so the process-wide registries
    cannot leak between them, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "assert len(calls) == 1\n" in s)
        mutated = source.replace("assert len(calls) == 1\n", "assert len(calls) == 2\n", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
