"""Tests to verify documented behaviour of the random module.

Almost everything here is counted rather than timed. Every operation in this
module reaches the Mersenne Twister through ``random()`` or ``getrandbits()``,
so a ``Random`` subclass that counts those two calls settles most of the page's
bounds with no tolerance at all: how many draws an operation makes, whether it
copies its population, and whether a rejection loop is running.

Three claims did not survive that check:

* ``sample()`` was documented as copying the population "when k is large or
  input is set/dict". Sets and dicts are not copied on any supported version -
  they raise TypeError on 3.11 through 3.14 and warn on 3.10. The copy is real,
  but neither term decides it alone: CPython sizes an n-element list against a
  set built for k, so at k=1 a population of 21 is copied and 22 is not, and at
  n=100 a k of 20 is indexed while 50 is copied. Both directions are pinned.
* ``seed()`` was documented O(1) space. A str or bytes seed becomes
  ``int.from_bytes(a + sha512(a).digest())`` - the whole input is kept, not
  just its digest - so the int and the key array built from it are both
  proportional to the seed. Measured peak rises 10x for a 10x seed, from
  3.4 KB at 1,000 characters to 3.1 MB at 1,000,000. Only the state it
  produces is fixed, at 625 words.
* Bogosort was documented "expected O(n!) time", which counts the shuffles and
  not what one costs. Each shuffle is O(n), so the expected total is O(n * n!);
  measured over 2,000 trials at n=4, the mean shuffle count is 24, matching n!.

The thread-safety note said the module-level RNG "is safe to call from multiple
threads". True of ``random()``, which is one C step, but not of ``gauss()``,
which caches its spare value in the instance and is documented in CPython as
"not thread-safe without a lock around calls". The page now says so.

Ten table rows were missing entirely, including every operation whose cost is
not constant: ``getrandbits``, ``randbytes``, ``sample(counts=...)``, and the
``cum_weights=`` form of ``choices()``, which skips the O(n) accumulation the
``weights=`` row is priced for.

Costs are counted in draws and element accesses, with an index taken as one
word. That is the model the rest of this site uses, and the split it rests on
is itself tested: what reaches ``getrandbits`` is the bit width of whatever
``_randbelow`` was given, which for a sequence is ``len(population)`` - it has
to fit a ``Py_ssize_t``, materialised or not, which is why a ``range`` argument
does not break the model - and for ``randrange`` or ``randint`` is an integer
the caller chose, with nothing bounding it. ``randrange(2**2048)`` is an
ordinary thing to write for a key and is not constant time, so those two rows
carry a bit-width term and the sequence rows do not.

``w`` is the widest integer the operation handles, not the width of the range:
``randrange`` draws its offset from the span but adds it back onto ``start``,
so a two-element range based at 2**100000 still builds a 100,000-bit result,
13,360 bytes against 28. Every test here that varies a bound also varies the
right operand - the earlier ones held ``start`` at 1 and could not have seen
this.

O(w) then holds for the unit-step path, whose work is shifts and an addition,
and not for the stepped one, which divides and multiplies w-bit operands.
CPython's long division is quadratic on 3.11, so ten times the width costs
about eighty-five times the call (78 us at 10,000 bits, 6.6 ms at 100,000,
593 ms at 1,000,000) against about ten times for the unit step; the division
dominates the multiplication, 5.7 ms against 0.9 ms at 100,000 bits. The two
forms are separate rows because of it.

Read against the 3.14 sources afterwards, which moved two things:

* ``randint`` no longer delegates to ``randrange``. Through 3.13 it was
  ``self.randrange(a, b + 1)``; 3.14 inlines ``a + self._randbelow(b - a + 1)``.
  The bound is the same either way, and the table said the mechanism, so the
  table now says the bound.
* ``long_divmod`` hands off to ``_pylong.int_divmod`` (Burnikel-Ziegler) past
  300 divisor digits from 3.12 on; 3.11 has no ``_pylong`` at all. The stepped
  path is superlinear on both, which is what the row claims, but by very
  different factors - hence a test framed as a comparison against the
  unit-step path rather than against a fixed ratio.

The rest read back clean: ``getstate`` builds ``PyTuple_New(N+1)`` for N=624,
so 625 is exact rather than measured; ``random_seed`` mallocs
``4 * ceil(bits/32)`` for the key and ``init_by_array`` loops
``max(624, key_length)`` times, which is the O(s) row in C rather than in
tracemalloc; and ``sample``'s ``setsize`` and ``choice``'s two ``len`` calls
are as counted.

Untested axes, and why:

* Element cost. Every count here uses ints. A population of objects with an
  expensive ``__getitem__`` would change the constant, not the number of
  lookups, which is what the table's terms are counted in.
* Weight type. The bisect probe uses a float subclass; integer or Decimal
  weights would take the same number of comparisons through the same C
  ``bisect_right``.
* Seed contents. Seed cost was varied by length only. It is a hash of the
  bytes, so their values cannot change the shape.

Not settled by execution:

* "Some algorithms (e.g. randrange) have changed for quality, so sequences may
  differ" - a statement about versions outside the supported range. The
  supported ones are checked against each other by the CI matrix, not here.
* `random.choices()` added in 3.6, `randbytes()` and `sample(counts=)` in 3.9:
  all present throughout 3.10-3.14, so no supported interpreter can show their
  absence. `binomialvariate()` is the one version note that is testable from
  here, and its test skips on 3.10 and 3.11, where it does not exist.
* "Assuming random() is cryptographically secure" - the Mersenne Twister's
  predictability is not something a unit test should demonstrate.
"""

