"""Tests for docs/stdlib/functools.md.

The page prices the module per call: a cache pays for the key it builds from
every argument, a `partial` for the bindings it stores and then joins on each
call, a wrapper update for the names and dictionary entries it copies, a fold
for the function it calls once per step, and a generic function for one
linearisation per argument type. Call counts, identity and traced allocation
settle most rows with no tolerance; a stopwatch is used only where a growth
class has no counter: the miss cost of a dispatch, the per-call cost of a
`partial`, a cache clear and the widening accumulators of `reduce`.

Measurement scope:

* `lru_cache`: `fibonacci(30)` is counted at 31 misses and 28 hits, and the
  undecorated function at more than 2**10 calls for n=20. A counting
  `__hash__` on 5,000 positional arguments and on 2,000 keyword values shows
  every argument hashed on a hit, and a counting `__eq__` shows each fresh
  equal key compared once. A miss retains more than 400 KB for a
  50,000-argument call and under 5 KB for five. `maxsize` modes: currsize is
  10 after 100 calls at `maxsize=10`, 500 at `maxsize=None` with the first
  key still a hit, and 0 with no key built at `maxsize=0`; eviction is
  asserted by which key misses again; `cache()` and `lru_cache(maxsize=None)`
  report identical statistics. Keyword order and `typed` are asserted by
  currsize on two-argument calls, since a lone `int` or `float` is keyed as
  the scalar or as a tuple and never shares an entry; an unhashable argument
  by `TypeError` with the function uncalled, and by a plain call at
  `maxsize=0`. `cache_clear()` is timed on 10 and on 100,000 entries, the
  fastest of five fresh caches each, and asserted above 100x; `cache_info()`,
  `cache_parameters()` and `__wrapped__` by value. Applying `cache` to a
  function with a 20,000-entry `__dict__` peaks above 150 KB, against under
  5 KB for a bare one. A cached method's instance is asserted alive through
  a weak reference until `cache_clear()`. A timing test puts a hit under a
  twentieth of a fresh miss of `sum(range(2_000_000))`.
* `cached_property`: one call per instance across two accesses, per-instance
  values, the entry in `__dict__`, recomputation after `del`, and `TypeError`
  on a `__slots__` instance. The per-property lock is asserted present on the
  descriptor before 3.12 and absent from 3.12.
* `partial`: `func`, `args` and `keywords` are the same objects on every
  access, and a mutation of `keywords` reaches the next call. A retained
  construction, with the bindings prepared outside tracing, adds under 5 KB
  for 20 bindings and above 150 KB for 20,000, positional and keyword alike,
  and a retained merge of a 20,000-binding partial with 20,000 more adds
  above 300 KB; an inner partial carrying an attribute, or one whose
  `__dict__` was merely created by `vars()`, is wrapped instead of merged. Calls are timed with 20 and 20,000 stored bindings of
  each kind and asserted above 50x; the callee's own packing of those
  bindings is inside the measurement, since the bound prices the call as a
  whole. `Placeholder` (3.14+) is asserted by a recording callee to fill
  two slots left to right with surplus arguments appended, and to raise
  `TypeError` when unfilled. A class-attribute `partial` is
  asserted to bind on 3.14, to warn on 3.13, and to do neither before.
* `partialmethod`: each access is a distinct `partial`, and the access peaks
  under 5 KB for 20 stored bindings and above 150 KB for 20,000; a callable
  instance without `__get__`, and a descriptor whose `__get__` returns
  itself, yield a bound method instead, each peaking under 5 KB with 20,000
  stored bindings.
* `update_wrapper`: names copied, `__wrapped__` set after the `__dict__`
  merge so a `__wrapped__` entry in the wrapped function's own `__dict__`
  does not survive, `__dict__` merged. A
  recording wrapped object is asked for exactly the 20,000 names in
  `assigned` when none resolves, and for exactly the 20,000 names in
  `updated` when every mapping is empty; the wrapper's peak is above 150 KB
  for a 20,000-entry `__dict__` against under 5 KB for ten; a custom
  `updated` mapping is copied and the default names are not.
* `reduce`: n-1 calls without `initial`, n with, `TypeError` on an empty
  fold, left-to-right order, the joined length of 5,000 one-character
  strings, and the bit length of n! more than doubling from n=1,000 to 4,000.
  Timing: concatenation of 20,000 and 80,000 characters against integer
  addition of the same counts, asserted above 8x and under 7x; `operator.mul`
  over 2,000 and 8,000 integers against `max`, the same thresholds. `initial`
  by keyword is asserted accepted on 3.14 and rejected before.
* `cmp_to_key`: wrapping an element calls the comparison zero times, one
  comparison of two wrapped elements calls it exactly once; ten elements
  produce more comparisons than elements, where `key=` runs exactly once per
  element (tests/test_stdlib_claims.py holds the 200-element
  version). `total_ordering` is counted at one call for `<`, `<=` and `>=`
  when `__lt__` settles them, two for `>` when it does not, and `ValueError`
  without a root.
* `singledispatch`: `_find_impl` is counted at one call for three dispatches
  of one class, at a second call after an unrelated `register()`, and the
  same through `singledispatchmethod`. The cache holds 200 entries for 200
  classes at k=1, is empty after those classes are collected, and is emptied
  by `register()` while they live; a foreign `ABCMeta.register()` of a new
  virtual subclass empties it on the next dispatch once an ABC is
  registered, and one of an existing subclass, or any before an ABC is
  registered, leaves it alone; an ABC registered only as a union member
  does not enable that invalidation, so a class it later recognises keeps
  dispatching to the cached default. `registry` is the same read-only view on
  every access and shows a later registration; a three-member union
  registers three entries on 3.11+; the annotation form registers through
  this file's string annotations. The s term is counted through a
  metaclass: a miss for a class one ABC recognises runs two subclass checks
  per direct subclass of that ABC, 2,000 for 1,000, once composing the MRO
  and once deciding whether `object` implements the ABC. Miss timing: 150 fresh
  classes against 20 and 4,000 unrelated registrations, asserted above 20x;
  100 and 400 pairwise unrelated ABCs registered against one class, the
  fastest of three fresh builds each, asserted above 16x, measured near 60x;
  a real inheritance chain of 100 and 400 registered classes, the fastest of
  three, asserted above 8x, measured near 40x; towers of 8 and 12 nested
  diamonds, whose MROs are 26 and 38 classes long, asserted above 8x where a
  cubic bound in L predicts about 3x, measured near 16x. Access through
  an instance peaks under 5 KB on 3.14 and above 150 KB before it with a
  20,000-entry function `__dict__`, and calling with no argument raises
  `TypeError`.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* Treating one argument's hashing and comparison as O(1) is a cost-model
  assumption; an argument whose `__hash__` scans its contents adds that cost
  to every hit and is not measured.
* O(P·L²) is an upper bound read from `_c3_mro` and `_c3_merge` in
  Lib/functools.py: the recursion linearises each base once per path to it,
  and each merge rescans every sequence for each rejected candidate. The
  measurements vary the virtual ABCs, the real MRO depth and the diamond
  depth one at a time, with the ABCs' own base chains held at zero; shapes
  mixing them are not measured, and the timing tests show only that each
  dimension grows super-linearly. The O(L²) transient space with repeated
  bases is read from the same recursion, which holds a sibling's
  linearisation at each level while the next one is computed; the diamond
  towers measured are too shallow for that term to show above the fixed
  allocation of a miss. The s term is counted, not timed, and each subclass
  check is treated as O(1). The MRO of a subclass that recognises the
  dispatched class is part of L on the page but not varied here: no
  subclass of a registered ABC recognises the dispatched class in any
  measurement, and the scan is a plain list walk with nothing to count.
* The lock removed from `cached_property` in 3.12 is asserted by the
  descriptor's attribute, not under thread contention.
* The annotation form of `register()` is asserted to resolve a string
  annotation; the cost of that resolution is not measured.
"""

