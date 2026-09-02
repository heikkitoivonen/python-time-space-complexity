"""Tests to verify documented time and space complexity of itertools.

A review of docs/stdlib/itertools.md, which had no test coverage at all. The
page was wrong in four places, and every one of them is pinned below:

* `tee()` was priced at O(n x k) space for n iterators and k items consumed.
  The buffer is shared, so the copies never multiply it, and what it holds is
  the gap between the leading and trailing iterator rather than everything
  consumed. Iterators advanced in lockstep hold almost nothing. Corrected to
  O(g + n) -- see TestTeeSharesOneBuffer.
* `combinations()`, `combinations_with_replacement()` and `permutations()`
  were priced at O(r) per item, omitting the O(n) copy each one makes of its
  input before yielding anything.
* the Performance Tips section called `product()` "lazy generation O(1)
  memory", contradicting the page's own table two screens earlier. It copies
  every input up front.
* three of the eight code blocks raised NameError on names the page never
  defined.

Category C, claims execution cannot settle here:

* "Infinite counter" for `count()` and the unbounded `repeat(obj)`. A test can
  only ever show that a prefix is produced without the iterator ending, which
  TestCreatingIterators does; it cannot show the absence of an end.
* The Version Notes for Python 2.6 and "Python 3.x: All modern functions
  available". The oldest interpreter this project supports is 3.10, so the
  earlier entries are history rather than something the suite can exercise.
  The 3.10 and 3.12 entries are covered by TestVersionedAdditions.
"""

import io
import itertools
import math
import sys
import time
import tracemalloc
from collections import deque
from collections.abc import Iterator
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
ITERTOOLS_PAGE = PROJECT_ROOT / "docs" / "stdlib" / "itertools.md"


class CountingSource:
    """An iterable that records how many items have been pulled from it.

    Laziness and eager copying are the page's central space claims, and both
    are visible as a pull count -- no stopwatch and no tolerance.
    """

    def __init__(self, size: int) -> None:
        self.size = size
        self.pulled = 0

    def __iter__(self) -> Iterator[int]:
        for value in range(self.size):
            self.pulled += 1
            yield value


def held_bytes(build, drive) -> int:
    """Bytes still held after driving an iterator, measured before releasing it.

    The reading has to be taken while the object is still alive: sample it
    after the last reference goes and every answer is zero, which is what the
    first draft of this helper did.
    """
    tracemalloc.start()
    try:
        base = tracemalloc.get_traced_memory()[0]
        iterators = build()
        drive(iterators)
        held = tracemalloc.get_traced_memory()[0] - base
        del iterators
        return held
    finally:
        tracemalloc.stop()


class TestCreatingIterators:
    """docs/stdlib/itertools.md: the Creating Iterators table."""

    def test_count_yields_without_holding_what_it_produced(self) -> None:
        counter = itertools.count(0, 1)

        assert [next(counter) for _ in range(5)] == [0, 1, 2, 3, 4]
        # O(1) space: the object carries a running value, not a history.
        assert sys.getsizeof(counter) == sys.getsizeof(itertools.count(0, 1))

    def test_count_honours_start_and_step(self) -> None:
        assert list(itertools.islice(itertools.count(10, 3), 4)) == [10, 13, 16, 19]

    def test_repeat_hands_back_the_same_object_every_time(self) -> None:
        """O(1) space: repeat stores one reference, not `times` of them."""
        sentinel = object()
        repeated = list(itertools.repeat(sentinel, 1_000))

        assert len(repeated) == 1_000
        assert all(item is sentinel for item in repeated)

    def test_cycle_caches_the_input_as_it_goes(self) -> None:
        """O(n) space, "stores copy of iterable" -- and it is lazy about it."""
        source = CountingSource(3)
        cycled = itertools.cycle(source)

        assert source.pulled == 0, "cycle does not read its input at construction"

        first = [next(cycled) for _ in range(3)]
        after_first_pass = source.pulled
        second = [next(cycled) for _ in range(3)]

        assert first == [0, 1, 2]
        assert after_first_pass == 3, "the first pass comes from the source"
        assert second == [0, 1, 2]
        assert source.pulled == 3, "the second pass comes from cycle's own copy"

    def test_accumulate_is_linear_and_keeps_only_the_running_total(self) -> None:
        source = CountingSource(1_000)
        running = itertools.accumulate(source)

        assert next(running) == 0
        assert source.pulled == 1, "one item in, one item out"

        assert list(itertools.accumulate([1, 2, 3, 4])) == [1, 3, 6, 10]
        assert list(itertools.accumulate([1, 2, 3, 4], lambda a, b: a * b)) == [1, 2, 6, 24]