from __future__ import annotations

import math
import pathlib
import random
import re
import statistics
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
EXPECTED_BLOCKS = 18


class CountingRandom(random.Random):
    """A generator that records how often the core engine is asked for bits.

    Everything in the module funnels through these two methods, so counting
    them measures an operation in the unit the table is written in: draws.

    A draw is one *request*, not one word of Mersenne Twister output.
    `random()` costs two 32-bit words and `getrandbits(k)` costs ceil(k/32)
    of them (Modules/_randommodule.c), which is the whole reason the rows
    that take an integer bound carry `w` while the sequence rows do not - a
    counter alone cannot see that, so the width tests below use the clock and
    `sys.getsizeof`.
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
    """A sequence that records every index lookup, including copies.

    ``list(self)`` goes through ``__getitem__`` too, so a population copy
    shows up as n lookups and index-only access as k.
    """

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

    A float subclass, so ``itertools.accumulate`` and the C ``bisect_right``
    both reach these methods: Python gives a subclass's reflected operation
    priority, which is what makes the comparisons inside bisect visible.
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


def peak_bytes(operation: Callable[[], Any]) -> int:
    """Peak Python allocation during one call, with the tracer left off."""
    tracemalloc.start()
    try:
        operation()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak


def per_call(operation: Callable[[], Any], number: int = 1000, repeat: int = 5) -> float:
    """Seconds per call, taking the best of several runs."""
    return min(timeit.repeat(operation, number=number, repeat=repeat)) / number


class TestCoreGenerator:
    """`random()`, `getrandbits(b)` and `randbytes(b)`."""

    def test_random_takes_exactly_one_draw(self) -> None:
        rng = CountingRandom(1)
        rng.reset()
        value = rng.random()

        assert (rng.random_calls, rng.getrandbits_calls) == (1, 0)
        assert 0.0 <= value < 1.0

    def test_getrandbits_returns_the_width_it_was_asked_for(self) -> None:
        for bits in (1, 8, 64, 10_000):
            assert random.getrandbits(bits).bit_length() <= bits

    def test_getrandbits_space_grows_with_the_bit_count(self) -> None:
        """The O(b) space half of the row, from the object it returns."""
        small = sys.getsizeof(random.getrandbits(10_000))
        large = sys.getsizeof(random.getrandbits(100_000))

        assert 8 < large / small < 12, (
            f"ten times the bits should be about ten times the int: {small} bytes vs {large} bytes"
        )

    @pytest.mark.timing
    def test_getrandbits_time_grows_with_the_bit_count(self) -> None:
        small = per_call(lambda: random.getrandbits(10_000), number=200)
        large = per_call(lambda: random.getrandbits(1_000_000), number=20)

        assert large > small * 20, (
            f"a hundred times the bits is not a constant-time request: "
            f"10k bits {small:.2e}s, 1M bits {large:.2e}s"
        )

    def test_randbytes_returns_the_length_it_was_asked_for(self) -> None:
        for count in (0, 1, 100, 10_000):
            assert len(random.randbytes(count)) == count

    def test_randbytes_makes_one_request_however_many_bytes(self) -> None:
        """O(count) is in the bits moved, not in the requests made.

        `randbytes(n)` is `getrandbits(n * 8).to_bytes(...)`, so it is always
        one call at this level, whatever it costs underneath.
        """
        assert draws_for(lambda rng: rng.randbytes(1)) == 1
        assert draws_for(lambda rng: rng.randbytes(10_000)) == 1

    @pytest.mark.timing
    def test_randbytes_time_grows_with_the_byte_count(self) -> None:
        small = per_call(lambda: random.randbytes(10_000), number=200)
        large = per_call(lambda: random.randbytes(1_000_000), number=20)

        assert large > small * 20, (
            f"a hundred times the bytes is not a constant-time request: "
            f"10k bytes {small:.2e}s, 1M bytes {large:.2e}s"
        )


class TestBoundedIntegers:
    """`randrange` and `randint`: O(w) expected in the bound's bit width.

    Two separate things scale here, and the table needs both. The number of
    draws is expected constant however wide the bound is, which is what the
    rejection loop buys; the cost of one draw follows `w`, because
    `_randbelow(n)` asks `getrandbits` for `n.bit_length()` bits.
    """

    def test_a_draw_costs_a_constant_number_of_requests(self) -> None:
        """Expected, not worst case: the loop retries, but rarely."""
        narrow = draws_for(lambda rng: [rng.randint(1, 10) for _ in range(10_000)])
        wide = draws_for(lambda rng: [rng.randint(1, 10**18) for _ in range(10_000)])

        assert 10_000 <= narrow < 20_000, f"expected under two draws per call, got {narrow}"
        assert 10_000 <= wide < 20_000, f"expected under two draws per call, got {wide}"

    def test_the_range_magnitude_does_not_change_the_draw_count(self) -> None:
        """The retry rate follows where the range sits between two powers of
        two, never its magnitude: fewer than half the draws can be rejected
        however wide the bound is.
        """
        calls = 5_000
        counts = {
            high: draws_for(lambda rng, hi=high: [rng.randrange(hi) for _ in range(calls)])
            for high in (10, 10**6, 10**18, 2**64 + 1)
        }

        assert all(calls <= count < 2 * calls for count in counts.values()), (
            f"expected under two draws per call at every magnitude, got "
            f"{ {high: count / calls for high, count in counts.items()} }"
        )

    def test_a_wide_bound_costs_a_wide_integer(self) -> None:
        """The O(w) space term, from the value the draw has to build.

        A population index is a word and this never bites, but a bound is an
        argument: `randrange(2**2048)` for a key really does allocate 2,048
        bits, and the row has to say so.
        """
        narrow = sys.getsizeof(random.randrange(1, 1 << 10_000))
        wide = sys.getsizeof(random.randrange(1, 1 << 100_000))

        assert 8 < wide / narrow < 12, (
            f"ten times the bound's bit width is about ten times the integer: "
            f"{narrow} bytes vs {wide} bytes"
        )

    def test_a_wide_start_costs_as_much_as_a_wide_range(self) -> None:
        """w is the widest integer handled, not the span between the ends.

        `randrange` draws the offset from the span but adds it back to
        `start`, so a two-element range based at 2**100000 still builds a
        100,000-bit result - the reason the variable is defined over the
        operands and not the range alone.
        """
        spans = [
            sys.getsizeof(random.randrange(1 << width, (1 << width) + 2)) for width in (10, 100_000)
        ]

        assert spans[1] > spans[0] * 100, (
            f"a two-element range is not a small integer when start is wide: "
            f"{spans[0]} bytes at 10 bits, {spans[1]} bytes at 100,000 bits"
        )

    @pytest.mark.timing
    def test_a_wide_bound_costs_proportionally_more_time(self) -> None:
        narrow = per_call(lambda: random.randrange(1, 1 << 10_000), number=2_000)
        wide = per_call(lambda: random.randrange(1, 1 << 1_000_000), number=20)

        assert wide > narrow * 20, (
            f"a hundred times the bit width is not a constant-time draw: "
            f"10k bits {narrow:.2e}s, 1M bits {wide:.2e}s"
        )

    @pytest.mark.timing
    def test_a_wide_start_costs_more_time_too(self) -> None:
        """The same point on the clock: the span is two, the endpoints are not."""
        narrow_start, wide_start = 1 << 10, 1 << 1_000_000

        narrow = per_call(lambda: random.randrange(narrow_start, narrow_start + 2), number=2_000)
        wide = per_call(lambda: random.randrange(wide_start, wide_start + 2), number=20)

        assert wide > narrow * 20, (
            f"the addition back onto start is the work: "
            f"10-bit start {narrow:.2e}s, 1M-bit start {wide:.2e}s"
        )

    def test_a_population_index_never_reaches_that_width(self) -> None:
        """Why the sequence rows stay at O(1) rather than carrying w.

        What reaches `getrandbits` is the argument's bit width either way.
        For a sequence it is `len(population)`, which has to fit a
        `Py_ssize_t` whether or not the elements are ever materialised - a
        `range` is the case in point. For `randrange` it is an integer the
        caller chose, and nothing bounds that.
        """
        indexing = CountingRandom(1)
        indexing.reset()
        indexing.choice(range(2**62))
        indexing.shuffle([0] * 100)

        bound = CountingRandom(1)
        bound.reset()
        bound.randrange(1 << 100_000)

        assert max(indexing.widths) <= 64, (
            f"an index into anything that fits in memory is a word: "
            f"widths up to {max(indexing.widths)} bits"
        )
        assert max(bound.widths) >= 100_000, (
            f"an integer bound is not: widths up to {max(bound.widths)} bits"
        )

    def test_a_step_does_not_change_the_draw_count(self) -> None:
        """Draws only, and on small operands.

        A step costs a division and a multiplication whose width the draw
        count cannot see - see the timing test below, which is why the
        stepped form is a row of its own.
        """
        plain = draws_for(lambda rng: [rng.randrange(0, 100) for _ in range(5_000)])
        stepped = draws_for(lambda rng: [rng.randrange(0, 100, 7) for _ in range(5_000)])

        assert max(plain, stepped) < min(plain, stepped) * 1.5, (
            f"a step is one division, not extra draws: {plain} vs {stepped}"
        )

    @pytest.mark.timing
    def test_a_step_is_superlinear_where_the_unit_step_is_not(self) -> None:
        """Why the stepped form is a separate row.

        `randrange(start, stop)` reaches the offset with shifts and an
        addition, all linear in w. A step adds `(width + step - 1) // step`
        and `step * offset`, and big-integer division is not linear. The two
        are compared over a hundredfold width so the gap survives every
        supported version: the stepped path grows x7,600 on 3.11 and x470 on
        3.14, while the unit path grows about x90 on both.

        The spread is not noise. 3.11 has no `_pylong` module, so every
        division is schoolbook and quadratic; from 3.12 `long_divmod` hands
        off to `_pylong.int_divmod` (Burnikel-Ziegler) once the divisor
        passes 300 digits and the quotient 150, which the wide end of this
        test reaches and the narrow end does not. Comparing against the
        unit-step path measured in the same run is what keeps the assertion
        independent of which algorithm ran.
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

        assert unit_growth < 200, f"the unit-step path should track w across x100: {report}"
        assert stepped_growth > unit_growth * 3, (
            f"the division should make the stepped path grow faster than w: {report}"
        )

    def test_randint_includes_both_endpoints(self) -> None:
        drawn = {random.randint(1, 3) for _ in range(200)}

        assert drawn == {1, 2, 3}