from __future__ import annotations

import abc
import contextlib
import gc
import math
import operator
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import warnings
import weakref
from collections.abc import Callable, Iterator
from functools import (
    WRAPPER_ASSIGNMENTS,
    WRAPPER_UPDATES,
    cache,
    cached_property,
    cmp_to_key,
    lru_cache,
    partial,
    partialmethod,
    reduce,
    singledispatch,
    singledispatchmethod,
    total_ordering,
    update_wrapper,
    wraps,
)
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "functools.md"
EXPECTED_BLOCKS = 15

SMALL = 20
LARGE = 20_000


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


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def retained_bytes(func: Callable[[], Any]) -> int:
    """Traced allocation still live after func returns."""
    tracemalloc.start()
    try:
        before = tracemalloc.get_traced_memory()[0]
        func()
        return tracemalloc.get_traced_memory()[0] - before
    finally:
        tracemalloc.stop()


def counting_key_class() -> tuple[type, dict[str, int]]:
    """A hashable class that counts its own __hash__ and __eq__ calls."""
    counts = {"hash": 0, "eq": 0}

    class Key:
        def __init__(self, payload: object) -> None:
            self.payload = payload

        def __hash__(self) -> int:
            counts["hash"] += 1
            return hash(self.payload)

        def __eq__(self, other: object) -> bool:
            counts["eq"] += 1
            return isinstance(other, Key) and self.payload == other.payload

    return Key, counts


def sink(*args: object, **keywords: object) -> None:
    return None


def add(a: int, b: int) -> int:
    return a + b


def bindings(size: int, kind: str) -> tuple[tuple, dict]:
    """`size` bindings of one kind, as (args, keywords) to splat."""
    if kind == "positional":
        return tuple(range(size)), {}
    return (), {f"k{index}": index for index in range(size)}


def function_with_dict_entries(entries: int) -> Callable[..., Any]:
    def func(*args: object) -> int:
        return 1

    for index in range(entries):
        setattr(func, f"attr{index}", index)
    return func


class TestLruCacheKeys:
    """Calling a cached function, hit | O(a + m) | O(a + m); miss | O(a + m + f).

    The key is built from every argument and hashed before the lookup, which
    a counting `__hash__` shows directly; a counting call shows each distinct
    key computed once.
    """

    def test_each_distinct_argument_is_computed_once(self) -> None:
        calls = {"n": 0}

        @lru_cache(maxsize=None)  # noqa: UP033 - the spelling on the page
        def fib(n: int) -> int:
            calls["n"] += 1
            if n < 2:
                return n
            return fib(n - 1) + fib(n - 2)

        assert fib(30) == 832040
        assert calls["n"] == 31, "one call per distinct n from 0 to 30"
        assert fib.cache_info().hits == 28

    def test_without_the_cache_the_same_value_is_recomputed(self) -> None:
        calls = {"n": 0}

        def fib(n: int) -> int:
            calls["n"] += 1
            if n < 2:
                return n
            return fib(n - 1) + fib(n - 2)

        fib(20)
        assert calls["n"] > 2**10, "no memoization means exponential re-computation"

    def test_a_hit_hashes_and_compares_a_fresh_equal_key(self) -> None:
        Key, counts = counting_key_class()

        @lru_cache(maxsize=128)
        def identity(key: object) -> int:
            return 1

        identity(Key((1, 2, 3)))
        counts.update(hash=0, eq=0)

        identity(Key((1, 2, 3)))
        identity(Key((1, 2, 3)))

        assert identity.cache_info().hits == 2
        assert counts["hash"] == 2, "each fresh key was hashed"
        assert counts["eq"] == 2, "each hit confirmed the key with __eq__"

    def test_a_hit_hashes_every_positional_argument(self) -> None:
        Key, counts = counting_key_class()

        @lru_cache(maxsize=128)
        def variadic(*args: object) -> int:
            return 1

        variadic(*(Key(value) for value in range(5_000)))
        counts["hash"] = 0

        variadic(*(Key(value) for value in range(5_000)))

        assert variadic.cache_info().hits == 1
        assert counts["hash"] == 5_000, "the fresh call key hashed every argument"

    def test_a_hit_hashes_every_keyword_value(self) -> None:
        Key, counts = counting_key_class()

        @lru_cache(maxsize=128)
        def variadic(**kwargs: object) -> int:
            return 1

        variadic(**{f"k{index}": Key(index) for index in range(2_000)})
        counts["hash"] = 0

        variadic(**{f"k{index}": Key(index) for index in range(2_000)})

        assert variadic.cache_info().hits == 1
        assert counts["hash"] == 2_000, "the fresh call key hashed every keyword value"

    def test_a_miss_retains_a_key_holding_every_argument(self) -> None:
        @lru_cache(maxsize=None)  # noqa: UP033 - the spelling on the page
        def variadic(*args: object) -> int:
            return 1

        small = retained_bytes(lambda: variadic(*range(5)))
        large = retained_bytes(lambda: variadic(*range(50_000)))

        assert variadic.cache_info().misses == 2
        assert small < 5_000, f"a five-argument entry retained {small} bytes"
        assert large > 50_000 * 8, f"a 50,000-argument entry retained only {large} bytes"

    def test_keyword_order_is_part_of_the_key(self) -> None:
        @lru_cache(maxsize=None)  # noqa: UP033 - the spelling on the page
        def combine(**kwargs: int) -> int:
            return len(kwargs)

        combine(a=1, b=2)
        combine(b=2, a=1)

        assert combine.cache_info() == (0, 2, None, 2)

    def test_typed_keeps_equal_values_of_different_types_apart(self) -> None:
        @lru_cache(typed=True)
        def typed(x: float, y: float) -> float:
            return (x + y) / 2

        assert typed(4, 0) == typed(4.0, 0) == 2.0
        assert typed.cache_info() == (0, 2, 128, 2), "typed=True keys 4 and 4.0 apart"

        @lru_cache(typed=False)
        def untyped(x: float, y: float) -> float:
            return (x + y) / 2

        assert untyped(4, 0) == untyped(4.0, 0) == 2.0
        assert untyped.cache_info() == (1, 1, 128, 1), "equal keys share an entry untyped"

    def test_an_unhashable_argument_raises_before_the_function_runs(self) -> None:
        calls = {"n": 0}

        @lru_cache(maxsize=128)
        def measure(value: object) -> int:
            calls["n"] += 1
            return 1

        with pytest.raises(TypeError, match="unhashable"):
            measure([1, 2])  # type: ignore[arg-type]

        assert calls["n"] == 0

    @pytest.mark.timing
    def test_a_cache_hit_is_much_faster_than_a_fresh_miss(self) -> None:
        """The f term: a miss pays the function, a hit only the key."""

        @lru_cache(maxsize=256)
        def expensive(x: int) -> int:
            return sum(range(x))

        miss_ns = best_ns(lambda: expensive(2_000_000), repeats=1)
        hit_ns = best_ns(lambda: expensive(2_000_000))

        assert expensive.cache_info().misses == 1
        assert hit_ns * 20 < miss_ns, (
            f"a hit should be far cheaper than recomputation: miss={miss_ns:.0f}ns hit={hit_ns:.0f}ns"
        )


