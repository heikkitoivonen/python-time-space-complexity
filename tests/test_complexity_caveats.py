"""Tests for the complexity claims that turned out to need a caveat.

Every test here corresponds to a claim these docs got wrong and had to
correct. The pattern was always the same: a clean bound stated for an
operation whose real cost has a qualifier -- an eager index, a fallback path,
a resize, a second dict operation -- and the qualifier is exactly what a
reader relies on. Documentation review does not catch these; running the code
does.

So each test pins the behaviour that forced the correction, in the file it was
corrected in:

* ``mode()`` on a tie returns a value, it does not raise (docs showed the
  opposite, and the example did not run)
* ``SequenceMatcher`` indexes its second sequence during construction
* installing a warnings filter scans the filter list
* ``d[k] += 1`` on a defaultdict is more than one dict operation
* equal-hashing keys still compare their elements
* ``int(str)`` and ``Decimal`` arithmetic are superlinear in inputs the docs
  described as linear
* Unicode normalization was superlinear before CPython's CVE-2026-3276 fix

Timing-based tests use a ratio between two sizes with wide tolerances: they
are checking the shape of the growth, not a benchmark. Where an
implementation differs by version the sizes are chosen so one threshold holds
for all of them, rather than branching on the version - see
TestIntFromStringIsSuperlinear, which is quadratic up to 3.11 and
subquadratic from 3.12.
"""

import glob
import io
import logging
import os
import re
import shutil
import sqlite3
import statistics
import sys
import time
import unicodedata
import warnings
from collections import defaultdict, deque
from collections.abc import Callable, Iterator
from decimal import Decimal, getcontext
from difflib import SequenceMatcher
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest

# How much faster a doubled input may get before we call it superlinear. The
# measured ratios are around 4x, so this leaves a wide margin for a loaded
# machine while still failing if an operation becomes genuinely linear.
SUPERLINEAR_RATIO = 2.5


def best_time(func: Callable[[], Any], repeats: int = 5) -> float:
    """Return the fastest of several runs, which is the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return min(times)


class TestStatisticsModeDoesNotRaiseOnTies:
    """docs/stdlib/statistics.md showed mode() raising on a tie. It does not.

    Since Python 3.8 mode() returns the first value with the highest count.
    The documented example could never have run.
    """

    def test_tie_returns_the_first_mode(self) -> None:
        assert statistics.mode([1, 2, 3]) == 1

    def test_tie_does_not_raise(self) -> None:
        # The bug this replaces: a try/except StatisticsError around this call.
        statistics.mode([1, 1, 2, 2])

    def test_multimode_is_how_you_detect_a_tie(self) -> None:
        assert statistics.multimode([1, 2, 3]) == [1, 2, 3]
        assert statistics.multimode([1, 1, 2]) == [1]

    def test_empty_input_does_raise(self) -> None:
        with pytest.raises(statistics.StatisticsError):
            statistics.mean([])
        with pytest.raises(statistics.StatisticsError):
            statistics.mode([])


class TestSequenceMatcherIndexesOnConstruction:
    """docs/stdlib/difflib.md priced SequenceMatcher() init at O(1).

    set_seq2() calls __chain_b() eagerly, so construction is O(m) in the
    second sequence.
    """

    def test_index_exists_before_any_comparison(self) -> None:
        matcher = SequenceMatcher(None, "abc", "xyzxyz")
        # b2j is built by __chain_b() during __init__, not lazily on ratio().
        # It is an implementation attribute, so skip rather than fail if a
        # future CPython drops it - the timing test below is the portable one.
        index = _b2j(matcher)
        assert index == {"x": [0, 3], "y": [1, 4], "z": [2, 5]}

    def test_index_covers_the_second_sequence_only(self) -> None:
        matcher = SequenceMatcher(None, "qqq", "ab")
        assert set(_b2j(matcher)) == {"a", "b"}

    @pytest.mark.timing
    def test_construction_cost_follows_the_second_sequence(self) -> None:
        small, large = "x" * 1_000, "x" * 200_000
        long_b = best_time(lambda: SequenceMatcher(None, small, large))
        long_a = best_time(lambda: SequenceMatcher(None, large, small))
        assert long_b > long_a, (
            f"construction should scale with b, not a: b={long_b:.2e}s a={long_a:.2e}s"
        )


def _b2j(matcher: "SequenceMatcher[str]") -> dict[str, list[int]]:
    """Return SequenceMatcher's index of the second sequence, or skip."""
    index = getattr(matcher, "b2j", None)
    if index is None:
        pytest.skip("SequenceMatcher no longer exposes its b2j index")
    return index