class TestChoice:
    """`random.choice(seq)` | O(1) expected | O(1) | one index lookup."""

    def test_one_lookup_however_long_the_sequence(self) -> None:
        for size in (10, 100_000):
            population = CountingSequence(list(range(size)))
            random.Random(3).choice(population)

            assert population.lookups == 1, f"size {size} took {population.lookups} lookups"

    def test_choosing_from_a_huge_range_allocates_nothing(self) -> None:
        """The page's "O(1) even for huge range!" - a range is never built out."""
        peak = peak_bytes(lambda: random.choice(range(10**9)))

        assert peak < 2_000, f"a materialised range would be gigabytes; peak was {peak} bytes"

    def test_choice_of_a_string_returns_one_character(self) -> None:
        assert random.choice("hello") in set("hello")

    def test_choice_of_an_empty_sequence_raises(self) -> None:
        """3.11 checks the length first; 3.10 lets the index lookup raise."""
        with pytest.raises(IndexError):
            random.choice([])


class TestChoices:
    """`choices()`: O(k) unweighted, O(n + k log n) weighted."""

    def test_unweighted_choices_makes_one_lookup_per_draw(self) -> None:
        population = CountingSequence(list(range(100_000)))
        random.Random(3).choices(population, k=25)

        assert population.lookups == 25, "the population is indexed, never copied"

    def test_unweighted_choices_takes_one_draw_per_selection(self) -> None:
        assert draws_for(lambda rng: rng.choices(range(1000), k=250)) == 250

    def test_weighted_choices_accumulates_the_weights_once(self) -> None:
        """The O(n) term: one pass over the weights, regardless of k."""
        counts = []
        for k in (1, 100):
            CountingWeight.reset()
            weights = [CountingWeight(1.0)] * 512
            random.Random(3).choices(range(512), weights=weights, k=k)
            counts.append(CountingWeight.additions)

        assert counts[0] == counts[1], (
            f"the accumulate should not repeat per draw: k=1 made {counts[0]} additions, "
            f"k=100 made {counts[1]}"
        )
        assert 512 <= counts[0] <= 513, f"one pass over 512 weights, got {counts[0]}"

    def test_weighted_choices_bisects_each_draw(self) -> None:
        """The k log n term, counted exactly: bisect_right probes log2(n) times."""
        draws = 10
        for size in (64, 4096):
            CountingWeight.reset()
            weights = [CountingWeight(1.0)] * size
            random.Random(3).choices(range(size), weights=weights, k=draws)

            expected = draws * (size.bit_length() - 1)
            assert expected <= CountingWeight.comparisons <= expected + 3, (
                f"n={size} should take about log2(n)={size.bit_length() - 1} comparisons "
                f"per draw, or {expected} in total; measured {CountingWeight.comparisons}"
            )

    def test_a_linear_scan_would_have_cost_far_more(self) -> None:
        """Separates O(k log n) from the O(k n) a scan of the weights costs."""
        CountingWeight.reset()
        weights = [CountingWeight(1.0)] * 4096
        random.Random(3).choices(range(4096), weights=weights, k=10)

        assert CountingWeight.comparisons < 10 * 4096 / 100, (
            f"a scan would take about {10 * 4096} comparisons; "
            f"measured {CountingWeight.comparisons}"
        )

    def test_cum_weights_skips_the_accumulation(self) -> None:
        """The `cum_weights=` row: no O(n) pass, so the population size is
        only reached through the bisect.

        The assertion is that additions do not follow n. Pinning the exact
        count would pin `cum_weights[-1] + 0.0` instead, and an equivalent
        conversion doing no overloaded addition would still be O(k log n).
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

        assert additions[512] == additions[4096] < draws, (
            f"eight times the weights should not cost more additions, and an "
            f"accumulation would cost n of them: {additions}"
        )
        for size, measured in comparisons.items():
            expected = draws * (size.bit_length() - 1)
            assert expected <= measured <= expected + 3, (
                f"the bisect is unchanged at about {expected} comparisons for "
                f"n={size}; measured {measured}"
            )

    def test_choices_draws_with_replacement(self) -> None:
        drawn = random.Random(3).choices(range(3), k=30)

        assert len(drawn) == 30
        assert len(set(drawn)) < 30, "with replacement, so repeats are expected"


class TestSample:
    """`sample()`: O(k) through an index set, O(n) when the population is copied."""

    def test_a_small_k_never_copies_the_population(self) -> None:
        population = CountingSequence(list(range(10_000)))
        random.Random(5).sample(population, 5)

        assert population.lookups == 5, "one lookup per selection, no copy"

    def test_a_large_k_copies_the_population(self) -> None:
        population = CountingSequence(list(range(100)))
        random.Random(5).sample(population, 50)

        assert population.lookups == 100, "the whole population is copied into a pool"

    @staticmethod
    def _lookups(size: int, drawn: int) -> int:
        population = CountingSequence(list(range(size)))
        random.Random(5).sample(population, drawn)
        return population.lookups

    def test_the_copy_threshold_moves_with_the_population(self) -> None:
        """CPython sizes an n-element list against a set built for k.

        Holding k at 1, where the set is a fixed 21 bytes' worth of table,
        isolates the n side of that comparison: 21 elements are copied and 22
        are not.
        """
        assert self._lookups(21, 1) == 21, "a 21-element list is cheaper than the set"
        assert self._lookups(22, 1) == 1, "one more element and the set wins"

    def test_the_copy_threshold_moves_with_k_as_well(self) -> None:
        """The other side of the same comparison, which k grows.

        Past k=5 the set's table is sized from k, so a fixed population
        crosses the threshold as k rises: at n=100, k=20 is indexed and k=50
        is copied. Neither term decides on its own.
        """
        assert self._lookups(100, 20) == 20, "the index set is still the smaller"
        assert self._lookups(100, 50) == 100, "a set for k=50 outgrows the population"

    def test_sampling_a_huge_population_stays_proportional_to_k(self) -> None:
        peak = peak_bytes(lambda: random.sample(range(10**7), 10))

        assert peak < 5_000, f"O(k), not O(n); peak was {peak} bytes"

    def test_sampling_most_of_a_population_pays_for_the_copy(self) -> None:
        small = peak_bytes(lambda: random.sample(list(range(1_000)), 500))
        large = peak_bytes(lambda: random.sample(list(range(4_000)), 2_000))

        assert large > small * 2, (
            f"the pool is a copy of the population, so it grows with n: "
            f"n=1,000 {small} bytes, n=4,000 {large} bytes"
        )

    def test_sample_is_without_replacement(self) -> None:
        drawn = random.Random(5).sample(range(100), 40)

        assert len(drawn) == len(set(drawn)) == 40

    def test_sample_leaves_the_original_untouched(self) -> None:
        original = [1, 2, 3, 4, 5]
        shuffled = random.Random(5).sample(original, k=len(original))

        assert original == [1, 2, 3, 4, 5]
        assert sorted(shuffled) == original
        assert shuffled is not original

    def test_sample_takes_about_one_draw_per_selection(self) -> None:
        drawn = draws_for(lambda rng: rng.sample(range(10**6), 1_000))

        assert 1_000 <= drawn < 2_000, f"expected near k draws, got {drawn}"

    def test_counts_accumulates_then_bisects(self) -> None:
        """The `counts=` row: an O(n) pass, then one lookup per selection."""
        population = CountingSequence(list(range(500)))
        random.Random(5).sample(population, 7, counts=[3] * 500)

        assert population.lookups == 7, "counts are accumulated, the population is indexed"

    def test_a_set_or_dict_is_not_a_population(self) -> None:
        """The claim the old note got wrong; 3.10 warns where 3.11 raises."""
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
    """`shuffle(list)` | O(n) | O(1) | in place."""

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
        assert 6 < large / small < 10, (
            f"eight times the elements should be about eight times the draws: "
            f"n=1,000 {small} draws, n=8,000 {large} draws"
        )

    def test_shuffle_peak_space_does_not_follow_the_list(self) -> None:
        small_list = list(range(20_000))
        large_list = list(range(200_000))

        small = peak_bytes(lambda: random.shuffle(small_list))
        large = peak_bytes(lambda: random.shuffle(large_list))

        assert max(small, large) < 5_000, (
            f"a Fisher-Yates swap allocates nothing per element, where copying "
            f"200,000 ints would take about 1.6 MB: n=20,000 {small} bytes, "
            f"n=200,000 {large} bytes"
        )


class TestDistributions:
    """One draw for the closed-form ones, a small constant for the loops."""

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
        "gammavariate": lambda rng: rng.gammavariate(2.0, 2.0),
        "betavariate": lambda rng: rng.betavariate(2.0, 5.0),
        "vonmisesvariate": lambda rng: rng.vonmisesvariate(0.0, 1.0),
    }

    @pytest.mark.parametrize("name", sorted(CLOSED_FORM))
    def test_a_closed_form_distribution_takes_exactly_one_draw(self, name: str) -> None:
        variate = self.CLOSED_FORM[name]
        drawn = draws_for(lambda rng: [variate(rng) for _ in range(2_000)])

        assert drawn == 2_000, f"{name} should take one draw per value, took {drawn / 2_000}"

    @pytest.mark.parametrize("name", sorted(REJECTION))
    def test_a_rejection_distribution_takes_a_small_constant(self, name: str) -> None:
        variate = self.REJECTION[name]
        drawn = draws_for(lambda rng: [variate(rng) for _ in range(2_000)])

        assert 1.0 < drawn / 2_000 < 8.0, (
            f"{name} loops, but its mean should stay a small constant: "
            f"{drawn / 2_000:.2f} draws per value"
        )

    def test_gauss_generates_values_in_pairs(self) -> None:
        """Not a rejection loop: two draws produce two values, one cached."""
        one = draws_for(lambda rng: rng.gauss(0.0, 1.0))
        two = draws_for(lambda rng: [rng.gauss(0.0, 1.0) for _ in range(2)])
        many = draws_for(lambda rng: [rng.gauss(0.0, 1.0) for _ in range(1_000)])

        assert one == two == 2, f"a pair costs two draws: {one} then {two}"
        assert many == 1_000, f"and one draw per value thereafter, got {many}"

    def test_the_spare_gauss_value_lives_in_the_generator_state(self) -> None:
        rng = random.Random(11)
        assert rng.getstate()[2] is None

        rng.gauss(0.0, 1.0)

        assert rng.getstate()[2] is not None, "the unused half of the pair is kept"

    @pytest.mark.skipif(
        not hasattr(random, "binomialvariate"), reason="binomialvariate is Python 3.12+"
    )
    def test_binomialvariate_takes_a_small_constant(self) -> None:
        """Both branches: a geometric loop under n*p=10, BTRS rejection above."""
        for trials, probability in ((5, 0.5), (10_000, 0.5), (10**6, 1e-9)):
            drawn = draws_for(
                lambda rng, n=trials, p=probability: [
                    rng.binomialvariate(n, p)  # type: ignore[attr-defined]
                    for _ in range(1_000)
                ]
            )
            assert drawn < 10_000, (
                f"n={trials} p={probability} should not scale with n: {drawn} draws "
                f"for 1,000 values"
            )


class TestSeeding:
    """`seed(a)` | O(s) | O(s) |, and the fixed state it produces."""

    def test_the_same_seed_reproduces_the_sequence(self) -> None:
        random.seed(42)
        first = [random.random(), random.randint(1, 100)]
        random.seed(42)
        second = [random.random(), random.randint(1, 100)]

        assert first == second

    def test_seed_space_follows_the_seed_length(self) -> None:
        """The corrected row: the whole seed is kept, not just its digest."""
        rng = random.Random()
        small = peak_bytes(lambda: rng.seed("x" * 100_000))
        large = peak_bytes(lambda: rng.seed("x" * 1_000_000))

        assert 5 < large / small < 20, (
            f"a ten times longer seed should cost about ten times the peak: "
            f"100k chars {small} bytes, 1M chars {large} bytes"
        )

    @pytest.mark.timing
    def test_seed_time_follows_the_seed_length(self) -> None:
        rng = random.Random()
        small = per_call(lambda: rng.seed("x" * 100_000), number=100)
        large = per_call(lambda: rng.seed("x" * 1_000_000), number=20)

        assert large > small * 5, (
            f"hashing and converting a ten times longer seed is not constant: "
            f"100k chars {small:.2e}s, 1M chars {large:.2e}s"
        )

    def test_the_state_is_the_same_size_whatever_the_seed(self) -> None:
        """The other half of the row: O(s) to seed, O(1) once seeded."""
        tiny = random.Random(1).getstate()
        huge = random.Random("x" * 1_000_000).getstate()

        assert len(tiny[1]) == len(huge[1]) == 625

    def test_getstate_and_setstate_round_trip(self) -> None:
        state = random.getstate()
        first = [random.random(), random.randint(1, 100)]
        random.setstate(state)
        second = [random.random(), random.randint(1, 100)]

        assert first == second

    def test_an_unsupported_seed_type_is_rejected(self) -> None:
        """3.11 rejects the type; 3.10 still tries to hash it, and fails."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            with pytest.raises(TypeError):
                random.seed([1, 2, 3])  # type: ignore[arg-type]