class TestFilteringIterators:
    """docs/stdlib/itertools.md: the Filtering Iterators table, all O(1) space.

    Every row is a claim that the function holds nothing but the item it is
    handing back, which shows up as pulling exactly one source item per output.
    """

    @pytest.mark.parametrize(
        ("name", "build"),
        [
            ("filterfalse", lambda it: itertools.filterfalse(lambda x: False, it)),
            ("compress", lambda it: itertools.compress(it, itertools.repeat(1))),
            ("takewhile", lambda it: itertools.takewhile(lambda x: True, it)),
            ("dropwhile", lambda it: itertools.dropwhile(lambda x: False, it)),
            ("islice", lambda it: itertools.islice(it, None)),
        ],
    )
    def test_one_item_in_one_item_out(self, name: str, build) -> None:
        source = CountingSource(1_000)
        produced = build(iter(source))

        assert next(produced) == 0
        assert source.pulled == 1, f"{name} should not read ahead of what it yields"

    def test_filterfalse_keeps_what_the_predicate_rejects(self) -> None:
        """The page's example named the result `even` and listed odd values."""
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9]

        assert list(itertools.filterfalse(lambda x: x % 2 == 0, data)) == [1, 3, 5, 7, 9]

    def test_takewhile_and_dropwhile_split_at_the_same_point(self) -> None:
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9]

        assert list(itertools.takewhile(lambda x: x < 5, data)) == [1, 2, 3, 4]
        assert list(itertools.dropwhile(lambda x: x < 5, data)) == [5, 6, 7, 8, 9]

    def test_takewhile_stops_at_the_first_failure_without_reading_on(self) -> None:
        source = CountingSource(1_000)
        taken = list(itertools.takewhile(lambda x: x < 3, source))

        assert taken == [0, 1, 2]
        assert source.pulled == 4, "three taken plus the one that ended it"

    def test_compress_follows_the_mask(self) -> None:
        assert list(itertools.compress("ABCDEF", [1, 0, 1, 0, 1, 1])) == ["A", "C", "E", "F"]

    def test_islice_consumes_and_discards_the_skipped_prefix(self) -> None:
        """O(n) total, not O(stop - start): the prefix is pulled and dropped."""
        source = CountingSource(1_000)
        sliced = itertools.islice(source, 900, 905)

        assert next(sliced) == 900
        assert source.pulled == 901, "everything up to start is read, then thrown away"

    def test_islice_honours_step(self) -> None:
        assert list(itertools.islice(range(10), 0, 10, 3)) == [0, 3, 6, 9]


