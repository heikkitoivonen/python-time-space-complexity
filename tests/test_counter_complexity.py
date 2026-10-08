"""Tests for docs/stdlib/counter.md.

`Counter` is a `dict` subclass whose arithmetic, comparison and selection
methods are Python loops over `items()`, lookups and `heapq`. Almost every row
is settled by observation: a subclass that counts its `items()` visits,
lookups and membership probes shows which operand an operator walks and how
often, recording wrappers around `heapq` and `sorted` show which selection path
`most_common()` takes, and traced allocation shows what counting holds. Only
the constant-time lookup and the linear-time update use a stopwatch.

Measurement scope:

* Counting an iterator consumes it and stores one key per distinct item, at 10
  and 1,000 items over 2 and 10 keys. Counting a generator of 200,000 items
  over ten keys peaks under 20 KB; the same number of distinct items peaks
  over 2 MB. `update()` with a mapping on a non-empty counter visits the
  mapping's items once and adds its values; keyword arguments add the same
  way. In a timing test, `update()` with 20,000, 200,000 and 2,000,000 items
  over 1,000 keys costs under 25x per 10x step.
* A missing key reads as 0 without being inserted, a count taken to zero stays
  in the counter, `del` on a missing key does not raise and `get()` returns
  `None`. A timing test holds 10,000 lookups under 3x from a 1,000-key to a
  200,000-key counter.
* `subtract()` with a 500-key mapping grows a one-key counter to 501 keys, an
  absent key ends negative, and an iterable creates its keys at -1.
* `most_common()` with no argument passes all n items to one `sorted()` call.
  With k it calls `heapq.nlargest`: k == 1 calls `max()` once and neither
  `heapify()` nor `sorted()`, k >= n calls `sorted()` and not `heapify()`, and
  at 128 and 8,192 keys with k of 2, 10 and 64 the heap is built at size k and
  stays there. Counts rising in iteration order replace its root n - k times,
  falling counts never. Ties keep insertion order. `repr()` calls
  `most_common()` once with no argument, and lists complex counts, which
  cannot be ordered, in insertion order.
* `elements()` visits no key when it is created and every key once when it is
  exhausted, at 10 and 1,000 keys with counts 0 and 5, yielding only positive
  counts. `total()` visits each value once and includes zero and negative
  counts.
* `copy()` returns the counter's class, every key, and the same count objects;
  `copy.copy()` and a pickle round trip return equal counters of the same
  class. `fromkeys()` raises `NotImplementedError`.
* `+`, `-` and `|` visit each operand's items once, with one lookup per left
  key and one membership probe per right key, at 10 and 1,000 keys a side,
  overlapping and disjoint. `&` visits the left operand's items once, makes
  one lookup in the right per left key, and never visits the right's items.
  Results drop non-positive counts.
* `+=`, `-=` and `|=` with a one-key operand visit all 1,000 items of the
  counter they update, and `&=` visits them twice; `update()` and `subtract()`
  with the same operand visit none of them.
* `==` makes two lookups per key of each operand when the two agree; a missing
  key counts as zero against a `Counter`, not against a `dict`.
* A 1,000-key counter's `sys.getsizeof` is within 1,000 bytes of the `dict`
  holding the same items.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* Treating key hashing and comparison, and rendering or pickling one entry,
  as O(1) is the page's cost model; keys with expensive `__hash__`, `__eq__`
  or `__repr__` are outside its bounds.
* The O(n log k) bound for `most_common(k)` is read from `heapq.nlargest` in
  Lib/heapq.py: the replacement count above, times one O(log k) heap
  operation each. How many replacements random or Zipf-like counts cause is
  not measured; only the two monotone orders are.
* Count magnitudes, key types and insertion order other than the shapes named
  above are not varied.
"""

from __future__ import annotations

import builtins
import collections
import copy
import heapq
import pathlib
import pickle
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections import Counter
from collections.abc import Callable, Iterator
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "counter.md"
EXPECTED_BLOCKS = 9


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


class Tally:
    """What an observed counter's operations touched."""

    def __init__(self) -> None:
        self.visits = 0
        self.lookups = 0
        self.probes = 0


class ObservedCounter(Counter):
    """A counter that records item visits, lookups and membership probes."""

    tally: Tally

    def items(self) -> Iterator[tuple[Any, int]]:  # pyright: ignore[reportIncompatibleMethodOverride]
        # A generator observes consumption instead of returning a dict view.
        for key, value in super().items():
            self.tally.visits += 1
            yield key, value

    def __getitem__(self, key: Any) -> int:
        self.tally.lookups += 1
        return super().__getitem__(key)

    def __contains__(self, key: Any) -> bool:
        self.tally.probes += 1
        return super().__contains__(key)