class TestLruCacheMaxsizeModes:
    """`lru_cache(maxsize)` | O(min(n, maxsize)); `maxsize=None` O(n); `maxsize=0` nothing.

    Each mode is asserted by `currsize` and by which keys miss again, which
    separates LRU eviction from insertion-order eviction and from no eviction.
    """

    def test_a_positive_maxsize_bounds_currsize(self) -> None:
        @lru_cache(maxsize=10)
        def identity(n: int) -> int:
            return n

        for n in range(100):
            identity(n)

        assert identity.cache_info().currsize == 10

    def test_eviction_drops_the_least_recently_used_entry(self) -> None:
        @lru_cache(maxsize=2)
        def identity(n: int) -> int:
            return n

        identity(1)
        identity(2)
        identity(1)  # 1 is now the most recently used
        identity(3)  # evicts 2

        assert identity.cache_info().currsize == 2
        identity(1)
        assert identity.cache_info().misses == 3, "1 was kept"
        identity(2)
        assert identity.cache_info().misses == 4, "2 was evicted"

    def test_maxsize_none_holds_every_key_and_evicts_nothing(self) -> None:
        @lru_cache(maxsize=None)  # noqa: UP033 - the spelling on the page
        def identity(n: int) -> int:
            return n

        for n in range(500):
            identity(n)

        info = identity.cache_info()
        assert info.maxsize is None
        assert info.currsize == 500

        identity(0)  # inserted first and untouched since: the victim if there were one
        assert identity.cache_info().hits == 1

    def test_cache_is_lru_cache_with_maxsize_none(self) -> None:
        @cache
        def by_decorator(n: int) -> int:
            return n

        @lru_cache(maxsize=None)  # noqa: UP033 - the spelling on the page
        def by_argument(n: int) -> int:
            return n

        for n in range(300):
            by_decorator(n)
            by_argument(n)

        assert by_decorator.cache_info().maxsize is None
        assert by_decorator.cache_info() == by_argument.cache_info() == (0, 300, None, 300)

    def test_maxsize_zero_stores_nothing_and_builds_no_key(self) -> None:
        Key, counts = counting_key_class()

        @lru_cache(maxsize=0)
        def identity(key: object) -> int:
            return 1

        key = Key((1, 2, 3))
        identity(key)
        identity(key)

        assert identity.cache_info() == (0, 2, 0, 0)
        assert counts["hash"] == 0, "a disabled cache does not build a key"
        assert identity([1, 2]) == 1, "so an unhashable argument is simply passed through"  # type: ignore[arg-type]


class TestLruCacheWrapperAttributes:
    """`cache_info()` | O(1); `cache_clear()` | O(n); `cache_parameters()` |
    O(1); `__wrapped__` | O(1)."""

    def test_cache_info_counts_hits_misses_and_entries(self) -> None:
        @lru_cache(maxsize=128)
        def square(n: int) -> int:
            return n * n

        square(5)
        square(5)
        square(6)
        square(5)

        assert square.cache_info() == (2, 2, 128, 2)
        assert square.cache_info() is not square.cache_info(), "a fresh tuple each call"

    def test_cache_clear_drops_entries_and_zeroes_the_counters(self) -> None:
        @lru_cache(maxsize=128)
        def square(n: int) -> int:
            return n * n

        square(1)
        square(1)
        square.cache_clear()

        assert square.cache_info() == (0, 0, 128, 0)
        square(1)
        assert square.cache_info().misses == 1, "the entry was really dropped"

    @pytest.mark.timing
    def test_cache_clear_cost_tracks_the_entries_held(self) -> None:
        def clear_ns(entries: int, repeats: int = 5) -> float:
            best = float("inf")
            for _ in range(repeats):

                @lru_cache(maxsize=None)  # noqa: UP033 - the spelling on the page
                def identity(n: int) -> int:
                    return n

                for n in range(entries):
                    identity(n)
                start = time.perf_counter_ns()
                identity.cache_clear()
                best = min(best, time.perf_counter_ns() - start)
                assert identity.cache_info().currsize == 0
            return best

        small_ns = clear_ns(10)
        large_ns = clear_ns(100_000)

        assert large_ns > small_ns * 100, (
            f"10,000x the entries cleared in x{large_ns / small_ns:.1f} "
            f"({small_ns:.0f}ns to {large_ns:.0f}ns); a constant-time clear would give x1"
        )

    def test_cache_parameters_reports_the_decorator_arguments(self) -> None:
        @lru_cache(maxsize=32, typed=True)
        def identity(n: int) -> int:
            return n

        assert identity.cache_parameters() == {"maxsize": 32, "typed": True}
        assert identity.cache_parameters() is not identity.cache_parameters()

        @cache
        def unbounded(n: int) -> int:
            return n

        assert unbounded.cache_parameters() == {"maxsize": None, "typed": False}

    def test_applying_the_decorator_copies_the_function_metadata(self) -> None:
        bare = function_with_dict_entries(0)
        heavy = function_with_dict_entries(LARGE)

        small = peak_bytes(lambda: cache(bare))
        large = peak_bytes(lambda: cache(heavy))

        assert small < 5_000, f"caching a bare function peaked at {small} bytes"
        assert large > 150_000, f"caching a {LARGE:,}-entry __dict__ peaked at only {large} bytes"
        assert cache(heavy).attr0 == 0  # type: ignore[attr-defined]

    def test_wrapped_is_the_undecorated_function(self) -> None:
        def cube(n: int) -> int:
            return n**3

        cached = lru_cache(maxsize=128)(cube)

        assert cached.__wrapped__ is cube
        assert cached.__wrapped__(3) == 27
        assert cached.cache_info().misses == 0, "calling __wrapped__ bypasses the cache"


class TestCachedMethodsHoldTheInstance:
    """Caching Methods: `self` is part of every key, so the cache keeps the
    instance alive until its entries go."""

    def test_the_instance_survives_until_cache_clear(self) -> None:
        class Report:
            @lru_cache(maxsize=None)  # noqa: UP033, B019 - the leak is the claim
            def total(self) -> int:
                return 42

        report = Report()
        ref = weakref.ref(report)
        assert report.total() == 42
        del report
        gc.collect()

        assert ref() is not None, "the cache entry's key holds the instance"

        Report.total.cache_clear()
        gc.collect()

        assert ref() is None


class TestCachedProperty:
    """`cached_property` | O(f) once, then O(1): the value is an instance
    attribute, so the instance needs a `__dict__`."""

    def test_computed_once_per_instance(self) -> None:
        calls = {"n": 0}

        class Widget:
            @cached_property
            def expensive(self) -> int:
                calls["n"] += 1
                return 42

        widget = Widget()
        assert widget.expensive == 42
        assert widget.expensive == 42
        assert calls["n"] == 1

    def test_each_instance_gets_its_own_value(self) -> None:
        class Widget:
            def __init__(self, base: int) -> None:
                self.base = base

            @cached_property
            def doubled(self) -> int:
                return self.base * 2

        assert (Widget(1).doubled, Widget(5).doubled) == (2, 10)

    def test_the_value_lives_in_the_instance_dict_and_del_recomputes(self) -> None:
        calls = {"n": 0}

        class Widget:
            @cached_property
            def value(self) -> int:
                calls["n"] += 1
                return 7

        widget = Widget()
        assert "value" not in widget.__dict__
        assert widget.value == 7
        assert widget.__dict__["value"] == 7

        del widget.value
        assert widget.value == 7
        assert calls["n"] == 2

    def test_an_instance_without_a_dict_raises(self) -> None:
        class Slotted:
            __slots__ = ("base",)

            @cached_property
            def value(self) -> int:
                return 7

        with pytest.raises(TypeError, match="__dict__"):
            _ = Slotted().value

    @pytest.mark.skipif(sys.version_info >= (3, 12), reason="the lock was removed in 3.12")
    def test_before_312_the_descriptor_holds_a_lock(self) -> None:
        class Widget:
            @cached_property
            def value(self) -> int:
                return 7

        assert hasattr(Widget.__dict__["value"], "lock")

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="the lock was removed in 3.12")
    def test_from_312_the_descriptor_holds_no_lock(self) -> None:
        class Widget:
            @cached_property
            def value(self) -> int:
                return 7

        assert not hasattr(Widget.__dict__["value"], "lock")