class TestCombiningIterators:
    """docs/stdlib/itertools.md: the Combining Iterators table."""

    def test_chain_is_linear_in_the_total_and_holds_nothing(self) -> None:
        left, right = CountingSource(500), CountingSource(500)
        chained = itertools.chain(left, right)

        assert next(chained) == 0
        assert (left.pulled, right.pulled) == (1, 0), "the second input is untouched"
        assert len(list(chained)) == 999

    def test_chain_from_iterable_flattens_one_level_lazily(self) -> None:
        """The outer iterable is pulled one sub-iterable at a time.

        Two earlier versions of this were too weak, both in the same way. The
        first asserted a pull count on a CountingSource never passed to the
        function. The second instrumented the sub-iterables but handed over a
        plain list, so an implementation that drained the outer iterable at
        construction would have passed. What needs watching is the outer one.
        """
        outer_pulled = 0

        def outer():
            nonlocal outer_pulled
            for chunk in ([0, 1], [2, 3], [4, 5]):
                outer_pulled += 1
                yield chunk

        flattened = itertools.chain.from_iterable(outer())

        assert outer_pulled == 0, "no sub-iterable is fetched at construction"
        assert next(flattened) == 0
        assert outer_pulled == 1, "exactly one sub-iterable in hand"
        assert next(flattened) == 1
        assert outer_pulled == 1, "still inside it, so the outer stays put"
        assert next(flattened) == 2
        assert outer_pulled == 2, "the next one is fetched only on crossing into it"

        assert list(flattened) == [3, 4, 5]
        assert outer_pulled == 3

    def test_zip_longest_pads_to_the_longest_input(self) -> None:
        assert list(itertools.zip_longest("AB", "xyz", fillvalue="-")) == [
            ("A", "x"),
            ("B", "y"),
            ("-", "z"),
        ]

    def test_zip_longest_reads_one_item_per_input_per_output(self) -> None:
        left, right = CountingSource(500), CountingSource(500)
        zipped = itertools.zip_longest(left, right)

        assert next(zipped) == (0, 0)
        assert (left.pulled, right.pulled) == (1, 1)

    def test_starmap_unpacks_each_tuple_as_arguments(self) -> None:
        assert list(itertools.starmap(pow, [(2, 3), (3, 2), (10, 0)])) == [8, 9, 1]

    def test_starmap_calls_the_function_once_per_item(self) -> None:
        calls = 0

        def counted(value: int) -> int:
            nonlocal calls
            calls += 1
            return value

        assert list(itertools.starmap(counted, [(1,), (2,), (3,)])) == [1, 2, 3]
        assert calls == 3, "O(n) total: one call per input tuple, no more"

    def test_pairwise_yields_overlapping_pairs(self) -> None:
        assert list(itertools.pairwise("ABCD")) == [("A", "B"), ("B", "C"), ("C", "D")]
        assert list(itertools.pairwise("A")) == [], "fewer than two items yields nothing"

    def test_pairwise_holds_only_the_previous_item(self) -> None:
        source = CountingSource(1_000)
        paired = itertools.pairwise(source)

        assert next(paired) == (0, 1)
        assert source.pulled == 2, "one pair costs two items, then one each"
        assert next(paired) == (1, 2)
        assert source.pulled == 3


class TestTeeSharesOneBuffer:
    """docs/stdlib/itertools.md priced tee() at O(n x k) space, as corrected.

    Two things were wrong. The n copies share a single buffer rather than each
    holding their own, so n does not multiply the cost. And what the buffer
    holds is the gap between the fastest and slowest iterator, not everything
    consumed -- lockstep iterators hold almost nothing however far they run.
    """

    ITEMS = 50_000

    def _race(self, iterators: tuple) -> None:
        """Advance one iterator the whole way; leave the rest at the start."""
        for _ in range(self.ITEMS):
            next(iterators[0])

    def _lockstep(self, iterators: tuple) -> None:
        for _ in range(self.ITEMS):
            for iterator in iterators:
                next(iterator)

    def test_more_iterators_do_not_multiply_the_buffer(self) -> None:
        source = list(range(self.ITEMS))
        two = held_bytes(lambda: itertools.tee(iter(source), 2), self._race)
        thirty_two = held_bytes(lambda: itertools.tee(iter(source), 32), self._race)

        # O(n x k) would predict sixteen times the memory for sixteen times
        # the iterators. The buffer is shared, so it barely moves.
        assert thirty_two < two * 2, (
            f"sixteen times the iterators should not multiply the buffer: "
            f"n=2 {two:,}B vs n=32 {thirty_two:,}B"
        )

    def test_the_buffer_holds_the_gap_not_everything_consumed(self) -> None:
        source = list(range(self.ITEMS))
        raced = held_bytes(lambda: itertools.tee(iter(source), 2), self._race)
        lockstep = held_bytes(lambda: itertools.tee(iter(source), 2), self._lockstep)

        # Same iterators, same number of items pulled through each. Only the
        # gap differs, and that is what the memory tracks.
        assert lockstep * 100 < raced, (
            f"lockstep iterators should hold almost nothing: "
            f"raced {raced:,}B vs lockstep {lockstep:,}B"
        )

    def test_the_copies_are_independent(self) -> None:
        left, right = itertools.tee(iter(range(5)), 2)

        assert list(left) == [0, 1, 2, 3, 4]
        assert list(right) == [0, 1, 2, 3, 4], "draining one does not drain the other"

    def test_tee_is_lazy_about_its_source(self) -> None:
        source = CountingSource(1_000)
        left, _right = itertools.tee(source, 2)

        assert source.pulled == 0, "O(n) init builds n objects, it does not read"
        assert next(left) == 0
        assert source.pulled == 1


