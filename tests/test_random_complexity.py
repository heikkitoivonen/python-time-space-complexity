"""Tests for docs/stdlib/random.md.

Every operation in the module reaches the Mersenne Twister through
``random()`` or ``getrandbits()``, so a ``Random`` subclass that counts those
two calls settles most of the page in the unit its table is written in: draws.
Counting needs no tolerance. Population access is counted the same way, by a
sequence whose ``__getitem__`` and ``__iter__`` record each element taken, and
weights by a float subclass whose additions and comparisons are counted inside
``itertools.accumulate`` and the C ``bisect_right``. Space is settled by
``sys.getsizeof`` of the integers built and by ``tracemalloc`` peaks; the
rows whose cost is a bit width are also timed.

Measurement scope:

* ``random()`` takes one draw. ``getrandbits(w)`` returns at most w bits, its
  integer grows about 10x from 10,000 to 100,000 bits, and 100x the bits costs
  more than 20x the time. ``randbytes(b)`` is one ``getrandbits`` call at 1 and
  10,000 bytes, and 100x the bytes costs more than 20x the time.
* ``randrange`` and ``randint`` take one to two draws per value on average:
  under 2x over 10,000 ``randint`` calls at spans of 10 and 10**18, and under
  2.2x over 5,000 ``randrange`` calls at bounds of 10, 10**6, 10**18, 2**64
  and 2**64 + 1, the last two being where a draw is rejected half the time. The value built grows about
  10x from 10,000 to 100,000 bits of bound, a two-element range based at
  2**100,000 builds an integer over 100x the size of one based at 2**10, and
  both effects are timed over a hundredfold width (more than 20x). A step
  keeps the draw count within 1.5x of the unit step's on small operands; over 10,000 to 1,000,000
  bits the stepped path grows more than three times faster than the unit-step
  path measured in the same run (about x7,600 against x90 on 3.11, x470
  against x90 on 3.14). Indexing a ``range(2**62)`` and shuffling a list never
  ask ``getrandbits`` for more than 64 bits, and a ``counts=`` total past
  ``sys.maxsize`` raises ``OverflowError``, so a sequence index is a word.
* ``choice()`` makes one lookup at 10 and 100,000 elements and allocates under
  2 KB on ``range(10**9)``. Unweighted ``choices()`` makes k lookups and k
  draws. Weighted ``choices()`` makes 512 additions over 512 weights at k=1 and
  k=100, twice that over two calls, and about log2(n) comparisons per draw at
  n=64 and 4,096, far below a scan. ``cum_weights=`` makes the same additions
  at 512 and 4,096 weights, fewer than the draws, with the same bisection.
* ``sample()``: one lookup per value at k=5 of 10,000. CPython keeps either a
  set of drawn indices or a copied list, whichever is smaller; the copy
  threshold is pinned on both sides (21 elements copied and 22 indexed at k=1;
  at n=100, k=20 indexed and k=50 copied), and over n from 1 to 2,000 at k=1,
  10 and 100 the lookups never exceed 21 + 12k, so the copy is O(k). The
  ``tracemalloc`` peak for k=10 is the same over 20,000 and 200,000 elements,
  and about k draws are taken at k=1,000 of 10**6. ``counts=`` indexes the
  population k times, makes n - 1 additions accumulating n counts and about
  log2(n) comparisons per value bisecting them, at n=64 and n=4,096. A dict is rejected on every supported version; a set
  is rejected from 3.11 and warns on 3.10, where Lib/random.py copies it to a
  tuple first.
* ``shuffle()`` keeps the list object, takes between n - 1 and 2n draws at
  n=1,000, about 8x the draws for 8x the list, and peaks under 5 KB at 20,000
  and 200,000 elements, which is O(1) extra space rather than no allocation.
* Distributions: uniform, triangular, expovariate, paretovariate and
  weibullvariate take exactly one draw per value. ``gauss()`` takes two draws
  for two values and leaves its spare in ``getstate()[2]``. The rejection
  loops average fewer than eight draws per value at every parameter tried:
  gammavariate alpha 0.01-10**6, vonmisesvariate kappa 10**-7-10**6 and
  betavariate (0.01, 0.01)-(1,000, 1,000). binomialvariate (3.12+) averages
  fewer than twelve from n=5 to 10**12 with p from 10**-11 to 0.999999; its
  geometric branch takes about n*p + 1 draws, approaching 11 just below
  the n*p = 10 switch to BTRS; (19, 0.5) measures about 10.5.
* ``seed()``: 10x a prebuilt str seed is 5-20x the traced peak and more
  than 5x the time, 10x an int seed's bits is 8-12x the peak, and the state is 625 words
  either way and after 10,000 draws. ``getstate()``/``setstate()`` round-trip.
  ``Random(x)`` is that seed on a new instance; two instances do not disturb
  each other, and the module functions are one seeded instance.
* ``SystemRandom``: ``random._urandom`` replaced by a recorder shows one call
  per ``random()``, ``uniform()`` and ``expovariate()``, one of ceil(w/8)
  bytes per ``getrandbits(w)``, one of b bytes per ``randbytes(b)``, and
  ``shuffle()`` of 1,000 elements making between 999 and 2,000 calls.
  ``seed()`` returns ``None`` and ``getstate()``/``setstate()`` raise
  ``NotImplementedError``.
* Threads: two threads drawing from the seeded module stream consume exactly
  its first 200 values between them; per-thread seeded instances reproduce;
  eight threads' 4,000 concurrent draws are all in range; and the ``gauss()``
  spare is handed out twice when two callers read it before either clears it,
  modelled with ``setstate``.
* ``main()`` (3.13+) calls the module's ``choice()``, ``randint()`` or
  ``uniform()`` exactly once for a ``-c`` list, several words, one spaced
  string, one integer and one float, and none of them with no arguments,
  when it returns the help text; its peak grows more than 5x from 20,000 to
  200,000 arguments.
* The page's reservoir sampler, taken from the page, takes between n - k and
  2n draws over 20,000 items and peaks under 20 KB over 200,000.
* Every fenced block runs in its own subprocess and working directory, and a
  mutated assertion in one of them is asserted to fail.

Not settled here:

* Indexing a sequence is priced O(1). The tests count lookups, not what
  each lookup costs.
* Weight type: only a float subclass is counted for ``choices()``. Integer
  weights go through the same ``accumulate`` and ``bisect_right``.
* Seed contents: seed cost is varied by length only; it is a hash of the
  bytes and an int conversion, so values cannot change the shape. Only the
  default ``version=2`` is measured.
* ``main()`` is varied in argument count at a fixed argument length, not in
  the length of one argument. Its hidden ``--test N`` option, suppressed from
  the help, runs the module's self-test and is outside the row.
* The ``gauss()`` spare race is modelled by restoring the state between two
  calls, not by racing threads, whose interleaving a test cannot force.
* That each ``Random`` method costs what the matching module function costs
  is read from Lib/random.py, where the module functions are bound methods of
  one instance; that ``random.random`` and ``random.shuffle`` are bound to
  ``random._inst`` is asserted.
* The Mersenne Twister's predictability, behind the page's advice to use
  ``secrets`` for tokens, is not something a unit test should demonstrate.
* Version notes for 3.6 and 3.9 (``choices()``, ``randbytes()``,
  ``sample(counts=)``) predate the supported range. The 3.11 set rejection,
  3.12 ``binomialvariate()`` and 3.13 ``main()`` are asserted on whichever
  side of their boundary the running interpreter is; CI runs both sides.
"""

