"""Tests for docs/stdlib/tracemalloc.md.

The page prices the module in two places: every allocation made while tracing
captures a traceback, and a snapshot copies the whole trace table into Python
objects that later calls group, filter and pickle. Tracing-side claims are
settled by observing the tracer - what a trace records, what the counters
read, what survives `stop()` and `clear_traces()` - with timing only where the
claim is about cost itself. Snapshot-side claims are settled on snapshots built
directly from trace tuples, so the trace count t, the stored frames f and the
distinct tracebacks u can each be set exactly and varied one at a time.

Measurement scope:

* An allocation walks the whole stack: with `nframe=1`, a block allocated
  600 frames below the test stores one frame and records a `total_nframe`
  above 600. In a timing test, 20,000 allocations 600 frames deeper cost
  more than 3x the same allocations 5 frames deeper, with `nframe=1`.
* `start()` while tracing leaves `get_traceback_limit()` unchanged, and
  `start(0)` raises `ValueError`. Starting the interpreter with
  `-X tracemalloc=5` or `PYTHONTRACEMALLOC=3` is observed in a subprocess
  to be tracing with that limit.
* `get_object_traceback()` is `None` for an object allocated before
  `start()` and after `stop()`, and otherwise has `min(nframe, depth)`
  frames, all from this file, oldest first as the recursive call and newest
  the allocating line, with `total_nframe` `None`. `Trace.traceback` is a new
  object on every access.
* `stop()` and `clear_traces()` both discard existing traces; after
  `clear_traces()` tracing continues and current and peak read no more than a
  few kilobytes where a 1 MB block was traced. In a timing test,
  `clear_traces()` over 500,000 traced blocks costs more than 20x the same
  call over 10,000.
* Recorded tracebacks outlive their blocks: 20,000 objects allocated on
  20,000 distinct lines and then freed leave `get_tracemalloc_memory()` more
  than 20x higher than the same objects allocated on one line and freed, and
  in a timing test the following `clear_traces()` costs more than 20x more.
* `start()` while tracing still rejects `nframe=0`. With a 1 MB block kept
  and a 3 MB one freed, `reset_peak()` leaves peak within 100 KB above
  current, and current above 1 MB.
* With 100,000 blocks traced, `get_traced_memory()`'s current is within
  50 KB of the sizes summed over a snapshot's traces, while
  `get_tracemalloc_memory()` reports over 1 MB of the tracer's own tables.
* `get_traced_memory()` is `(0, 0)` when not tracing, `reset_peak()` then
  does nothing, and after a freed 1 MB block it brings peak back under 1 MB. `get_tracemalloc_memory()` grows more than 20x from 1,000 to
  100,000 traced blocks. In a timing test, `get_traced_memory()` over
  500,000 traced blocks costs less than 3x the same call over 1,000.
* `take_snapshot()` raises `RuntimeError` when not tracing, holds at least one
  trace per live block, and shares one frames tuple among the traces of each
  distinct traceback: 20,000 blocks allocated on one line hold a handful of
  distinct frames tuples, not 20,000. In a timing test with the cyclic
  collector disabled, a snapshot of 640,000 live blocks costs between 16x and
  1,000x one of 10,000, where linear predicts 64x and quadratic 4,096x.
* `statistics()` on 20,000 traces sharing one traceback: on 3.10-3.13,
  1,000 stored frames cost more than 8x one frame for `'lineno'`; on 3.14+
  less than 5x, because the shared tuple's hash is cached. With
  `cumulative=True`, 100 frames cost more than 20x one on every version. Over 5,000
  distinct tracebacks, grouping by `'lineno'` peaks within 1.5x at one or
  200 frames and `'traceback'` more than 3x higher at 200; over 2,000,
  `cumulative=True` peaks more than 3x higher at 100 frames than at one.
  `'filename'` returns one group per file; results are sorted largest first.
* `compare_to()` reports a group present only in the old snapshot with size 0
  and a negative `size_diff`, and sorts by absolute `size_diff`.
* `filter_traces()` calls the frame matcher once per trace per filter when no
  filter matches (t·p), and once per frame as well with `all_frames=True`
  (t·p·f); an empty filter list returns a new list sharing the same trace
  tuples. A default `Filter` matches only the most recent frame; `lineno`
  and `domain` narrow it, and `DomainFilter` matches the domain whatever the
  frames.
* `dump()` of 2,000 traces sharing one traceback grows less than 1.5x from
  one to 100 frames, against more than 20x when every traceback is distinct;
  `load()` returns a snapshot whose traces again share one frames tuple.
* `Snapshot.traces` answers `len()` and indexing; in a timing test, `in` over
  100,000 traces costs more than 20x `in` over 1,000.
* `Traceback.format()` returns the source line through `linecache`, which
  holds every line of the test file afterwards, and reverses with
  `most_recent_first=True`. `total_nframe` is set on `Trace.traceback` and
  `None` on a grouped statistic's traceback.
* Every fenced Python block runs in its own subprocess, so tracing state
  cannot leak between them, and a mutated assertion in one is asserted to
  fail.

Not settled here:

* The O(f) space for `start()` and for a new distinct traceback, and O(1) for
  a free, are read from `traceback_new()` and
  `tracemalloc_remove_trace_unlocked()` in Python/tracemalloc.c
  (Modules/_tracemalloc.c before 3.12). The r·f term of clearing and of the
  tracer's overhead - interned filenames as well as tracebacks - is read from
  `tracemalloc_clear_traces_unlocked()`; the tests vary r at `nframe=1`, not
  the stored traceback depth or the number of distinct filenames.
* The g log g sort term is `list.sort()` in Lib/tracemalloc.py; the grouping
  tests hold g small.
* Filename hashing, `fnmatch` matching and `os.path.normcase` are priced at
  O(1) per frame; filename length is not varied.
* `get_tracemalloc_memory()` walks one table per tracked domain; only the
  default domain is exercised, since other domains come from the C API.
* `filter_traces()` first splits its p filters into inclusive and exclusive
  lists, O(p), which the O(t·p) bound absorbs for any snapshot holding a
  trace; an empty snapshot is not priced separately.
* `tracemalloc.BaseFilter` is an undocumented base class of `Filter` and
  `DomainFilter` and is not on the page.
* Allocation cost is measured on `object()` and `bytearray` blocks only;
  allocator, block size and thread count are not varied.
"""