class TestIndependentStreams:
    """`Random(a)` instances, and the hidden one the module functions share."""

    def test_two_instances_do_not_disturb_each_other(self) -> None:
        first, second = random.Random(42), random.Random(43)
        expected = random.Random(42).random()

        for _ in range(10):
            second.random()

        assert first.random() == expected

    def test_the_module_functions_are_one_hidden_instance(self) -> None:
        random.seed(1234)
        module_value = random.random()

        assert module_value == random.Random(1234).random()

    def test_systemrandom_keeps_no_state_to_seed(self) -> None:
        source = random.SystemRandom()

        assert source.seed(42) is None, "seeding is a no-op"
        with pytest.raises(NotImplementedError):
            source.getstate()

    @pytest.mark.timing
    def test_systemrandom_is_the_slower_source(self) -> None:
        """The page's "secure but slow" against the Mersenne Twister."""
        source = random.SystemRandom()

        twister = per_call(random.random, number=50_000)
        system = per_call(source.random, number=20_000)

        assert system > twister * 3, (
            f"reading the OS entropy pool should cost more than a C step: "
            f"random() {twister:.2e}s, SystemRandom.random() {system:.2e}s"
        )


class TestThreadSafety:
    """The page's Thread Safety section, and the exception it now names."""

    def test_threads_draw_from_one_shared_stream(self) -> None:
        """Interleaving is unpredictable; what they consume is not.

        Whatever order the two threads run in, between them they take the
        first 200 values of the single seeded stream - which is what "shares
        state" means, and why no thread gets a sequence of its own.
        """
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
        """The page's recommendation: a seeded instance per thread."""
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
        """`random()` is one C step, so sharing it corrupts nothing."""
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
        """Why gauss() is the exception the page now names.

        The interleaving is modelled with setstate rather than raced: both
        callers read gauss_next before either clears it, which is exactly the
        window CPython's own comment describes.
        """
        rng = random.Random(11)
        rng.gauss(0.0, 1.0)  # leaves a spare in the instance

        before_either_call = rng.getstate()
        first = rng.gauss(0.0, 1.0)
        rng.setstate(before_either_call)
        second = rng.gauss(0.0, 1.0)

        assert first == second, "both callers took the one cached value"