def observed(counts: dict[Any, int]) -> ObservedCounter:
    """An observed counter holding `counts`, with a fresh tally."""
    counter = ObservedCounter()
    counter.tally = Tally()
    dict.update(counter, counts)
    return counter


class CounterSubclass(Counter):
    """A module-level subclass, so that it can be pickled."""


class TestCountingHoldsDistinctKeys:
    """`Counter(iterable)` and `update()` are O(t + m) time and keep O(n): one
    key per distinct item, never the items, and a mapping adds its values."""

    @pytest.mark.parametrize("size", [10, 1_000])
    @pytest.mark.parametrize("distinct", [2, 10])
    def test_construction_consumes_items_and_stores_distinct_keys(
        self, size: int, distinct: int
    ) -> None:
        items = iter(index % distinct for index in range(size))
        counter = Counter(items)
        assert list(items) == []
        assert len(counter) == distinct
        assert counter == dict.fromkeys(range(distinct), size // distinct)

    def test_counting_a_generator_holds_the_keys_not_the_items(self) -> None:
        repeated = peak_bytes(lambda: Counter(x % 10 for x in range(200_000)))
        distinct = peak_bytes(lambda: Counter(x for x in range(200_000)))

        assert repeated < 20_000, f"ten keys peaked at {repeated} bytes"
        assert distinct > 2_000_000, f"200,000 keys peaked at only {distinct} bytes"

    def test_a_mapping_adds_its_values(self) -> None:
        counter = Counter("mississippi")
        source = observed({"m": 2, "z": 1})
        counter.update(source)

        assert source.tally.visits == 2
        assert counter["m"] == 3 and counter["z"] == 1 and counter["s"] == 4

    def test_keyword_arguments_add_like_a_mapping(self) -> None:
        counter = Counter(a=1)
        counter.update(a=2, b=1)
        assert dict(counter) == {"a": 3, "b": 1}
        assert Counter(a=3, b=1) == Counter({"a": 3, "b": 1})

    @pytest.mark.timing
    def test_update_is_linear_in_the_items(self) -> None:
        sizes = (20_000, 200_000, 2_000_000)
        samples = [[index % 1_000 for index in range(size)] for size in sizes]
        times = [best_ns(lambda s=sample: Counter().update(s), repeats=5) for sample in samples]

        for small, large in zip(times, times[1:], strict=False):
            assert large < small * 25, f"10x the items cost x{large / small:.1f}: {times}"


class TestMissingKeysReadAsZero:
    """`c[key]` is O(1) and inserts nothing on a miss; zero counts stay until
    deleted, `del` of a missing key is silent, and `get()` is dict's."""

    def test_a_missing_key_reads_as_zero_without_being_created(self) -> None:
        counter = Counter(a=2)
        assert counter["absent"] == 0
        assert "absent" not in counter and len(counter) == 1
        assert counter.get("absent") is None

    def test_a_count_taken_to_zero_stays(self) -> None:
        counter = Counter(a=2)
        counter["a"] -= 2
        assert "a" in counter and len(counter) == 1 and list(counter) == ["a"]

    def test_deleting_a_missing_key_is_silent(self) -> None:
        counter = Counter(a=1)
        del counter["a"]
        del counter["a"]
        assert len(counter) == 0

    def test_len_counts_keys_not_elements(self) -> None:
        assert len(Counter(a=1_000)) == 1

    @pytest.mark.timing
    def test_lookup_is_constant_time(self) -> None:
        small = Counter(range(1_000))
        large = Counter(range(200_000))

        small_ns = best_ns(lambda: [small[500] for _ in range(10_000)])
        large_ns = best_ns(lambda: [large[100_000] for _ in range(10_000)])

        assert large_ns < small_ns * 3, f"lookup: {small_ns:.0f}ns vs {large_ns:.0f}ns"


class TestSubtractGrowsTheCounter:
    """`subtract()` is O(u) space: every absent key it subtracts is created,
    and zero and negative counts are kept, where `-` drops them."""

    def test_space_grows_with_the_argument(self) -> None:
        counter = Counter(a=1)
        counter.subtract({f"k{index}": 1 for index in range(500)})

        assert len(counter) == 501
        assert counter["k0"] == -1

    def test_an_iterable_creates_its_keys_negative(self) -> None:
        counter = Counter(a=1)
        counter.subtract("abb")
        assert dict(counter) == {"a": 0, "b": -2}

    def test_negative_counts_are_kept_and_the_operator_drops_them(self) -> None:
        counter = Counter(a=1)
        counter.subtract(Counter(a=3, b=2))
        assert dict(counter) == {"a": -2, "b": -2}

        assert Counter(a=1) - Counter(a=3, b=2) == Counter()
        assert +counter == Counter()


class TestMostCommonSelectionPath:
    """`most_common()` sorts all n; `most_common(k)` keeps a k-item heap, with
    `max()` for k == 1 and a full sort for k >= n. Only an item beating the
    heap's smallest pays a replacement, so rising counts are the worst case."""

    @pytest.fixture
    def calls(self, monkeypatch: pytest.MonkeyPatch) -> dict[str, list[int]]:
        """Record the size of each heapify, sorted and max call in heapq."""
        recorded: dict[str, list[int]] = {"heapify": [], "sorted": [], "max": []}

        def recorder(name: str, original: Callable[..., Any]) -> Callable[..., Any]:
            def record(iterable: Any, *args: Any, **kwargs: Any) -> Any:
                items = list(iterable)
                recorded[name].append(len(items))
                if name == "heapify":
                    original(iterable)
                    return None
                return original(items, *args, **kwargs)

            return record

        monkeypatch.setattr(heapq, "heapify", recorder("heapify", heapq.heapify))
        monkeypatch.setattr(heapq, "sorted", recorder("sorted", builtins.sorted), raising=False)
        monkeypatch.setattr(heapq, "max", recorder("max", builtins.max), raising=False)
        return recorded

    def test_results_and_ties(self) -> None:
        counter = Counter("abracadabra")
        assert counter.most_common(2) == [("a", 5), ("b", 2)]
        assert counter.most_common(1) == [("a", 5)]
        assert counter.most_common() == [("a", 5), ("b", 2), ("r", 2), ("c", 1), ("d", 1)]

    def test_no_argument_sorts_every_item(self, monkeypatch: pytest.MonkeyPatch) -> None:
        sizes: list[int] = []

        def record(iterable: Any, **kwargs: Any) -> list[Any]:
            items = list(iterable)
            sizes.append(len(items))
            return builtins.sorted(items, **kwargs)

        monkeypatch.setattr(collections, "sorted", record, raising=False)
        counter = Counter({f"k{index}": index for index in range(1_000)})
        assert counter.most_common()[0] == ("k999", 999)
        assert sizes == [1_000]

    def test_k_of_one_is_one_max_pass(self, calls: dict[str, list[int]]) -> None:
        counter = Counter({f"k{index}": index for index in range(1_000)})
        assert counter.most_common(1) == [("k999", 999)]
        assert calls == {"heapify": [], "sorted": [], "max": [1_000]}

    def test_k_of_at_least_n_sorts_everything(self, calls: dict[str, list[int]]) -> None:
        counter = Counter({f"k{index}": index for index in range(100)})
        assert counter.most_common(500)[0] == ("k99", 99)
        assert calls == {"heapify": [], "sorted": [100], "max": []}

    @pytest.mark.parametrize("ascending", [True, False])
    @pytest.mark.parametrize("k", [2, 10, 64])
    def test_count_order_controls_heap_replacements(
        self, monkeypatch: pytest.MonkeyPatch, ascending: bool, k: int
    ) -> None:
        """Strictly rising counts replace the heap root n - k times; falling
        counts replace it zero times. Heap size stays k and both orders return
        the same top k. This does not compare elapsed time with sorting."""
        replacements = 0
        original_replace = heapq.heapreplace
        original_heapify = heapq.heapify
        heap_sizes: list[int] = []

        def heapify(heap: list[Any]) -> None:
            heap_sizes.append(len(heap))
            original_heapify(heap)

        def replace(heap: list[Any], item: Any) -> Any:
            nonlocal replacements
            replacements += 1
            assert len(heap) == k
            return original_replace(heap, item)

        monkeypatch.setattr(heapq, "heapreplace", replace)
        monkeypatch.setattr(heapq, "heapify", heapify)
        for size in (128, 8_192):
            counts = range(size) if ascending else range(size - 1, -1, -1)
            counter = Counter({f"k{count}": count for count in counts})
            replacements = 0
            heap_sizes.clear()
            result = counter.most_common(k)
            assert heap_sizes == [k]
            assert replacements == (size - k if ascending else 0)
            assert result == [(f"k{count}", count) for count in range(size - 1, size - k - 1, -1)]

    def test_repr_sorts_through_most_common(self) -> None:
        calls: list[Any] = []

        class Recording(Counter):
            def most_common(self, n: int | None = None) -> list[tuple[Any, int]]:
                calls.append(n)
                return super().most_common(n)

        counter = Recording("abracadabra")
        assert repr(counter) == "Recording({'a': 5, 'b': 2, 'r': 2, 'c': 1, 'd': 1})"
        assert calls == [None]

    def test_repr_falls_back_to_insertion_order_for_unorderable_counts(self) -> None:
        counter = Counter({"a": 1j, "b": 2j})
        assert repr(counter) == "Counter({'a': 1j, 'b': 2j})"


class TestElementsTotalsAndCopies:
    """`elements()` is lazy and O(n + e), `total()` is O(n) over every count,
    `copy()` is a shallow O(n) copy of the counter's class, and `fromkeys()`
    raises."""

    @pytest.mark.parametrize("size", [10, 1_000])
    @pytest.mark.parametrize("count", [0, 5])
    def test_elements_visits_keys_lazily_and_repeats_positive_counts(
        self, size: int, count: int
    ) -> None:
        counter = observed(dict.fromkeys(range(size), count))
        dict.__setitem__(counter, -1, -2)
        elements = counter.elements()
        assert counter.tally.visits == 0
        assert list(elements) == [key for key in range(size) for _ in range(count)]
        assert counter.tally.visits == size + 1

    def test_total_visits_each_count_once_including_non_positive_ones(self) -> None:
        visits = 0

        class Recording(Counter):
            def values(self) -> Iterator[int]:  # pyright: ignore[reportIncompatibleMethodOverride]
                nonlocal visits
                for value in super().values():
                    visits += 1
                    yield value

        assert Recording(a=3, b=0, c=-1).total() == 2
        assert visits == 3

    @pytest.mark.parametrize("size", [10, 1_000])
    def test_copy_preserves_every_key_and_shares_count_objects(self, size: int) -> None:
        counter = Counter(dict.fromkeys(range(size), 10**30))
        copied = counter.copy()
        assert copied is not counter and copied == counter
        assert len(copied) == size
        assert all(copied[key] is counter[key] for key in counter)

    def test_copies_and_pickles_keep_the_class(self) -> None:
        counter = CounterSubclass("aab")
        assert counter.__reduce__() == (CounterSubclass, ({"a": 2, "b": 1},))
        for result in (counter.copy(), copy.copy(counter), pickle.loads(pickle.dumps(counter))):
            assert type(result) is CounterSubclass and result == counter

    def test_fromkeys_is_unsupported(self) -> None:
        with pytest.raises(NotImplementedError, match=re.escape("Counter(iterable)")):
            Counter.fromkeys(["a", "b"])


class TestBinaryOperatorsWalkTheirOperands:
    """`+`, `-` and `|` are O(n + m), visiting both operands; `&` is O(n),
    visiting only the left operand and looking each key up in the right."""

    @pytest.mark.parametrize("operator", ["+", "-", "|"])
    @pytest.mark.parametrize("left_size", [10, 1_000])
    @pytest.mark.parametrize("right_size", [10, 1_000])
    @pytest.mark.parametrize("overlap", [False, True])
    def test_both_operands_are_walked_once(
        self, operator: str, left_size: int, right_size: int, overlap: bool
    ) -> None:
        offset = 0 if overlap else left_size
        left_counts = dict.fromkeys(range(left_size), 2)
        right_counts = dict.fromkeys(range(offset, offset + right_size), 3)
        left, right = observed(left_counts), observed(right_counts)
        tally = Tally()
        left.tally = right.tally = tally

        result = {"+": left.__add__, "-": left.__sub__, "|": left.__or__}[operator](right)

        assert tally.visits == left_size + right_size
        assert tally.lookups == left_size
        assert tally.probes == right_size
        plain = {"+": Counter.__add__, "-": Counter.__sub__, "|": Counter.__or__}[operator]
        assert result == plain(Counter(left_counts), Counter(right_counts))

    @pytest.mark.parametrize(("left_size", "right_size"), [(10, 1_000), (1_000, 10)])
    def test_intersection_walks_only_the_left_operand(
        self, left_size: int, right_size: int
    ) -> None:
        left = observed(dict.fromkeys(range(left_size), 2))
        right = observed(dict.fromkeys(range(right_size), 3))

        result = left & right

        assert left.tally.visits == left_size and left.tally.lookups == 0
        assert right.tally.visits == 0 and right.tally.lookups == left_size
        assert result == dict.fromkeys(range(min(left_size, right_size)), 2)
        assert len(result) <= min(left_size, right_size)

    def test_results_drop_non_positive_counts(self) -> None:
        a, b = Counter(x=3, y=1), Counter(x=1, y=2, z=4)
        assert a + b == Counter(x=4, y=3, z=4)
        assert dict(a - b) == {"x": 2}
        assert a | b == Counter(x=3, y=2, z=4)
        assert dict(a & b) == {"x": 1, "y": 1} and b & a == a & b
        assert dict(Counter(a=1) + Counter(a=-1)) == {}
        assert dict(Counter(a=-1, b=0) | Counter(a=-2)) == {}
        assert dict(Counter(a=2, b=1) & Counter(a=-1, b=1)) == {"b": 1}

    def test_unary_operators_keep_one_sign(self) -> None:
        counter = Counter(a=1, b=-2, c=0)
        assert dict(+counter) == {"a": 1}
        assert dict(-counter) == {"b": 2}


class TestInPlaceOperatorsRescanTheCounter:
    """`+=`, `-=` and `|=` are O(n + m) and `&=` O(n), because each scans the
    whole counter afterwards; `update()` and `subtract()` touch only `other`."""

    SIZE = 1_000

    @pytest.mark.parametrize(("operator", "scans"), [("+=", 1), ("-=", 1), ("|=", 1), ("&=", 2)])
    def test_a_one_key_operand_still_scans_every_key(self, operator: str, scans: int) -> None:
        counter = observed(dict.fromkeys(range(self.SIZE), 5))
        other = Counter({0: 1})

        method = {
            "+=": counter.__iadd__,
            "-=": counter.__isub__,
            "|=": counter.__ior__,
            "&=": counter.__iand__,
        }[operator]
        method(other)

        assert counter.tally.visits == scans * self.SIZE

    @pytest.mark.parametrize("method", ["update", "subtract"])
    def test_update_and_subtract_touch_only_the_operand(self, method: str) -> None:
        counter = observed(dict.fromkeys(range(self.SIZE), 5))
        getattr(counter, method)(Counter({0: 1}))

        assert counter.tally.visits == 0
        assert counter[0] == (6 if method == "update" else 4)

    def test_in_place_deletes_what_update_keeps(self) -> None:
        totals = Counter(a=1, b=-1)
        totals.update(c=2)
        assert dict(totals) == {"a": 1, "b": -1, "c": 2}
        totals += Counter(c=1)
        assert dict(totals) == {"a": 1, "c": 3}


class TestComparisons:
    """Comparisons are O(n + m) and O(1) space; against a `Counter` a missing
    key counts as zero, against a plain `dict` it is `dict` equality."""

    @pytest.mark.parametrize("size", [10, 1_000])
    def test_equality_looks_up_each_key_of_both_operands(self, size: int) -> None:
        left = observed(dict.fromkeys(range(size), 1))
        right = observed(dict.fromkeys(range(size), 1))
        tally = Tally()
        left.tally = right.tally = tally

        assert left == right
        assert tally.lookups == 4 * size

    def test_missing_counts_as_zero_only_against_a_counter(self) -> None:
        assert Counter(x=1, y=0) == Counter(x=1)
        assert Counter(x=1, y=0) != {"x": 1}

    def test_inclusion(self) -> None:
        a, b = Counter(x=3, y=1), Counter(x=1, y=2, z=4)
        assert a <= a + b and not a <= b
        assert a + b >= a and a + b > a and not a < a


class TestCounterIsADictSubclass:
    """A counter costs what the `dict` holding the same keys does."""

    def test_it_costs_about_what_the_dict_would(self) -> None:
        counter = Counter(range(1_000))
        plain = dict(counter)

        assert isinstance(counter, dict)
        assert abs(sys.getsizeof(counter) - sys.getsizeof(plain)) < 1_000, (
            f"Counter {sys.getsizeof(counter)} vs dict {sys.getsizeof(plain)}"
        )


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
        line, source = next((n, s) for n, s in _blocks() if "c['m'] == 4" in s)
        mutated = source.replace("c['m'] == 4", "c['m'] == 3", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
