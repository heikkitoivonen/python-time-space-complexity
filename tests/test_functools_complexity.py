"""Tests to verify documented time and space complexity of functools.

A review of docs/stdlib/functools.md turned up real defects in the
`singledispatch`/`singledispatchmethod` row, corrected across two passes:

* Dispatch is only O(1) on a cache hit; a miss (the first call for a given
  argument type) runs `_find_impl()` -- see TestSingledispatchCacheBehaviour.
* `register()` unconditionally clears the *entire* dispatch cache, not just
  the entries related to the newly-registered type, so one new registration
  forces every previously-fast type to re-pay the miss cost.
* A first pass corrected the flat "O(1) dispatch" claim to "O(1) hit, O(k)
  miss" -- but O(k) is itself a false upper bound. When several of the k
  registrations are ancestors (real or virtual) of the dispatched class,
  `_compose_mro()` compares each of them against every other one, and the
  cost measured in TestSingledispatchMissIsSuperlinearForRelatedTypes grows
  far faster than k. The table and admonition now describe this instead of
  claiming a specific polynomial bound that has not been established.
* The Space column's O(k) also missed the dispatch cache itself, which is
  keyed by argument type rather than by registration -- see
  TestSingledispatchCacheSizeTracksDispatchedTypesNotJustK, which reads the
  cache directly (via closure introspection) rather than inferring its size
  from retained-object memory, which an earlier version of this test did and
  which would have passed even with the cache entirely disabled. A second
  pass corrected the claim that a live type's entry survives "as long as the
  type does": it is a WeakKeyDictionary, so garbage collection does prune
  it, but register() clears live entries too -- the same behavior the
  admonition's first point already demonstrates.

A further review round found three more defects, unrelated to singledispatch:

* `get_cache_token()` and `recursive_repr()` were documented as functools
  functions, each with its own table row. Neither is in
  `functools.__all__` or the documented functools API -- `functools.py`
  imports both from their real owners (`abc` and `reprlib`) purely for its
  own internal use, and the only reason `functools.get_cache_token` and
  `functools.recursive_repr` work at all is that any name imported into a
  module's namespace is reachable as an attribute of it. `get_cache_token`
  already had a (previously untested) row on docs/stdlib/abc.md;
  `recursive_repr` had no row anywhere else, so one was added to
  docs/stdlib/reprlib.md. Both rows were removed from this page, and their
  tests moved to tests/test_abc_complexity.py and
  tests/test_reprlib_complexity.py, importing from the modules the
  documentation now actually points to.
* `partial`/`partialmethod` were priced at O(1) time despite the table's own
  Space column already saying O(k) for k stored args -- storing k arguments
  cannot be done in less than O(k). See TestPartialAndPartialMethod.
* Correcting that time column left the definition of k wrong in both rows,
  which a later review caught. k counted positional args only, and the
  signatures were written `partial(func, *args)` with no `**keywords` at
  all, so a call storing nothing but q keyword bindings was priced at O(0)
  by a row whose own notes said keywords are stored. Both kinds are copied,
  and flattening merges both, so the bound is over every stored binding:
  O(p + q). The tests now cross both constructors with both kinds --
  `partialmethod` construction had no timing coverage whatsoever, and the
  keyword dimension none on either.
* `wraps`/`update_wrapper` were priced at flat O(1). `update_wrapper` copies
  a fixed handful of names (`WRAPPER_ASSIGNMENTS`) in O(1), but then updates
  the wrapper's `__dict__` from the wrapped callable's `__dict__` in full --
  O(1) only because an ordinary function starts with an empty `__dict__`,
  not in general.
* And that correction, like the `partial` one above it, described the
  default arguments rather than the operation. `assigned` and `updated` are
  public parameters, omitted from both displayed signatures: the first is a
  list of a attribute names, each fetched and set one at a time, the second
  names the mappings whose u entries are copied. The defaults (a = 5,
  u = len(wrapped.__dict__)) are where the m came from, but
  `update_wrapper(w, bare, assigned=20_000_names, updated=())` does Θ(a)
  work against an empty `__dict__` -- a case the O(m) bound priced at zero.
  The bound is O(a + u); see TestWrapsAndUpdateWrapper.
* `reduce` was priced at flat O(n) time and O(1) space, and had been listed
  above as a row that checked out -- on the strength of tests that counted
  its n-1 invocations. The count was right and proved neither bound: both
  belong to the callback and the accumulator, not to `reduce`'s own walk.
  Summing ones, the fold those tests used, is precisely the shape that hides
  this. Folding n one-character strings with `+` re-copies the accumulator
  every call -- Theta(n^2) time, Theta(n) space. The row is now O(n*f) with
  the accumulator called out separately; see TestReduce.
* Fixing that, this module then explained the blind spot by saying integer
  addition "keeps both callback and accumulator constant-size", and the
  page's example labelled its product fold O(n). Python has no fixed-size
  integers. Summing ones is cheap because log2(n) bits fit in a machine word
  for any n anyone benchmarks, not because the accumulator cannot grow --
  and `operator.mul` over range(1, n+1) builds n!, whose Theta(n log n) bits
  make each call dearer than the last: 18.3x for a 4x input, against 4.0x
  for `max` over the very same numbers. So arbitrary precision breaks the
  row on its own, with no strings involved. The example no longer calls the
  product fold O(n) in general, and TestReduce covers the widening
  accumulator both exactly (bit_length) and by timing.

* `lru_cache`/`cache` claimed a flat "O(1) avg hit (hash-based)". Reaching
  that dict lookup means building a key from the call's arguments and
  hashing it, then confirming the match with `__eq__` -- paid on every call,
  hits included. Integer keys, which every test here had used, are the shape
  that hides it: a confirmed hit on an argument whose `__hash__` scans
  100,000 elements costs about 1,400x one hashing in constant time, and
  5,000 positional arguments about 50x two, because the key is a tuple over
  all of them. The rows are now O(h) avg hit / O(h + w) miss. This makes
  `cached_property`'s neighbouring O(1) the interesting one: it is genuine,
  because it looks up a fixed attribute name rather than a derived key.

* Fixing that row still left its Space column and its eviction note
  describing only one of `maxsize`'s three modes. `maxsize=None` is the
  documented unbounded mode -- the one `cache()` is defined as -- where
  nothing is ever evicted and `min(n, maxsize)` has no value to take, and
  `maxsize=0` disables the cache outright, so nothing is stored and no key
  is even built. Only a positive `maxsize` evicts. The Space column is now
  piecewise over all three modes. The unbounded case did have a test
  already, but it asserted on `cache()`, which pins the `cache()` row
  rather than this one.

Everything else on the page checked out: the fourteen code blocks execute
without error and print what their comments say, and the remaining table
rows (`cached_property`, `total_ordering`) match CPython's
`Lib/functools.py`.

`cmp_to_key`'s claim -- that the wrapper calls `compare()` per comparison
rather than computing a key once per element -- already has a test in
tests/test_stdlib_claims.py::TestCmpToKeyCallsPerComparison and is not
repeated here.

Category C, claims execution cannot settle:

* The Version Notes entries for Python 2.5, 3.2, 3.4 and 3.8 are history --
  the oldest interpreter this project supports is 3.10, well past all of
  them. What is testable is that every documented function still exists on
  every supported version, which TestVersionedFunctions covers directly
  rather than skipping.
"""