class TestInstallingAWarningsFilterScansTheList:
    """docs/stdlib/warnings.md priced simplefilter() at O(1).

    _add_filter() removes any duplicate and inserts at the front, so both
    filterwarnings() and simplefilter() are O(f) in the filter list.
    """

    def test_duplicate_filter_is_removed_not_appended(self) -> None:
        # catch_warnings() restores the global filter list on exit.
        with warnings.catch_warnings():
            warnings.filterwarnings("error", category=RuntimeWarning)
            after_first = len(warnings.filters)
            warnings.filterwarnings("error", category=RuntimeWarning)
            assert len(warnings.filters) == after_first, (
                "a duplicate is removed before the insert, which is the O(f) scan"
            )

    def test_new_filter_is_prepended(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            warnings.simplefilter("error", RuntimeWarning)
            assert warnings.filters[0][0] == "error"


class TestDefaultdictIncrementIsTwoOperations:
    """docs/stdlib/collections.md called d[k] += 1 "one lookup".

    It is a __getitem__ followed by a __setitem__, and on a missing key the
    factory adds a third.
    """

    def test_existing_key_does_a_get_and_a_set(self) -> None:
        counts = _CountingDefaultDict(int)
        counts["k"] = 0
        counts.gets = counts.sets = 0

        counts["k"] += 1

        assert (counts.gets, counts.sets) == (1, 1)

    def test_missing_key_also_pays_for_the_factory(self) -> None:
        counts = _CountingDefaultDict(int)
        counts["k"] += 1
        assert counts.sets == 2, "factory insert plus the increment's own store"


class _CountingDefaultDict(defaultdict):  # type: ignore[type-arg]
    """A defaultdict that counts the dict operations performed on it."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.gets = 0
        self.sets = 0

    def __getitem__(self, key: Any) -> Any:
        self.gets += 1
        return super().__getitem__(key)

    def __setitem__(self, key: Any, value: Any) -> None:
        self.sets += 1
        super().__setitem__(key, value)


class TestTupleTiesCompareLaterFields:
    """docs/stdlib/heapq.md said tuple priorities cost no more than an int key.

    Equal first elements fall through to the next field, so a tie costs a
    comparison the int key would never make.
    """

    def test_equal_priorities_compare_the_next_field(self) -> None:
        import heapq

        _Tracked.comparisons = 0
        heap = [(1, _Tracked("b")), (1, _Tracked("a")), (2, _Tracked("c"))]
        heapq.heapify(heap)
        while heap:
            heapq.heappop(heap)

        assert _Tracked.comparisons > 0, "a tie on the first field must reach the second"

    def test_distinct_priorities_never_reach_the_second_field(self) -> None:
        import heapq

        _Tracked.comparisons = 0
        heap = [(3, _Tracked("b")), (1, _Tracked("a")), (2, _Tracked("c"))]
        heapq.heapify(heap)
        while heap:
            heapq.heappop(heap)

        assert _Tracked.comparisons == 0


class _Tracked:
    """A payload that records every comparison made against it."""

    comparisons = 0

    def __init__(self, value: str) -> None:
        self.value = value

    def __lt__(self, other: "_Tracked") -> bool:
        type(self).comparisons += 1
        return self.value < other.value


class TestCachedHashDoesNotMakeCollisionsFree:
    """docs/builtins/frozenset.md said a cached hash makes a frozenset key
    cost the same as a str key. Equal hashes still compare elements."""

    def test_equal_hashes_fall_through_to_element_comparison(self) -> None:
        one, two = frozenset([_SameHash(1)]), frozenset([_SameHash(2)])
        assert hash(one) == hash(two), "test needs colliding keys to be meaningful"

        table = {one: "first"}
        _SameHash.comparisons = 0
        assert two not in table
        assert _SameHash.comparisons > 0, "a colliding lookup must compare elements"

    def test_hash_is_still_cached(self) -> None:
        _SameHash.hashes = 0
        frozen = frozenset([_SameHash(1)])
        hash(frozen)
        after_first = _SameHash.hashes
        hash(frozen)
        assert _SameHash.hashes == after_first, "the second hash() must not rehash"


class _SameHash:
    """An element whose hash collides with every other instance."""

    comparisons = 0
    hashes = 0

    def __init__(self, value: int) -> None:
        self.value = value

    def __hash__(self) -> int:
        type(self).hashes += 1
        return 42

    def __eq__(self, other: object) -> bool:
        type(self).comparisons += 1
        return isinstance(other, _SameHash) and self.value == other.value


class TestBytearrayAppendReallocates:
    """docs/builtins/bytes.md said append() copies nothing. Amortized O(1)
    means most appends are free and an occasional one reallocates."""

    def test_buffer_grows_in_jumps_not_per_append(self) -> None:
        buffer = bytearray()
        sizes: set[int] = set()
        for _ in range(2_000):
            buffer.append(0)
            sizes.add(sys.getsizeof(buffer))

        assert 1 < len(sizes) < 2_000, (
            f"expected occasional reallocation, saw {len(sizes)} distinct sizes"
        )


class TestIsinstanceIsNotUniversallyConstant:
    """docs/builtins/type_func.md claimed isinstance() is O(1)."""

    def test_instancecheck_hook_runs_arbitrary_work(self) -> None:
        assert isinstance(1, _Expensive) is False
        assert _ExpensiveMeta.checks == 1, "__instancecheck__ is user code on the hot path"

    @pytest.mark.timing
    def test_cost_grows_with_the_candidate_tuple(self) -> None:
        few = tuple(type(f"C{i}", (), {}) for i in range(2))
        many = tuple(type(f"C{i}", (), {}) for i in range(500))
        value = object()

        few_time = best_time(lambda: [isinstance(value, few) for _ in range(2_000)])
        many_time = best_time(lambda: [isinstance(value, many) for _ in range(2_000)])

        assert many_time > few_time, (
            f"a longer candidate tuple must cost more: {many_time:.2e}s vs {few_time:.2e}s"
        )


class _ExpensiveMeta(type):
    checks = 0

    def __instancecheck__(cls, instance: object) -> bool:
        _ExpensiveMeta.checks += 1
        return False


class _Expensive(metaclass=_ExpensiveMeta):
    pass


class TestUnicodeDataCaveats:
    """docs/stdlib/unicodedata.md priced lookup() at O(1) and normalization
    as linear. The lookup claim was wrong; the normalization claim became true
    after CPython replaced its quadratic insertion sort for long combining runs
    to fix CVE-2026-3276."""

    def test_lookup_reads_the_whole_name(self) -> None:
        assert unicodedata.lookup("GREEK SMALL LETTER MU") == "μ"
        with pytest.raises(KeyError):
            # A prefix of a valid name fails, so the whole name is examined.
            unicodedata.lookup("GREEK SMALL LETTER M")

    @pytest.mark.timing
    def test_patched_normalization_is_linear_in_a_combining_run(self) -> None:
        """Twenty times the marks in one run should cost about twenty times.

        The page documents the pre-fix quadratic shape but this asserts only
        the patched one, so the threshold has to exclude the shape it replaced:
        counting sort predicts 20x, insertion sort 400x, and 100x sits five
        times above the first and four below the second. Unpatched
        interpreters measured 350-400x here (3.11.14, 3.12.3, 3.13.11, 3.14.2),
        so the excluded end is not theoretical.
        """
        # 3.15 and later shipped with the fix, so a minor absent from this map
        # is treated as patched. A distributor that backports while keeping an
        # older version number is skipped rather than run -- the wrong call for
        # coverage, but the safe one, since the alternative fails a Python that
        # is not actually vulnerable.
        fixed_releases = {
            (3, 10): (3, 10, 21),
            (3, 11): (3, 11, 16),
            (3, 12): (3, 12, 14),
            (3, 13): (3, 13, 14),
            (3, 14): (3, 14, 6),
        }
        release = fixed_releases.get(sys.version_info[:2])
        if release is not None and sys.version_info[:3] < release:
            version = ".".join(str(part) for part in sys.version_info[:3])
            needed = ".".join(str(part) for part in release)
            message = f"Python {version} predates the CVE-2026-3276 fix in {needed}"
            # The `timing` job pins a patched interpreter so that this runs. A
            # skip there means the pin drifted, not that the claim cannot be
            # checked -- and a drifted pin is invisible if it stays a skip.
            if os.environ.get("COMPLEXITY_REQUIRE_PATCHED_PYTHON"):
                pytest.fail(f"{message}, but this job pins one to check the claim")
            pytest.skip(message)

        def run(marks: int) -> Callable[[], str]:
            text = "a" + "".join(chr(0x0300 + (i % 40)) for i in range(marks))
            return lambda: unicodedata.normalize("NFC", text)

        small = best_time(run(1_000))
        large = best_time(run(20_000))

        assert large / small < 100, (
            f"twenty times the input should stay near twenty times the time "
            f"after the security fix: {small:.2e}s vs {large:.2e}s "
            f"({large / small:.0f}x)"
        )

    def test_is_normalized_agrees_with_normalize(self) -> None:
        text = "café"
        assert unicodedata.is_normalized("NFC", text) is False
        assert unicodedata.normalize("NFC", text) != text


class TestIntFromStringIsSuperlinear:
    """docs/builtins/float_func.md priced int(str) at O(n) alongside float().

    How superlinear depends on the version: decimal-to-binary conversion is
    quadratic up to 3.11, and about O(n^1.58) from 3.12, which added a
    subquadratic path for large inputs. What survives both is that it is not
    linear, which is why there is a digit cap at all.

    So this compares four times the digits rather than twice, where the two
    algorithms are 16x and 9x against linear's 4x - far enough apart from
    linear to assert on, and far enough from each other not to need a
    version check. Measured here: 16.5x on 3.11, 9.7x on 3.14.
    """

    # Four times the input. Linear would be 4x, so 6x separates "not linear"
    # from either real implementation with room to spare.
    DIGIT_MULTIPLE = 4
    SUPERLINEAR_AT_4X = 6.0

    @pytest.mark.timing
    def test_parsing_four_times_the_digits_costs_far_more(self) -> None:
        limit = sys.get_int_max_str_digits()
        sys.set_int_max_str_digits(2_000_000)
        try:
            small_digits = "9" * 20_000
            large_digits = "9" * (20_000 * self.DIGIT_MULTIPLE)
            small = best_time(lambda: int(small_digits))
            large = best_time(lambda: int(large_digits))
        finally:
            sys.set_int_max_str_digits(limit)

        assert large / small > self.SUPERLINEAR_AT_4X, (
            f"int(str) should be superlinear on any version: "
            f"{large / small:.1f}x for {self.DIGIT_MULTIPLE}x the digits "
            f"({small:.2e}s vs {large:.2e}s)"
        )

    def test_a_digit_cap_exists_because_of_that_cost(self) -> None:
        assert sys.int_info.default_max_str_digits == 4300
        with pytest.raises(ValueError):
            int("9" * (sys.int_info.default_max_str_digits + 1))

    def test_float_has_no_such_cap(self) -> None:
        # float() only scans: the result is fixed width however many digits
        # it is given.
        assert float("9" * 10_000) == float("inf")


class TestDecimalIsNotAConstantFactorOverFloat:
    """docs/builtins/round.md called Decimal "a constant factor over float,
    not a change in complexity". It is a change in complexity."""

    @pytest.mark.timing
    def test_multiplication_scales_with_the_digit_count(self) -> None:
        precision = getcontext().prec
        getcontext().prec = 200_000
        try:
            small_value = Decimal("1." + "9" * 5_000)
            large_value = Decimal("1." + "9" * 10_000)
            small = best_time(lambda: small_value * small_value)
            large = best_time(lambda: large_value * large_value)
        finally:
            getcontext().prec = precision

        assert large / small > SUPERLINEAR_RATIO, (
            f"Decimal multiplication should grow with digits: {small:.2e}s vs {large:.2e}s"
        )

    @pytest.mark.timing
    def test_float_multiplication_does_not(self) -> None:
        small, large = 1.9, 1.9e300
        small_time = best_time(lambda: [small * small for _ in range(10_000)])
        large_time = best_time(lambda: [large * large for _ in range(10_000)])
        assert max(small_time, large_time) < min(small_time, large_time) * 3


class TestAnchoredRegexIsBoundedByThePattern:
    """docs/stdlib/fnmatch.md called a fixed anchored re.match() O(n) in the
    filename. It examines a bounded prefix."""

    @pytest.mark.timing
    def test_match_cost_ignores_the_rest_of_the_string(self) -> None:
        pattern = re.compile(r"test[0-9]{3}\.txt")
        short, long = "x" * 10, "x" * 100_000

        short_time = best_time(lambda: [pattern.match(short) for _ in range(20_000)])
        long_time = best_time(lambda: [pattern.match(long) for _ in range(20_000)])

        assert long_time < short_time * 3, (
            f"an anchored fixed pattern should not scale with the subject: "
            f"{short_time:.2e}s vs {long_time:.2e}s"
        )


class TestIndexingIsNotConstantForEverySequence:
    """docs/builtins/range.md wrote items[i] as O(1) without qualification.

    deque is the stdlib counterexample: indexing walks blocks.
    """

    @pytest.mark.timing
    def test_deque_middle_indexing_is_far_slower_than_list(self) -> None:
        size = 100_000
        as_list = list(range(size))
        as_deque = deque(as_list)
        middle = size // 2

        list_time = best_time(lambda: [as_list[middle] for _ in range(2_000)])
        deque_time = best_time(lambda: [as_deque[middle] for _ in range(2_000)])

        assert deque_time > list_time * 3, (
            f"deque indexing should not look constant-time: "
            f"list={list_time:.2e}s deque={deque_time:.2e}s"
        )


class TestFileinputHoldsTheCurrentLine:
    """docs/stdlib/fileinput.md priced iteration at O(1) space. It holds one
    line, and a line can be arbitrarily long."""

    def test_a_single_long_line_is_materialized_whole(self, tmp_path: Path) -> None:
        import fileinput

        length = 200_000
        source = tmp_path / "one_long_line.txt"
        source.write_text("x" * length + "\n", encoding="utf-8")

        with fileinput.input([str(source)]) as lines:
            first = next(iter(lines))

        assert len(first.rstrip("\n")) == length, (
            "the whole line is in memory, so the space bound is the longest line"
        )


class TestRecursiveGlobScalesWithEntries:
    """docs/stdlib/glob.md priced recursive ** at O(depth) in three places.

    It examines every entry in the walked tree.
    """

    def test_entries_examined_track_file_count_not_depth(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _build_tree(tmp_path / "deep", depth=8, files_per_dir=1)
        _build_tree(tmp_path / "wide", depth=1, files_per_dir=200)

        deep_seen = _count_scandir_entries(monkeypatch, tmp_path / "deep")
        wide_seen = _count_scandir_entries(monkeypatch, tmp_path / "wide")

        assert wide_seen > deep_seen * 5, (
            f"a shallow tree with more files must cost more than a deep one: "
            f"deep={deep_seen} wide={wide_seen}"
        )


def _build_tree(root: Path, depth: int, files_per_dir: int) -> None:
    directory = root
    for level in range(depth):
        directory.mkdir(parents=True, exist_ok=True)
        for index in range(files_per_dir):
            (directory / f"f{index}.txt").write_text("", encoding="utf-8")
        directory = directory / f"sub{level}"
    directory.mkdir(parents=True, exist_ok=True)


def _count_scandir_entries(monkeypatch: pytest.MonkeyPatch, root: Path) -> int:
    """Run a recursive glob over root and count the directory entries read."""
    real_scandir = os.scandir
    counter = {"seen": 0}

    class CountingScandir:
        def __init__(self, path: Any = ".") -> None:
            self._it = real_scandir(path)

        def __enter__(self) -> "CountingScandir":
            return self

        def __exit__(self, *exc: object) -> bool:
            self._it.close()
            return False

        def __iter__(self) -> Iterator[Any]:
            return self

        def __next__(self) -> Any:
            entry = next(self._it)
            counter["seen"] += 1
            return entry

        def close(self) -> None:
            self._it.close()

    with monkeypatch.context() as patched:
        patched.setattr(os, "scandir", CountingScandir)
        glob.glob(str(root / "**" / "*.py"), recursive=True)
    return counter["seen"]


class TestCopytreeCostsPerEntry:
    """docs/stdlib/shutil.md priced copytree() in bytes copied alone. It also
    walks and stats every entry."""

    def test_copying_empty_files_still_does_work_per_file(self, tmp_path: Path) -> None:
        source = tmp_path / "src"
        source.mkdir()
        for index in range(50):
            (source / f"empty{index}.dat").write_bytes(b"")

        copied: list[str] = []

        def counting_copy(src: Any, dst: Any, **kwargs: Any) -> Any:
            copied.append(str(src))
            return shutil.copy2(src, dst, **kwargs)

        shutil.copytree(source, tmp_path / "dst", copy_function=counting_copy)

        assert len(copied) == 50, "zero bytes copied, fifty entries of work"


class TestSqliteInsertTouchesEveryIndex:
    """docs/stdlib/sqlite3.md priced INSERT at an unconditional O(log n)."""

    @pytest.mark.timing
    def test_more_indexes_make_inserts_slower(self) -> None:
        rows = [(i, i, i, i, i) for i in range(4_000)]

        def insert_with(index_count: int) -> float:
            connection = sqlite3.connect(":memory:")
            connection.execute("CREATE TABLE t (a INT, b INT, c INT, d INT, e INT)")
            for position, column in enumerate("abcde"[:index_count]):
                connection.execute(f"CREATE INDEX i{position} ON t({column})")

            start = time.perf_counter()
            connection.executemany("INSERT INTO t VALUES (?,?,?,?,?)", rows)
            connection.commit()
            elapsed = time.perf_counter() - start
            connection.close()
            return elapsed

        unindexed = min(insert_with(0) for _ in range(3))
        indexed = min(insert_with(5) for _ in range(3))

        assert indexed > unindexed, (
            f"each index is another B-tree insert: {unindexed:.2e}s vs {indexed:.2e}s"
        )


class TestFractionDenominatorsGrowThroughASum:
    """docs/stdlib/fractions.md implied a fixed cost per addition. Unless the
    denominators share factors they multiply out, so every later step is
    working with bigger numbers."""

    def test_coprime_denominators_multiply_out(self) -> None:
        primes = [2, 3, 5, 7, 11, 13, 17, 19]
        total = sum((Fraction(1, p) for p in primes), Fraction(0))

        product = 1
        for prime in primes:
            product *= prime
        assert total.denominator == product

    def test_shared_factors_do_not_grow(self) -> None:
        total = sum((Fraction(1, 8) for _ in range(8)), Fraction(0))
        assert total == 1
        assert total.denominator == 1


class TestLoggingFormatsPerHandler:
    """docs/stdlib/logging.md priced exception logging by stack depth. The
    formatting happens once per emitting handler."""

    def test_every_handler_formats_the_record(self) -> None:
        logger = logging.getLogger("test_complexity_caveats")
        logger.handlers.clear()
        logger.propagate = False
        logger.setLevel(logging.DEBUG)

        formatters = [_CountingFormatter(), _CountingFormatter()]
        for formatter in formatters:
            handler = logging.StreamHandler(io.StringIO())
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        try:
            try:
                raise ValueError("boom")
            except ValueError:
                logger.exception("failed")
        finally:
            logger.handlers.clear()

        assert [formatter.calls for formatter in formatters] == [1, 1]


class _CountingFormatter(logging.Formatter):
    """A formatter that records how often it was asked to render a record."""

    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def format(self, record: logging.LogRecord) -> str:
        self.calls += 1
        return super().format(record)