class TestPartial:
    """`partial(func, /, *args, **keywords)` | O(p + q); its attributes O(1);
    calling it O(p + q + a + m + f).

    Storage is settled by traced allocation across 20 and 20,000 bindings of
    each kind, the attributes by identity, and the per-call join by timing.
    """

    def test_construction_only_stores_arguments(self) -> None:
        calls = {"n": 0}

        def multiply(x: int, y: int) -> int:
            calls["n"] += 1
            return x * y

        times_3 = partial(multiply, 3)
        assert calls["n"] == 0
        assert times_3(5) == 15
        assert calls["n"] == 1

    def test_the_attributes_are_the_stored_objects(self) -> None:
        bound = partial(sink, 1, 2, x=3)

        assert bound.func is sink
        assert bound.args is bound.args
        assert bound.args == (1, 2)
        assert bound.keywords is bound.keywords
        assert bound.keywords == {"x": 3}

    def test_mutating_keywords_reaches_the_next_call(self) -> None:
        def power(base: int, exponent: int) -> int:
            return base**exponent

        square = partial(power, exponent=2)
        assert square(3) == 9

        square.keywords["exponent"] = 3
        assert square(3) == 27

    def test_wrapping_a_partial_merges_the_bindings(self) -> None:
        inner = partial(sink, "a", first=1)
        outer = partial(inner, "b", second=2)

        assert outer.func is sink
        assert outer.args == ("a", "b")
        assert outer.keywords == {"first": 1, "second": 2}

    def test_an_inner_partial_with_attributes_is_wrapped_not_merged(self) -> None:
        inner = partial(sink, "a")
        inner.tag = "kept"  # type: ignore[attr-defined]
        outer = partial(inner, "b")

        assert outer.func is inner
        assert outer.args == ("b",)

    def test_an_inner_partial_whose_dict_was_created_is_wrapped_too(self) -> None:
        inner = partial(sink, "a")
        assert vars(inner) == {}, "reading __dict__ creates it without adding anything"
        outer = partial(inner, "b")

        assert outer.func is inner
        assert outer.args == ("b",)

        untouched = partial(sink, "a")
        assert partial(untouched, "b").func is sink

    @pytest.mark.parametrize("kind", ["positional", "keyword"])
    def test_construction_allocates_for_every_binding(self, kind: str) -> None:
        small_args, small_keywords = bindings(SMALL, kind)
        large_args, large_keywords = bindings(LARGE, kind)
        kept: list[partial] = []

        small = retained_bytes(lambda: kept.append(partial(sink, *small_args, **small_keywords)))
        large = retained_bytes(lambda: kept.append(partial(sink, *large_args, **large_keywords)))

        assert small < 5_000, f"{SMALL} {kind} bindings retained {small} bytes"
        assert large > 150_000, f"{LARGE:,} {kind} bindings retained only {large} bytes"
        assert len(kept[1].args) + len(kept[1].keywords) == LARGE

    def test_merging_allocates_for_both_sets(self) -> None:
        large_args, _ = bindings(LARGE, "positional")
        base = partial(sink, *large_args)
        kept: list[partial] = []

        merged = retained_bytes(lambda: kept.append(partial(base, *large_args)))

        assert merged > 300_000, f"merging two {LARGE:,}-binding sets retained {merged} bytes"
        assert len(kept[0].args) == 2 * LARGE

    @pytest.mark.timing
    @pytest.mark.parametrize("kind", ["positional", "keyword"])
    def test_each_call_joins_the_stored_bindings(self, kind: str) -> None:
        small_args, small_keywords = bindings(SMALL, kind)
        large_args, large_keywords = bindings(LARGE, kind)
        small = partial(sink, *small_args, **small_keywords)
        large = partial(sink, *large_args, **large_keywords)

        small_ns = best_ns(small, inner=100)
        large_ns = best_ns(large, inner=100)

        assert large_ns > small_ns * 50, (
            f"1,000x the stored {kind} bindings cost x{large_ns / small_ns:.1f} per call "
            f"({small_ns:.0f}ns to {large_ns:.0f}ns); a bound without p and q would give x1"
        )


class TestPlaceholder:
    """`functools.Placeholder` | O(1): a stored binding that a call's positional
    arguments fill left to right."""

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="Placeholder was added in 3.14")
    def test_call_arguments_fill_placeholders_left_to_right(self) -> None:
        import functools

        Placeholder: Any = functools.Placeholder  # type: ignore[attr-defined]

        def divide(numerator: float, denominator: float) -> float:
            return numerator / denominator

        halve: Any = partial(divide, Placeholder, 2)

        assert halve.args == (Placeholder, 2)
        assert halve(10) == 5.0

        def record(*args: object) -> tuple:
            return args

        bound: Any = partial(record, Placeholder, "b", Placeholder, "d")
        assert bound.args == (Placeholder, "b", Placeholder, "d")
        assert bound("a", "c", "e") == ("a", "b", "c", "d", "e")

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="Placeholder was added in 3.14")
    def test_a_call_supplying_fewer_arguments_than_placeholders_raises(self) -> None:
        import functools

        Placeholder: Any = functools.Placeholder  # type: ignore[attr-defined]
        halve = partial(operator.truediv, Placeholder, 2)

        with pytest.raises(TypeError, match="missing positional arguments"):
            halve()

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="Placeholder was added in 3.14")
    def test_before_314_there_is_no_placeholder(self) -> None:
        import functools

        assert not hasattr(functools, "Placeholder")


class TestPartialAsClassAttribute:
    """Version Notes: a class-attribute `partial` warns on 3.13 and binds
    the instance from 3.14."""

    @staticmethod
    def _holder() -> type:
        def record(*args: object) -> tuple:
            return args

        class Holder:
            method = partial(record, 1)

        return Holder

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="partial binds from 3.14")
    def test_from_314_the_instance_is_passed_first(self) -> None:
        holder = self._holder()()

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert holder.method(2) == (1, holder, 2)

    @pytest.mark.skipif(sys.version_info[:2] != (3, 13), reason="the warning is 3.13's")
    def test_on_313_reading_it_warns(self) -> None:
        holder = self._holder()()

        with pytest.warns(FutureWarning, match="method descriptor"):
            method = holder.method

        assert method(2) == (1, 2)

    @pytest.mark.skipif(sys.version_info >= (3, 13), reason="a plain attribute before 3.13")
    def test_before_313_it_is_a_plain_attribute(self) -> None:
        holder = self._holder()()

        with warnings.catch_warnings():
            warnings.simplefilter("error")
            assert holder.method(2) == (1, 2)