from __future__ import annotations

import gc
import linecache
import os
import pathlib
import pickle
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "tracemalloc.md"
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
    with tracing():
        func()
        return tracemalloc.get_traced_memory()[1]


@contextmanager
def tracing(nframe: int = 1) -> Iterator[None]:
    """Trace for the duration of the block, refusing to nest inside another trace."""
    assert not tracemalloc.is_tracing(), "something else left tracemalloc running"
    tracemalloc.start(nframe)
    try:
        yield
    finally:
        tracemalloc.stop()


def synthetic(traces: int, frames: int, distinct: int = 1) -> tracemalloc.Snapshot:
    """A snapshot of `traces` traces over `distinct` tracebacks of `frames` frames.

    Traces with the same traceback share one frames tuple, as `take_snapshot()`
    builds them. Frames are most recent first, which is the order the C tracer
    hands to `Snapshot`.
    """
    tracebacks = [
        tuple((f"file{index}.py", line) for line in range(1, frames + 1))
        for index in range(distinct)
    ]
    return tracemalloc.Snapshot(
        [(0, 32, tracebacks[index % distinct], frames) for index in range(traces)], frames
    )


def trace_tuples(snapshot: tracemalloc.Snapshot) -> list[Any]:
    """The raw trace tuples behind `Snapshot.traces`, where sharing shows."""
    return snapshot.traces._traces  # type: ignore[attr-defined]  # noqa: SLF001


def allocate_at_depth(depth: int, count: int) -> list[object]:
    """Allocate `count` objects `depth` frames below the caller."""
    if depth:
        return allocate_at_depth(depth - 1, count)
    return [object() for _ in range(count)]


class TestAnAllocationWalksTheWholeStack:
    """An allocation while tracing | O(d) | O(1), O(f) for a new traceback.

    `nframe` caps what is stored, not what is walked: `total_nframe` counts
    every frame, so a deep stack is expensive to trace even at `nframe=1`.
    """

    def test_one_frame_is_stored_but_every_frame_is_counted(self) -> None:
        with tracing(1):
            block = allocate_at_depth(600, 1)
            snapshot = tracemalloc.take_snapshot()
            stored = tracemalloc.get_object_traceback(block[0])

        assert stored is not None and len(stored) == 1
        deepest = max(trace.traceback.total_nframe or 0 for trace in snapshot.traces)
        assert deepest > 600, f"the deepest trace counted {deepest} frames"

    @pytest.mark.timing
    def test_a_deeper_stack_costs_more_per_allocation(self) -> None:
        with tracing(1):
            allocate_at_depth(600, 20_000)  # warm
            shallow = best_ns(lambda: allocate_at_depth(5, 20_000), repeats=5)
            deep = best_ns(lambda: allocate_at_depth(600, 20_000), repeats=5)

        ratio = deep / shallow
        assert ratio > 3, (
            f"20,000 allocations 600 frames deeper cost x{ratio:.2f} "
            f"({shallow:.0f}ns to {deep:.0f}ns) at nframe=1"
        )


class TestStartingAndStopping:
    """`start(nframe=1)` | O(1) | O(f); `stop()` and `clear_traces()` | O(t + r·f)."""

    def test_a_second_start_changes_nothing(self) -> None:
        with tracing(1):
            tracemalloc.start(25)

            assert tracemalloc.get_traceback_limit() == 1

    def test_a_second_start_still_validates_nframe(self) -> None:
        with tracing(1):
            with pytest.raises(ValueError, match="number of frames"):
                tracemalloc.start(0)
            assert tracemalloc.is_tracing()

    def test_nframe_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="number of frames"):
            tracemalloc.start(0)
        assert not tracemalloc.is_tracing()

    def test_stop_discards_every_trace(self) -> None:
        with tracing():
            block = bytearray(1000)
            assert tracemalloc.get_object_traceback(block) is not None

        assert not tracemalloc.is_tracing()
        assert tracemalloc.get_object_traceback(block) is None

    def test_a_snapshot_needs_tracing(self) -> None:
        with pytest.raises(RuntimeError, match="must be tracing"):
            tracemalloc.take_snapshot()

    def test_clear_traces_keeps_tracing_and_zeroes_the_counters(self) -> None:
        with tracing():
            block = bytearray(1_000_000)
            tracemalloc.clear_traces()

            assert tracemalloc.is_tracing()
            assert tracemalloc.get_object_traceback(block) is None
            current, peak = tracemalloc.get_traced_memory()
            assert current < 10_000 and peak < 10_000, (current, peak)

            after = bytearray(1000)
            assert tracemalloc.get_object_traceback(after) is not None

    @pytest.mark.timing
    def test_clear_traces_grows_with_the_traces(self) -> None:
        durations = []
        with tracing():
            for blocks in (10_000, 500_000):
                trials = []
                for _ in range(3):
                    keep = [object() for _ in range(blocks)]
                    trials.append(best_ns(tracemalloc.clear_traces, repeats=1))
                    del keep
                durations.append(min(trials))

        ratio = durations[1] / durations[0]
        assert ratio > 20, f"50x the traces cleared in x{ratio:.2f}: {durations}"

    @pytest.mark.parametrize(
        ("flag", "environment", "limit"),
        [(["-X", "tracemalloc=5"], {}, 5), ([], {"PYTHONTRACEMALLOC": "3"}, 3)],
    )
    def test_tracing_can_start_with_the_interpreter(
        self, flag: list[str], environment: dict[str, str], limit: int
    ) -> None:
        code = (
            "import tracemalloc; print(tracemalloc.is_tracing(), tracemalloc.get_traceback_limit())"
        )
        result = subprocess.run(
            [sys.executable, *flag, "-c", code],
            env={**os.environ, **environment},
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )

        assert result.stdout.split() == ["True", str(limit)]


class TestCounters:
    """`get_traced_memory()`, `reset_peak()`, `get_tracemalloc_memory()` | O(1).

    Two running counters and a sum of table sizes; the overhead the last one
    reports grows with the traces.
    """

    def test_peak_remembers_a_freed_block_until_reset(self) -> None:
        with tracing():
            data = bytearray(1_000_000)
            current, peak = tracemalloc.get_traced_memory()
            assert current >= 1_000_000 and peak >= current

            del data
            current, peak = tracemalloc.get_traced_memory()
            assert current < 1_000_000 <= peak

            tracemalloc.reset_peak()
            assert tracemalloc.get_traced_memory()[1] < 1_000_000

    def test_reset_peak_sets_peak_to_current_not_to_zero(self) -> None:
        with tracing():
            kept = bytearray(1_000_000)
            spike = bytearray(3_000_000)
            del spike

            tracemalloc.reset_peak()
            current, peak = tracemalloc.get_traced_memory()

            assert current >= 1_000_000, current
            assert current <= peak < current + 100_000, (current, peak)
            del kept

    def test_everything_reads_zero_when_not_tracing(self) -> None:
        tracemalloc.reset_peak()

        assert tracemalloc.get_traced_memory() == (0, 0)

    def test_the_tracer_s_own_memory_grows_with_the_traces(self) -> None:
        sizes = []
        with tracing():
            for blocks in (1_000, 100_000):
                keep = [object() for _ in range(blocks)]
                sizes.append(tracemalloc.get_tracemalloc_memory())
                del keep
                tracemalloc.clear_traces()

        assert sizes[1] > sizes[0] * 20, f"100x the traced blocks: {sizes}"

    def test_current_counts_the_traced_blocks_not_the_tracer(self) -> None:
        with tracing():
            keep = [object() for _ in range(100_000)]
            snapshot = tracemalloc.take_snapshot()
            current = tracemalloc.get_traced_memory()[0]
            overhead = tracemalloc.get_tracemalloc_memory()
        del keep

        traced = sum(trace.size for trace in snapshot.traces)
        assert overhead > 1_000_000
        assert abs(current - traced) < 50_000, (current, traced, overhead)

    @staticmethod
    def allocate_and_free(distinct_lines: bool) -> tuple[int, float]:
        """Tracer memory after 20,000 freed objects, and the cost of clearing then."""
        count = 20_000
        if distinct_lines:
            body = "\n".join("    keep.append(object())" for _ in range(count))
        else:
            body = f"    for _ in range({count}):\n        keep.append(object())"
        namespace: dict[str, Any] = {}
        exec(f"def fill(keep):\n{body}", namespace)
        with tracing():
            keep: list[object] = []
            namespace["fill"](keep)
            del keep
            retained = tracemalloc.get_tracemalloc_memory()
            start = time.perf_counter_ns()
            tracemalloc.clear_traces()
            return retained, time.perf_counter_ns() - start

    def test_a_freed_block_s_traceback_stays_recorded(self) -> None:
        one_line, _ = self.allocate_and_free(distinct_lines=False)
        many_lines, _ = self.allocate_and_free(distinct_lines=True)

        assert many_lines > one_line * 20, f"retained after freeing: {one_line}, {many_lines}"

    @pytest.mark.timing
    def test_clearing_walks_the_recorded_tracebacks(self) -> None:
        one_line = min(self.allocate_and_free(distinct_lines=False)[1] for _ in range(3))
        many_lines = min(self.allocate_and_free(distinct_lines=True)[1] for _ in range(3))

        ratio = many_lines / one_line
        assert ratio > 20, f"20,000 recorded tracebacks cost x{ratio:.2f} to clear"

    @pytest.mark.timing
    def test_reading_the_counters_does_not_grow_with_the_traces(self) -> None:
        durations = []
        with tracing():
            for blocks in (1_000, 500_000):
                keep = [object() for _ in range(blocks)]
                durations.append(best_ns(tracemalloc.get_traced_memory, inner=1_000))
                del keep
                tracemalloc.clear_traces()

        ratio = durations[1] / durations[0]
        assert ratio < 3, f"500x the traced blocks cost x{ratio:.2f}: {durations}"


class TestObjectTracebacks:
    """`get_object_traceback(obj)` | O(f) | O(f); `Trace.traceback` | O(f)."""

    def test_an_object_from_before_start_has_no_traceback(self) -> None:
        before = bytearray(1000)
        with tracing():
            after = bytearray(1000)

            assert tracemalloc.get_object_traceback(before) is None
            assert tracemalloc.get_object_traceback(after) is not None

    def test_it_stores_at_most_nframe_frames_oldest_first(self) -> None:
        with tracing(5):
            block = allocate_at_depth(20, 1)
            traceback = tracemalloc.get_object_traceback(block[0])

        assert traceback is not None
        assert len(traceback) == 5
        assert {frame.filename for frame in traceback} == {__file__}
        newest = linecache.getline(__file__, traceback[-1].lineno)
        oldest = linecache.getline(__file__, traceback[0].lineno)
        assert "object()" in newest, newest
        assert "allocate_at_depth(depth - 1" in oldest, oldest
        assert traceback.total_nframe is None

    def test_trace_traceback_is_built_on_every_access(self) -> None:
        trace = synthetic(1, 3).traces[0]

        assert trace.traceback is not trace.traceback
        assert trace.traceback == trace.traceback
        assert len(trace.traceback) == 3
        assert (trace.size, trace.domain) == (32, 0)


class TestTakingASnapshot:
    """`take_snapshot()` | O(t + u·f) | O(t + u·f)."""

    def test_one_frames_tuple_per_distinct_traceback(self) -> None:
        with tracing():
            blocks = [object() for _ in range(20_000)]
            snapshot = tracemalloc.take_snapshot()
        del blocks

        traces = trace_tuples(snapshot)
        assert len(traces) >= 20_000
        distinct = len({id(trace[2]) for trace in traces})
        assert distinct < 100, f"{len(traces)} traces held {distinct} frames tuples"

    @pytest.mark.timing
    def test_it_is_linear_in_the_live_blocks(self) -> None:
        durations = []
        gc.disable()  # a collection triggered by the snapshot's own tuples is not its cost
        try:
            with tracing():
                for blocks in (10_000, 640_000):
                    keep = [object() for _ in range(blocks)]
                    durations.append(best_ns(tracemalloc.take_snapshot, repeats=3))
                    del keep
                    tracemalloc.clear_traces()
        finally:
            gc.enable()

        ratio = durations[1] / durations[0]
        assert 16 < ratio < 1_000, (
            f"64x the live blocks cost x{ratio:.2f}: {durations}; "
            "linear predicts x64, quadratic x4096"
        )


class TestGrouping:
    """`statistics()` and `compare_to()` | O(t·f + g log g) | O(u), O(u·f) for
    `'traceback'` or `cumulative=True`; Python 3.14+ is O(t + u·f + g log g)
    without `cumulative`."""

    TRACES = 20_000

    def test_filename_groups_are_per_file_and_sorted_largest_first(self) -> None:
        snapshot = tracemalloc.Snapshot(
            [
                (0, 100, (("a.py", 1),), 1),
                (0, 200, (("a.py", 2),), 1),
                (0, 50, (("b.py", 1),), 1),
            ],
            1,
        )

        by_line = snapshot.statistics("lineno")
        by_file = snapshot.statistics("filename")

        assert [stat.size for stat in by_line] == [200, 100, 50]
        assert [(stat.traceback[0].filename, stat.size, stat.count) for stat in by_file] == [
            ("a.py", 300, 2),
            ("b.py", 50, 1),
        ]

    def test_compare_to_reports_groups_that_vanished(self) -> None:
        old = tracemalloc.Snapshot(
            [(0, 500, (("gone.py", 1),), 1), (0, 100, (("kept.py", 1),), 1)], 1
        )
        new = tracemalloc.Snapshot(
            [(0, 150, (("kept.py", 1),), 1), (0, 300, (("new.py", 1),), 1)], 1
        )

        diffs = new.compare_to(old, "lineno")

        summary = [(d.traceback[0].filename, d.size, d.size_diff, d.count_diff) for d in diffs]
        assert summary == [
            ("gone.py", 0, -500, -1),
            ("new.py", 300, 300, 1),
            ("kept.py", 150, 50, 0),
        ]
        assert diffs[0].count == 0

    @staticmethod
    def _cost(key: str, frames: int, cumulative: bool = False) -> float:
        snapshot = synthetic(TestGrouping.TRACES, frames)
        return best_ns(lambda: snapshot.statistics(key, cumulative=cumulative), repeats=5)

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info >= (3, 14), reason="3.14 caches tuple hashes")
    def test_before_314_each_trace_hashes_its_frames(self) -> None:
        ratio = self._cost("lineno", 1_000) / self._cost("lineno", 1)

        assert ratio > 8, f"1,000 shared frames per trace cost x{ratio:.2f} to group"

    @pytest.mark.timing
    @pytest.mark.skipif(sys.version_info < (3, 14), reason="tuple hashes are cached from 3.14")
    def test_from_314_a_shared_traceback_is_hashed_once(self) -> None:
        ratio = self._cost("lineno", 1_000) / self._cost("lineno", 1)

        assert ratio < 5, f"1,000 shared frames per trace cost x{ratio:.2f} to group"

    @pytest.mark.timing
    def test_cumulative_visits_every_frame(self) -> None:
        ratio = self._cost("lineno", 100, cumulative=True) / self._cost(
            "lineno", 1, cumulative=True
        )

        assert ratio > 20, f"100 frames per trace cost x{ratio:.2f} to group cumulatively"

    @pytest.mark.parametrize(
        ("key", "cumulative", "distinct", "frames", "grows"),
        [
            ("lineno", False, 5_000, 200, False),
            ("traceback", False, 5_000, 200, True),
            ("lineno", True, 2_000, 100, True),
        ],
    )
    def test_space_grows_with_frames_only_when_they_are_kept(
        self, key: str, cumulative: bool, distinct: int, frames: int, grows: bool
    ) -> None:
        peaks = []
        for stored in (1, frames):
            snapshot = synthetic(distinct, stored, distinct)
            snapshot.statistics(key, cumulative=cumulative)  # warm
            peaks.append(peak_bytes(lambda s=snapshot: s.statistics(key, cumulative=cumulative)))

        ratio = peaks[1] / peaks[0]
        if grows:
            assert ratio > 3, (
                f"{key}, cumulative={cumulative}: {frames}x frames peaked x{ratio:.2f}"
            )
        else:
            assert ratio < 1.5, f"{key}: {frames}x frames peaked x{ratio:.2f}"


class TestFiltering:
    """`filter_traces(filters)` | O(t·p) | O(t); `all_frames=True` is O(t·p·f)."""

    class CountingFilter(tracemalloc.Filter):
        calls = 0

        def _match_frame_impl(self, filename: str, lineno: int) -> bool:
            type(self).calls += 1
            return super()._match_frame_impl(filename, lineno)  # type: ignore[misc]

    @pytest.fixture(autouse=True)
    def _reset_count(self) -> None:
        self.CountingFilter.calls = 0

    def test_each_filter_tests_each_trace_once(self) -> None:
        snapshot = synthetic(1_000, 10, 1_000)
        filters = [self.CountingFilter(True, f"nomatch{index}.py") for index in range(3)]

        result = snapshot.filter_traces(filters)

        assert len(result.traces) == 0
        assert self.CountingFilter.calls == 1_000 * 3

    def test_all_frames_tests_each_frame(self) -> None:
        snapshot = synthetic(1_000, 10, 1_000)
        filters = [
            self.CountingFilter(True, f"nomatch{index}.py", all_frames=True) for index in range(3)
        ]

        snapshot.filter_traces(filters)

        assert self.CountingFilter.calls == 1_000 * 3 * 10

    def test_an_empty_list_copies_the_traces_and_shares_the_tracebacks(self) -> None:
        snapshot = synthetic(1_000, 3)

        copy = snapshot.filter_traces([])

        assert trace_tuples(copy) is not trace_tuples(snapshot)
        assert all(a is b for a, b in zip(trace_tuples(copy), trace_tuples(snapshot), strict=True))

    def test_a_default_filter_matches_the_most_recent_frame_only(self) -> None:
        snapshot = tracemalloc.Snapshot([(0, 10, (("inner.py", 5), ("outer.py", 9)), 2)], 2)

        assert len(snapshot.filter_traces([tracemalloc.Filter(True, "inner.py")]).traces) == 1
        assert len(snapshot.filter_traces([tracemalloc.Filter(True, "outer.py")]).traces) == 0
        every_frame = tracemalloc.Filter(True, "outer.py", all_frames=True)
        assert len(snapshot.filter_traces([every_frame]).traces) == 1

    def test_lineno_and_domain_narrow_a_filter(self) -> None:
        snapshot = tracemalloc.Snapshot(
            [(0, 10, (("a.py", 1),), 1), (0, 10, (("a.py", 2),), 1), (7, 10, (("a.py", 1),), 1)],
            1,
        )

        line_one = snapshot.filter_traces([tracemalloc.Filter(True, "a.py", lineno=1)])
        domain_seven = snapshot.filter_traces([tracemalloc.Filter(True, "a.py", domain=7)])
        not_seven = snapshot.filter_traces([tracemalloc.DomainFilter(False, 7)])

        assert len(line_one.traces) == 2
        assert [trace.domain for trace in domain_seven.traces] == [7]
        assert [trace.domain for trace in not_seven.traces] == [0, 0]

    def test_filter_attributes(self) -> None:
        default = tracemalloc.Filter(False, "x.py")
        domain = tracemalloc.DomainFilter(True, 3)

        assert (default.inclusive, default.filename_pattern) == (False, "x.py")
        assert (default.lineno, default.all_frames, default.domain) == (None, False, None)
        assert (domain.inclusive, domain.domain) == (True, 3)


class TestDumpAndLoad:
    """`dump()` and `load()` | O(t + u·f): a shared traceback is written once."""

    @staticmethod
    def dumped_size(snapshot: tracemalloc.Snapshot, path: pathlib.Path) -> int:
        snapshot.dump(str(path))
        return path.stat().st_size

    def test_shared_tracebacks_are_written_once(self, tmp_path: pathlib.Path) -> None:
        shared = [self.dumped_size(synthetic(2_000, f), tmp_path / f"s{f}") for f in (1, 100)]
        distinct = [
            self.dumped_size(synthetic(2_000, f, 2_000), tmp_path / f"d{f}") for f in (1, 100)
        ]

        assert shared[1] < shared[0] * 1.5, f"100x frames on one shared traceback: {shared}"
        assert distinct[1] > distinct[0] * 20, f"100x frames on distinct tracebacks: {distinct}"

    def test_loading_restores_the_sharing(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "snapshot.pickle"
        synthetic(1_000, 5).dump(str(path))

        loaded = tracemalloc.Snapshot.load(str(path))

        traces = trace_tuples(loaded)
        assert len(traces) == 1_000
        assert len({id(trace[2]) for trace in traces}) == 1
        assert loaded.traceback_limit == 5

    def test_the_pickle_is_an_ordinary_snapshot_pickle(self, tmp_path: pathlib.Path) -> None:
        path = tmp_path / "snapshot.pickle"
        original = synthetic(10, 2, 3)
        original.dump(str(path))

        with path.open("rb") as file:
            restored = pickle.load(file)

        assert restored.statistics("traceback") == original.statistics("traceback")


class TestSnapshotTraces:
    """`Snapshot.traces` | O(1): `len()` and indexing are O(1); `in` is O(t)."""

    def test_length_and_indexing(self) -> None:
        snapshot = synthetic(10, 1)

        assert snapshot.traces is snapshot.traces
        assert len(snapshot.traces) == 10
        assert snapshot.traces[3].size == 32
        assert snapshot.traces[0] in snapshot.traces

    @pytest.mark.timing
    def test_membership_scans(self) -> None:
        probe = tracemalloc.Trace((0, 999, (("absent.py", 1),), 1))
        durations = []
        for size in (1_000, 100_000):
            traces = synthetic(size, 1).traces
            durations.append(best_ns(lambda t=traces: probe in t, inner=5))

        ratio = durations[1] / durations[0]
        assert ratio > 20, f"100x the traces cost x{ratio:.2f} to search"


class TestTracebacksAndStatistics:
    """`Traceback`, `Frame`, `Statistic` and `StatisticDiff` accessors | O(1);
    `Traceback.format()` | O(f) plus the source lines `linecache` loads."""

    def test_format_reads_the_source_and_reverses_on_request(self) -> None:
        with tracing(3):
            block = bytearray(1000)
            traceback = tracemalloc.get_object_traceback(block)

        assert traceback is not None
        linecache.clearcache()
        lines = traceback.format()
        whole_file = pathlib.Path(__file__).read_text(encoding="utf-8").splitlines()
        cached: Any = linecache.cache[__file__]  # (size, mtime, lines, fullname)
        assert len(cached[2]) == len(whole_file)
        assert any("block = bytearray(1000)" in line for line in lines)
        assert traceback.format(most_recent_first=True)[0] == lines[-2]
        assert len(traceback.format(limit=1)) == 2

    def test_frames_and_statistics_expose_their_fields(self) -> None:
        snapshot = synthetic(4, 2)
        stat = snapshot.statistics("traceback")[0]
        diff = snapshot.compare_to(synthetic(1, 2), "traceback")[0]

        frame = stat.traceback[0]
        assert (frame.filename, frame.lineno) == ("file0.py", 2)
        assert (stat.size, stat.count) == (128, 4)
        assert (diff.size, diff.size_diff, diff.count, diff.count_diff) == (128, 96, 4, 3)
        assert diff.traceback == stat.traceback

    def test_total_nframe_is_set_only_on_a_trace_s_traceback(self) -> None:
        snapshot = synthetic(1, 2)

        assert snapshot.traces[0].traceback.total_nframe == 2
        assert snapshot.statistics("traceback")[0].traceback.total_nframe is None


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
    """Each block runs in its own subprocess, so tracing state cannot leak
    between them, and asserts its own result."""

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
        line, source = next((n, s) for n, s in _blocks() if "get_traceback_limit() == 1" in s)
        mutated = source.replace("get_traceback_limit() == 1", "get_traceback_limit() == 25", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