from __future__ import annotations

import pathlib
import random
import re
import subprocess
import sys
import textwrap
import threading
import timeit
import tracemalloc
import warnings
from collections.abc import Callable, Iterator, Sequence
from typing import Any, overload

import pytest

PAGE = pathlib.Path(__file__).resolve().parent.parent / "docs" / "stdlib" / "random.md"
EXPECTED_BLOCKS = 10


class CountingRandom(random.Random):
    """A generator that records how often the core engine is asked for bits.

    A draw is one request, not one word of Twister output: `random()` costs
    two 32-bit words and `getrandbits(w)` ceil(w/32), which is why the rows
    that take an integer bound carry `w` and the width tests below use the
    clock and `sys.getsizeof` rather than this counter.
    """

    def __init__(self, seed: int | None = None) -> None:
        self.random_calls = 0
        self.getrandbits_calls = 0
        self.widths: list[int] = []
        super().__init__(seed)

    def random(self) -> float:
        self.random_calls += 1
        return super().random()

    def getrandbits(self, k: int, /) -> int:
        self.getrandbits_calls += 1
        self.widths.append(k)
        return super().getrandbits(k)

    @property
    def draws(self) -> int:
        return self.random_calls + self.getrandbits_calls

    def reset(self) -> None:
        self.random_calls = 0
        self.getrandbits_calls = 0
        self.widths.clear()


def draws_for(operation: Callable[[CountingRandom], Any], seed: int = 7) -> int:
    """Core-engine calls made by one operation, excluding construction."""
    rng = CountingRandom(seed)
    rng.reset()
    operation(rng)
    return rng.draws


class CountingSequence(Sequence[int]):
    """A sequence that records every element taken, by index or by iteration."""

    def __init__(self, data: list[int]) -> None:
        self.data = data
        self.lookups = 0

    def __len__(self) -> int:
        return len(self.data)

    @overload
    def __getitem__(self, index: int) -> int: ...

    @overload
    def __getitem__(self, index: slice) -> Sequence[int]: ...

    def __getitem__(self, index: int | slice) -> int | Sequence[int]:
        self.lookups += 1
        return self.data[index]

    def __iter__(self) -> Iterator[int]:
        for index in range(len(self.data)):
            self.lookups += 1
            yield self.data[index]


class CountingWeight(float):
    """A weight that records the additions and comparisons made on it.

    A float subclass, so `itertools.accumulate` and the C `bisect_right` both
    reach these methods: a subclass's reflected operation takes priority.
    """

    additions = 0
    comparisons = 0

    @classmethod
    def reset(cls) -> None:
        cls.additions = 0
        cls.comparisons = 0

    def __add__(self, other: float) -> CountingWeight:
        CountingWeight.additions += 1
        return CountingWeight(float(self) + float(other))

    def __radd__(self, other: float) -> CountingWeight:
        return self.__add__(other)

    def __lt__(self, other: float) -> bool:
        CountingWeight.comparisons += 1
        return float(self) < float(other)

    def __gt__(self, other: float) -> bool:
        CountingWeight.comparisons += 1
        return float(self) > float(other)

    def __le__(self, other: float) -> bool:
        CountingWeight.comparisons += 1
        return float(self) <= float(other)

    def __ge__(self, other: float) -> bool:
        CountingWeight.comparisons += 1
        return float(self) >= float(other)


class CountingInt(int):
    """A count that records additions and comparisons, as `CountingWeight` does."""

    additions = 0
    comparisons = 0

    @classmethod
    def reset(cls) -> None:
        cls.additions = 0
        cls.comparisons = 0

    def __add__(self, other: int) -> CountingInt:
        CountingInt.additions += 1
        return CountingInt(int(self) + int(other))

    def __radd__(self, other: int) -> CountingInt:
        return self.__add__(other)

    def __lt__(self, other: int) -> bool:
        CountingInt.comparisons += 1
        return int(self) < int(other)

    def __gt__(self, other: int) -> bool:
        CountingInt.comparisons += 1
        return int(self) > int(other)

    def __le__(self, other: int) -> bool:
        CountingInt.comparisons += 1
        return int(self) <= int(other)

    def __ge__(self, other: int) -> bool:
        CountingInt.comparisons += 1
        return int(self) >= int(other)


def peak_bytes(operation: Callable[[], Any]) -> int:
    """Peak traced allocation during one call."""
    tracemalloc.start()
    try:
        operation()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def per_call(operation: Callable[[], Any], number: int = 1000, repeat: int = 5) -> float:
    """Seconds per call, taking the best of several runs."""
    return min(timeit.repeat(operation, number=number, repeat=repeat)) / number


class TestIntegersAndBytes:
    """`random()` | O(1); `getrandbits(w)` | O(w) | O(w); `randbytes(b)` |
    O(b) | O(b), one `getrandbits(8 * b)`."""

    def test_random_takes_exactly_one_draw(self) -> None:
        rng = CountingRandom(1)
        rng.reset()
        value = rng.random()

        assert (rng.random_calls, rng.getrandbits_calls) == (1, 0)
        assert 0.0 <= value < 1.0

    def test_getrandbits_returns_at_most_the_width_asked_for(self) -> None:
        for bits in (1, 8, 64, 10_000):
            assert 0 <= random.getrandbits(bits) < 1 << bits

    def test_getrandbits_space_grows_with_the_bit_count(self) -> None:
        small = sys.getsizeof(random.getrandbits(10_000))
        large = sys.getsizeof(random.getrandbits(100_000))

        assert 8 < large / small < 12, f"10x the bits: {small} bytes vs {large} bytes"

    @pytest.mark.timing
    def test_getrandbits_time_grows_with_the_bit_count(self) -> None:
        small = per_call(lambda: random.getrandbits(10_000), number=200)
        large = per_call(lambda: random.getrandbits(1_000_000), number=20)

        assert large > small * 20, f"100x the bits: 10k {small:.2e}s, 1M {large:.2e}s"

    def test_randbytes_is_one_getrandbits_call(self) -> None:
        for count in (1, 10_000):
            rng = CountingRandom(7)
            rng.reset()
            assert len(rng.randbytes(count)) == count
            assert rng.widths == [8 * count]

    @pytest.mark.timing
    def test_randbytes_time_grows_with_the_byte_count(self) -> None:
        small = per_call(lambda: random.randbytes(10_000), number=200)
        large = per_call(lambda: random.randbytes(1_000_000), number=20)

        assert large > small * 20, f"100x the bytes: 10k {small:.2e}s, 1M {large:.2e}s"


class TestBoundedIntegersCarryTheBitWidth:
    """`randrange` and `randint` | O(w) expected | O(w).

    The draw count is a small constant whatever the bound, which is the
    rejection loop's "expected"; the cost of one draw, and of the value
    built, follows w.
    """

    def test_randint_takes_under_two_draws_per_value(self) -> None:
        narrow = draws_for(lambda rng: [rng.randint(1, 10) for _ in range(10_000)])
        wide = draws_for(lambda rng: [rng.randint(1, 10**18) for _ in range(10_000)])

        assert 10_000 <= narrow < 20_000, f"{narrow} draws for 10,000 values"
        assert 10_000 <= wide < 20_000, f"{wide} draws for 10,000 values"

    def test_rejection_is_at_most_half_at_every_magnitude(self) -> None:
        """2**64 and 2**64 + 1 are the worst case: half of all draws fall outside."""
        calls = 5_000
        counts = {
            high: draws_for(lambda rng, hi=high: [rng.randrange(hi) for _ in range(calls)])
            for high in (10, 10**6, 10**18, 2**64, 2**64 + 1)
        }

        assert all(calls <= count < 2.2 * calls for count in counts.values()), (
            f"draws per call: { {high: count / calls for high, count in counts.items()} }"
        )

    def test_a_wide_bound_builds_a_wide_integer(self) -> None:
        narrow = sys.getsizeof(random.randrange(1, 1 << 10_000))
        wide = sys.getsizeof(random.randrange(1, 1 << 100_000))

        assert 8 < wide / narrow < 12, f"10x the bound's width: {narrow} vs {wide} bytes"

    def test_a_wide_start_builds_a_wide_result(self) -> None:
        """A two-element range based at 2**100000 still builds 100,000 bits."""
        sizes = [
            sys.getsizeof(random.randrange(1 << width, (1 << width) + 2)) for width in (10, 100_000)
        ]

        assert sizes[1] > sizes[0] * 100, f"{sizes[0]} bytes at 10 bits, {sizes[1]} at 100,000"

    @pytest.mark.timing
    def test_a_wide_bound_costs_proportionally_more_time(self) -> None:
        narrow = per_call(lambda: random.randrange(1, 1 << 10_000), number=2_000)
        wide = per_call(lambda: random.randrange(1, 1 << 1_000_000), number=20)

        assert wide > narrow * 20, f"100x the width: 10k {narrow:.2e}s, 1M {wide:.2e}s"

    @pytest.mark.timing
    def test_a_wide_start_costs_more_time_too(self) -> None:
        narrow_start, wide_start = 1 << 10, 1 << 1_000_000

        narrow = per_call(lambda: random.randrange(narrow_start, narrow_start + 2), number=2_000)
        wide = per_call(lambda: random.randrange(wide_start, wide_start + 2), number=20)

        assert wide > narrow * 20, f"10-bit start {narrow:.2e}s, 1M-bit start {wide:.2e}s"

    def test_a_sequence_index_never_reaches_that_width(self) -> None:
        """The sequence rows carry no w: `len()` bounds what reaches `getrandbits`."""
        indexing = CountingRandom(1)
        indexing.reset()
        indexing.choice(range(2**62))
        indexing.shuffle([0] * 100)
        indexing.sample(range(2**62), 5)

        bound = CountingRandom(1)
        bound.reset()
        bound.randrange(1 << 100_000)

        assert max(indexing.widths) <= 64, f"index widths up to {max(indexing.widths)} bits"
        assert max(bound.widths) >= 100_000, f"bound widths up to {max(bound.widths)} bits"

    def test_a_counts_total_must_fit_a_word_too(self) -> None:
        with pytest.raises(OverflowError):
            random.sample(["a", "b"], 1, counts=[sys.maxsize, 1])

    def test_a_step_keeps_the_draw_count_comparable(self) -> None:
        plain = draws_for(lambda rng: [rng.randrange(0, 100) for _ in range(5_000)])
        stepped = draws_for(lambda rng: [rng.randrange(0, 100, 7) for _ in range(5_000)])

        assert max(plain, stepped) < min(plain, stepped) * 1.5, f"{plain} vs {stepped} draws"

    @pytest.mark.timing
    def test_a_step_is_superlinear_where_the_unit_step_is_not(self) -> None:
        """The stepped row's `//` and `*` on w-bit operands.

        The unit-step path is shifts and an addition; a step adds a division
        and a multiplication. 3.10 and 3.11 divide by schoolbook; from 3.12
        `long_divmod` hands off to `_pylong.int_divmod` once the divisor
        passes 300 digits, which the wide end reaches. Comparing growth with
        the unit-step path in the same run keeps the assertion independent of
        which division ran.
        """
        narrow, wide = 10_000, 1_000_000
        stops = {bits: (1 << bits) - 1 for bits in (narrow, wide)}
        steps = {bits: (1 << (bits // 2)) - 1 for bits in (narrow, wide)}

        stepped = {
            bits: per_call(
                lambda s=stops[bits], st=steps[bits]: random.randrange(0, s, st),
                number=50 if bits == narrow else 1,
                repeat=3,
            )
            for bits in (narrow, wide)
        }
        unit = {
            bits: per_call(
                lambda s=stops[bits]: random.randrange(0, s),
                number=1_000 if bits == narrow else 50,
                repeat=3,
            )
            for bits in (narrow, wide)
        }

        stepped_growth = stepped[wide] / stepped[narrow]
        unit_growth = unit[wide] / unit[narrow]
        report = (
            f"unit {unit[narrow]:.2e}s -> {unit[wide]:.2e}s (x{unit_growth:.0f}), "
            f"stepped {stepped[narrow]:.2e}s -> {stepped[wide]:.2e}s (x{stepped_growth:.0f})"
        )

        assert unit_growth < 200, f"the unit-step path should track w: {report}"
        assert stepped_growth > unit_growth * 3, f"the stepped path should outgrow w: {report}"


class TestChoice:
    """`choice(seq)` | O(1) expected | O(1) | one index lookup."""

    def test_one_lookup_however_long_the_sequence(self) -> None:
        for size in (10, 100_000):
            population = CountingSequence(list(range(size)))
            random.Random(3).choice(population)

            assert population.lookups == 1, f"size {size} took {population.lookups} lookups"

    def test_choosing_from_a_huge_range_does_not_build_it(self) -> None:
        peak = peak_bytes(lambda: random.choice(range(10**9)))

        assert peak < 2_000, f"a built range would be gigabytes; peak was {peak} bytes"


class TestChoices:
    """`choices()`: O(k) unweighted, O(n + k log n) with `weights=` on every
    call, O(k log n) with `cum_weights=`."""

    def test_unweighted_choices_indexes_once_per_value(self) -> None:
        population = CountingSequence(list(range(100_000)))
        random.Random(3).choices(population, k=25)

        assert population.lookups == 25, "the population is indexed, never copied"

    def test_unweighted_choices_takes_one_draw_per_value(self) -> None:
        assert draws_for(lambda rng: rng.choices(range(1000), k=250)) == 250

    def test_choices_draws_with_replacement(self) -> None:
        drawn = random.Random(3).choices(range(3), k=30)

        assert len(drawn) == 30
        assert len(set(drawn)) < 30

    def test_weights_are_accumulated_once_per_call_whatever_k(self) -> None:
        counts = []
        for k in (1, 100):
            CountingWeight.reset()
            weights = [CountingWeight(1.0)] * 512
            random.Random(3).choices(range(512), weights=weights, k=k)
            counts.append(CountingWeight.additions)

        assert counts[0] == counts[1], f"k=1 made {counts[0]} additions, k=100 {counts[1]}"
        assert 512 <= counts[0] <= 513, f"one pass over 512 weights, got {counts[0]}"

    def test_weights_are_accumulated_again_on_every_call(self) -> None:
        """Why `cum_weights=` pays when the same weights serve many calls."""
        weights = [CountingWeight(1.0)] * 512
        rng = random.Random(3)

        CountingWeight.reset()
        rng.choices(range(512), weights=weights, k=1)
        one_call = CountingWeight.additions
        CountingWeight.reset()
        rng.choices(range(512), weights=weights, k=1)
        rng.choices(range(512), weights=weights, k=1)

        assert CountingWeight.additions == 2 * one_call >= 1_024

    def test_each_weighted_draw_is_a_bisection(self) -> None:
        draws = 10
        for size in (64, 4096):
            CountingWeight.reset()
            weights = [CountingWeight(1.0)] * size
            random.Random(3).choices(range(size), weights=weights, k=draws)

            expected = draws * (size.bit_length() - 1)
            assert expected <= CountingWeight.comparisons <= expected + 3, (
                f"n={size}: about {expected} comparisons, measured {CountingWeight.comparisons}"
            )
        assert CountingWeight.comparisons < draws * 4096 / 100, "a scan would take n per draw"

    def test_cum_weights_skips_the_accumulation(self) -> None:
        """Additions do not follow n; the bisection is unchanged.

        The exact count is not pinned: it is `cum_weights[-1] + 0.0`, and an
        equivalent conversion with no overloaded addition would still be
        O(k log n).
        """
        draws = 10
        additions: dict[int, int] = {}
        comparisons: dict[int, int] = {}

        for size in (512, 4096):
            prepared = [CountingWeight(float(index + 1)) for index in range(size)]
            population = CountingSequence(list(range(size)))

            CountingWeight.reset()
            random.Random(3).choices(population, cum_weights=prepared, k=draws)

            additions[size] = CountingWeight.additions
            comparisons[size] = CountingWeight.comparisons
            assert population.lookups == draws, "one lookup per draw, no copy"

        assert additions[512] == additions[4096] < draws, f"additions: {additions}"
        for size, measured in comparisons.items():
            expected = draws * (size.bit_length() - 1)
            assert expected <= measured <= expected + 3, (
                f"n={size}: about {expected} comparisons, measured {measured}"
            )


class TestSampleFollowsK:
    """`sample(population, k)` | O(k) expected | O(k) | independent of n."""

    @staticmethod
    def _lookups(size: int, drawn: int) -> int:
        population = CountingSequence(list(range(size)))
        random.Random(5).sample(population, drawn)
        return population.lookups

    def test_a_small_k_indexes_without_copying(self) -> None:
        assert self._lookups(10_000, 5) == 5

    def test_the_copy_threshold_on_the_population_side(self) -> None:
        """At k=1 the set is a fixed 21: 21 elements are copied, 22 are not."""
        assert self._lookups(21, 1) == 21
        assert self._lookups(22, 1) == 1

    def test_the_copy_threshold_on_the_k_side(self) -> None:
        """At n=100, k=20 is indexed and k=50 copied."""
        assert self._lookups(100, 20) == 20
        assert self._lookups(100, 50) == 100

    def test_the_copy_is_never_more_than_a_constant_times_k(self) -> None:
        """Why the row is O(k) rather than O(n): only a population no bigger
        than the k-sized set is copied. Lib/random.py sizes that set as 21,
        plus 4 ** ceil(log4(3k)) past k=5, which is under 21 + 12k."""
        for drawn in (1, 10, 100):
            worst = max(self._lookups(size, drawn) for size in range(drawn, 2_001, 7))
            assert worst <= 21 + 12 * drawn, f"k={drawn} took up to {worst} lookups"

    def test_the_peak_does_not_follow_the_population(self) -> None:
        small_list = list(range(20_000))
        large_list = list(range(200_000))
        random.sample(small_list, 10)

        small = peak_bytes(lambda: random.sample(small_list, 10))
        large = peak_bytes(lambda: random.sample(large_list, 10))

        assert large < small * 2 + 500, f"n=20,000 {small} bytes, n=200,000 {large} bytes"

    def test_a_huge_range_is_not_built(self) -> None:
        peak = peak_bytes(lambda: random.sample(range(10**7), 10))

        assert peak < 5_000, f"peak was {peak} bytes"

    def test_about_one_draw_per_value(self) -> None:
        drawn = draws_for(lambda rng: rng.sample(range(10**6), 1_000))

        assert 1_000 <= drawn < 2_000, f"expected near k draws, got {drawn}"

    def test_sample_is_without_replacement_and_leaves_the_original(self) -> None:
        original = list(range(100))
        drawn = random.Random(5).sample(original, 40)

        assert len(set(drawn)) == 40
        assert original == list(range(100))

    def test_counts_indexes_the_population_once_per_value(self) -> None:
        population = CountingSequence(list(range(500)))
        random.Random(5).sample(population, 7, counts=[3] * 500)

        assert population.lookups == 7, "counts are accumulated, the population is indexed"

    def test_counts_are_accumulated_once_then_bisected_per_value(self) -> None:
        drawn = 10
        for size in (64, 4096):
            counts = [CountingInt(3)] * size
            CountingInt.reset()

            random.Random(5).sample(range(size), drawn, counts=counts)

            assert CountingInt.additions == size - 1, f"n={size}: {CountingInt.additions}"
            expected = drawn * (size.bit_length() - 1)
            assert expected <= CountingInt.comparisons <= expected + drawn, (
                f"n={size}: about {expected} comparisons, measured {CountingInt.comparisons}"
            )

    def test_a_dict_is_rejected_and_a_set_from_3_11(self) -> None:
        with pytest.raises(TypeError, match="must be a sequence"):
            random.sample({1: "a", 2: "b"}, 1)  # type: ignore[arg-type]

        if sys.version_info >= (3, 11):
            with pytest.raises(TypeError, match="must be a sequence"):
                random.sample({1, 2, 3, 4, 5}, 2)  # type: ignore[arg-type]
        else:
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                random.sample({1, 2, 3, 4, 5}, 2)  # type: ignore[arg-type]
            assert any(issubclass(w.category, DeprecationWarning) for w in caught)


class TestShuffle:
    """`shuffle(x)` | O(n) expected | O(1) | in place."""

    def test_shuffle_is_in_place(self) -> None:
        items = list(range(50))
        identity = id(items)

        random.Random(9).shuffle(items)

        assert id(items) == identity
        assert sorted(items) == list(range(50))

    def test_shuffle_takes_about_one_draw_per_element(self) -> None:
        small = draws_for(lambda rng: rng.shuffle(list(range(1_000))))
        large = draws_for(lambda rng: rng.shuffle(list(range(8_000))))

        assert 999 <= small < 2_000, f"expected near n draws, got {small}"
        assert 6 < large / small < 10, f"n=1,000 {small} draws, n=8,000 {large} draws"

    def test_shuffle_peak_does_not_follow_the_list(self) -> None:
        small_list = list(range(20_000))
        large_list = list(range(200_000))

        small = peak_bytes(lambda: random.shuffle(small_list))
        large = peak_bytes(lambda: random.shuffle(large_list))

        assert max(small, large) < 5_000, f"n=20,000 {small} bytes, n=200,000 {large} bytes"


class TestDistributions:
    """One draw for the closed-form rows, a small constant mean for the
    rejection loops at every parameter tried."""

    CLOSED_FORM: dict[str, Callable[[random.Random], float]] = {
        "uniform": lambda rng: rng.uniform(0.0, 1.0),
        "triangular": lambda rng: rng.triangular(0.0, 1.0, 0.5),
        "expovariate": lambda rng: rng.expovariate(1.0),
        "paretovariate": lambda rng: rng.paretovariate(2.0),
        "weibullvariate": lambda rng: rng.weibullvariate(1.0, 2.0),
    }

    REJECTION: dict[str, Callable[[random.Random], float]] = {
        "normalvariate": lambda rng: rng.normalvariate(0.0, 1.0),
        "lognormvariate": lambda rng: rng.lognormvariate(0.0, 1.0),
        **{
            f"gammavariate({alpha})": (lambda rng, a=alpha: rng.gammavariate(a, 1.0))
            for alpha in (0.01, 0.5, 1.0, 1.01, 10.0, 1e6)
        },
        **{
            f"vonmisesvariate({kappa})": (lambda rng, k=kappa: rng.vonmisesvariate(0.0, k))
            for kappa in (1e-7, 0.1, 10.0, 1e6)
        },
        **{
            f"betavariate({alpha})": (lambda rng, a=alpha: rng.betavariate(a, a))
            for alpha in (0.01, 0.5, 1_000.0)
        },
        "betavariate(2, 5)": lambda rng: rng.betavariate(2.0, 5.0),
    }

    @pytest.mark.parametrize("name", sorted(CLOSED_FORM))
    def test_a_closed_form_distribution_takes_exactly_one_draw(self, name: str) -> None:
        variate = self.CLOSED_FORM[name]
        drawn = draws_for(lambda rng: [variate(rng) for _ in range(2_000)])

        assert drawn == 2_000, f"{name}: {drawn / 2_000} draws per value"

    @pytest.mark.parametrize("name", sorted(REJECTION))
    def test_a_rejection_loop_averages_a_small_constant(self, name: str) -> None:
        variate = self.REJECTION[name]
        drawn = draws_for(lambda rng: [variate(rng) for _ in range(2_000)])

        assert 1.0 <= drawn / 2_000 < 8.0, f"{name}: {drawn / 2_000:.2f} draws per value"

    @pytest.mark.skipif(
        not hasattr(random, "binomialvariate"), reason="version: binomialvariate is 3.12+"
    )
    @pytest.mark.parametrize(
        ("trials", "probability"),
        [(5, 0.5), (19, 0.5), (21, 0.5), (10**6, 0.5), (10**12, 0.3), (10**12, 1e-11)]
        + [(10**9, 0.999999)],
    )
    def test_binomialvariate_draws_do_not_follow_the_trial_count(
        self, trials: int, probability: float
    ) -> None:
        """Both branches: the geometric loop below n*p = 10, BTRS above."""
        drawn = draws_for(
            lambda rng: [
                rng.binomialvariate(trials, probability)  # type: ignore[attr-defined]
                for _ in range(1_000)
            ]
        )

        assert drawn < 12_000, f"n={trials} p={probability}: {drawn / 1_000} draws per value"

    def test_binomialvariate_exists_from_3_12(self) -> None:
        assert hasattr(random, "binomialvariate") == (sys.version_info >= (3, 12))

    def test_gauss_makes_values_in_pairs(self) -> None:
        one = draws_for(lambda rng: rng.gauss(0.0, 1.0))
        two = draws_for(lambda rng: [rng.gauss(0.0, 1.0) for _ in range(2)])
        many = draws_for(lambda rng: [rng.gauss(0.0, 1.0) for _ in range(1_000)])

        assert one == two == 2, f"a pair costs two draws: {one} then {two}"
        assert many == 1_000, f"one draw per value thereafter, got {many}"

    def test_the_gauss_spare_lives_in_the_generator(self) -> None:
        rng = random.Random(11)
        assert rng.getstate()[2] is None

        rng.gauss(0.0, 1.0)

        assert rng.getstate()[2] is not None

    def test_normalvariate_keeps_nothing(self) -> None:
        rng = random.Random(11)
        rng.normalvariate(0.0, 1.0)

        assert rng.getstate()[2] is None


class TestSeedingAndState:
    """`seed(a)` | O(s) | O(s); `getstate()` and `setstate()` | O(1)."""

    def test_the_same_seed_reproduces_the_sequence(self) -> None:
        random.seed(42)
        first = [random.random(), random.randint(1, 100)]
        random.seed(42)

        assert [random.random(), random.randint(1, 100)] == first

    def test_a_str_seed_costs_its_length_in_space(self) -> None:
        rng = random.Random()
        short, long = "x" * 100_000, "x" * 1_000_000
        rng.seed(short)

        small = peak_bytes(lambda: rng.seed(short))
        large = peak_bytes(lambda: rng.seed(long))

        assert 5 < large / small < 20, f"100k chars {small} bytes, 1M chars {large} bytes"

    def test_an_int_seed_costs_its_bit_width_in_space(self) -> None:
        rng = random.Random()
        narrow, wide = 1 << 100_000, 1 << 1_000_000
        rng.seed(narrow)

        small = peak_bytes(lambda: rng.seed(narrow))
        large = peak_bytes(lambda: rng.seed(wide))

        assert 8 < large / small < 12, f"100k bits {small} bytes, 1M bits {large} bytes"

    @pytest.mark.timing
    def test_a_str_seed_costs_its_length_in_time(self) -> None:
        rng = random.Random()
        short, long = "x" * 100_000, "x" * 1_000_000
        small = per_call(lambda: rng.seed(short), number=100)
        large = per_call(lambda: rng.seed(long), number=20)

        assert large > small * 5, f"100k chars {small:.2e}s, 1M chars {large:.2e}s"

    def test_the_state_is_the_same_size_whatever_the_seed_or_history(self) -> None:
        tiny = random.Random(1)
        huge = random.Random("x" * 1_000_000)
        for _ in range(10_000):
            huge.random()

        assert len(tiny.getstate()[1]) == len(huge.getstate()[1]) == 625
        assert all(0 <= word < 2**32 for word in huge.getstate()[1][:624])

    def test_getstate_and_setstate_round_trip(self) -> None:
        state = random.getstate()
        first = [random.random(), random.randint(1, 100)]
        random.setstate(state)

        assert [random.random(), random.randint(1, 100)] == first


class TestRandomInstances:
    """`Random(x)` | O(s) | O(s): an independent generator; the module
    functions are bound methods of one hidden instance."""

    def test_two_instances_do_not_disturb_each_other(self) -> None:
        first, second = random.Random(42), random.Random(43)
        expected = random.Random(42).random()

        for _ in range(10):
            second.random()

        assert first.random() == expected

    def test_the_module_functions_are_one_hidden_instance(self) -> None:
        hidden = random._inst  # type: ignore[attr-defined]  # noqa: SLF001

        assert random.random.__self__ is hidden  # type: ignore[attr-defined]
        assert random.shuffle.__self__ is hidden  # type: ignore[attr-defined]
        random.seed(1234)
        assert random.random() == random.Random(1234).random()

    def test_construction_is_a_seed(self) -> None:
        seeded = random.Random()
        seeded.seed("abc")
        assert random.Random("abc").getstate() == seeded.getstate()


class TestSystemRandom:
    """`SystemRandom`: one `os.urandom()` call per draw, and no state."""

    @pytest.fixture
    def urandom_calls(self, monkeypatch: pytest.MonkeyPatch) -> list[int]:
        calls: list[int] = []
        original = random._urandom  # type: ignore[attr-defined]  # noqa: SLF001

        def recording(size: int) -> bytes:
            calls.append(size)
            return original(size)

        monkeypatch.setattr(random, "_urandom", recording)
        return calls

    def test_one_call_per_float(self, urandom_calls: list[int]) -> None:
        source = random.SystemRandom()
        source.random()
        source.uniform(0.0, 1.0)
        source.expovariate(1.0)

        assert len(urandom_calls) == 3

    def test_getrandbits_reads_the_bytes_holding_w_bits(self, urandom_calls: list[int]) -> None:
        source = random.SystemRandom()
        for bits in (1, 64, 10_001):
            assert 0 <= source.getrandbits(bits) < 1 << bits

        assert urandom_calls == [1, 8, 1_251]

    def test_randbytes_is_one_call_of_b_bytes(self, urandom_calls: list[int]) -> None:
        assert len(random.SystemRandom().randbytes(10_000)) == 10_000
        assert urandom_calls == [10_000]

    def test_inherited_methods_take_the_same_number_of_draws(
        self, urandom_calls: list[int]
    ) -> None:
        random.SystemRandom().shuffle(list(range(1_000)))

        assert 999 <= len(urandom_calls) < 2_000, f"{len(urandom_calls)} calls for n=1,000"

    def test_there_is_no_state_to_seed_or_save(self) -> None:
        source = random.SystemRandom()

        assert source.seed(42) is None
        with pytest.raises(NotImplementedError):
            source.getstate()
        with pytest.raises(NotImplementedError):
            source.setstate(random.getstate())


class TestThreads:
    """Independent streams: per-thread instances reproduce, the module stream
    is shared, and the `gauss()` spare can be handed out twice."""

    def test_threads_draw_from_one_shared_module_stream(self) -> None:
        """Whatever the interleaving, two threads take the first 200 values."""
        random.seed(2024)
        solo = [random.random() for _ in range(200)]

        random.seed(2024)
        collected: list[list[float]] = [[], []]

        def worker(slot: int) -> None:
            for _ in range(100):
                collected[slot].append(random.random())

        threads = [threading.Thread(target=worker, args=(slot,)) for slot in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert sorted(collected[0] + collected[1]) == sorted(solo)

    def test_a_per_thread_instance_reproduces_its_own_sequence(self) -> None:
        expected = {seed: random.Random(seed).random() for seed in range(10)}
        produced: dict[int, float] = {}

        def worker(seed: int) -> None:
            produced[seed] = random.Random(seed).random()

        threads = [threading.Thread(target=worker, args=(seed,)) for seed in range(10)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert produced == expected

    def test_concurrent_module_draws_stay_well_formed(self) -> None:
        values: list[float] = []
        lock = threading.Lock()

        def worker() -> None:
            drawn = [random.random() for _ in range(500)]
            with lock:
                values.extend(drawn)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(values) == 4_000
        assert all(0.0 <= value < 1.0 for value in values)

    def test_two_gauss_callers_can_be_handed_the_same_spare(self) -> None:
        """Both read the spare before either clears it, modelled with setstate."""
        rng = random.Random(11)
        rng.gauss(0.0, 1.0)

        before_either_call = rng.getstate()
        first = rng.gauss(0.0, 1.0)
        rng.setstate(before_either_call)
        second = rng.gauss(0.0, 1.0)

        assert first == second


class TestCommandLine:
    """`random.main(arg_list=None)` | O(a) | O(a) | 3.13+."""

    def test_main_exists_from_3_13(self) -> None:
        assert hasattr(random, "main") == (sys.version_info >= (3, 13))

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="version: random.main is 3.13+")
    def test_main_makes_one_choice_randint_or_uniform(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        main: Callable[[list[str]], Any] = random.main  # type: ignore[attr-defined]
        calls: list[str] = []
        for name in ("choice", "randint", "uniform"):
            original = getattr(random, name)

            def recording(*args: Any, _name: str = name, _original: Any = original) -> Any:
                calls.append(_name)
                return _original(*args)

            monkeypatch.setattr(random, name, recording)

        cases: list[tuple[list[str], str, Callable[[Any], bool]]] = [
            (["-c", "a", "b", "c"], "choice", lambda v: v in {"a", "b", "c"}),
            (["a", "b"], "choice", lambda v: v in {"a", "b"}),
            (["a b c"], "choice", lambda v: v in {"a", "b", "c"}),
            (["7"], "randint", lambda v: v in range(1, 8)),
            (["2.5"], "uniform", lambda v: isinstance(v, float) and 0.0 <= v <= 2.5),
        ]
        for arguments, expected, check in cases:
            calls.clear()
            assert check(main(arguments)), arguments
            assert calls == [expected], f"{arguments} made {calls}"

        calls.clear()
        assert main([]).startswith("usage:")
        assert calls == []

    @pytest.mark.skipif(sys.version_info < (3, 13), reason="version: random.main is 3.13+")
    def test_main_follows_the_arguments(self) -> None:
        main: Callable[[list[str]], Any] = random.main  # type: ignore[attr-defined]
        small = ["-c", *(f"x{index:06d}" for index in range(20_000))]
        large = ["-c", *(f"x{index:06d}" for index in range(200_000))]
        main(small)

        peaks = [peak_bytes(lambda: main(small)), peak_bytes(lambda: main(large))]

        assert peaks[1] > peaks[0] * 5, f"10x the arguments: {peaks}"


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


class TestReservoirSampling:
    """The page's reservoir sampler: O(n) expected time, O(k) space."""

    @staticmethod
    def sampler() -> Callable[..., list[int]]:
        source = next(s for _, s in _blocks() if "def reservoir_sample" in s)
        namespace: dict[str, Any] = {}
        exec(compile(source, str(PAGE), "exec"), namespace)  # noqa: S102
        return namespace["reservoir_sample"]

    def test_one_draw_per_item_past_the_first_k(self) -> None:
        rng = CountingRandom(4)
        rng.reset()
        self.sampler()(iter(range(20_000)), 100, rng)

        assert 19_900 <= rng.draws < 40_000, f"about n - k draws, got {rng.draws}"

    def test_only_k_items_are_held(self) -> None:
        reservoir_sample = self.sampler()
        rng = random.Random(4)

        peak = peak_bytes(lambda: reservoir_sample(iter(range(200_000)), 100, rng))

        assert peak < 20_000, f"a 200,000-item stream would be megabytes; peak {peak} bytes"


class TestDocumentedExamples:
    """Each block runs in its own subprocess and working directory, so the
    module-level generator's state cannot leak between them, and asserts its
    own result. No block touches the filesystem, the network or stdin."""

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
        line, source = next((n, s) for n, s in _blocks() if "len(state[1]) == 625" in s)
        mutated = source.replace("len(state[1]) == 625", "len(state[1]) == 624", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