class TestGroupingAndCombinatorics:
    """docs/stdlib/itertools.md: the Grouping & Windowing table."""

    def test_groupby_groups_consecutive_runs_only(self) -> None:
        data = [1, 1, 2, 2, 2, 3, 1, 1]
        grouped = [(key, list(group)) for key, group in itertools.groupby(data)]

        assert grouped == [(1, [1, 1]), (2, [2, 2, 2]), (3, [3]), (1, [1, 1])]

    def test_groupby_with_a_key_function(self) -> None:
        data = ["apple", "apricot", "banana", "blueberry"]
        grouped = [(key, list(group)) for key, group in itertools.groupby(data, key=lambda x: x[0])]

        assert grouped == [("a", ["apple", "apricot"]), ("b", ["banana", "blueberry"])]

    def test_groupby_keeps_no_per_group_buffer(self) -> None:
        """O(1) space: advancing invalidates the group you were holding."""
        groups = itertools.groupby([1, 1, 2, 2, 3])
        _first_key, first_group = next(groups)
        next(groups)

        assert list(first_group) == [], "the earlier group was never buffered"

    def test_groupby_is_linear_in_the_input(self) -> None:
        source = CountingSource(1_000)
        groups = itertools.groupby(source)

        key, _group = next(groups)
        assert key == 0
        assert source.pulled == 1, "one item settles the first group's key"

    @pytest.mark.parametrize(
        ("name", "produce", "expected"),
        [
            ("combinations", lambda: itertools.combinations(range(8), 3), math.comb(8, 3)),
            (
                "combinations_with_replacement",
                lambda: itertools.combinations_with_replacement(range(8), 3),
                math.comb(8 + 3 - 1, 3),
            ),
            ("permutations", lambda: itertools.permutations(range(8), 3), math.perm(8, 3)),
        ],
    )
    def test_output_count_matches_the_documented_formula(
        self, name: str, produce, expected: int
    ) -> None:
        assert sum(1 for _ in produce()) == expected, f"{name} should yield exactly {expected}"

    def test_each_item_is_an_r_tuple(self) -> None:
        """O(r) per item: a fresh tuple of length r, not a growing structure."""
        for item in itertools.combinations(range(6), 3):
            assert isinstance(item, tuple)
            assert len(item) == 3

    def test_the_documented_small_examples(self) -> None:
        assert list(itertools.combinations("ABC", 2)) == [
            ("A", "B"),
            ("A", "C"),
            ("B", "C"),
        ]
        assert list(itertools.permutations("ABC", 2))[:3] == [
            ("A", "B"),
            ("A", "C"),
            ("B", "A"),
        ]
        assert list(itertools.product("AB", "12")) == [
            ("A", "1"),
            ("A", "2"),
            ("B", "1"),
            ("B", "2"),
        ]

    @pytest.mark.parametrize(
        ("name", "build"),
        [
            ("combinations", lambda source: itertools.combinations(source, 2)),
            (
                "combinations_with_replacement",
                lambda source: itertools.combinations_with_replacement(source, 2),
            ),
            ("permutations", lambda source: itertools.permutations(source, 2)),
            ("product", lambda source: itertools.product(source, repeat=1)),
        ],
    )
    def test_the_input_is_copied_before_anything_is_yielded(self, name: str, build) -> None:
        """The O(n) input copy the table's space column had omitted."""
        source = CountingSource(100)
        produced = build(source)

        assert source.pulled == 100, f"{name} reads its whole input at construction"
        next(produced)
        assert source.pulled == 100, "and reads nothing further"

    def test_product_is_not_o1_memory(self) -> None:
        """The Performance Tips section claimed product() was O(1) memory.

        It contradicted the page's own table, which says product stores all
        inputs first. The table was right.
        """
        left, right = CountingSource(1_000), CountingSource(1_000)
        pairs = itertools.product(left, right)

        assert (left.pulled, right.pulled) == (1_000, 1_000), (
            "both inputs are copied to tuples before the first pair is yielded"
        )
        assert next(pairs) == (0, 0)

    def test_product_yields_the_cartesian_product_lazily(self) -> None:
        """What the Performance Tips section was reaching for: the results are
        not materialised, even though the inputs are."""
        pairs = itertools.product(range(1_000), range(1_000))

        assert next(pairs) == (0, 0)
        assert sum(1 for _ in itertools.islice(pairs, 5)) == 5