class TestPartialmethod:
    """`partialmethod(func, /, *args, **keywords)` | O(p + q), and each access
    through an instance builds a new `partial`, O(p + q) again."""

    def test_binds_as_an_instance_method(self) -> None:
        class Formatter:
            def render(self, value: object, width: int) -> str:
                return f"{value:>{width}}"

            right = partialmethod(render, width=6)

        assert Formatter().right(42) == "    42"

    def test_flattening_merges_both_tuples_and_both_dicts(self) -> None:
        inner = partialmethod(sink, "a", first=1)
        outer = partialmethod(inner, "b", second=2)

        assert outer.func is sink
        assert outer.args == ("a", "b")
        assert outer.keywords == {"first": 1, "second": 2}

    def test_each_access_is_a_fresh_partial(self) -> None:
        class Cell:
            def set_state(self, state: str) -> str:
                return state

            turn_on = partialmethod(set_state, "on")

        cell = Cell()
        first = cell.turn_on
        second = cell.turn_on

        assert isinstance(first, partial)
        assert first is not second
        assert first() == "on"

    def test_a_callable_without_get_becomes_a_bound_method_instead(self) -> None:
        class Callable:
            def __call__(self, owner: object, *args: object) -> tuple:
                return (owner, *args)

        class Cell:
            render = partialmethod(Callable(), *range(LARGE))

        cell = Cell()

        peak = peak_bytes(lambda: cell.render)

        assert not isinstance(cell.render, partial)
        assert peak < 5_000, f"reading the method peaked at {peak} bytes"
        assert cell.render()[:3] == (cell, 0, 1)

    def test_a_descriptor_returning_itself_takes_the_same_path(self) -> None:
        class SelfReturning:
            def __get__(self, obj: object, owner: type | None = None) -> SelfReturning:
                return self

            def __call__(self, owner: object, *args: object) -> tuple:
                return (owner, *args)

        class Cell:
            render = partialmethod(SelfReturning(), *range(LARGE))

        cell = Cell()

        peak = peak_bytes(lambda: cell.render)

        assert not isinstance(cell.render, partial)
        assert peak < 5_000, f"reading the method peaked at {peak} bytes"
        assert cell.render()[:3] == (cell, 0, 1)

    def test_access_allocates_for_every_stored_binding(self) -> None:
        class Cell:
            def render(self, *args: object) -> None:
                return None

            small = partialmethod(render, *range(SMALL))
            large = partialmethod(render, *range(LARGE))

        cell = Cell()

        small = peak_bytes(lambda: cell.small)
        large = peak_bytes(lambda: cell.large)

        assert small < 5_000, f"reading a {SMALL}-binding partialmethod peaked at {small} bytes"
        assert large > 150_000, (
            f"reading a {LARGE:,}-binding partialmethod peaked at only {large} bytes"
        )


class TestUpdateWrapperAndWraps:
    """`update_wrapper(wrapper, wrapped, assigned, updated)` | O(w + u).

    w is counted through a wrapped object that records every name asked of
    it; u is settled by the wrapper's traced allocation as `__dict__` grows.
    """

    def test_wraps_copies_identity_metadata_and_the_dict(self) -> None:
        def original(x: int) -> int:
            """Docstring for original."""
            return x

        original.registered = True  # type: ignore[attr-defined]

        @wraps(original)
        def wrapper(x: int) -> int:
            return original(x)

        assert wrapper.__name__ == "original"
        assert wrapper.__doc__ == "Docstring for original."
        assert wrapper.registered is True  # type: ignore[attr-defined]
        assert wrapper.__wrapped__ is original

    def test_wrapped_is_set_after_the_dict_is_copied(self) -> None:
        def innermost() -> None:
            pass

        def original() -> None:
            pass

        original.__wrapped__ = innermost  # type: ignore[attr-defined]

        def wrapper() -> None:
            pass

        update_wrapper(wrapper, original)

        assert wrapper.__wrapped__ is original, "the copied __dict__ entry did not win"  # type: ignore[attr-defined]

    def test_update_wrapper_returns_the_wrapper(self) -> None:
        def original() -> None:
            pass

        def wrapper() -> None:
            pass

        assert update_wrapper(wrapper, original) is wrapper
        assert wrapper.__name__ == "original"

    def test_the_default_name_tuples(self) -> None:
        assert "__name__" in WRAPPER_ASSIGNMENTS
        assert "__doc__" in WRAPPER_ASSIGNMENTS
        assert WRAPPER_UPDATES == ("__dict__",)

    def test_every_assigned_name_is_looked_up_even_when_none_resolves(self) -> None:
        asked: list[str] = []

        class Recorder:
            def __getattr__(self, name: str) -> object:
                asked.append(name)
                raise AttributeError(name)

        names = [f"missing{index}" for index in range(LARGE)]
        wrapped: Any = Recorder()

        update_wrapper(lambda: None, wrapped, assigned=names, updated=())

        assert asked == names

    def test_every_updated_name_is_visited_even_when_its_mapping_is_empty(self) -> None:
        asked: list[str] = []

        class Recorder:
            def __getattr__(self, name: str) -> dict:
                asked.append(name)
                return {}

        class Target:
            def __getattr__(self, name: str) -> dict:
                return {}

        names = [f"empty{index}" for index in range(LARGE)]
        wrapped: Any = Recorder()
        wrapper: Any = Target()

        update_wrapper(wrapper, wrapped, assigned=(), updated=names)

        assert asked == names

    def test_the_wrapped_dict_is_copied_entry_by_entry(self) -> None:
        few = function_with_dict_entries(10)
        many = function_with_dict_entries(LARGE)

        small = peak_bytes(lambda: update_wrapper(lambda: None, few))
        large = peak_bytes(lambda: update_wrapper(lambda: None, many))

        assert small < 5_000, f"wrapping a 10-entry __dict__ peaked at {small} bytes"
        assert large > 150_000, f"wrapping a {LARGE:,}-entry __dict__ peaked at only {large} bytes"

    def test_custom_assigned_and_updated_replace_the_defaults(self) -> None:
        def wrapped() -> None:
            """A docstring the defaults would have copied."""

        wrapped.picked = "yes"  # type: ignore[attr-defined]
        wrapped.registry = {"a": 1}  # type: ignore[attr-defined]

        def wrapper() -> None:
            pass

        wrapper.registry = {}  # type: ignore[attr-defined]

        update_wrapper(wrapper, wrapped, assigned=("picked",), updated=("registry",))

        assert wrapper.picked == "yes"  # type: ignore[attr-defined]
        assert wrapper.registry == {"a": 1}  # type: ignore[attr-defined]
        assert wrapper.__doc__ is None, "the default names were not copied"
        assert wrapper.__name__ == "wrapper"


class TestReduce:
    """`reduce(function, iterable[, initial])` | O(n·f) | O(1) auxiliary plus
    the accumulator.

    The call count is exact. The accumulator's growth is shown exactly by
    length and bit length, and its effect on time by folding the same counts
    with a copying callback and a constant one.
    """

    def test_matches_the_documented_examples(self) -> None:
        data = [1, 2, 3, 4, 5]
        assert reduce(operator.add, data) == 15
        assert reduce(operator.mul, data) == 120
        assert reduce(max, data) == 5

    def test_applies_the_function_left_to_right(self) -> None:
        assert reduce(lambda a, b: f"({a}-{b})", ["1", "2", "3"]) == "((1-2)-3)"

    def test_calls_the_function_n_minus_one_times_without_an_initial_value(self) -> None:
        calls = {"n": 0}

        def combine(a: int, b: int) -> int:
            calls["n"] += 1
            return a + b

        reduce(combine, range(10))
        assert calls["n"] == 9

    def test_calls_the_function_n_times_with_an_initial_value(self) -> None:
        calls = {"n": 0}

        def combine(a: int, b: int) -> int:
            calls["n"] += 1
            return a + b

        reduce(combine, range(10), 0)
        assert calls["n"] == 10

    def test_an_empty_fold_needs_an_initial_value(self) -> None:
        empty: list[int] = []
        with pytest.raises(TypeError, match="empty"):
            reduce(add, empty)

        assert reduce(add, empty, 99) == 99

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="initial by keyword is 3.14+")
    def test_from_314_initial_is_accepted_by_keyword(self) -> None:
        empty: list[int] = []
        assert reduce(add, empty, initial=7) == 7  # type: ignore[call-arg]

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="initial by keyword is 3.14+")
    def test_before_314_initial_is_positional_only(self) -> None:
        empty: list[int] = []
        with pytest.raises(TypeError):
            reduce(add, empty, initial=7)  # type: ignore[call-arg]

    def test_the_accumulator_is_whatever_the_function_returns(self) -> None:
        joined = reduce(operator.add, ["x"] * 5_000)

        assert len(joined) == 5_000

    def test_an_integer_accumulator_widens_faster_than_the_input_grows(self) -> None:
        widths = [math.prod(range(1, size + 1)).bit_length() for size in (1_000, 2_000, 4_000)]

        assert widths[1] > widths[0] * 2, f"n! outgrows a doubling of n: {widths}"
        assert widths[2] > widths[1] * 2, f"and keeps doing so: {widths}"

    @pytest.mark.timing
    def test_a_copying_callback_makes_the_fold_superlinear(self) -> None:
        """Same `reduce`, same n, same call count; only the callback differs.

        Integer addition stays inside one machine word across these sizes and
        is the constant-cost control. Thresholds come from the spread over
        ten trials at five repeats: the control lands in 4.0-4.2 for a 4x
        step and concatenation in 14-17.
        """
        small, large = 20_000, 80_000
        small_chars, large_chars = ["x"] * small, ["x"] * large
        small_ints, large_ints = [1] * small, [1] * large

        concat_growth = best_ns(lambda: reduce(operator.add, large_chars), repeats=5) / best_ns(
            lambda: reduce(operator.add, small_chars), repeats=5
        )
        addition_growth = best_ns(lambda: reduce(operator.add, large_ints), repeats=5) / best_ns(
            lambda: reduce(operator.add, small_ints), repeats=5
        )

        assert addition_growth < 7, f"a constant-cost callback tracks 4x: {addition_growth:.1f}x"
        assert concat_growth > 8, (
            f"a callback that copies the accumulator should cost far more than 4x: "
            f"{concat_growth:.1f}x against addition's {addition_growth:.1f}x"
        )

    @pytest.mark.timing
    def test_a_widening_integer_accumulator_makes_the_fold_superlinear(self) -> None:
        """The same numbers folded two ways: `max` keeps the accumulator to one
        of the inputs, `mul` lets it widen. Thresholds from ten trials at five
        repeats: the control lands in 3.6-4.5 and the product in 18-26.
        """
        small, large = 2_000, 8_000
        small_data, large_data = list(range(1, small + 1)), list(range(1, large + 1))

        product_growth = best_ns(lambda: reduce(operator.mul, large_data), repeats=5) / best_ns(
            lambda: reduce(operator.mul, small_data), repeats=5
        )
        max_growth = best_ns(lambda: reduce(max, large_data), repeats=5) / best_ns(
            lambda: reduce(max, small_data), repeats=5
        )

        assert max_growth < 7, f"an accumulator that cannot grow tracks 4x: {max_growth:.1f}x"
        assert product_growth > 8, (
            f"a widening integer accumulator should cost far more than 4x: "
            f"product {product_growth:.1f}x vs max {max_growth:.1f}x"
        )


class TestCmpToKeyAndTotalOrdering:
    """`cmp_to_key(func)` | O(1) to wrap, then one call of func per
    comparison; `total_ordering(cls)` | O(1), with derived comparisons
    calling up to two methods."""

    def test_wrapping_an_element_calls_nothing(self) -> None:
        calls = {"n": 0}

        def compare(left: int, right: int) -> int:
            calls["n"] += 1
            return (left > right) - (left < right)

        key = cmp_to_key(compare)
        wrapped = [key(value) for value in range(100)]

        assert len(wrapped) == 100
        assert calls["n"] == 0

        assert wrapped[0] < wrapped[1]
        assert calls["n"] == 1, "one comparison of wrapped elements is one call of func"
        assert not wrapped[1] < wrapped[0]
        assert calls["n"] == 2

    def test_compare_runs_per_comparison_where_key_runs_per_element(self) -> None:
        comparisons: list[tuple[int, int]] = []
        key_calls: list[int] = []

        def compare(left: int, right: int) -> int:
            comparisons.append((left, right))
            return (left > right) - (left < right)

        def key(value: int) -> int:
            key_calls.append(value)
            return value

        data = [5, 3, 8, 1, 9, 2, 7, 4, 6, 0]

        assert sorted(data, key=cmp_to_key(compare)) == list(range(10))
        assert sorted(data, key=key) == list(range(10))
        assert len(comparisons) > len(data)
        assert len(key_calls) == len(data)

    @staticmethod
    def _counted_class() -> tuple[type, list[str]]:
        calls: list[str] = []

        @total_ordering
        class Version:
            def __init__(self, number: int) -> None:
                self.number = number

            def __eq__(self, other: object) -> bool:
                calls.append("eq")
                return isinstance(other, Version) and self.number == other.number

            def __lt__(self, other: Version) -> bool:
                calls.append("lt")
                return self.number < other.number

        return Version, calls

    def test_fills_in_the_three_missing_methods(self) -> None:
        Version, _ = self._counted_class()

        assert all(name in Version.__dict__ for name in ("__le__", "__gt__", "__ge__"))
        assert Version(1) < Version(2)
        assert Version(1) <= Version(2)
        assert Version(2) > Version(1)
        assert Version(2) >= Version(1)
        assert not Version(2) < Version(1)

    def test_a_derived_comparison_calls_up_to_two_methods(self) -> None:
        Version, calls = self._counted_class()

        assert Version(1) < Version(2)
        assert calls == ["lt"]

        calls.clear()
        assert Version(2) > Version(1)
        assert calls == ["lt", "eq"], "not __lt__, then __ne__"

        calls.clear()
        assert not Version(1) > Version(2)
        assert calls == ["lt"], "__lt__ true settles > on its own"

        calls.clear()
        assert Version(1) <= Version(2)
        assert calls == ["lt"]

        calls.clear()
        assert Version(1) >= Version(1)
        assert calls == ["lt"], "__ge__ is not __lt__"

    def test_raises_without_any_ordering_method(self) -> None:
        with pytest.raises(ValueError, match="must define at least one ordering"):

            @total_ordering  # type: ignore[reportGeneralTypeIssues]
            class NoOrdering:
                def __eq__(self, other: object) -> bool:
                    return NotImplemented


@contextlib.contextmanager
def count_find_impl_calls() -> Iterator[dict[str, int]]:
    """Count cache misses: dispatch() looks `_find_impl` up in the module
    globals at call time, so patching the module attribute sees every miss."""
    import functools as functools_module

    calls = {"n": 0}
    real_find_impl = functools_module._find_impl  # type: ignore[attr-defined]

    def counting_find_impl(cls: type, registry: dict) -> object:
        calls["n"] += 1
        return real_find_impl(cls, registry)

    functools_module._find_impl = counting_find_impl  # type: ignore[attr-defined]
    try:
        yield calls
    finally:
        functools_module._find_impl = real_find_impl  # type: ignore[attr-defined]


def dispatch_cache(generic_func: Any) -> Any:
    """The `WeakKeyDictionary` a generic function's `dispatch` closes over."""
    dispatch = generic_func.dispatch
    index = dispatch.__code__.co_freevars.index("dispatch_cache")
    return dispatch.__closure__[index].cell_contents


class TestSingledispatchCache:
    """`singledispatch.dispatch(cls)` | O(1) avg hit, a miss otherwise |
    O(t); `register()` clears the t cached entries.

    Misses are counted through `_find_impl`, and the cache is read directly
    rather than inferred from retained memory, which would show the class
    objects themselves whether or not anything was cached.
    """

    def test_dispatch_picks_the_most_specific_registered_implementation(self) -> None:
        @singledispatch
        def process(arg: object) -> str:
            return f"Default: {arg}"

        @process.register(int)
        def _(arg: int) -> str:
            return f"Integer: {arg * 2}"

        @process.register(list)
        def _(arg: list) -> str:
            return f"List of {len(arg)} items"

        assert process("hello") == "Default: hello"
        assert process(5) == "Integer: 10"
        assert process(True) == "Integer: 2", "bool dispatches through its MRO to int"
        assert process([1, 2, 3]) == "List of 3 items"
        assert process.dispatch(bool) is process.dispatch(int)

    def test_a_call_without_a_positional_argument_raises(self) -> None:
        @singledispatch
        def process(arg: object) -> str:
            return "default"

        with pytest.raises(TypeError, match="at least 1 positional argument"):
            process()

        with pytest.raises(TypeError, match="at least 1 positional argument"):
            process(arg=1)

    def test_the_generic_function_carries_the_original_metadata(self) -> None:
        def process(arg: object) -> str:
            """Handle one value."""
            return "default"

        process.registered = True  # type: ignore[attr-defined]

        generic: Any = singledispatch(process)

        assert generic.__name__ == "process"
        assert generic.__doc__ == "Handle one value."
        assert generic.registered is True  # type: ignore[attr-defined]
        assert generic.__wrapped__ is process

    def test_repeated_dispatch_on_the_same_type_is_a_cache_hit(self) -> None:
        @singledispatch
        def process(arg: object) -> str:
            return "default"

        class Probe:
            pass

        with count_find_impl_calls() as calls:
            process.dispatch(Probe)
            process.dispatch(Probe)
            process.dispatch(Probe)

        assert calls["n"] == 1

    def test_an_exact_registration_never_misses(self) -> None:
        @singledispatch
        def process(arg: object) -> str:
            return "default"

        process.register(int, lambda arg: "int")

        with count_find_impl_calls() as calls:
            process.dispatch(int)

        assert calls["n"] == 0

    def test_register_clears_the_entire_dispatch_cache(self) -> None:
        @singledispatch
        def process(arg: object) -> str:
            return "default"

        class Unrelated:
            pass

        class AlsoUnrelated:
            pass

        with count_find_impl_calls() as calls:
            process.dispatch(Unrelated)
            process.dispatch(Unrelated)
            assert calls["n"] == 1

            process.register(AlsoUnrelated, lambda arg: "also unrelated")
            process.dispatch(Unrelated)

        assert calls["n"] == 2, "registering AlsoUnrelated cleared Unrelated's entry too"

    def test_the_cache_holds_one_entry_per_distinct_type_dispatched(self) -> None:
        @singledispatch
        def process(arg: object) -> str:
            return "default"

        cache = dispatch_cache(process)
        kept = [type(f"Probe{index}", (), {}) for index in range(200)]

        for probe in kept:
            process.dispatch(probe)

        assert len(cache) == 200, "one entry per distinct type, with k fixed at 1"

    def test_entries_are_pruned_once_their_type_is_garbage_collected(self) -> None:
        @singledispatch
        def process(arg: object) -> str:
            return "default"

        cache = dispatch_cache(process)

        for index in range(500):
            process.dispatch(type(f"Ephemeral{index}", (), {}))

        gc.collect()
        assert len(cache) == 0

    def test_register_clears_entries_for_types_that_are_still_alive(self) -> None:
        @singledispatch
        def process(arg: object) -> str:
            return "default"

        cache = dispatch_cache(process)
        kept = [type(f"Alive{index}", (), {}) for index in range(50)]
        for probe in kept:
            process.dispatch(probe)
        assert len(cache) == 50

        process.register(int, lambda arg: "int")

        assert len(cache) == 0
        assert len(kept) == 50

    def test_a_foreign_abc_registration_clears_the_cache_once_an_abc_is_registered(
        self,
    ) -> None:
        @singledispatch
        def process(arg: object) -> str:
            return "default"

        class Probe:
            pass

        class Foreign(abc.ABC):  # noqa: B024 - registration, not abstraction, is the point
            pass

        cache = dispatch_cache(process)
        process.dispatch(Probe)
        Foreign.register(type("Before", (), {}))
        process.dispatch(int)
        assert Probe in cache, "with no ABC registered, foreign registrations are ignored"

        class Registered(abc.ABC):  # noqa: B024 - registration, not abstraction, is the point
            pass

        process.register(Registered, lambda arg: "abc")
        process.dispatch(Probe)
        assert Probe in cache

        class AlreadyForeign(Foreign):
            pass

        Foreign.register(AlreadyForeign)
        process.dispatch(int)
        assert Probe in cache, "registering an existing subclass changes no token"

        Foreign.register(type("After", (), {}))
        assert Probe in cache, "invalidation is applied on the next dispatch"
        process.dispatch(int)

        assert Probe not in cache, "a new virtual subclass elsewhere invalidated the cache"

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="union registration is 3.11+")
    def test_an_abc_registered_through_a_union_enables_no_invalidation(self) -> None:
        class Interface(abc.ABC):  # noqa: B024 - registration, not abstraction, is the point
            pass

        @singledispatch
        def process(arg: object) -> str:
            return "default"

        process.register(Interface | int, lambda arg: "interface")  # type: ignore[arg-type]

        class Concrete:
            pass

        assert process(Concrete()) == "default"
        Interface.register(Concrete)

        assert process(Concrete()) == "default", "the stale entry survives the registration"
        process._clear_cache()  # type: ignore[attr-defined]
        assert process(Concrete()) == "interface"

    def test_a_miss_checks_every_direct_subclass_of_a_recognising_abc(self) -> None:
        """The s term: each direct subclass of an ABC that recognises the class
        is checked against it."""
        checks = {"n": 0}

        class Counting(abc.ABCMeta):
            def __subclasscheck__(cls, subclass: type) -> bool:
                checks["n"] += 1
                return super().__subclasscheck__(subclass)

        interface: Any = abc.ABCMeta("Interface", (), {})
        subclasses = [Counting(f"Sub{index}", (interface,), {}) for index in range(1_000)]

        @singledispatch
        def process(arg: object) -> str:
            return "default"

        process.register(interface, lambda arg: "interface")

        class Concrete:
            pass

        interface.register(Concrete)
        checks["n"] = 0

        assert process.dispatch(Concrete)(None) == "interface"
        assert checks["n"] == 2 * len(subclasses), (
            "each direct subclass is checked while composing the MRO and again while "
            "deciding whether object implements the ABC"
        )


class TestSingledispatchMiss:
    """`singledispatch.dispatch(cls)` miss | O(k + s + P·L²).

    k is varied with unrelated registrations against fresh classes; L with
    pairwise unrelated ABCs registered as virtual ancestors of one class,
    and separately with a real inheritance chain; P with nested diamonds,
    whose L grows linearly while the paths double per level. Each shape is
    timed alone.
    """

    @pytest.mark.timing
    def test_a_miss_checks_every_registration(self) -> None:
        def build_registry(size: int) -> Any:
            @singledispatch
            def process(arg: object) -> str:
                return "default"

            for index in range(size):
                process.register(type(f"Registered{index}", (), {}), lambda arg: "matched")
            return process

        def first_dispatch_ns(process: Any, count: int = 150, repeats: int = 3) -> float:
            best = float("inf")
            for trial in range(repeats):
                probes = [type(f"Probe{trial}_{i}", (), {}) for i in range(count)]
                start = time.perf_counter_ns()
                for probe in probes:
                    process.dispatch(probe)
                best = min(best, time.perf_counter_ns() - start)
            return best

        small_ns = first_dispatch_ns(build_registry(20))
        large_ns = first_dispatch_ns(build_registry(4_000))

        assert large_ns > small_ns * 20, (
            f"200x the registrations cost x{large_ns / small_ns:.1f} per first dispatch "
            f"({small_ns:.0f}ns to {large_ns:.0f}ns); a bound without k would give x1"
        )

    @staticmethod
    def _virtual_ancestors(count: int) -> tuple[Any, type]:
        """`count` pairwise unrelated ABCs, each registered as a virtual
        ancestor of one concrete class."""

        @singledispatch
        def process(arg: object) -> str:
            return "default"

        interfaces = []
        for index in range(count):
            interface = abc.ABCMeta(f"Interface{index}", (), {})
            process.register(interface, lambda arg: "matched")
            interfaces.append(interface)

        class Concrete:
            pass

        for interface in interfaces:
            interface.register(Concrete)

        return process, Concrete

    @pytest.mark.timing
    def test_quadrupling_the_virtual_ancestors_costs_more_than_quadratic(self) -> None:
        def dispatch_ns(count: int, repeats: int = 3) -> float:
            best = float("inf")
            for _ in range(repeats):
                process, concrete = self._virtual_ancestors(count)
                start = time.perf_counter_ns()
                with contextlib.suppress(RuntimeError):
                    # Ambiguous virtual ancestors raise, after the linearisation.
                    process.dispatch(concrete)
                best = min(best, time.perf_counter_ns() - start)
            return best

        small_ns = dispatch_ns(100)
        large_ns = dispatch_ns(400)

        assert large_ns > small_ns * 16, (
            f"4x the virtual ancestors cost x{large_ns / small_ns:.1f} "
            f"({small_ns:.0f}ns to {large_ns:.0f}ns); quadratic would give x16"
        )

    @staticmethod
    def _real_chain(depth: int) -> tuple[Any, type]:
        """`depth` registered classes in one inheritance chain, and a fresh
        subclass of the deepest to dispatch."""

        @singledispatch
        def process(arg: object) -> str:
            return "default"

        base: type = object
        for index in range(depth):
            base = type(f"Link{index}", (base,), {})
            process.register(base, lambda arg: "matched")

        return process, type("Leaf", (base,), {})

    @pytest.mark.timing
    def test_quadrupling_the_mro_costs_more_than_linear(self) -> None:
        def dispatch_ns(depth: int, repeats: int = 3) -> float:
            best = float("inf")
            for _ in range(repeats):
                process, leaf = self._real_chain(depth)
                start = time.perf_counter_ns()
                process.dispatch(leaf)
                best = min(best, time.perf_counter_ns() - start)
            return best

        small_ns = dispatch_ns(100)
        large_ns = dispatch_ns(400)

        assert large_ns > small_ns * 8, (
            f"4x the MRO cost x{large_ns / small_ns:.1f} "
            f"({small_ns:.0f}ns to {large_ns:.0f}ns); linear would give x4"
        )

    @staticmethod
    def _diamond_tower(depth: int) -> type:
        """`depth` nested diamonds: each level inherits the previous one
        twice, so the linearisation reaches it along twice as many paths."""
        current = type("Top", (), {})
        for index in range(depth):
            left = type(f"Left{index}", (current,), {})
            right = type(f"Right{index}", (current,), {})
            current = type(f"Diamond{index}", (left, right), {})
        return current

    @pytest.mark.timing
    def test_nested_diamonds_cost_more_than_the_mro_length_predicts(self) -> None:
        def dispatch_ns(depth: int, repeats: int = 3) -> float:
            best = float("inf")
            for _ in range(repeats):

                @singledispatch
                def process(arg: object) -> str:
                    return "default"

                leaf = self._diamond_tower(depth)
                start = time.perf_counter_ns()
                process.dispatch(leaf)
                best = min(best, time.perf_counter_ns() - start)
            return best

        shallow_ns = dispatch_ns(8)
        deep_ns = dispatch_ns(12)
        assert len(self._diamond_tower(8).__mro__) == 26
        assert len(self._diamond_tower(12).__mro__) == 38

        assert deep_ns > shallow_ns * 8, (
            f"four more diamonds cost x{deep_ns / shallow_ns:.1f} "
            f"({shallow_ns:.0f}ns to {deep_ns:.0f}ns); cubic in the MRO would give about x3"
        )


class TestSingledispatchRegistry:
    """`singledispatch.register(cls, func=None)` | O(t) and
    `singledispatch.registry` | O(1): a live read-only view."""

    def test_registry_is_the_same_live_view_on_every_access(self) -> None:
        @singledispatch
        def process(arg: object) -> str:
            return "default"

        view = process.registry
        assert view is process.registry
        assert set(view) == {object}

        process.register(int, lambda arg: "int")

        assert set(view) == {object, int}, "the view reflects a later registration"
        with pytest.raises(TypeError):
            view[str] = lambda arg: "str"  # type: ignore[index]

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="union registration is 3.11+")
    def test_a_union_registers_one_entry_per_member(self) -> None:
        @singledispatch
        def process(arg: object) -> str:
            return "default"

        process.register(int | str | bytes, lambda arg: "text-like")  # type: ignore[arg-type]

        assert set(process.registry) == {object, int, str, bytes}
        assert process(1) == process("x") == process(b"y") == "text-like"

    def test_the_annotation_form_resolves_the_annotation(self) -> None:
        """This file's annotations are strings, so the registration below
        has to evaluate one to find `int`."""

        @singledispatch
        def process(arg: object) -> str:
            return "default"

        @process.register
        def _(arg: int) -> str:
            return "int"

        assert int in process.registry
        assert process(1) == "int"


class TestSingledispatchmethod:
    """`singledispatchmethod(func)`, `register()` sharing the wrapped generic
    function's cache, and access through an instance: O(1) from 3.14, a
    metadata copy before."""

    def test_dispatches_on_the_argument_after_self(self) -> None:
        class Formatter:
            @singledispatchmethod
            def render(self, value: object) -> str:
                return repr(value)

            @render.register
            def _(self, value: int) -> str:
                return f"{value:+d}"

        formatter = Formatter()
        assert formatter.render(3) == "+3"
        assert formatter.render("x") == "'x'"
        assert formatter.render(True) == "+1"

    def test_register_clears_the_shared_cache(self) -> None:
        class Handler:
            @singledispatchmethod
            def process(self, arg: object) -> str:
                return "default"

        class Unrelated:
            pass

        class AlsoUnrelated:
            pass

        dispatcher = Handler.__dict__["process"].dispatcher

        with count_find_impl_calls() as calls:
            dispatcher.dispatch(Unrelated)
            dispatcher.dispatch(Unrelated)
            assert calls["n"] == 1

            Handler().process.register(AlsoUnrelated, lambda self, arg: "also")  # type: ignore[reportFunctionMemberAccess]
            dispatcher.dispatch(Unrelated)

        assert calls["n"] == 2

    @staticmethod
    def _holder_with_large_dict() -> Any:
        class Holder:
            method = singledispatchmethod(function_with_dict_entries(LARGE))

        return Holder()

    @pytest.mark.skipif(sys.version_info < (3, 14), reason="lazy access is 3.14+")
    def test_from_314_access_copies_nothing(self) -> None:
        holder = self._holder_with_large_dict()

        peak = peak_bytes(lambda: holder.method)

        assert peak < 5_000, f"reading the method peaked at {peak} bytes"
        assert holder.method.__name__ == "func", "the metadata is resolved on demand"

    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="lazy access is 3.14+")
    def test_before_314_access_copies_the_function_dict(self) -> None:
        holder = self._holder_with_large_dict()

        peak = peak_bytes(lambda: holder.method)

        assert peak > 150_000, f"reading the method peaked at only {peak} bytes"


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
        line, source = next((n, s) for n, s in _blocks() if "info.misses == 31" in s)
        mutated = source.replace("info.misses == 31", "info.misses == 30", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
