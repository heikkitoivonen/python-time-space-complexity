"""Tests for docs/stdlib/pstats.md.

The page prices a `Stats` object as the whole profile in memory: f functions,
each with a caller dictionary, e caller edges in all. Almost every claim is
settled by observation. Profiles are built as plain dictionaries in the format
`cProfile` produces and handed to `Stats` through an object with a
`create_stats()` method, or written with `marshal` and loaded by filename, so
no profiler is ever installed in the test process. Work is counted by
substituting counting versions of the module-level helpers and of the
comparison `sort_stats()` sorts with, and space is a traced allocation peak.
No test here uses a stopwatch.

Measurement scope:

* Loading: `Stats(filename)` peaks more than 50x higher at 10 functions with
  10,000 callers each than at 10 callers each, and more than 20x higher at
  10,000 single-caller functions than at 100. `dump_stats()` peaks more than
  10x higher over the same 1,000x step in edges, and round-trips the
  dictionary exactly. A profiler object has `create_stats()` called once;
  `Stats(a, b)` equals `Stats(a).add(b)`, and `Stats()` is empty.
* `add()` sums counts and unions callers. A function both profiles share gets
  a new caller dictionary holding the old entries plus the new, the old one
  left untouched: merging a one-caller profile into a function with 100,000
  callers peaks more than 100x higher than merging one that shares nothing.
  It sets the sort order back to none.
* `strip_dirs()` calls the path-stripping helper exactly f + e times over 500
  functions with three callers each. g = 200 entries that collide once
  directories are gone merge into one, their counts summed; with pairwise
  distinct callers the merges copy g(g - 1) / 2 existing caller entries, and
  with one shared caller g - 1. It drops the sort order and the callee map.
* `sort_stats()` on 1,000 and 100,000 functions with seeded random times makes
  between f·log2(f)/2 and f·log2(f) comparisons at each size, and the larger
  profile makes between 130x and 1,000x the comparisons of the smaller:
  linear would be 100x, quadratic 10,000x. Its peak rises more than 20x from
  100 to 10,000 functions. Key forms are asserted by result: `SortKey`
  members, strings, an unambiguous prefix, a `KeyError` for an ambiguous one,
  a `TypeError` for a mix, and later keys breaking only ties.
* `reverse_order()` reverses the same list object with a traced peak under
  1 KB at 10,000 functions, and leaves an unsorted profile unsorted.
* Print restrictions: a counting regex is searched 1,000 times by
  `print_stats('fn')` and by `print_stats('fn', 10)` over 1,000 functions, and
  10 times by `print_stats(10, 'fn')`. `print_stats(1)` peaks more than 20x
  higher at 10,000 functions than at 100, because it copies the ordered list.
  An int keeps that many lines, a float that fraction, and an int at or above
  f keeps them all, counted by the lines printed.
* `print_callers()` sorts once per printed function, a list the length of its
  callers, and never builds the callee map. `print_callees()` builds a map
  holding e entries on its first call and reuses the same object on the
  second; `strip_dirs()` clears it, `add()` does not, and the callees printed
  after `add()` miss the merged call, while the function the merge added
  prints with an empty callee list.
* `get_stats_profile()` returns one `FunctionProfile` per function name, in
  sort order; two functions named alike in different files leave one entry,
  the later one in that order.
  `ncalls` is `'3/1'` for three calls of which one was primitive.
* `SortKey` has the nine members the page lists, and `SortKey('ncalls')` is
  `SortKey.CALLS`. `str(SortKey.TIME)` is `'time'` from 3.11 and
  `'SortKey.TIME'` on 3.10, each side guarded on `sys.version_info`.
  `SortKey` and `get_stats_profile()` both predate the supported range.
* Every method in the `Stats` table except `get_stats_profile()` and
  `dump_stats()` returns the same `Stats` object.
* Every fenced Python block runs in its own subprocess with its own working
  directory, so no example's profiler outlives it, and a mutated assertion in
  one of them is asserted to fail.

Not settled here:

* What `create_stats()` costs. That is the profiler's work, priced on the
  cProfile and profile pages; `Stats(profiler)` is priced from the dictionary
  it receives.
* A regex restriction's pattern cost, and the length of function names, which
  the page prices at O(1) to hash, compare and format.
* The log factors in O(f log f) and Σ c log c come from the builtin sort
  `sort_stats()` and `print_call_line()` call, read from Lib/pstats.py;
  `sort_stats()` is counted on random order only, and an already ordered
  profile needs fewer comparisons.
* The caller dictionaries are the tuple-valued format `cProfile` writes; the
  integer counts the pure-Python `profile` module writes are not varied.
* Whether a file from `dump_stats()` loads under another Python version: the
  marshal format is not guaranteed stable across versions.
* Report layout and column widths are not asserted.
* The page-scoped audit reports no missing names. Its classification review
  lists `SortKey`, `FunctionProfile` and `StatsProfile`, which the page
  documents, and the helpers the official documentation does not:
  `Stats.load_stats`, `init`, `get_top_level_stats`, `get_sort_arg_defs`,
  `sort_arg_dict_default`, `calc_callees`, `eval_print_amount`,
  `get_print_list`, `print_title`, `print_line`, `print_call_heading`,
  `print_call_line`, `TupleComp`, `add_callers`, `add_func_stats`,
  `count_calls`, `f8`, `func_get_function_name`, `func_std_string` and
  `func_strip_path`. Those are left off the page.
"""

from __future__ import annotations

import io
import marshal
import math
import pathlib
import pstats
import random
import re
import subprocess
import sys
import textwrap
import tracemalloc
import types
from collections.abc import Callable
from functools import partial
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "pstats.md"
EXPECTED_BLOCKS = 6
# Module-level helpers the tests count calls to; typeshed does not declare them.
PRIVATE: Any = pstats

Key = tuple[str, int, str]
Entry = tuple[int, int, float, float, dict[Key, Any]]


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


class FakeProfile:
    """Anything with `create_stats()` and a `stats` dict is a profiler to `Stats`."""

    def __init__(self, stats: dict[Key, Entry]) -> None:
        self._stats = stats
        self.snapshots = 0

    def create_stats(self) -> None:
        self.snapshots += 1
        self.stats = self._stats


def fake(stats: dict[Key, Entry]) -> Any:
    """A `FakeProfile`, typed loosely: `Stats` is annotated for real profilers only."""
    return FakeProfile(stats)


def raw_stats(functions: int, callers: int = 1, seed: int = 0) -> dict[Key, Entry]:
    """A cProfile-format dictionary: `functions` entries of `callers` callers each."""
    rng = random.Random(seed)
    stats: dict[Key, Entry] = {}
    for index in range(functions):
        called_by = {
            (f"/src/c{index}_{j}.py", j, f"caller{j}"): (1, 1, 0.001, 0.002) for j in range(callers)
        }
        stats[(f"/src/m{index}.py", index + 1, f"fn{index}")] = (
            1,
            1,
            rng.random(),
            rng.random(),
            called_by,
        )
    return stats


def make_stats(stats: dict[Key, Entry]) -> pstats.Stats:
    return pstats.Stats(fake(stats), stream=io.StringIO())


def write_profile(path: pathlib.Path, stats: dict[Key, Entry]) -> str:
    with open(path, "wb") as handle:
        marshal.dump(stats, handle)
    return str(path)


def printed_lines(stats: pstats.Stats, *restrictions: Any) -> int:
    """How many function lines `print_stats(*restrictions)` writes."""
    count = 0
    original = stats.print_line

    def counting(func: Any) -> None:
        nonlocal count
        count += 1
        original(func)

    stats.print_line = counting  # type: ignore[method-assign]
    try:
        stats.print_stats(*restrictions)
    finally:
        del stats.print_line
    return count


LEAF: Key = ("/src/app.py", 1, "leaf")
BRANCH: Key = ("/src/app.py", 5, "branch")
OTHER: Key = ("/lib/other.py", 9, "other")


def small_graph() -> dict[Key, Entry]:
    """branch calls leaf three times."""
    return {
        BRANCH: (1, 1, 0.1, 0.4, {}),
        LEAF: (3, 3, 0.3, 0.3, {BRANCH: (3, 3, 0.3, 0.3)}),
    }


class TestLoadingIsLinear:
    """`Stats(*filenames_or_profiles)` | O(f + e) | O(f + e), and
    `dump_stats(filename)` | O(f + e) | O(f + e)."""

    def test_a_dumped_profile_loads_back_unchanged(self, tmp_path: pathlib.Path) -> None:
        original = raw_stats(50, callers=3)
        stats = make_stats(original)

        stats.dump_stats(str(tmp_path / "run.prof"))
        reloaded = pstats.Stats(str(tmp_path / "run.prof"), stream=io.StringIO())

        assert reloaded.stats == original  # type: ignore[attr-defined]

    def test_the_peak_grows_with_caller_edges(self, tmp_path: pathlib.Path) -> None:
        sparse = write_profile(tmp_path / "sparse", raw_stats(10, callers=10))
        dense = write_profile(tmp_path / "dense", raw_stats(10, callers=10_000))

        peaks = [peak_bytes(partial(pstats.Stats, path)) for path in (sparse, dense)]

        assert peaks[1] > peaks[0] * 50, f"1,000x the edges at 10 functions: {peaks}"

    def test_the_peak_grows_with_functions(self, tmp_path: pathlib.Path) -> None:
        few = write_profile(tmp_path / "few", raw_stats(100))
        many = write_profile(tmp_path / "many", raw_stats(10_000))

        peaks = [peak_bytes(partial(pstats.Stats, path)) for path in (few, many)]

        assert peaks[1] > peaks[0] * 20, f"100x the functions: {peaks}"

    def test_dumping_holds_the_whole_profile(self, tmp_path: pathlib.Path) -> None:
        target = str(tmp_path / "out.prof")
        peaks = []
        for callers in (10, 10_000):
            stats = make_stats(raw_stats(10, callers=callers))
            peaks.append(peak_bytes(lambda s=stats: s.dump_stats(target)))  # type: ignore[misc]

        assert peaks[1] > peaks[0] * 10, f"1,000x the edges at 10 functions: {peaks}"

    def test_a_profiler_is_snapshotted_once(self) -> None:
        profiler = fake(small_graph())

        stats = pstats.Stats(profiler, stream=io.StringIO())

        assert profiler.snapshots == 1
        assert stats.stats == small_graph()  # type: ignore[attr-defined]

    def test_later_arguments_are_added(self) -> None:
        together = pstats.Stats(fake(small_graph()), fake(small_graph()))
        apart = make_stats(small_graph()).add(fake(small_graph()))

        assert together.stats == apart.stats  # type: ignore[attr-defined]
        assert together.stats[LEAF][:2] == (6, 6)  # type: ignore[attr-defined]

    def test_no_arguments_is_empty(self) -> None:
        empty = pstats.Stats(stream=io.StringIO())

        assert empty.stats == {}  # type: ignore[attr-defined]
        assert empty.get_stats_profile().func_profiles == {}


class TestAddMerges:
    """`add()` | O(f₂ + e₂ + e) per profile: shared functions get a new caller
    dictionary holding both sets, and the sort order is dropped."""

    def test_counts_are_summed_and_callers_unioned(self) -> None:
        stats = make_stats(small_graph())
        extra = {LEAF: (1, 1, 0.1, 0.1, {OTHER: (1, 1, 0.1, 0.1)})}

        stats.add(fake(extra))

        cc, nc, _, _, callers = stats.stats[LEAF]  # type: ignore[attr-defined]
        assert (cc, nc) == (4, 4)
        assert set(callers) == {BRANCH, OTHER}

    def test_a_shared_function_copies_its_existing_callers(self) -> None:
        big = raw_stats(1, callers=100_000)
        key = next(iter(big))
        stats = make_stats(big)
        before = stats.stats[key][4]  # type: ignore[attr-defined]

        stats.add(fake({key: (1, 1, 0.1, 0.1, {OTHER: (1, 1, 0.1, 0.1)})}))

        after = stats.stats[key][4]  # type: ignore[attr-defined]
        assert after is not before
        assert len(after) == 100_001
        assert len(before) == 100_000 and OTHER not in before

    def test_the_copy_is_what_costs(self) -> None:
        peaks = []
        for shared in (True, False):
            big = raw_stats(1, callers=100_000)
            stats = make_stats(big)
            key = next(iter(big)) if shared else OTHER
            other = make_stats({key: (1, 1, 0.1, 0.1, {LEAF: (1, 1, 0.1, 0.1)})})
            peaks.append(peak_bytes(lambda s=stats, o=other: s.add(o)))  # type: ignore[misc]

        assert peaks[0] > peaks[1] * 100, f"shared vs unshared one-function merge: {peaks}"

    def test_add_drops_the_sort_order(self) -> None:
        stats = make_stats(small_graph()).sort_stats("calls")
        assert stats.fcn_list  # type: ignore[attr-defined]

        stats.add(fake(small_graph()))

        assert stats.fcn_list is None  # type: ignore[attr-defined]

    def test_a_filename_is_loaded_first(self, tmp_path: pathlib.Path) -> None:
        path = write_profile(tmp_path / "run.prof", small_graph())

        stats = make_stats(small_graph()).add(path)

        assert stats.stats[LEAF][:2] == (6, 6)  # type: ignore[attr-defined]
        assert any(path in name for name in stats.files)  # type: ignore[attr-defined]


class TestStripDirs:
    """`strip_dirs()` | O(f + e) | O(f + e); colliding entries merge, and g
    collisions with distinct callers cost O(g²)."""

    def test_every_key_and_caller_is_rebuilt_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stats = make_stats(raw_stats(500, callers=3))
        calls = 0
        original = PRIVATE.func_strip_path

        def counting(func: Key) -> Key:
            nonlocal calls
            calls += 1
            return original(func)

        monkeypatch.setattr(PRIVATE, "func_strip_path", counting)
        stats.strip_dirs()

        assert calls == 500 + 500 * 3
        assert ("m0.py", 1, "fn0") in stats.stats  # type: ignore[attr-defined]

    @staticmethod
    def colliding(groups: int, distinct_callers: bool) -> dict[Key, Entry]:
        stats: dict[Key, Entry] = {}
        for index in range(groups):
            caller = (f"/c/c{index}.py", index, "g") if distinct_callers else ("/c/c.py", 1, "g")
            stats[(f"/d{index}/same.py", 1, "f")] = (1, 1, 0.1, 0.1, {caller: (1, 1, 0.1, 0.1)})
        return stats

    def copied_entries(self, monkeypatch: pytest.MonkeyPatch, stats: pstats.Stats) -> int:
        copied = 0
        original = PRIVATE.add_callers

        def counting(target: dict[Key, Any], source: dict[Key, Any]) -> dict[Key, Any]:
            nonlocal copied
            copied += len(target)
            return original(target, source)

        monkeypatch.setattr(pstats, "add_callers", counting)
        stats.strip_dirs()
        return copied

    def test_colliding_entries_merge(self) -> None:
        stats = make_stats(self.colliding(200, distinct_callers=True))

        stats.strip_dirs()

        assert list(stats.stats) == [("same.py", 1, "f")]  # type: ignore[attr-defined]
        cc, nc, _, _, callers = stats.stats[("same.py", 1, "f")]  # type: ignore[attr-defined]
        assert (cc, nc, len(callers)) == (200, 200, 200)

    def test_distinct_callers_make_the_merges_quadratic(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stats = make_stats(self.colliding(200, distinct_callers=True))

        assert self.copied_entries(monkeypatch, stats) == 200 * 199 // 2

    def test_shared_callers_keep_them_linear(self, monkeypatch: pytest.MonkeyPatch) -> None:
        stats = make_stats(self.colliding(200, distinct_callers=False))

        assert self.copied_entries(monkeypatch, stats) == 199

    def test_it_drops_the_order_and_the_callee_map(self) -> None:
        stats = make_stats(small_graph()).sort_stats("calls")
        stats.print_callees()
        assert stats.fcn_list and stats.all_callees  # type: ignore[attr-defined]

        stats.strip_dirs()

        assert stats.fcn_list is None  # type: ignore[attr-defined]
        assert stats.all_callees is None  # type: ignore[attr-defined]


class TestSortStats:
    """`sort_stats(*keys)` | O(f log f) | O(f), and `reverse_order()` | O(f) | O(1)."""

    @staticmethod
    def comparisons(monkeypatch: pytest.MonkeyPatch, functions: int) -> int:
        stats = make_stats(raw_stats(functions))
        count = 0
        original = PRIVATE.TupleComp.compare

        def counting(self: Any, left: Any, right: Any) -> int:
            nonlocal count
            count += 1
            return original(self, left, right)

        with monkeypatch.context() as patch:
            patch.setattr(PRIVATE.TupleComp, "compare", counting)
            stats.sort_stats("time")
        return count

    def test_comparisons_grow_as_f_log_f(self, monkeypatch: pytest.MonkeyPatch) -> None:
        counts = {f: self.comparisons(monkeypatch, f) for f in (1_000, 100_000)}

        for f, count in counts.items():
            bound = f * math.log2(f)
            assert bound / 2 < count <= bound, f"{count} comparisons for {f} functions"
        ratio = counts[100_000] / counts[1_000]
        assert 130 < ratio < 1_000, f"100x the functions made x{ratio:.1f} the comparisons"

    def test_the_peak_grows_with_functions(self) -> None:
        peaks = []
        for functions in (100, 10_000):
            stats = make_stats(raw_stats(functions))
            peaks.append(peak_bytes(lambda s=stats: s.sort_stats("time")))  # type: ignore[misc]

        assert peaks[1] > peaks[0] * 20, f"100x the functions: {peaks}"

    @staticmethod
    def order(stats: pstats.Stats) -> list[str]:
        return list(stats.get_stats_profile().func_profiles)

    def graph(self) -> pstats.Stats:
        return make_stats(
            {
                BRANCH: (1, 1, 0.1, 0.4, {}),
                OTHER: (1, 1, 0.2, 0.2, {}),
                LEAF: (3, 3, 0.3, 0.3, {BRANCH: (3, 3, 0.3, 0.3)}),
            }
        )

    def test_sortkey_and_string_and_prefix_agree(self) -> None:
        by_key = self.order(self.graph().sort_stats(pstats.SortKey.CALLS, pstats.SortKey.NAME))
        by_string = self.order(self.graph().sort_stats("ncalls", "name"))
        by_prefix = self.order(self.graph().sort_stats("nc", "na"))

        assert by_key == by_string == by_prefix == ["leaf", "branch", "other"]

    def test_later_keys_only_break_ties(self) -> None:
        by_name = self.order(self.graph().sort_stats("calls", "name"))
        by_time = self.order(self.graph().sort_stats("calls", "time"))

        assert by_name == ["leaf", "branch", "other"]
        assert by_time == ["leaf", "other", "branch"]

    def test_an_ambiguous_prefix_is_rejected(self) -> None:
        with pytest.raises(KeyError):
            self.graph().sort_stats("cum")
        assert self.order(self.graph().sort_stats("cumu"))[0] == "branch"

    def test_a_mix_of_forms_is_rejected(self) -> None:
        with pytest.raises(TypeError, match="mixed"):
            self.graph().sort_stats("calls", pstats.SortKey.NAME)

    def test_no_keys_goes_back_to_the_unsorted_order(self) -> None:
        stats = self.graph().sort_stats("calls")

        stats.sort_stats()

        assert self.order(stats) == ["branch", "other", "leaf"]

    def test_reverse_order_reverses_in_place(self) -> None:
        stats = make_stats(raw_stats(10_000)).sort_stats("time")
        ordered = stats.fcn_list  # type: ignore[attr-defined]
        expected = ordered[::-1]

        peak = peak_bytes(stats.reverse_order)

        assert stats.fcn_list is ordered and ordered == expected  # type: ignore[attr-defined]
        assert peak < 1_000, f"reverse_order allocated {peak} bytes over 10,000 functions"

    def test_reverse_order_does_nothing_before_a_sort(self) -> None:
        stats = self.graph()

        stats.reverse_order()

        assert self.order(stats) == ["branch", "other", "leaf"]


class TestRestrictions:
    """`print_stats(*restrictions)` | O(f) | O(f): the ordered list is copied,
    then each restriction applies to what the previous one kept."""

    @staticmethod
    def searches(monkeypatch: pytest.MonkeyPatch, *restrictions: Any) -> int:
        stats = make_stats(raw_stats(1_000)).sort_stats("time")
        count = 0

        class CountingPattern:
            def __init__(self, pattern: str) -> None:
                self._pattern = re.compile(pattern)

            def search(self, text: str) -> Any:
                nonlocal count
                count += 1
                return self._pattern.search(text)

        fake_re = types.SimpleNamespace(
            compile=CountingPattern,
            error=re.error,
            PatternError=getattr(re, "PatternError", re.error),
        )
        with monkeypatch.context() as patch:
            patch.setattr(pstats, "re", fake_re)
            stats.print_stats(*restrictions)
        return count

    def test_a_regex_searches_every_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self.searches(monkeypatch, "fn") == 1_000

    def test_a_count_first_limits_the_regex(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self.searches(monkeypatch, 10, "fn") == 10

    def test_a_count_after_does_not(self, monkeypatch: pytest.MonkeyPatch) -> None:
        assert self.searches(monkeypatch, "fn", 10) == 1_000

    def test_even_one_line_copies_the_list(self) -> None:
        peaks = []
        for functions in (100, 10_000):
            stats = make_stats(raw_stats(functions)).sort_stats("time")
            peaks.append(peak_bytes(lambda s=stats: s.print_stats(1)))  # type: ignore[misc]

        assert peaks[1] > peaks[0] * 20, f"print_stats(1) over 100x the functions: {peaks}"

    def test_int_float_and_oversized_restrictions(self) -> None:
        stats = make_stats(raw_stats(100)).sort_stats("time")

        assert printed_lines(stats, 7) == 7
        assert printed_lines(stats, 0.25) == 25
        assert printed_lines(stats, 100) == 100
        assert printed_lines(stats, 500) == 100
        assert printed_lines(stats) == 100


class TestCallGraph:
    """`print_callers` sorts each printed function's callers; `print_callees`
    builds and caches the callee map on its first call, which `strip_dirs()`
    clears and `add()` does not."""

    def test_print_callers_sorts_each_printed_function_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        stats = make_stats(raw_stats(50, callers=7)).sort_stats("time")
        lengths: list[int] = []

        def counting(iterable: Any, **kwargs: Any) -> list[Any]:
            items = list(iterable)
            lengths.append(len(items))
            return sorted(items, **kwargs)

        monkeypatch.setattr(pstats, "sorted", counting, raising=False)
        stats.print_callers(5)

        assert lengths == [7] * 5
        assert stats.all_callees is None  # type: ignore[attr-defined]

    def test_print_callees_builds_the_map_once(self) -> None:
        stats = make_stats(raw_stats(200, callers=4))

        stats.print_callees(1)
        built = stats.all_callees  # type: ignore[attr-defined]
        stats.print_callees(1)

        assert stats.all_callees is built  # type: ignore[attr-defined]
        assert sum(len(callees) for callees in built.values()) == 200 * 4

    def test_callees_printed_after_add_miss_the_merged_calls(self) -> None:
        stream = io.StringIO()
        stats = pstats.Stats(fake(small_graph()), stream=stream)
        stats.print_callees()
        extra = {OTHER: (1, 1, 0.1, 0.1, {BRANCH: (1, 1, 0.1, 0.1)})}

        stats.add(fake(extra))
        stream.seek(0)
        stream.truncate()
        stats.print_callees(r"\(branch\)")

        assert "(leaf)" in stream.getvalue()
        assert "(other)" not in stream.getvalue(), "the cached callee map was refreshed"

        stream.seek(0)
        stream.truncate()
        stats.print_callees()
        added = [line for line in stream.getvalue().splitlines() if "(other)" in line]

        assert len(added) == 1 and "->" in added[0] and added[0].rstrip().endswith("->"), added

        stats.strip_dirs()
        stream.seek(0)
        stream.truncate()
        stats.print_callees(r"\(branch\)")

        assert "(other)" in stream.getvalue()


class TestStatsProfile:
    """`get_stats_profile()` | O(f) | O(f): one `FunctionProfile` per function,
    in sort order, keyed by bare function name."""

    def test_one_profile_per_function_in_sort_order(self) -> None:
        stats = make_stats(raw_stats(20)).sort_stats("time")

        profile = stats.get_stats_profile()

        assert isinstance(profile, pstats.StatsProfile)
        assert list(profile.func_profiles) == [
            name
            for _, _, name in stats.fcn_list  # type: ignore[attr-defined]
        ]
        assert all(isinstance(p, pstats.FunctionProfile) for p in profile.func_profiles.values())

    def test_same_named_functions_overwrite_each_other(self) -> None:
        stats = make_stats(
            {
                ("/a/one.py", 1, "run"): (1, 1, 0.1, 0.1, {}),
                ("/b/two.py", 1, "run"): (2, 2, 0.1, 0.1, {}),
            }
        )

        profile = stats.get_stats_profile()

        assert len(stats.stats) == 2  # type: ignore[attr-defined]
        assert list(profile.func_profiles) == ["run"]
        survivor = profile.func_profiles["run"]
        assert (survivor.file_name, survivor.ncalls) == ("/b/two.py", "2")

    def test_recursive_calls_read_total_over_primitive(self) -> None:
        stats = make_stats({LEAF: (1, 3, 0.3, 0.3, {})})

        leaf = stats.get_stats_profile().func_profiles["leaf"]

        assert leaf.ncalls == "3/1"
        assert (leaf.file_name, leaf.line_number) == ("/src/app.py", 1)
        assert leaf.tottime == pytest.approx(0.3)
        assert leaf.percall_tottime == pytest.approx(0.1)
        assert leaf.cumtime == pytest.approx(0.3)
        assert leaf.percall_cumtime == pytest.approx(0.3)
        assert stats.get_stats_profile().total_tt == pytest.approx(0.3)


class TestSortKey:
    """`SortKey` members are O(1) string enum constants; `SortKey(value)` takes
    the alternative spellings too."""

    def test_the_nine_members(self) -> None:
        assert {member.name for member in pstats.SortKey} == {
            "CALLS",
            "CUMULATIVE",
            "FILENAME",
            "LINE",
            "NAME",
            "NFL",
            "PCALLS",
            "STDNAME",
            "TIME",
        }

    def test_alternative_spellings_look_up_the_same_member(self) -> None:
        assert pstats.SortKey("ncalls") is pstats.SortKey.CALLS
        assert pstats.SortKey("tottime") is pstats.SortKey.TIME
        assert pstats.SortKey.CALLS == "calls"

    @pytest.mark.skipif(sys.version_info < (3, 11), reason="StrEnum from 3.11")
    def test_str_is_the_value_from_311(self) -> None:
        assert str(pstats.SortKey.TIME) == "time"

    @pytest.mark.skipif(sys.version_info >= (3, 11), reason="a str-mixin Enum on 3.10")
    def test_str_is_the_member_name_on_310(self) -> None:
        assert str(pstats.SortKey.TIME) == "SortKey.TIME"


class TestChaining:
    """Every method in the `Stats` table except `get_stats_profile()` and
    `dump_stats()` returns the `Stats` object."""

    def test_the_chainable_methods_return_self(self, tmp_path: pathlib.Path) -> None:
        stats = make_stats(small_graph())
        calls: list[Callable[[], Any]] = [
            lambda: stats.add(fake(small_graph())),
            stats.strip_dirs,
            lambda: stats.sort_stats("calls"),
            stats.reverse_order,
            stats.print_stats,
            stats.print_callers,
            stats.print_callees,
        ]

        assert all(call() is stats for call in calls)
        assert stats.dump_stats(str(tmp_path / "out.prof")) is None  # type: ignore[func-returns-value]


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
    """Each block runs in its own subprocess, so the profilers the examples
    run never touch this process, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "ncalls == '3'" in s)
        mutated = source.replace("ncalls == '3'", "ncalls == '4'", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