import io
import math
import operator
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from functools import (
    cache,
    cached_property,
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
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
FUNCTOOLS_PAGE = PROJECT_ROOT / "docs" / "stdlib" / "functools.md"


def best_time(func, repeats: int = 5) -> float:
    """Return the fastest of several runs, the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return min(times)


class TestLruCacheHitsAndMisses:
    """docs/stdlib/functools.md: lru_cache table row and Caching Complexity.

    The rows claimed a flat "O(1) avg hit (hash-based)". Reaching that dict
    lookup means building a key from the call's arguments and hashing it,
    then confirming the match with `__eq__` -- work every call pays, hits
    included, and constant only if the arguments are few and hash in
    constant time. That is a property of the arguments, not of the cache.

    The tests below this docstring's first group use integer keys, which is
    the shape that cannot show any of it; the last four supply arguments
    whose hashing and equality cost real time.

    A later round found the Space column and the eviction note describing
    only a positive `maxsize`; the three tests naming the parameter's modes
    cover the two that never evict.
    """

    def test_each_distinct_argument_is_computed_once(self) -> None:
        """The fibonacci example's "each value computed once", by call count."""
        calls = {"n": 0}

        @cache
        def fib(n: int) -> int:
            calls["n"] += 1
            if n < 2:
                return n
            return fib(n - 1) + fib(n - 2)

        assert fib(30) == 832040
        assert calls["n"] == 31, "one call per distinct n from 0 to 30, no repeats"

    def test_without_the_cache_the_same_value_is_recomputed(self) -> None:
        """The contrasting "without cache would be O(2^n)" claim, by call count."""
        calls = {"n": 0}

        def fib(n: int) -> int:
            calls["n"] += 1
            if n < 2:
                return n
            return fib(n - 1) + fib(n - 2)

        fib(20)
        assert calls["n"] > 2**10, "no memoization means exponential re-computation"

    def test_hit_and_miss_counters_match_the_calls_made(self) -> None:
        @lru_cache(maxsize=128)
        def compute(n: int) -> int:
            return n * n

        compute(5)
        compute(5)
        compute(6)
        compute(5)

        info = compute.cache_info()
        assert (info.hits, info.misses, info.currsize) == (2, 2, 2)

    def test_cache_clear_resets_both_entries_and_statistics(self) -> None:
        @lru_cache(maxsize=128)
        def compute(n: int) -> int:
            return n * n

        compute(1)
        compute(1)
        compute.cache_clear()

        assert compute.cache_info() == (0, 0, 128, 0)

    def test_maxsize_bounds_currsize_at_min_of_n_and_maxsize(self) -> None:
        """Space: O(min(n, maxsize)) -- the positive-`maxsize` branch."""

        @lru_cache(maxsize=10)
        def identity(n: int) -> int:
            return n

        for n in range(100):
            identity(n)

        assert identity.cache_info().currsize == 10, "currsize never exceeds maxsize"

    def test_maxsize_none_holds_every_distinct_key_and_evicts_nothing(self) -> None:
        """Space: O(n), not O(min(n, maxsize)) -- `maxsize=None` is the
        unbounded mode, where the row's expression has no value to take."""

        @lru_cache(maxsize=None)  # noqa: UP033 - the spelling under test
        def identity(n: int) -> int:
            return n

        for n in range(500):
            identity(n)

        info = identity.cache_info()
        assert info.maxsize is None, "the parameter survives as None, not as a number"
        assert info.currsize == 500, "every distinct key is still held"

        identity(0)  # inserted first, and untouched since: the LRU victim if there were one
        assert identity.cache_info().hits == 1, "nothing was evicted to make room"

    def test_cache_is_the_maxsize_none_mode_of_lru_cache(self) -> None:
        """Why the `cache()` row's O(n) is the bound for `maxsize=None`:
        `cache` is defined as `lru_cache(maxsize=None)`."""

        @cache
        def by_decorator(n: int) -> int:
            return n

        @lru_cache(maxsize=None)  # noqa: UP033 - the spelling under test
        def by_argument(n: int) -> int:
            return n

        for n in range(300):
            by_decorator(n)
            by_argument(n)

        assert by_decorator.cache_info().maxsize is None, "cache() is the unbounded mode"
        assert by_decorator.cache_info().currsize == 300
        assert by_decorator.cache_info() == by_argument.cache_info(), (
            "the two spellings produce the same cache, entry for entry"
        )

    def test_maxsize_zero_stores_nothing_and_builds_no_key(self) -> None:
        """The third mode: a disabled cache has nothing to evict, and does
        not reach the key-building step h prices."""
        hashes = {"n": 0}

        class Key:
            def __init__(self, payload: tuple) -> None:
                self.payload = payload

            def __hash__(self) -> int:
                hashes["n"] += 1
                return hash(self.payload)

            def __eq__(self, other: object) -> bool:
                return isinstance(other, Key) and self.payload == other.payload

        @lru_cache(maxsize=0)
        def identity(key: Key) -> int:
            return 1

        key = Key((1, 2, 3))
        identity(key)
        identity(key)
        identity(key)

        info = identity.cache_info()
        assert (info.hits, info.misses, info.currsize) == (0, 3, 0), "nothing was cached"
        assert hashes["n"] == 0, "a disabled cache does not even build a key"

    def test_cache_is_unbounded_unlike_a_sized_lru_cache(self) -> None:
        """Space: O(n) for `cache()`, contrasted with a bounded lru_cache."""

        @cache
        def identity(n: int) -> int:
            return n

        for n in range(500):
            identity(n)

        assert identity.cache_info().currsize == 500, "cache() never evicts"

    def test_eviction_drops_the_least_recently_used_entry(self) -> None:
        """LRU is not incidental -- recency, not insertion order, decides."""

        @lru_cache(maxsize=2)
        def identity(n: int) -> int:
            return n

        identity(1)
        identity(2)
        identity(1)  # touch 1 again, so 2 is now the least recently used
        identity(3)  # should evict 2, not 1

        info_before = identity.cache_info()
        identity(1)  # still cached: no new miss
        identity(2)  # was evicted: a fresh miss
        info_after = identity.cache_info()

        assert info_before.misses == 3
        assert info_after.misses == 4, "2 should have been evicted, 1 should remain"

    @pytest.mark.timing
    def test_a_cache_hit_is_much_faster_than_a_fresh_miss(self) -> None:
        """The Cache Performance example's "second_time << first_time"."""

        @lru_cache(maxsize=256)
        def expensive(x: int) -> int:
            return sum(range(x))

        miss_time = best_time(lambda: expensive(2_000_000), repeats=1)
        expensive(2_000_000)  # ensure it is cached before timing the hit
        hit_time = best_time(lambda: expensive(2_000_000))

        assert hit_time * 20 < miss_time, (
            f"a cache hit should be far cheaper than recomputation: "
            f"miss={miss_time:.2e}s hit={hit_time:.2e}s"
        )

    def test_a_confirmed_hit_still_hashes_its_argument(self) -> None:
        """Exact, no tolerance: the key has to be built and hashed before
        there is anything to look the hit up with."""
        hashes = {"n": 0}

        class Key:
            def __init__(self, payload: tuple) -> None:
                self.payload = payload

            def __hash__(self) -> int:
                hashes["n"] += 1
                return hash(self.payload)

            def __eq__(self, other: object) -> bool:
                return isinstance(other, Key) and self.payload == other.payload

        @lru_cache(maxsize=128)
        def identity(key: Key) -> int:
            return 1

        key = Key((1, 2, 3))
        identity(key)
        hashes["n"] = 0

        identity(key)
        identity(key)
        identity(key)

        assert identity.cache_info().hits == 3, "all three were hits"
        assert hashes["n"] == 3, "and each one hashed the argument again"

    def test_a_hit_on_an_equal_key_also_compares_it(self) -> None:
        """The realistic case -- callers pass an equal object, not the
        identical one, so identity cannot short-circuit the comparison."""
        comparisons = {"n": 0}

        class Key:
            def __init__(self, payload: tuple) -> None:
                self.payload = payload

            def __hash__(self) -> int:
                return hash(self.payload)

            def __eq__(self, other: object) -> bool:
                comparisons["n"] += 1
                return isinstance(other, Key) and self.payload == other.payload

        @lru_cache(maxsize=128)
        def identity(key: Key) -> int:
            return 1

        identity(Key((1, 2, 3)))
        comparisons["n"] = 0

        identity(Key((1, 2, 3)))
        identity(Key((1, 2, 3)))

        assert identity.cache_info().hits == 2
        assert comparisons["n"] == 2, "each hit confirmed the key with __eq__"

    @pytest.mark.timing
    def test_hit_cost_tracks_what_hashing_the_argument_costs(self) -> None:
        """Both calls are hits on a warm cache; only the argument's hash cost
        differs, and a flat O(1) row says that should not matter."""

        class Key:
            def __init__(self, payload: tuple) -> None:
                self.payload = payload

            def __hash__(self) -> int:
                return hash(self.payload)

            def __eq__(self, other: object) -> bool:
                return isinstance(other, Key) and self.payload == other.payload

        @lru_cache(maxsize=128)
        def identity(key: Key) -> int:
            return 1

        cheap = Key(tuple(range(10)))
        costly = Key(tuple(range(100_000)))
        identity(cheap)
        identity(costly)

        cheap_time = best_time(lambda: identity(cheap))
        costly_time = best_time(lambda: identity(costly))

        assert identity.cache_info().misses == 2, "everything timed was a hit"
        assert costly_time > cheap_time * 20, (
            f"a hit whose key hashes 100,000 elements is not the same price "
            f"as one hashing 10: {cheap_time:.2e}s vs {costly_time:.2e}s"
        )

    @pytest.mark.timing
    def test_hit_cost_tracks_the_number_of_arguments(self) -> None:
        """Key construction, separately from per-argument hash cost: these
        are plain ints, and only how many of them there are changes."""

        @lru_cache(maxsize=128)
        def variadic(*args: int) -> int:
            return 1

        few = tuple(range(2))
        many = tuple(range(5_000))
        variadic(*few)
        variadic(*many)

        few_time = best_time(lambda: variadic(*few))
        many_time = best_time(lambda: variadic(*many))

        assert variadic.cache_info().misses == 2, "everything timed was a hit"
        assert many_time > few_time * 10, (
            f"the key is a tuple over every argument, so 5,000 of them cost "
            f"more than 2: {few_time:.2e}s vs {many_time:.2e}s"
        )


class TestCachedProperty:
    """docs/stdlib/functools.md: `cached_property` -- O(1) after first call,
    O(1) space per property, "Descriptor cache"."""

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
        assert calls["n"] == 1, "the second access must not re-run the function"

    def test_each_instance_gets_its_own_value(self) -> None:
        class Widget:
            def __init__(self, base: int) -> None:
                self.base = base

            @cached_property
            def doubled(self) -> int:
                return self.base * 2

        a, b = Widget(1), Widget(5)
        assert (a.doubled, b.doubled) == (2, 10), "instances do not share the cache"

    def test_the_value_lives_in_the_instances_dict(self) -> None:
        """O(1) space per property: it is stored as an ordinary attribute."""

        class Widget:
            @cached_property
            def value(self) -> int:
                return 7

        widget = Widget()
        assert "value" not in widget.__dict__
        assert widget.value == 7
        assert widget.__dict__["value"] == 7


class TestReduce:
    """docs/stdlib/functools.md, as corrected across two rounds.

    The row read O(n) time, O(1) space. `reduce` itself only walks the
    iterable once, but it calls an arbitrary callback n-1 times and threads
    each result into the next call, so both figures belong to the callback
    and the accumulator rather than to `reduce`. Folding one-character
    strings with `+` re-copies the whole accumulator every step: Theta(n^2)
    time, Theta(n) space.

    Counting the n-1 invocations, which is what the first tests here do,
    establishes the call count and nothing about either bound. Summing ones
    is exactly the shape that cannot tell the two apart -- though not
    because the accumulator is fixed-size, which is how the previous round
    of this docstring put it. Python has no fixed-size integers: the total
    of n ones occupies log2(n) bits, one machine word up to n = 2**64, which
    is a bound on the sizes anyone tests rather than a property of the type.

    Arbitrary precision is enough on its own to break the row, without
    involving strings at all: `operator.mul` over range(1, n+1) builds n!,
    whose Theta(n log n) bits make every call more expensive than the last.
    `max` is the shape that really is safe, since its accumulator is always
    one of the inputs and so cannot outgrow them.
    """

    def test_matches_the_documented_examples(self) -> None:
        data = [1, 2, 3, 4, 5]
        assert reduce(lambda a, b: a + b, data) == 15
        assert reduce(lambda a, b: a * b, data) == 120
        assert reduce(lambda a, b: a if a > b else b, data) == 5

    def test_applies_the_function_left_to_right(self) -> None:
        """Order matters: a non-commutative operator exposes the direction."""
        assert reduce(lambda a, b: f"({a}-{b})", ["1", "2", "3"]) == "((1-2)-3)"

    def test_calls_the_function_n_minus_one_times_without_an_initial_value(self) -> None:
        """The page's "applies function n-1 times", counted exactly."""
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

    def test_empty_iterable_without_initial_raises(self) -> None:
        with pytest.raises(TypeError):
            reduce(lambda a, b: a + b, [])

    def test_empty_iterable_with_initial_returns_the_initial_value(self) -> None:
        empty: list[int] = []
        assert reduce(lambda a, b: a + b, empty, 99) == 99

    def test_the_accumulator_is_not_fixed_size(self) -> None:
        """The O(1) space claim, refuted exactly rather than by measurement:
        the value threaded between calls is as large as the fold makes it."""
        size = 5_000

        joined = reduce(lambda a, b: a + b, ["x"] * size)

        assert len(joined) == size, "the accumulator grew to hold the whole input"

    @pytest.mark.timing
    def test_the_time_is_the_callbacks_not_reduces_own_walk(self) -> None:
        """Same `reduce`, same n, same call count -- only the callback's cost
        differs, and that is what decides the shape.

        Summing ones comes out linear because the running total stays inside
        one machine word across the range measured here -- 80,000 fits in 17
        bits. That makes it a usable constant-cost control, not an example of
        a fixed-size accumulator, which Python does not have; see
        test_an_integer_accumulator_widens_faster_than_the_input_grows for a
        fold where the width is the whole point. Concatenation copies the
        accumulator on every call, so four times the input costs far more
        than four times the work.

        Both thresholds come from the measured spread over ten trials rather
        than from the 4x the input step suggests: at five repeats the control
        lands in 4.0-4.2 and concatenation in 14.3-16.5. An earlier version
        took three repeats and put the control at 6 -- barely above a linear
        result, and it duly flaked at 7.2.
        """
        small, large = 20_000, 80_000
        small_chars, large_chars = ["x"] * small, ["x"] * large
        small_ints, large_ints = [1] * small, [1] * large

        concat_growth = best_time(
            lambda: reduce(lambda a, b: a + b, large_chars), repeats=5
        ) / best_time(lambda: reduce(lambda a, b: a + b, small_chars), repeats=5)
        addition_growth = best_time(
            lambda: reduce(lambda a, b: a + b, large_ints), repeats=5
        ) / best_time(lambda: reduce(lambda a, b: a + b, small_ints), repeats=5)

        assert addition_growth < 7, (
            f"a constant-time callback should track the 4x input: {addition_growth:.1f}x"
        )
        assert concat_growth > 8, (
            f"a callback that copies the accumulator should cost far more "
            f"than 4x, which the flat O(n) row denies: {concat_growth:.1f}x "
            f"against addition's {addition_growth:.1f}x"
        )

    def test_an_integer_accumulator_widens_faster_than_the_input_grows(self) -> None:
        """No strings needed to break the row -- arbitrary precision does it.

        Exact, no stopwatch: doubling n more than doubles the width of the
        product accumulator, which is the Theta(n log n) bits of n!. A
        fixed-size accumulator would hold this flat.
        """
        widths = [math.prod(range(1, size + 1)).bit_length() for size in (1_000, 2_000, 4_000)]

        assert widths[0] > 0
        assert widths[1] > widths[0] * 2, f"n! outgrows a doubling of n: {widths}"
        assert widths[2] > widths[1] * 2, f"and keeps doing so: {widths}"

    @pytest.mark.timing
    def test_a_widening_integer_accumulator_makes_the_fold_superlinear(self) -> None:
        """The same iterable, folded two ways. `max` keeps the accumulator to
        one of the inputs and stays linear; `mul` lets it widen without
        bound, and the row's flat O(n) covers neither case by itself.

        Thresholds from ten measured trials at five repeats: the control
        lands in 3.6-4.5 and the product fold in 18.7-25.2. At three repeats
        the control's spread reached 6.6, which is what flaked the original
        threshold of 6.
        """
        small, large = 2_000, 8_000
        small_data, large_data = list(range(1, small + 1)), list(range(1, large + 1))

        def largest(a: int, b: int) -> int:
            return a if a > b else b

        product_growth = best_time(lambda: reduce(operator.mul, large_data), repeats=5) / best_time(
            lambda: reduce(operator.mul, small_data), repeats=5
        )
        max_growth = best_time(lambda: reduce(largest, large_data), repeats=5) / best_time(
            lambda: reduce(largest, small_data), repeats=5
        )

        assert max_growth < 7, (
            f"an accumulator that cannot grow should track the 4x input: {max_growth:.1f}x"
        )
        assert product_growth > 8, (
            f"a widening integer accumulator should cost far more than 4x, "
            f"over the very same numbers: product {product_growth:.1f}x vs "
            f"max {max_growth:.1f}x"
        )


class TestPartialAndPartialMethod:
    """docs/stdlib/functools.md, as corrected across two rounds.

    `partial`/`partialmethod` were first priced at O(1) time despite the
    table's own Space column already saying O(k) for k stored args --
    storing k arguments cannot be done in less than O(k).

    Correcting the time column to match left the deeper problem in place:
    k was defined over positional args alone, and the signatures did not
    even show `**keywords`, so `partial(f, **twenty_thousand_bindings)` was
    priced at O(0) by a table whose own notes said keywords are stored.
    Both are copied, and flattening merges both. The bound is over every
    stored binding, O(p + q), and the tests below cross both constructors
    with both kinds rather than timing positional args on `partial` alone.
    """

    SMALL = 20
    LARGE = 20_000

    def test_construction_only_stores_arguments(self) -> None:
        calls = {"n": 0}

        def multiply(x: int, y: int) -> int:
            calls["n"] += 1
            return x * y

        times_3 = partial(multiply, 3)
        assert calls["n"] == 0, "partial() must not call the underlying function"
        assert times_3(5) == 15
        assert calls["n"] == 1

    def test_stored_positional_and_keyword_args_both_apply(self) -> None:
        def format_data(value: int, width: int, align: str = "<") -> str:
            return f"{value:{align}{width}}"

        left_align = partial(format_data, width=10, align="<")
        right_align = partial(format_data, width=10, align=">")

        assert left_align(42) == "42        "
        assert right_align(42) == "        42"

    def test_nested_partials_flatten_instead_of_chaining(self) -> None:
        """Flattening, not the depth-1 call chain a naive wrapper would build."""

        def add3(a: int, b: int, c: int) -> int:
            return a + b + c

        once = partial(add3, 1)
        twice = partial(once, 2)

        assert twice.func is add3, "the outer partial should not wrap `once` itself"
        assert twice.args == (1, 2)
        assert twice(3) == 6

    def test_partialmethod_binds_as_an_instance_method(self) -> None:
        class Formatter:
            def render(self, value: object, width: int) -> str:
                return f"{value:>{width}}"

            right = partialmethod(render, width=6)

        assert Formatter().right(42) == "    42"

    @staticmethod
    def _sink(*args: object, **keywords: object) -> None:
        return None

    def _bindings(self, size: int, kind: str) -> tuple[tuple, dict]:
        """`size` bindings of one kind, as (args, keywords) to splat."""
        if kind == "positional":
            return tuple(range(size)), {}
        return (), {f"k{index}": index for index in range(size)}

    def test_every_stored_binding_is_kept_whichever_kind_it_is(self) -> None:
        """The space bound, counted exactly rather than timed. O(p + q) with
        q dropped would predict the keyword case holding nothing."""
        args, _ = self._bindings(self.LARGE, "positional")
        _, keywords = self._bindings(self.LARGE, "keyword")

        positional_only = partial(self._sink, *args)
        keyword_only = partial(self._sink, **keywords)
        both = partial(self._sink, *args, **keywords)

        assert (len(positional_only.args), len(positional_only.keywords)) == (self.LARGE, 0)
        assert (len(keyword_only.args), len(keyword_only.keywords)) == (0, self.LARGE)
        assert (len(both.args), len(both.keywords)) == (self.LARGE, self.LARGE)

    @pytest.mark.timing
    @pytest.mark.parametrize("kind", ["positional", "keyword"])
    @pytest.mark.parametrize(
        ("name", "construct"),
        [("partial", partial), ("partialmethod", partialmethod)],
    )
    def test_construction_scales_with_the_bindings_stored(
        self, name: str, construct, kind: str
    ) -> None:
        """Both constructors, both kinds of binding. Timing only `partial`
        with positional args -- what the previous round did -- left three of
        these four cells resting on the assumption that they behave alike."""
        small_args, small_keywords = self._bindings(self.SMALL, kind)
        large_args, large_keywords = self._bindings(self.LARGE, kind)

        small_time = best_time(lambda: construct(self._sink, *small_args, **small_keywords))
        large_time = best_time(lambda: construct(self._sink, *large_args, **large_keywords))

        assert large_time > small_time * 50, (
            f"1,000x the stored {kind} bindings should cost noticeably more "
            f"to {name}, not the same: {self.SMALL} {small_time:.2e}s vs "
            f"{self.LARGE:,} {large_time:.2e}s"
        )

    @pytest.mark.parametrize(
        ("name", "construct"),
        [("partial", partial), ("partialmethod", partialmethod)],
    )
    def test_flattening_merges_both_tuples_and_both_dicts(self, name: str, construct) -> None:
        """Exact: the flattened object holds the union of what the two levels
        stored, which is why its cost is the merged size and not the outer."""
        inner = construct(self._sink, "a", first=1)
        outer = construct(inner, "b", second=2)

        assert outer.func is self._sink, f"{name} should flatten, not nest"
        assert outer.args == ("a", "b")
        assert outer.keywords == {"first": 1, "second": 2}

    @pytest.mark.timing
    @pytest.mark.parametrize("kind", ["positional", "keyword"])
    def test_flattening_a_nested_partial_costs_the_merged_size(self, kind: str) -> None:
        small_args, small_keywords = self._bindings(self.SMALL, kind)
        large_args, large_keywords = self._bindings(self.LARGE, kind)
        small_base = partial(self._sink, *small_args, **small_keywords)
        large_base = partial(self._sink, *large_args, **large_keywords)

        small_time = best_time(lambda: partial(small_base, *small_args, **small_keywords))
        large_time = best_time(lambda: partial(large_base, *large_args, **large_keywords))

        assert large_time > small_time * 50, (
            f"flattening two large sets of {kind} bindings should cost far "
            f"more than two small ones: {self.SMALL} {small_time:.2e}s vs "
            f"{self.LARGE:,} {large_time:.2e}s"
        )


class TestWrapsAndUpdateWrapper:
    """docs/stdlib/functools.md, as corrected across two rounds.

    These were first priced at flat O(1), which held only because an
    ordinary function starts with an empty `__dict__`; a wrapped callable
    carrying m attributes costs O(m) to copy them.

    That correction still described only the default arguments. `assigned`
    and `updated` are public parameters: the first is a list of a attribute
    names, each fetched and set individually, and the second names the
    mappings whose u total entries get copied. Defaults make a = 5 and
    u = len(wrapped.__dict__), which is where the m came from -- but a
    caller passing 10,000 names in `assigned` pays for all of them against
    an empty `__dict__`, a case the O(m) bound priced at zero.
    """

    def test_wraps_copies_identity_metadata(self) -> None:
        def original(x: int) -> int:
            """Docstring for original."""
            return x

        @wraps(original)
        def wrapper(x: int) -> int:
            return original(x)

        assert wrapper.__name__ == "original"
        assert wrapper.__doc__ == "Docstring for original."
        assert wrapper.__wrapped__ is original

    def test_update_wrapper_can_be_used_directly(self) -> None:
        def original() -> None:
            pass

        def wrapper() -> None:
            pass

        returned = update_wrapper(wrapper, original)
        assert returned is wrapper
        assert wrapper.__name__ == "original"

    @pytest.mark.timing
    def test_cost_tracks_the_wrapped_callables_dict_size(self) -> None:
        def make_wrapped(attribute_count: int):
            def wrapped() -> None:
                pass

            for index in range(attribute_count):
                setattr(wrapped, f"attr{index}", index)
            return wrapped

        few_attrs = make_wrapped(10)
        many_attrs = make_wrapped(20_000)

        few_time = best_time(lambda: update_wrapper(lambda: None, few_attrs))
        many_time = best_time(lambda: update_wrapper(lambda: None, many_attrs))

        assert many_time > few_time * 50, (
            f"2,000x the entries in wrapped.__dict__ should cost noticeably "
            f"more, not O(1): m=10 {few_time:.2e}s vs m=20,000 {many_time:.2e}s"
        )

    def test_custom_assigned_and_updated_replace_the_defaults(self) -> None:
        """The parameters the rows had left out, shown to be load-bearing:
        pass your own and the documented default names are not copied."""

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
        assert wrapper.__doc__ is None, "the default `assigned` names were not used"
        assert wrapper.__name__ == "wrapper", "nor was __name__ among them"

    @pytest.mark.timing
    def test_a_custom_assigned_list_is_paid_for_even_when_nothing_is_copied(self) -> None:
        """The sharpest case against the old O(m) bound: `wrapped.__dict__`
        is empty and not one name resolves, so m = 0 and O(m) predicts no
        work at all. Every name in `assigned` is still looked up."""

        def bare() -> None:
            pass

        assert bare.__dict__ == {}, "m = 0, so an O(m) bound predicts O(1)"

        few_names = [f"missing{index}" for index in range(10)]
        many_names = [f"missing{index}" for index in range(20_000)]

        few_time = best_time(
            lambda: update_wrapper(lambda: None, bare, assigned=few_names, updated=())
        )
        many_time = best_time(
            lambda: update_wrapper(lambda: None, bare, assigned=many_names, updated=())
        )

        assert many_time > few_time * 50, (
            f"2,000x the names in `assigned` should cost noticeably more "
            f"even with nothing to copy: a=10 {few_time:.2e}s vs "
            f"a=20,000 {many_time:.2e}s"
        )

    @pytest.mark.timing
    def test_a_custom_updated_mapping_is_what_gets_copied(self) -> None:
        """u is the entries in the mappings `updated` names -- not
        specifically `__dict__`, which here stays the same size throughout."""

        def make_source(entries: int):
            def source() -> None:
                pass

            source.registry = {f"k{index}": index for index in range(entries)}  # type: ignore[attr-defined]
            return source

        small_source = make_source(10)
        large_source = make_source(20_000)

        def copy_from(source) -> None:
            wrapper = lambda: None  # noqa: E731 - a fresh target per run
            wrapper.registry = {}  # type: ignore[attr-defined]
            update_wrapper(wrapper, source, assigned=(), updated=("registry",))

        small_time = best_time(lambda: copy_from(small_source))
        large_time = best_time(lambda: copy_from(large_source))

        assert large_time > small_time * 20, (
            f"2,000x the entries in the named mapping should cost noticeably "
            f"more: u=10 {small_time:.2e}s vs u=20,000 {large_time:.2e}s"
        )


class TestTotalOrdering:
    """docs/stdlib/functools.md: `total_ordering` -- O(1), "fills in missing
    comparison methods"."""

    def test_fills_in_the_three_missing_methods_from_lt_and_eq(self) -> None:
        @total_ordering
        class Box:
            def __init__(self, size: int) -> None:
                self.size = size

            def __eq__(self, other: object) -> bool:
                return isinstance(other, Box) and self.size == other.size

            def __lt__(self, other: "Box") -> bool:
                return self.size < other.size

        small, big = Box(1), Box(2)
        assert small < big
        assert small <= big
        assert big > small
        assert big >= small
        assert not (big < small)

    def test_raises_without_any_ordering_method(self) -> None:
        with pytest.raises(ValueError):

            @total_ordering  # type: ignore[reportGeneralTypeIssues]
            class NoOrdering:
                def __eq__(self, other: object) -> bool:
                    return NotImplemented


@contextmanager
def _count_find_impl_calls() -> Iterator[dict[str, int]]:
    """Patch functools._find_impl to count calls, restoring it afterward.

    dispatch() looks up `_find_impl` by name in the module's globals at call
    time, so patching the module attribute intercepts every cache miss
    without needing to touch the closure itself.
    """
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


class TestSingledispatchCacheBehaviour:
    """docs/stdlib/functools.md, as corrected by these tests.

    The page priced dispatch at a flat O(1). It is O(1) only once a type has
    been dispatched before -- the result is cached by argument type. The
    first dispatch for a type is a cache miss that runs `_find_impl()`, which
    scans every one of the k registered types. And `register()` clears the
    *whole* dispatch cache, so it is not only new types that pay the miss
    cost again after a registration -- every type dispatched before does too.
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
        assert process([1, 2, 3]) == "List of 3 items"

    def test_repeated_dispatch_on_the_same_type_is_a_cache_hit(self) -> None:
        """O(1) avg hit: the second dispatch for a type must not re-run
        _find_impl(), counted exactly rather than timed."""

        @singledispatch
        def process(arg: object) -> str:
            return "default"

        class Probe:
            pass

        with _count_find_impl_calls() as calls:
            process.dispatch(Probe)
            process.dispatch(Probe)
            process.dispatch(Probe)

        assert calls["n"] == 1, "only the first dispatch for a type should miss"

    def test_register_clears_the_entire_dispatch_cache(self) -> None:
        """Not just the affected type's entry -- everything cached so far."""

        @singledispatch
        def process(arg: object) -> str:
            return "default"

        class Unrelated:
            pass

        class AlsoUnrelated:
            pass

        with _count_find_impl_calls() as calls:
            process.dispatch(Unrelated)
            process.dispatch(Unrelated)
            assert calls["n"] == 1, "warmed up: cached after the first dispatch"

            @process.register(AlsoUnrelated)
            def _(arg: object) -> str:
                return "also unrelated"

            process.dispatch(Unrelated)

        assert calls["n"] == 2, (
            "registering AlsoUnrelated should have cleared Unrelated's cache "
            "entry too, forcing a second miss"
        )

    def test_singledispatchmethod_shares_the_same_cache_invalidation(self) -> None:
        class Handler:
            @singledispatchmethod
            def process(self, arg: object) -> str:
                return "default"

        class Unrelated:
            pass

        class AlsoUnrelated:
            pass

        handler = Handler()
        dispatcher = Handler.__dict__["process"].dispatcher

        with _count_find_impl_calls() as calls:
            dispatcher.dispatch(Unrelated)
            dispatcher.dispatch(Unrelated)
            assert calls["n"] == 1

            @handler.process.register(AlsoUnrelated)  # type: ignore[reportFunctionMemberAccess]
            def _(self: Handler, arg: object) -> str:
                return "also unrelated"

            dispatcher.dispatch(Unrelated)

        assert calls["n"] == 2, "the method descriptor's cache is cleared the same way"

    @pytest.mark.timing
    def test_a_dispatch_miss_is_not_free_when_the_dispatched_class_is_unrelated(self) -> None:
        """A miss is at least as expensive as O(1) -- it is not, on its own,
        evidence of a specific upper bound. See
        TestSingledispatchMissIsSuperlinearForRelatedTypes for the case where
        the cost is much worse than the registry size alone would suggest.
        """

        def build_registry(size: int):
            @singledispatch
            def process(arg: object) -> str:
                return "default"

            for index in range(size):
                registered_type = type(f"Registered{index}", (), {})
                process.register(registered_type, lambda arg: "matched")
            return process

        def first_dispatch_time(process, count: int = 150, repeats: int = 3) -> float:
            best = float("inf")
            for trial in range(repeats):
                probes = [type(f"Probe{trial}_{i}", (), {}) for i in range(count)]
                start = time.perf_counter()
                for probe in probes:
                    process.dispatch(probe)
                best = min(best, time.perf_counter() - start)
            return best

        small = build_registry(20)
        large = build_registry(4_000)

        small_time = first_dispatch_time(small)
        large_time = first_dispatch_time(large)

        assert large_time > small_time * 20, (
            f"200x the registered types should cost noticeably more per "
            f"first dispatch, not the same: k=20 {small_time:.2e}s vs "
            f"k=4,000 {large_time:.2e}s"
        )


class TestSingledispatchMissIsSuperlinearForRelatedTypes:
    """docs/stdlib/functools.md, as corrected by this test.

    An earlier version of the page's fix claimed a flat O(k) upper bound for
    a dispatch miss. That undersells the pathological case: when several of
    the k registrations are ancestors -- real or virtual, via
    `ABCMeta.register()` -- of the dispatched class, `_compose_mro()` checks
    each of those ancestors against every other one before composing the
    MRO, and the cost measured here grows far faster than k.
    """

    @staticmethod
    def _build(related_count: int):
        """k pairwise-unrelated ABCs, each registered as a virtual ancestor
        of the same concrete class -- the shape that defeats the fast path.
        """
        import abc

        @singledispatch
        def process(arg: object) -> str:
            return "default"

        interfaces = []
        for index in range(related_count):
            interface = abc.ABCMeta(f"Interface{index}", (), {})
            process.register(interface, lambda arg: "matched")
            interfaces.append(interface)

        class Concrete:
            pass

        for interface in interfaces:
            interface.register(Concrete)

        return process, Concrete

    @pytest.mark.timing
    def test_quadrupling_related_registrations_costs_far_more_than_4x(self) -> None:
        import contextlib

        def dispatch_time(related_count: int) -> float:
            process, concrete = self._build(related_count)
            start = time.perf_counter()
            with contextlib.suppress(RuntimeError):
                # Ambiguous virtual ancestors raise -- but only after
                # _compose_mro() has already done the expensive part.
                process.dispatch(concrete)
            return time.perf_counter() - start

        small_time = dispatch_time(100)
        large_time = dispatch_time(400)

        assert large_time > small_time * 16, (
            f"4x the related registrations should cost much more than 4x, "
            f"and even more than the 16x a quadratic bound would predict: "
            f"k=100 {small_time:.2e}s vs k=400 {large_time:.2e}s "
            f"({large_time / small_time:.0f}x)"
        )


class TestSingledispatchCacheSizeTracksDispatchedTypesNotJustK:
    """docs/stdlib/functools.md, as corrected by this test.

    The Space column priced singledispatch at O(k) for k registered types.
    That leaves out the dispatch cache: it holds one entry per distinct
    argument type dispatched since the cache was last cleared, so a function
    with a single registration (k=1) can still accumulate many entries.

    An earlier version of this test inferred cache growth from retained
    memory while holding thousands of dynamically-created classes alive.
    That measured the class objects themselves, not the cache -- the same
    result would appear even if `process.dispatch()` were never called at
    all. These tests instead read `dispatch_cache`, the `WeakKeyDictionary`
    singledispatch's `dispatch()` closes over, directly by inspecting the
    closure -- not public API, but the only way to observe the cache rather
    than something correlated with it.
    """

    @staticmethod
    def _dispatch_cache(generic_func) -> dict:
        dispatch = generic_func.dispatch
        index = dispatch.__code__.co_freevars.index("dispatch_cache")
        return dispatch.__closure__[index].cell_contents  # type: ignore[union-attr]

    def test_the_cache_holds_one_entry_per_distinct_type_dispatched(self) -> None:
        @singledispatch
        def process(arg: object) -> str:
            return "default"

        cache = self._dispatch_cache(process)
        kept = [type(f"Probe{index}", (), {}) for index in range(200)]

        for probe in kept:
            process.dispatch(probe)

        assert len(cache) == 200, "one cache entry per distinct type, with k fixed at 1"

    def test_entries_are_pruned_once_their_type_is_garbage_collected(self) -> None:
        """The WeakKeyDictionary claim: types nothing else references do not
        accumulate in the cache."""
        import gc

        @singledispatch
        def process(arg: object) -> str:
            return "default"

        cache = self._dispatch_cache(process)

        for index in range(500):
            process.dispatch(type(f"Ephemeral{index}", (), {}))

        gc.collect()
        assert len(cache) == 0, "nothing outside the loop holds the dispatched types"

    def test_register_clears_entries_for_types_that_are_still_alive(self) -> None:
        """Corrects "as long as a type stays alive, so does its entry" --
        register() clears live entries too, not only dead ones."""

        @singledispatch
        def process(arg: object) -> str:
            return "default"

        cache = self._dispatch_cache(process)
        kept = [type(f"Alive{index}", (), {}) for index in range(50)]
        for probe in kept:
            process.dispatch(probe)
        assert len(cache) == 50

        @process.register(int)
        def _(arg: int) -> str:
            return "int"

        assert len(cache) == 0, "register() clears the cache regardless of liveness"
        assert len(kept) == 50, "the dispatched types are still alive throughout"


class TestVersionedFunctions:
    """docs/stdlib/functools.md Version Notes.

    Every entry predates this project's minimum supported version (3.10), so
    the historical "added in" facts are not something a running interpreter
    can check. What is checkable, and checked here, is that every documented
    function is actually present -- on this interpreter and, since none of
    them are version-gated above 3.10, on every version this project claims
    to support.
    """

    def test_every_documented_function_exists(self) -> None:
        import functools as functools_module

        for name in (
            "reduce",
            "partial",
            "partialmethod",
            "wraps",
            "update_wrapper",
            "lru_cache",
            "cache",
            "cached_property",
            "cmp_to_key",
            "total_ordering",
            "singledispatch",
            "singledispatchmethod",
        ):
            assert hasattr(functools_module, name), f"{name} should exist on 3.10+"

    def test_minimum_supported_version_is_at_or_above_all_documented_additions(self) -> None:
        assert sys.version_info >= (3, 10), "cache (3.9+) predates this project's floor"


class TestDocumentedExamplesRun:
    """Every Python block on docs/stdlib/functools.md must execute."""

    def _blocks(self) -> list[tuple[int, str]]:
        blocks: list[tuple[int, str]] = []
        inside = False
        start = 0
        body: list[str] = []
        for number, line in enumerate(
            FUNCTOOLS_PAGE.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not inside and line.strip() == "```python":
                inside, start, body = True, number, []
            elif inside and line.strip() == "```":
                blocks.append((start, "\n".join(body)))
                inside = False
            elif inside:
                body.append(line)
        return blocks

    def test_the_page_has_examples_to_check(self) -> None:
        assert len(self._blocks()) >= 14

    def test_every_example_executes(self) -> None:
        failures: list[str] = []
        for line_number, source in self._blocks():
            captured, real_stdout = io.StringIO(), sys.stdout
            try:
                sys.stdout = captured
                exec(  # noqa: S102 - executing the docs is the point
                    compile(source, f"functools.md:{line_number}", "exec"),
                    {"__name__": "__main__"},
                )
            except Exception as error:  # noqa: BLE001 - report, do not raise
                failures.append(f"line {line_number}: {type(error).__name__}: {error}")
            finally:
                sys.stdout = real_stdout

        assert not failures, "examples on the page do not run:\n" + "\n".join(failures)

    def test_the_partial_alignment_example_prints_what_the_page_says(self) -> None:
        source = next(body for _, body in self._blocks() if "left_align = partial" in body)
        captured, real_stdout = io.StringIO(), sys.stdout
        try:
            sys.stdout = captured
            exec(
                compile(source, "functools.md:partial-alignment", "exec"), {"__name__": "__main__"}
            )  # noqa: S102
        finally:
            sys.stdout = real_stdout

        assert captured.getvalue().splitlines() == ["42        ", "        42"]

    def test_the_cache_stats_example_prints_what_the_page_says(self) -> None:
        source = next(body for _, body in self._blocks() if "cache_info()" in body)
        captured, real_stdout = io.StringIO(), sys.stdout
        try:
            sys.stdout = captured
            exec(compile(source, "functools.md:cache-stats", "exec"), {"__name__": "__main__"})  # noqa: S102
        finally:
            sys.stdout = real_stdout

        assert (
            captured.getvalue().splitlines()[0]
            == "CacheInfo(hits=2, misses=2, maxsize=128, currsize=2)"
        )