class TestVersionedAdditions:
    """docs/stdlib/itertools.md Version Notes: pairwise 3.10+, batched 3.12+."""

    def test_pairwise_exists_on_every_supported_version(self) -> None:
        assert hasattr(itertools, "pairwise"), "the page dates pairwise() to 3.10"

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="batched() is new in 3.12")
    def test_batched_groups_into_n_sized_tuples(self) -> None:
        # pyright targets the pinned 3.11, where batched() does not exist;
        # the skipif above is what keeps this safe at runtime.
        batches = itertools.batched("ABCDEFG", 3)  # type: ignore[reportAttributeAccessIssue]
        assert list(batches) == [
            ("A", "B", "C"),
            ("D", "E", "F"),
            ("G",),
        ]

    @pytest.mark.skipif(sys.version_info < (3, 12), reason="batched() is new in 3.12")
    def test_batched_holds_one_batch_at_a_time(self) -> None:
        """O(n) per batch space, where n is the batch size."""
        source = CountingSource(1_000)
        batches = itertools.batched(source, 10)  # type: ignore[reportAttributeAccessIssue]

        assert next(batches) == tuple(range(10))
        assert source.pulled == 10, "one batch read, not the whole input"

    def test_batched_is_absent_before_312(self) -> None:
        assert hasattr(itertools, "batched") == (sys.version_info >= (3, 12))


class TestDocumentedExamplesRun:
    """Every Python block on the page must execute.

    Three of the eight raised NameError on names the page never defined -- one
    of them in the block illustrating what is O(1) memory. Nothing on the page
    or in the suite had ever run them.
    """

    def _blocks(self) -> list[tuple[int, str]]:
        blocks: list[tuple[int, str]] = []
        inside = False
        start = 0
        body: list[str] = []
        for number, line in enumerate(
            ITERTOOLS_PAGE.read_text(encoding="utf-8").splitlines(), start=1
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
        """So the runner below cannot silently test nothing."""
        assert len(self._blocks()) >= 8

    def test_every_example_executes(self) -> None:
        failures: list[str] = []
        for line_number, source in self._blocks():
            captured, real_stdout = io.StringIO(), sys.stdout
            try:
                sys.stdout = captured
                exec(  # noqa: S102 - executing the docs is the point
                    compile(source, f"itertools.md:{line_number}", "exec"),
                    {"__name__": "__main__"},
                )
            except Exception as error:  # noqa: BLE001 - report, do not raise
                failures.append(f"line {line_number}: {type(error).__name__}: {error}")
            finally:
                sys.stdout = real_stdout

        assert not failures, "examples on the page do not run:\n" + "\n".join(failures)

    def test_the_groupby_example_prints_what_the_page_says(self) -> None:
        """Executing a block proves nothing about the output in its comments."""
        captured, real_stdout = io.StringIO(), sys.stdout
        try:
            sys.stdout = captured
            for key, group in itertools.groupby([1, 1, 2, 2, 2, 3, 1, 1]):
                print(key, list(group))
        finally:
            sys.stdout = real_stdout

        assert captured.getvalue().splitlines() == [
            "1 [1, 1]",
            "2 [2, 2, 2]",
            "3 [3]",
            "1 [1, 1]",
        ]

    def test_the_window_helper_slides_as_documented(self) -> None:
        """The Window Operations example, which the page shows output for."""
        source = self._blocks()[-1][1]
        namespace: dict[str, object] = {"__name__": "__main__"}
        captured, real_stdout = io.StringIO(), sys.stdout
        try:
            sys.stdout = captured
            exec(compile(source, "itertools.md:window", "exec"), namespace)  # noqa: S102
        finally:
            sys.stdout = real_stdout

        window = namespace["window"]
        assert list(window(range(10), 3))[:3] == [(0, 1, 2), (1, 2, 3), (2, 3, 4)]  # type: ignore[operator]
        assert len(list(window(range(10), 3))) == 8  # type: ignore[operator]


class TestWindowHelperCost:
    """docs/stdlib/itertools.md Window Operations, as corrected by these tests.

    The example was priced at "O(n) items, O(w) memory". The memory was right;
    the time was not. Each window is a fresh w-tuple, so the windows alone come
    to n*w items and the helper is O(n*w) -- which is a property of
    materialising every window, not of the `w[1:] + (item,)` rebuild. Yielding
    one reused deque instead is flat in w.
    """

    ITEMS = 50_000
    NARROW = 2
    WIDE = 256

    @staticmethod
    def _tuple_window(iterable, size):
        """The page's helper."""
        iterator = iter(iterable)
        window = tuple(itertools.islice(iterator, size))
        yield window
        for item in iterator:
            window = window[1:] + (item,)
            yield window

    @staticmethod
    def _reused_deque(iterable, size):
        """One deque, handed back each time and valid until the next item."""
        iterator = iter(iterable)
        window = deque(itertools.islice(iterator, size), maxlen=size)
        yield window
        for item in iterator:
            window.append(item)
            yield window

    def _drain(self, helper, size) -> float:
        best = float("inf")
        for _ in range(3):
            start = time.perf_counter()
            deque(helper(range(self.ITEMS), size), maxlen=0)
            best = min(best, time.perf_counter() - start)
        return best

    @pytest.mark.timing
    def test_the_page_helper_grows_with_the_window(self) -> None:
        """O(n) would mean the window size does not matter. It does."""
        narrow = self._drain(self._tuple_window, self.NARROW)
        wide = self._drain(self._tuple_window, self.WIDE)

        assert wide / narrow > 4, (
            f"a wider window should cost more per item, not the same: "
            f"w={self.NARROW} {narrow:.2e}s vs w={self.WIDE} {wide:.2e}s "
            f"({wide / narrow:.1f}x)"
        )

    @pytest.mark.timing
    def test_a_reused_deque_is_flat_in_the_window_size(self) -> None:
        """Which locates the cost: materialising each window, not sliding."""
        narrow = self._drain(self._reused_deque, self.NARROW)
        wide = self._drain(self._reused_deque, self.WIDE)

        assert wide / narrow < 3, (
            f"handing back one deque should not care how wide it is: "
            f"w={self.NARROW} {narrow:.2e}s vs w={self.WIDE} {wide:.2e}s "
            f"({wide / narrow:.1f}x)"
        )

    def test_the_reused_deque_is_only_valid_until_the_next_item(self) -> None:
        """The caveat that buys the flat cost, so it is not a free upgrade."""
        windows = list(self._reused_deque(range(5), 3))

        assert all(window is windows[0] for window in windows), "the same object throughout"
        assert list(windows[0]) == [2, 3, 4], "every entry shows only the final window"

    def test_both_helpers_yield_the_same_windows_when_copied(self) -> None:
        from_page = list(self._tuple_window(range(10), 3))
        from_deque = [tuple(window) for window in self._reused_deque(range(10), 3)]

        assert from_page == from_deque
        assert len(from_page) == 10 - 3 + 1, "n - w + 1 windows"


class TestCombinatoricsCostIsNotJustTheResultCount:
    """docs/stdlib/itertools.md priced the combinatorics rows by result count.

    Four rounds of review took that to O(n + r + r x M), one term at a time:

    * the input is consumed whatever r is, so C(n,n) yields one result and
      still costs n;
    * an r-entry index array is allocated before any result exists, which is
      the standalone r and the only term left when n = M = 0;
    * up to r slots are filled per result, so C(n,1) and C(n,n-1) are the same
      count and nowhere near the same cost.

    That last term is an upper bound rather than a flat rate. CPython refills
    the result tuple in place when nothing holds the previous one, rewriting
    only the suffix from the leftmost changed index -- about one slot when r
    is small next to n, but n/2 when r = n-1. Keeping the results forces the
    full r-element copy every time.

    Every term here is countable, so only the last test needs a stopwatch.
    """

    def test_the_input_is_read_even_when_there_is_one_result(self) -> None:
        """The O(n) term. C(n,n) = 1, and the count alone would predict O(1)."""
        source = CountingSource(500)
        results = list(itertools.combinations(source, 500))

        assert len(results) == 1, "C(n,n) is a single result"
        assert source.pulled == 500, "and the whole input was read to produce it"

    def test_an_empty_result_set_still_costs_the_input(self) -> None:
        """r > n yields nothing at all, and still reads everything."""
        source = CountingSource(500)

        assert list(itertools.combinations(source, 501)) == []
        assert source.pulled == 500

    @pytest.mark.parametrize(
        "produce",
        [
            itertools.combinations,
            itertools.combinations_with_replacement,
            itertools.permutations,
        ],
    )
    def test_an_r_entry_index_array_is_allocated_before_any_result(self, produce) -> None:
        """The standalone r term, which only shows when n = M = 0.

        With an empty input there is no input to copy and no result to build,
        so a bound of O(n + r x M) would predict constant cost. The index
        array is allocated anyway, and it is one entry per r.
        """
        assert list(produce((), 1_000)) == [], "nothing is yielded at all"

        small = held_bytes(lambda: produce((), 1_000), lambda obj: None)
        large = held_bytes(lambda: produce((), 100_000), lambda obj: None)

        assert large > small * 50, (
            f"a hundred times the r should hold about a hundred times the "
            f"state, not the same: r=1,000 {small:,}B vs r=100,000 {large:,}B"
        )

    def test_product_keeps_per_pool_state_with_the_inputs_held_at_nothing(self) -> None:
        """The k term, isolated from the Sum(ni) term.

        An earlier version grew k by adding 50-element pools, which grew
        Sum(ni) in step -- so the older O(Sum(ni)) bound explained the result
        just as well and the test proved nothing about k. Every pool here is
        empty, so Sum(ni) stays 0 and only k moves.
        """

        def build(pools: int):
            return lambda: itertools.product(*([()] * pools))

        assert list(itertools.product((), (), ())) == [], "empty pools yield nothing"

        small = held_bytes(build(100), lambda obj: None)
        large = held_bytes(build(10_000), lambda obj: None)

        assert large > small * 20, (
            f"with Sum(ni) fixed at 0, a hundred times the pools should still "
            f"cost: k=100 {small:,}B vs k=10,000 {large:,}B"
        )

    @staticmethod
    def _slots_rewritten_per_result(n: int, r: int) -> float:
        """Mean suffix length combinations() rewrites, by the same walk it uses.

        Mirrors combinations_next: scan right-to-left for the first index below
        its maximum, bump it, reset everything to its right, and rewrite the
        result from that index onward. Exact and deterministic -- no timing.
        """
        indices = list(range(r))
        steps = writes = 0
        while True:
            i = r - 1
            while i >= 0 and indices[i] == i + n - r:
                i -= 1
            if i < 0:
                break
            indices[i] += 1
            for j in range(i + 1, r):
                indices[j] = indices[j - 1] + 1
            steps += 1
            writes += r - i
        return writes / steps if steps else 0.0

    @pytest.mark.parametrize(("n", "r"), [(7, 3), (9, 4), (6, 5), (5, 1)])
    def test_the_simulated_index_walk_matches_itertools(self, n: int, r: int) -> None:
        """The suffix counts below are only worth anything if the walk is real.

        Replays the same scan and reset that _slots_rewritten_per_result
        counts, and checks it lands on exactly the tuples combinations()
        yields.
        """
        indices = list(range(r))
        walked = [tuple(indices)]
        while True:
            i = r - 1
            while i >= 0 and indices[i] == i + n - r:
                i -= 1
            if i < 0:
                break
            indices[i] += 1
            for j in range(i + 1, r):
                indices[j] = indices[j - 1] + 1
            walked.append(tuple(indices))

        assert walked == list(itertools.combinations(range(n), r))

    def test_the_rewritten_suffix_is_not_a_constant(self) -> None:
        """Why O(r) per result is an upper bound and not a flat rate.

        An earlier version of the page called the reuse path "O(1) amortised".
        It is nearly that when r is small next to n, and nothing like it when
        r approaches n -- at r = n-1 the mean suffix is exactly n/2, which
        grows without bound. The claim now says so, and this is the arithmetic
        behind the wider-result timing test in this class.
        """
        # r small next to n: essentially one slot per result.
        assert self._slots_rewritten_per_result(20, 2) < 1.2
        assert self._slots_rewritten_per_result(100, 2) < 1.1
        assert self._slots_rewritten_per_result(20, 12) < 3

        # r = n-1: exactly n/2, so it tracks r rather than a constant.
        for n in (20, 100, 500):
            assert self._slots_rewritten_per_result(n, n - 1) == n / 2

        # And therefore grows with n, which "O(1) amortised" denies.
        assert self._slots_rewritten_per_result(500, 499) > 20 * self._slots_rewritten_per_result(
            20, 19
        )

    def test_permutations_carries_more_setup_than_combinations(self) -> None:
        """permutations() keeps an n-entry indices array combinations() has not.

        The page used to describe both as holding "an r-entry index array".
        The O(n + r) bound was right, but for permutations the n comes from a
        second array rather than only from the input copy, so at a fixed small
        r the gap between the two grows with n.
        """

        def gap(n: int) -> int:
            with_cycles = held_bytes(lambda: itertools.permutations(range(n), 2), lambda o: None)
            without = held_bytes(lambda: itertools.combinations(range(n), 2), lambda o: None)
            return with_cycles - without

        small, large = gap(10_000), gap(100_000)

        assert small > 0, "permutations holds strictly more at the same n and r"
        assert large > small * 5, (
            f"the extra array is n-entry, so ten times the n should cost about "
            f"ten times more: n=10,000 {small:,}B vs n=100,000 {large:,}B"
        )

    def test_the_result_tuple_is_reused_unless_you_hold_it(self) -> None:
        """CPython hands back the same tuple when nothing references the old one.

        So "a fresh tuple every time" is wrong. What replaced it was wrong too:
        the r writes do NOT happen either way. On the reuse path
        combinations_next() updates the result "starting with i, the leftmost
        index that changed", while the copy path runs a full
        _PyTuple_FromArray of all r. O(r) per result is an upper bound, tight
        only on the copy path. The retained identities below distinguish that
        path directly, without a timing threshold.
        """
        recycled = [id(item) for item in itertools.combinations(range(5), 2)]
        retained = [id(item) for item in list(itertools.combinations(range(5), 2))]

        assert len(recycled) == len(retained) == math.comb(5, 2)
        assert len(set(recycled)) < len(recycled), "ids repeat when nothing holds them"
        assert len(set(retained)) == len(retained), "list() holds each, forcing a new tuple"

        results = itertools.combinations(range(5), 2)
        first = next(results)
        first_id = id(first)
        del first
        assert id(next(results)) == first_id, "the dropped tuple is refilled in place"

        held = next(results)
        assert id(next(results)) != id(held), "one still referenced forces a fresh tuple"

    @pytest.mark.parametrize("r", [1, 2, 3, 4])
    def test_elements_handed_back_are_r_times_the_result_count(self, r: int) -> None:
        """The r x M term, counted exactly rather than timed."""
        results = list(itertools.combinations(range(9), r))
        elements = sum(len(item) for item in results)

        assert len(results) == math.comb(9, r)
        assert elements == r * math.comb(9, r)

    def test_equal_result_counts_can_mean_very_different_work(self) -> None:
        """C(n,1) and C(n,n-1) are both n results -- the resemblance ends there.

        This is the case that shows the old bound could not have been right:
        by result count these two are identical.
        """
        n = 200
        few = list(itertools.combinations(range(n), 1))
        many = list(itertools.combinations(range(n), n - 1))

        assert len(few) == len(many) == n, "the same number of results"
        assert sum(len(item) for item in few) == n
        assert sum(len(item) for item in many) == n * (n - 1)

    @pytest.mark.timing
    def test_the_wider_result_actually_costs_more(self) -> None:
        """And the element count is not bookkeeping -- it is the runtime."""
        n = 2_000

        def drain(r: int) -> float:
            best = float("inf")
            for _ in range(3):
                start = time.perf_counter()
                deque(itertools.combinations(range(n), r), maxlen=0)
                best = min(best, time.perf_counter() - start)
            return best

        narrow, wide = drain(1), drain(n - 1)

        assert wide / narrow > 20, (
            f"C(n,1) and C(n,n-1) are both {n} results, so a bound in the "
            f"result count alone predicts parity: r=1 {narrow:.2e}s vs "
            f"r=n-1 {wide:.2e}s ({wide / narrow:.0f}x)"
        )

    def test_product_builds_a_k_tuple_per_result(self) -> None:
        """The k factor the product row's time column had omitted."""
        for k in (2, 4, 6):
            results = list(itertools.product(*[range(2)] * k))

            assert len(results) == 2**k
            assert all(len(item) == k for item in results)
            assert sum(len(item) for item in results) == k * 2**k