class TestDocumentedPatterns:
    """The algorithms the page writes out, and the costs it gives them."""

    @staticmethod
    def reservoir_sample(iterable: range, k: int, rng: random.Random) -> list[int]:
        """The page's reservoir_sample, with its RNG made injectable."""
        reservoir: list[int] = []
        for index, item in enumerate(iterable):
            if index < k:
                reservoir.append(item)
            else:
                position = rng.randint(0, index)
                if position < k:
                    reservoir[position] = item
        return reservoir

    def test_reservoir_sampling_draws_once_per_item(self) -> None:
        """ "O(n) time": one draw for every item past the first k."""
        rng = CountingRandom(4)
        rng.reset()
        self.reservoir_sample(range(20_000), 100, rng)

        assert 19_900 <= rng.draws < 40_000, f"about n - k draws, got {rng.draws}"

    def test_reservoir_sampling_holds_only_k_items(self) -> None:
        """ "O(k) space": the stream is never materialised."""
        rng = random.Random(4)
        result = self.reservoir_sample(range(200_000), 100, rng)

        assert len(result) == 100
        peak = peak_bytes(lambda: self.reservoir_sample(range(200_000), 100, rng))
        assert peak < 20_000, f"a 200,000-item stream would be megabytes; peak {peak} bytes"

    def test_bogosort_needs_about_n_factorial_shuffles(self) -> None:
        """The corrected claim: n! shuffles, each O(n), so O(n * n!) overall.

        Each shuffle is an independent uniform permutation, so the count is
        geometric with mean n! - measured from the first shuffle, since the
        page's loop returns immediately on an input that arrives sorted.
        """
        rng = random.Random(17)
        size = 4
        ordered = list(range(size))

        counts: list[int] = []
        for _ in range(2_000):
            items = ordered[:]
            shuffles = 0
            while True:
                rng.shuffle(items)
                shuffles += 1
                if items == ordered:
                    break
            counts.append(shuffles)

        mean = statistics.fmean(counts)
        expected = math.factorial(size)
        assert expected * 0.75 < mean < expected * 1.25, (
            f"expected about {expected} shuffles for n={size}, measured {mean:.1f}"
        )

    def test_estimate_pi_converges(self) -> None:
        """The Monte Carlo block's own claim, on a fixed seed."""
        rng = random.Random(2718)
        samples = 100_000
        inside = sum(1 for _ in range(samples) if rng.random() ** 2 + rng.random() ** 2 <= 1)

        assert abs(4 * inside / samples - math.pi) < 0.02


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


class TestDocumentedExamples:
    """Every block on the page runs.

    Nothing here touches the filesystem, the network or stdin, so unlike the
    os page there is no block to hold back and no failure to allow for: a
    non-zero exit is a defect in the example.
    """

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        failures: list[str] = []

        for line, source in _blocks():
            result = _run(source, tmp_path)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()}")

        assert not failures, "\n".join(failures)

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = _blocks()[0][1]
        broken = original.replace("import random\n", "", 1)
        assert broken != original, "the mutation did not remove the import"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr
