"""Tests for docs/stdlib/gc.md.

The page prices the collector by the objects and references it visits. Those
bounds are settled by timing a call at two heap sizes a factor of 60 or 100
apart, with the rest of the process's heap frozen out of the way first
(`gc.freeze()` puts it where no collection or search looks), or in a fresh
interpreter where a frozen baseline would itself be the thing measured. The
behavioural rows - what a call returns, what it skips, which callbacks run -
are settled by observation, and the amortized cost of automatic collection by
counting, from a `gc.callbacks` hook, the objects each collection examines.

Measurement scope:

* `gc.collect()` over 5,000 against 300,000 tracked empty lists costs more
  than 15x (about x50 measured), and over one list of 20,000 against
  2,000,000 ints more than 10x, so objects and references are both terms.
  In a fresh interpreter, with 300,000 lists frozen it costs under 4x what
  it does with 5,000 frozen. Its traced peak over 300,000 live lists stays
  under 200 KB, where one pointer per object would be 2.4 MB.
* `gc.collect(0)` and `gc.collect(1)` cost under 4x more beside 300,000 old
  objects than beside 5,000, where a full collection costs about x50;
  afterwards generation 0 is empty.
* Automatic collection: with thresholds (100, 10, 10) and the baseline heap
  frozen, a hook sums the objects in the generations each collection
  examines. Building 300,000 lists examines under 40x what building 30,000
  does (x18 measured on 3.10 to 3.14.7; a full collection every
  threshold0 x threshold1 x threshold2 allocations would give x100), under
  ten examinations per list, and includes at least one full collection
  (11 measured). The e/n term: building 30,000 lists under the same
  thresholds beside one old list of 2,000,000 ints costs more than 3x the
  build beside nothing (about x6 measured), since each full collection
  walks those references again. `gc.disable()` and a `threshold0` of 0 each leave the hook
  uncalled over 10,000 allocations, and `collect()` still frees a cycle
  while disabled.
* `get_referrers()` costs more than 15x over 300,000 lists than over 5,000,
  and more than 20x for 1,000 targets than for one over 10,000 lists of ten
  ints (about x240 measured). `get_referents()` costs under 4x more beside
  300,000 lists than beside 5,000, and returns direct referents only; a
  one-element set left by deleting 199,999 of 200,000 members costs more
  than 50x a fresh one-element set (about x1,800 measured), so references
  are counted as table slots.
  `get_objects(0)` costs under 4x more beside 300,000 old objects than
  beside 5,000; `get_objects()` contains each object created and omits the
  list it returns and frozen objects. Frozen objects are also absent from
  `get_referrers()`.
* In a fresh interpreter, over about 306,000 frozen objects (300,000 lists
  and the interpreter's own): `freeze()` of them while young and
  `unfreeze()` each take under a twentieth of the time `get_freeze_count()`
  takes to walk them (a few hundred times less measured), on every release
  but 3.14.0 to 3.14.4, where `freeze()` of 300,000 young lists costs more
  than 15x what 5,000 cost. `get_freeze_count()` grows at least a quarter as
  fast as the frozen count, which grows about 24x. Unfrozen objects land in
  generation 2.
* 3.14.0 to 3.14.4 (run on 3.14.4): after `collect(0)` and `collect(1)`,
  `get_objects(1)` is empty and the survivors are in generation 2; on every
  other release `collect(0)` moves them to generation 1. The 3.14.5
  boundary was located by running 3.14.4 and 3.14.5: the second reports
  thresholds (2000, 10, 10) and populates generation 1.
* `is_tracked()` is false for ints and strings and true for a list; an empty
  dict and a dict of atomic keys and values are tracked from 3.14 and
  untracked before. `is_finalized()` is true for an object whose `__del__`
  resurrected it, and a second collection does not run `__del__` again;
  calling `__del__` directly leaves it false.
* `DEBUG_LEAK` is `DEBUG_COLLECTABLE | DEBUG_UNCOLLECTABLE | DEBUG_SAVEALL`;
  with `DEBUG_SAVEALL` a collected cycle lands in `gc.garbage` and stays
  there through a second collection. Three registered callbacks receive six
  calls per collection, `'start'` then `'stop'`.
* `get_threshold()` round-trips `set_threshold()`, `get_count()` has three
  entries, `get_stats()` three dicts with the same keys, and an
  out-of-range generation raises `ValueError` from `collect()` and
  `get_objects()`.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* The O(1) rows for `enable()`, `disable()`, `isenabled()`, the threshold,
  count, stats and debug accessors, `is_tracked()`, `is_finalized()` and the
  constants are read from Modules/gcmodule.c and Python/gc.c: each reads or
  writes fixed fields or one object header. Only their results are asserted.
* The auxiliary O(1) space of a collection is measured with live objects
  only; with garbage, finalizers and weak reference callbacks run arbitrary
  code, which the page leaves to the caller.
* Automatic collection on 3.14.0 to 3.14.4 is incremental: collections report
  generation 1 and scan part of the old generation, which the examined-objects
  hook cannot see, so its amortized bound there is not measured. CI runs
  3.14.7, so the 3.14.0 to 3.14.4 test runs only locally.
* The free-threaded build has a different collector and is not measured.
* `freeze()` and `unfreeze()` are compared with a walk of the same objects at
  one size rather than scaled between sizes: their sub-microsecond times at
  5,000 objects are too close to timer resolution for a stable ratio.
* `DEBUG_STATS`, `DEBUG_COLLECTABLE` and `DEBUG_UNCOLLECTABLE` output is not
  asserted. The collection, referrer and freeze measurements use only empty
  lists and lists of ints; only the `get_referents()` table test uses a
  set.
"""

from __future__ import annotations

import gc
import json
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
import weakref
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "gc.md"
EXPECTED_BLOCKS = 7

SMALL = 5_000
LARGE = 300_000

INCREMENTAL = (3, 14, 0) <= sys.version_info[:3] < (3, 14, 5)


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
    if tracemalloc.is_tracing():
        pytest.skip(
            "missing untraced-process: tracemalloc is already tracing; a peak here would include its traces"
        )
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def empty_lists(count: int) -> list[list[Any]]:
    return [[] for _ in range(count)]


@pytest.fixture(autouse=True)
def restore_gc_state() -> Iterator[None]:
    """Put back every collector setting a test may change."""
    enabled = gc.isenabled()
    thresholds = gc.get_threshold()
    debug = gc.get_debug()
    callbacks = list(gc.callbacks)
    garbage = len(gc.garbage)
    try:
        yield
    finally:
        gc.set_debug(debug)
        gc.callbacks[:] = callbacks
        del gc.garbage[garbage:]
        gc.set_threshold(*thresholds)
        if enabled:
            gc.enable()
        else:
            gc.disable()


@contextmanager
def baseline_frozen() -> Iterator[None]:
    """Freeze everything alive now, so only what the test builds is visited.

    `unfreeze()` releases the whole permanent generation, so a process that
    already froze objects is left alone rather than having them released.
    """
    if gc.get_freeze_count():
        pytest.skip(
            "missing unfrozen-gc: objects were already frozen; unfreezing would release them"
        )
    gc.collect()
    gc.freeze()
    try:
        yield
    finally:
        gc.unfreeze()


def fresh_interpreter(source: str) -> dict[str, Any]:
    """Run source in a new interpreter and return the JSON it prints."""
    result = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(source)],
        capture_output=True,
        text=True,
        timeout=300,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


class TestFullCollectionWalksObjectsAndReferences:
    """`gc.collect()` | O(n + e) | O(1), frozen objects skipped.

    Timing at 60x the objects, and at 100x the references with one object,
    separates a walk from a constant; the peak separates O(1) auxiliary space
    from a per-object allocation.
    """

    @pytest.mark.timing
    def test_time_follows_the_tracked_objects(self) -> None:
        with baseline_frozen():
            small = empty_lists(SMALL)
            small_ns = best_ns(gc.collect)
            del small
            large = empty_lists(LARGE)
            large_ns = best_ns(gc.collect)
            del large

        ratio = large_ns / small_ns
        assert ratio > 15, (
            f"60x the objects cost x{ratio:.1f} ({small_ns:.0f}ns to {large_ns:.0f}ns); "
            "a walk over them predicts x60"
        )

    @pytest.mark.timing
    def test_time_follows_the_references_at_one_object(self) -> None:
        with baseline_frozen():
            few = [0] * 20_000
            few_ns = best_ns(gc.collect)
            del few
            many = [0] * 2_000_000
            many_ns = best_ns(gc.collect)
            del many

        ratio = many_ns / few_ns
        assert ratio > 10, (
            f"100x the references in one list cost x{ratio:.1f}; "
            "a bound in tracked objects alone predicts x1"
        )

    @pytest.mark.timing
    def test_frozen_objects_cost_nothing(self) -> None:
        source = """
            import gc, json, time

            def best(func):
                result = None
                for _ in range(7):
                    start = time.perf_counter_ns()
                    func()
                    elapsed = time.perf_counter_ns() - start
                    result = elapsed if result is None else min(result, elapsed)
                return result

            out = {}
            for label, count in (("small", 5_000), ("large", 300_000)):
                held = [[] for _ in range(count)]
                gc.collect()
                gc.freeze()
                out[label] = best(gc.collect)
                gc.unfreeze()
                del held
                gc.collect()
            print(json.dumps(out))
        """
        result = fresh_interpreter(source)

        ratio = result["large"] / result["small"]
        assert ratio < 4, (
            f"with 300,000 lists frozen a collection cost x{ratio:.1f} what it did with "
            "5,000 frozen; a collection that visited them would cost x60"
        )

    def test_a_collection_allocates_nothing_per_object(self) -> None:
        held = empty_lists(LARGE)
        gc.collect()

        peak = peak_bytes(gc.collect)

        assert len(held) == LARGE
        assert peak < 200_000, f"collecting over {LARGE} live lists peaked at {peak} bytes"

    def test_it_frees_a_cycle_even_while_disabled(self) -> None:
        class Node:
            self_ref: Any = None

        node = Node()
        node.self_ref = node
        alive = weakref.ref(node)
        gc.disable()
        del node

        assert alive() is not None
        gc.collect()
        assert alive() is None


class TestYoungCollectionsSkipOlderObjects:
    """`gc.collect(0)`, `gc.collect(1)` | O(g + h): only the named generations.

    Beside 60x the old objects the cost stays flat, where a full collection's
    grows 60x.
    """

    def _cost_beside(self, count: int, generation: int) -> float:
        held = empty_lists(count)
        gc.collect()
        try:
            return best_ns(lambda: gc.collect(generation), inner=50)
        finally:
            del held

    @pytest.mark.timing
    def test_collecting_generation_0_ignores_the_old_heap(self) -> None:
        with baseline_frozen():
            small_ns = self._cost_beside(SMALL, 0)
            large_ns = self._cost_beside(LARGE, 0)

        ratio = large_ns / small_ns
        assert ratio < 4, f"collect(0) cost x{ratio:.1f} beside 60x the old objects"

    @pytest.mark.timing
    @pytest.mark.skipif(INCREMENTAL, reason="collect(1) also scans an old-generation increment")
    def test_collecting_generation_1_ignores_the_old_heap(self) -> None:
        with baseline_frozen():
            small_ns = self._cost_beside(SMALL, 1)
            large_ns = self._cost_beside(LARGE, 1)

        ratio = large_ns / small_ns
        assert ratio < 4, f"collect(1) cost x{ratio:.1f} beside 60x the old objects"

    def test_generation_0_is_empty_afterwards(self) -> None:
        gc.disable()
        survivors = empty_lists(1_000)
        assert len(gc.get_objects(0)) >= 1_000

        gc.collect(0)

        assert gc.get_objects(0) == []
        older = 2 if INCREMENTAL else 1
        assert any(o is survivors[0] for o in gc.get_objects(older))


class TestAutomaticCollectionIsAmortized:
    """Automatic collection | amortized O(1 + e/n) per allocation.

    A hook sums the objects in the generations each collection examines. A
    full collection every fixed number of allocations would make that total
    grow with the square of what is built; waiting for the survivors to grow
    by a quarter keeps it linear in objects. Each full collection still walks
    every reference, which is the e/n term: a timing test puts one old list
    holding most of the references beside the build.
    """

    @staticmethod
    def _examined_while_building(count: int) -> tuple[int, int]:
        examined = 0
        full = 0

        def hook(phase: str, info: dict[str, int]) -> None:
            nonlocal examined, full
            if phase != "start":
                return
            generation = info["generation"]
            full += generation == 2
            examined += sum(len(gc.get_objects(g)) for g in range(generation + 1))

        with baseline_frozen():
            gc.set_threshold(100, 10, 10)
            gc.callbacks.append(hook)
            try:
                built = empty_lists(count)
            finally:
                gc.callbacks.remove(hook)
            assert len(built) == count
            del built
        return examined, full

    @pytest.mark.skipif(INCREMENTAL, reason="the incremental collector scans old increments")
    def test_ten_times_the_objects_examines_far_less_than_a_hundred_times(self) -> None:
        small, _ = self._examined_while_building(30_000)
        large, full = self._examined_while_building(LARGE)

        ratio = large / small
        assert ratio < 40, (
            f"building 10x the lists examined x{ratio:.1f} the objects "
            f"({small} to {large}); a full walk every 10,000 allocations predicts x100"
        )
        assert large < 10 * LARGE, f"{large} examinations for {LARGE} lists"
        assert full > 0, "no full collection ran, so the test measured young ones only"

    @pytest.mark.timing
    @pytest.mark.skipif(INCREMENTAL, reason="the incremental collector scans old increments")
    def test_references_held_by_old_objects_are_walked_again(self) -> None:
        def build_beside(references: int) -> float:
            with baseline_frozen():
                old = [0] * references
                gc.collect()
                previous = gc.get_threshold()
                gc.set_threshold(100, 10, 10)
                try:
                    return best_ns(lambda: empty_lists(30_000), repeats=5)
                finally:
                    gc.set_threshold(*previous)
                    del old

        alone_ns = build_beside(1)
        beside_ns = build_beside(2_000_000)

        ratio = beside_ns / alone_ns
        assert ratio > 3, (
            f"building 30,000 lists beside one list of 2,000,000 references cost "
            f"x{ratio:.1f}; a bound in allocated objects alone predicts x1"
        )

    def test_disabling_stops_automatic_collection(self) -> None:
        runs: list[str] = []
        gc.disable()
        assert not gc.isenabled()
        gc.callbacks.append(lambda phase, info: runs.append(phase))
        gc.set_threshold(100, 10, 10)

        disabled = empty_lists(10_000)
        assert runs == []

        gc.enable()
        gc.set_threshold(0)
        unthresholded = empty_lists(10_000)
        assert runs == []

        gc.set_threshold(100, 10, 10)
        enabled = empty_lists(10_000)
        assert runs, "no collection ran with collection enabled"
        assert len(disabled) == len(unthresholded) == len(enabled)


class TestSettingsAndCounters:
    """The threshold, count and stats accessors return fixed-size results."""

    def test_thresholds_round_trip(self) -> None:
        gc.set_threshold(123, 7, 5)

        expected = (123, 7, 0) if INCREMENTAL else (123, 7, 5)
        assert gc.get_threshold() == expected

    def test_count_and_stats_have_one_entry_per_generation(self) -> None:
        assert len(gc.get_count()) == 3
        stats = gc.get_stats()
        assert len(stats) == 3
        assert all(set(s) == {"collections", "collected", "uncollectable"} for s in stats)

    def test_an_invalid_generation_raises(self) -> None:
        with pytest.raises(ValueError):
            gc.collect(3)
        with pytest.raises(ValueError):
            gc.get_objects(3)


class TestInspectingObjects:
    """`get_objects()` | O(n) | O(n); `get_objects(generation)` | O(g);
    `get_referrers()` | O(n + k·e) | O(r); `get_referents()` | O(k + a) | O(a).

    `get_referrers()` is timed along both of its dimensions; the other two are
    shown not to grow with the heap they do not visit.
    """

    def test_get_objects_lists_what_is_tracked_but_not_itself(self) -> None:
        held = empty_lists(10_000)
        members = {id(item) for item in held}

        listed = gc.get_objects()

        assert sum(id(o) in members for o in listed) == 10_000
        assert any(o is held for o in listed)
        assert not any(o is listed for o in listed)

    @pytest.mark.timing
    def test_one_generation_costs_its_own_objects(self) -> None:
        with baseline_frozen():
            small = empty_lists(SMALL)
            gc.collect()
            small_ns = best_ns(lambda: gc.get_objects(0), inner=50)
            del small
            large = empty_lists(LARGE)
            gc.collect()
            large_ns = best_ns(lambda: gc.get_objects(0), inner=50)
            del large

        ratio = large_ns / small_ns
        assert ratio < 4, f"get_objects(0) cost x{ratio:.1f} beside 60x the old objects"

    @pytest.mark.timing
    def test_get_referrers_walks_the_heap(self) -> None:
        target = object()
        with baseline_frozen():
            small = empty_lists(SMALL)
            small_ns = best_ns(lambda: gc.get_referrers(target))
            del small
            large = empty_lists(LARGE)
            large_ns = best_ns(lambda: gc.get_referrers(target))
            del large

        ratio = large_ns / small_ns
        assert ratio > 15, f"get_referrers over 60x the objects cost x{ratio:.1f}"

    @pytest.mark.timing
    def test_get_referrers_checks_every_reference_against_every_target(self) -> None:
        one = [object()]
        thousand = [object() for _ in range(1_000)]
        with baseline_frozen():
            held = [list(range(10)) for _ in range(10_000)]
            one_ns = best_ns(lambda: gc.get_referrers(*one), repeats=5)
            thousand_ns = best_ns(lambda: gc.get_referrers(*thousand), repeats=5)
            del held

        ratio = thousand_ns / one_ns
        assert ratio > 20, (
            f"1,000 targets cost x{ratio:.1f} what one did over 100,000 references; "
            "a bound without k predicts x1"
        )

    @pytest.mark.timing
    def test_get_referents_ignores_the_heap(self) -> None:
        probe = [1, 2, 3]
        with baseline_frozen():
            small = empty_lists(SMALL)
            small_ns = best_ns(lambda: gc.get_referents(probe), inner=200)
            del small
            large = empty_lists(LARGE)
            large_ns = best_ns(lambda: gc.get_referents(probe), inner=200)
            del large

        ratio = large_ns / small_ns
        assert ratio < 4, f"get_referents cost x{ratio:.1f} beside 60x the objects"

    @pytest.mark.timing
    def test_get_referents_walks_a_table_emptied_by_deletions(self) -> None:
        emptied = set(range(200_000))
        for value in range(1, 200_000):
            emptied.discard(value)
        fresh = {0}

        emptied_ns = best_ns(lambda: gc.get_referents(emptied), inner=20)
        fresh_ns = best_ns(lambda: gc.get_referents(fresh), inner=20)

        assert len(gc.get_referents(emptied)) == 1
        ratio = emptied_ns / fresh_ns
        assert ratio > 50, (
            f"a one-element set left from 200,000 cost x{ratio:.0f} a fresh one; "
            "a bound in live references predicts x1"
        )

    def test_get_referents_returns_direct_references_only(self) -> None:
        inner = [object()]
        outer = [inner]

        assert gc.get_referents(outer) == [inner]
        assert len(gc.get_referents(inner, outer)) == 2

    def test_get_referrers_finds_the_holder(self) -> None:
        target = {"value": 1}
        holder = [target]

        assert any(r is holder for r in gc.get_referrers(target))


class TestFreezing:
    """`freeze()`, `unfreeze()` | O(1); `get_freeze_count()` | O(f).

    Timed in a fresh interpreter, where the baseline heap is a few thousand
    objects rather than the test runner's.
    """

    SOURCE = """
        import gc, json, time

        def once(func):
            start = time.perf_counter_ns()
            func()
            return time.perf_counter_ns() - start

        def best(func):
            return min(once(func) for _ in range(7))

        out = {}
        for label, count in (("small", 5_000), ("large", 300_000)):
            gc.collect()
            gc.disable()
            freezes, unfreezes, counts = [], [], []
            for _ in range(5):
                held = [[] for _ in range(count)]
                freezes.append(once(gc.freeze))
                counts.append(best(gc.get_freeze_count))
                frozen = gc.get_freeze_count()
                unfreezes.append(once(gc.unfreeze))
                del held
                gc.collect()
            gc.enable()
            out[label] = {
                "freeze": min(freezes),
                "unfreeze": min(unfreezes),
                "count": min(counts),
                "frozen": frozen,
            }

        held = [[] for _ in range(100)]
        gc.freeze()
        gc.unfreeze()
        out["unfrozen_in_2"] = any(o is held[0] for o in gc.get_objects(2))
        print(json.dumps(out))
    """

    @pytest.fixture(scope="class")
    @classmethod
    def measured(cls) -> dict[str, Any]:
        return fresh_interpreter(cls.SOURCE)

    @pytest.mark.timing
    @pytest.mark.skipif(INCREMENTAL, reason="3.14.0 to 3.14.4 walk the young objects")
    def test_freezing_does_not_walk_the_objects(self, measured: dict[str, Any]) -> None:
        large = measured["large"]
        assert large["freeze"] * 20 < large["count"], (
            f"freezing {large['frozen']} objects took {large['freeze']}ns against "
            f"{large['count']}ns for get_freeze_count() to walk them"
        )

    @pytest.mark.timing
    @pytest.mark.skipif(not INCREMENTAL, reason="only 3.14.0 to 3.14.4 walk the young objects")
    def test_freezing_walks_the_objects_on_the_incremental_collector(
        self, measured: dict[str, Any]
    ) -> None:
        ratio = measured["large"]["freeze"] / measured["small"]["freeze"]
        assert ratio > 15, f"freezing 60x the young objects cost only x{ratio:.1f}"

    @pytest.mark.timing
    def test_unfreezing_does_not_walk_the_objects(self, measured: dict[str, Any]) -> None:
        large = measured["large"]
        assert large["unfreeze"] * 20 < large["count"], (
            f"unfreezing {large['frozen']} objects took {large['unfreeze']}ns against "
            f"{large['count']}ns for get_freeze_count() to walk them"
        )

    @pytest.mark.timing
    def test_counting_the_frozen_objects_walks_them(self, measured: dict[str, Any]) -> None:
        small, large = measured["small"], measured["large"]
        grew = large["frozen"] / small["frozen"]
        ratio = large["count"] / small["count"]
        assert ratio > grew / 4, (
            f"{grew:.1f}x the frozen objects made get_freeze_count() cost x{ratio:.1f}; "
            f"a walk predicts x{grew:.1f} and a stored count x1"
        )

    def test_unfrozen_objects_land_in_the_oldest_generation(self, measured: dict[str, Any]) -> None:
        assert measured["unfrozen_in_2"] is True

    def test_frozen_objects_are_neither_listed_nor_searched(self) -> None:
        held: list[Any] = [[]]
        with baseline_frozen():
            assert gc.get_freeze_count() > 0
            assert not any(o is held for o in gc.get_objects())
            assert gc.get_referrers(held[0]) == []
        assert any(r is held for r in gc.get_referrers(held[0]))


class TestTracking:
    """`is_tracked()` and `is_finalized()` | O(1), and the 3.14 dict change."""

    def test_atomic_objects_are_not_tracked(self) -> None:
        assert not gc.is_tracked(42)
        assert not gc.is_tracked("text")
        assert gc.is_tracked([])

    def test_a_dict_of_atomic_values_is_tracked_from_3_14(self) -> None:
        expected = sys.version_info >= (3, 14)
        assert gc.is_tracked({"a": 1}) is expected
        assert gc.is_tracked({}) is expected
        assert gc.is_tracked({"a": []})

    def test_a_resurrected_object_is_finalized_once(self) -> None:
        saved: list[Any] = []
        finalized = 0

        class Phoenix:
            self_ref: Any = None

            def __del__(self) -> None:
                nonlocal finalized
                finalized += 1
                saved.append(self)

        bird = Phoenix()
        assert not gc.is_finalized(bird)
        bird.self_ref = bird
        del bird
        gc.collect()

        assert gc.is_finalized(saved[0])
        assert finalized == 1

        saved.clear()
        gc.collect()
        assert finalized == 1, "__del__ ran again on the second collection"

    def test_calling_del_yourself_does_not_finalize(self) -> None:
        class Plain:
            def __del__(self) -> None:
                pass

        plain = Plain()
        plain.__del__()

        assert not gc.is_finalized(plain)


@pytest.mark.skipif(not INCREMENTAL, reason="the incremental collector of 3.14.0 to 3.14.4")
class TestIncrementalReleases:
    """3.14.0 to 3.14.4: two generations, and `get_objects(1)` always empty."""

    def test_generation_1_is_always_empty(self) -> None:
        gc.disable()
        held = empty_lists(1_000)
        gc.collect(0)
        gc.collect(1)

        assert gc.get_objects(1) == []
        assert any(o is held[0] for o in gc.get_objects(2))


class TestDebuggingAndCallbacks:
    """`gc.garbage`, the `DEBUG_*` flags and `gc.callbacks`."""

    def test_debug_leak_includes_saveall(self) -> None:
        assert gc.DEBUG_LEAK == (gc.DEBUG_COLLECTABLE | gc.DEBUG_UNCOLLECTABLE | gc.DEBUG_SAVEALL)
        assert gc.DEBUG_STATS & gc.DEBUG_LEAK == 0

    def test_saveall_keeps_what_it_finds_until_you_empty_the_list(self) -> None:
        gc.collect()
        gc.set_debug(gc.DEBUG_SAVEALL)
        assert gc.get_debug() == gc.DEBUG_SAVEALL
        cycle: list[Any] = []
        cycle.append(cycle)
        marker = id(cycle)
        del cycle

        gc.collect()
        gc.collect()

        assert any(id(o) == marker for o in gc.garbage)

    def test_each_collection_calls_every_callback_twice(self) -> None:
        calls: list[tuple[int, str]] = []
        gc.disable()
        for index in range(3):
            gc.callbacks.append(lambda phase, info, index=index: calls.append((index, phase)))

        gc.collect()

        assert sorted(calls) == [(i, p) for i in range(3) for p in ("start", "stop")]
        assert [p for _, p in calls] == ["start"] * 3 + ["stop"] * 3


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
    """Each block runs in its own subprocess, so collector settings, frozen
    objects and callbacks cannot leak between them, and asserts its own
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
        line, source = next((n, s) for n, s in _blocks() if "gc.get_freeze_count() == 0" in s)
        mutated = source.replace("gc.get_freeze_count() == 0", "gc.get_freeze_count() == 1", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
