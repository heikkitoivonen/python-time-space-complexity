"""Tests to verify documented behaviour of the heapq module.

The timing tests below check that operations scale as documented; the rest
observe counts and results directly, which needs no tolerance.

All thirteen code blocks on docs/stdlib/heapq.md run, and every output the
page states is checked against what the module actually returns. One block
could never have run: the Priority Queue Simulation used `priority` and
`task` before defining either, so it raised NameError on its first heappush.

On the "more efficient than separate calls" notes for heappushpop and
heapreplace: both are true, but not for the reason a reader might assume.
On a 1023-item heap the combined calls make the same number of comparisons
as the separate ones (12 against 12 for heappushpop, 11 against 12 for
heapreplace) - the saving is call overhead and list churn, plus a shortcut
that skips the sift entirely when the pushed item does not exceed the root.
That shortcut is what the counting test below pins, because it is the one
part of the claim that shows up as an exact, tolerance-free difference.

Not settled by execution:

* "PyPy: JIT compilation provides additional optimization" - this suite runs
  on CPython only.
* "Uses array-based binary heap, highly optimized" - a source-level fact.
  The list layout is observable (heap[0] is the root, children at 2i+1 and
  2i+2, asserted below); "highly optimized" is not a measurable claim.
* The max-heap table needs Python 3.14; those tests skip below that.
"""

import heapq
import math
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from typing import Any

import pytest

# pyright targets the pinned 3.11, where the max-heap functions do not exist.
# The MAX_HEAP skip below is what keeps every use of these safe at runtime;
# binding them once here keeps that ignore off twenty separate call sites.
heapify_max: Callable[[list[Any]], None] = getattr(heapq, "heapify_max", None)  # type: ignore[assignment]
heappush_max: Callable[[list[Any], Any], None] = getattr(heapq, "heappush_max", None)  # type: ignore[assignment]
heappop_max: Callable[[list[Any]], Any] = getattr(heapq, "heappop_max", None)  # type: ignore[assignment]
heapreplace_max: Callable[[list[Any], Any], Any] = getattr(heapq, "heapreplace_max", None)  # type: ignore[assignment]
heappushpop_max: Callable[[list[Any], Any], Any] = getattr(heapq, "heappushpop_max", None)  # type: ignore[assignment]


def trimmed_mean(samples: list[float], trim_fraction: float = 0.1) -> float:
    """Return the trimmed mean to reduce outlier impact."""
    if not samples:
        return 0.0
    if trim_fraction <= 0:
        return sum(samples) / len(samples)
    k = int(len(samples) * trim_fraction)
    if len(samples) - 2 * k <= 0:
        return sum(samples) / len(samples)
    samples = sorted(samples)
    core = samples[k : len(samples) - k]
    return sum(core) / len(core)


def measure_time(func: Callable[[], Any], iterations: int = 100) -> float:
    """Measure trimmed mean time for a function over multiple iterations."""
    times: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        times.append(end - start)
    return trimmed_mean(times)


def is_linear_time(
    small_time: float,
    large_time: float,
    size_ratio: float,
    tolerance: float = 3.0,
) -> bool:
    """Check if time scales linearly with size."""
    if small_time == 0:
        return True
    ratio = large_time / small_time
    expected_ratio = size_ratio
    return ratio < expected_ratio * tolerance


def is_logarithmic_time(
    small_time: float,
    large_time: float,
    small_size: int,
    large_size: int,
    tolerance: float = 3.0,
) -> bool:
    """Check if time scales logarithmically with size."""
    if small_time == 0:
        return True
    ratio = large_time / small_time
    expected_ratio = math.log2(large_size) / math.log2(small_size)
    return ratio < expected_ratio * tolerance


class TestHeapqComplexity:
    """Test heapq operation complexities as documented in docs/stdlib/heapq.md."""

    SMALL_SIZE = 1_000
    LARGE_SIZE = 100_000
    SIZE_RATIO = LARGE_SIZE / SMALL_SIZE

    @pytest.mark.timing
    def test_heapify_is_on(self) -> None:
        """heapify() should be O(n)."""
        small_list = list(range(self.SMALL_SIZE, 0, -1))
        large_list = list(range(self.LARGE_SIZE, 0, -1))

        def heapify_small() -> None:
            lst = small_list.copy()
            heapq.heapify(lst)

        def heapify_large() -> None:
            lst = large_list.copy()
            heapq.heapify(lst)

        small_time = measure_time(heapify_small, iterations=50)
        large_time = measure_time(heapify_large, iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"heapify() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    @pytest.mark.timing
    def test_heappush_is_ologn(self) -> None:
        """heappush() should be O(log n)."""
        small_heap = list(range(self.SMALL_SIZE))
        large_heap = list(range(self.LARGE_SIZE))
        heapq.heapify(small_heap)
        heapq.heapify(large_heap)

        def push_small() -> None:
            heapq.heappush(small_heap, 0)
            heapq.heappop(small_heap)

        def push_large() -> None:
            heapq.heappush(large_heap, 0)
            heapq.heappop(large_heap)

        small_time = measure_time(push_small)
        large_time = measure_time(push_large)

        assert is_logarithmic_time(small_time, large_time, self.SMALL_SIZE, self.LARGE_SIZE), (
            f"heappush() doesn't appear O(log n): {small_time:.2e}s vs {large_time:.2e}s"
        )

    @pytest.mark.timing
    def test_heappop_is_ologn(self) -> None:
        """heappop() should be O(log n)."""
        small_heap = list(range(self.SMALL_SIZE))
        large_heap = list(range(self.LARGE_SIZE))
        heapq.heapify(small_heap)
        heapq.heapify(large_heap)

        def pop_small() -> None:
            val = heapq.heappop(small_heap)
            heapq.heappush(small_heap, val)

        def pop_large() -> None:
            val = heapq.heappop(large_heap)
            heapq.heappush(large_heap, val)

        small_time = measure_time(pop_small)
        large_time = measure_time(pop_large)

        assert is_logarithmic_time(small_time, large_time, self.SMALL_SIZE, self.LARGE_SIZE), (
            f"heappop() doesn't appear O(log n): {small_time:.2e}s vs {large_time:.2e}s"
        )

    @pytest.mark.timing
    def test_heappushpop_is_ologn(self) -> None:
        """heappushpop() should be O(log n).

        The item has to exceed the root or heappushpop returns it untouched:
        pushing -1 into a heap rooted at 0 costs exactly one comparison at
        every size, which is what this test used to measure while asserting a
        logarithmic ratio. Pushing root + 1 costs 19 comparisons at n=1,000
        and 33 at n=100,000.
        """
        small_heap = list(range(self.SMALL_SIZE))
        large_heap = list(range(self.LARGE_SIZE))
        heapq.heapify(small_heap)
        heapq.heapify(large_heap)

        def pushpop_small() -> None:
            heapq.heappushpop(small_heap, small_heap[0] + 1)

        def pushpop_large() -> None:
            heapq.heappushpop(large_heap, large_heap[0] + 1)

        small_time = measure_time(pushpop_small, iterations=200)
        large_time = measure_time(pushpop_large, iterations=200)

        assert is_logarithmic_time(small_time, large_time, self.SMALL_SIZE, self.LARGE_SIZE), (
            f"heappushpop() doesn't appear O(log n): {small_time:.2e}s vs {large_time:.2e}s"
        )

    @pytest.mark.timing
    def test_heapreplace_is_ologn(self) -> None:
        """heapreplace() should be O(log n)."""
        small_heap = list(range(self.SMALL_SIZE))
        large_heap = list(range(self.LARGE_SIZE))
        heapq.heapify(small_heap)
        heapq.heapify(large_heap)

        def replace_small() -> None:
            val = heapq.heapreplace(small_heap, -1)
            heapq.heappush(small_heap, val)
            heapq.heappop(small_heap)

        def replace_large() -> None:
            val = heapq.heapreplace(large_heap, -1)
            heapq.heappush(large_heap, val)
            heapq.heappop(large_heap)

        small_time = measure_time(replace_small)
        large_time = measure_time(replace_large)

        assert is_logarithmic_time(small_time, large_time, self.SMALL_SIZE, self.LARGE_SIZE), (
            f"heapreplace() doesn't appear O(log n): {small_time:.2e}s vs {large_time:.2e}s"
        )

    @pytest.mark.timing
    def test_nlargest_scales_with_n(self) -> None:
        """nlargest(k, iterable) should be O(N log k) where N = iterable length."""
        small_data = list(range(self.SMALL_SIZE))
        large_data = list(range(self.LARGE_SIZE))
        k = 10

        small_time = measure_time(lambda: heapq.nlargest(k, small_data), iterations=50)
        large_time = measure_time(lambda: heapq.nlargest(k, large_data), iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"nlargest() doesn't scale linearly with N: {small_time:.2e}s vs {large_time:.2e}s"
        )

    @pytest.mark.timing
    def test_nsmallest_scales_with_n(self) -> None:
        """nsmallest(k, iterable) should be O(N log k) where N = iterable length."""
        small_data = list(range(self.SMALL_SIZE))
        large_data = list(range(self.LARGE_SIZE))
        k = 10

        small_time = measure_time(lambda: heapq.nsmallest(k, small_data), iterations=50)
        large_time = measure_time(lambda: heapq.nsmallest(k, large_data), iterations=50)

        assert is_linear_time(small_time, large_time, self.SIZE_RATIO), (
            f"nsmallest() doesn't scale linearly with N: {small_time:.2e}s vs {large_time:.2e}s"
        )

    @pytest.mark.timing
    def test_nlargest_scales_with_k(self) -> None:
        """nlargest with larger k should be slower (O(N log k))."""
        data = list(range(self.LARGE_SIZE))

        small_k_time = measure_time(lambda: heapq.nlargest(10, data), iterations=20)
        large_k_time = measure_time(lambda: heapq.nlargest(1000, data), iterations=20)

        # log2(1000)/log2(10) predicts about 3x; a bare > would pass on noise.
        assert large_k_time > 1.5 * small_k_time, (
            f"nlargest() should be markedly slower with larger k: "
            f"k=10: {small_k_time:.2e}s vs k=1000: {large_k_time:.2e}s"
        )

    @pytest.mark.timing
    def test_merge_scales_with_total_items(self) -> None:
        """merge() should scale with total items O(n log k)."""
        small_lists = [list(range(i, i + 100)) for i in range(10)]
        large_lists = [list(range(i, i + 10000)) for i in range(10)]

        def merge_small() -> None:
            list(heapq.merge(*small_lists))

        def merge_large() -> None:
            list(heapq.merge(*large_lists))

        small_time = measure_time(merge_small, iterations=50)
        large_time = measure_time(merge_large, iterations=50)

        assert is_linear_time(small_time, large_time, 100), (
            f"merge() doesn't scale linearly with total items: "
            f"{small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_heap_maintains_invariant(self) -> None:
        """Verify heap property is maintained after operations."""
        import random

        data = list(range(1000))
        random.Random(7).shuffle(data)

        heap: list[int] = []
        for item in data:
            heapq.heappush(heap, item)

        sorted_result = []
        while heap:
            sorted_result.append(heapq.heappop(heap))

        assert sorted_result == sorted(data), "Heap did not maintain sorted order"

    def test_heapify_produces_valid_heap(self) -> None:
        """Verify heapify produces valid min-heap."""
        import random

        data = list(range(1000))
        random.Random(11).shuffle(data)

        heapq.heapify(data)

        for i in range(len(data)):
            left = 2 * i + 1
            right = 2 * i + 2
            if left < len(data):
                assert data[i] <= data[left], f"Heap violated at {i} vs left {left}"
            if right < len(data):
                assert data[i] <= data[right], f"Heap violated at {i} vs right {right}"


class CountingInt(int):
    """A heap element that counts the comparisons made against it."""

    comparisons = 0

    def __lt__(self, other: int) -> bool:
        CountingInt.comparisons += 1
        return int.__lt__(self, other)


def counted(operation: Callable[[list[CountingInt]], Any], size: int) -> int:
    """Comparisons made by one operation on a freshly heapified list."""
    heap = [CountingInt(value) for value in range(size)]
    heapq.heapify(heap)
    CountingInt.comparisons = 0
    operation(heap)
    return CountingInt.comparisons


class TestCombinedOperationsBeatSeparateCalls:
    """The "more efficient than separate calls" notes on the table.

    Both notes are true, but comparison counts alone barely show it: for an
    item above the root, heappushpop costs the same 12 comparisons as a push
    and a pop on a 1023-item heap. What is exact and reproducible is the
    shortcut, and heapreplace's one-comparison edge, which holds at every
    size tried (63, 255, 1023, 4095).
    """

    SIZE = 1_023

    def test_heappushpop_skips_the_sift_when_the_item_loses(self) -> None:
        """An item that does not beat the root is handed straight back."""
        shortcut = counted(lambda h: heapq.heappushpop(h, CountingInt(-1)), self.SIZE)
        sifted = counted(lambda h: heapq.heappushpop(h, CountingInt(h[0] + 1)), self.SIZE)

        assert shortcut == 1, f"the shortcut should cost one comparison, not {shortcut}"
        assert sifted > 10 * shortcut, (
            f"pushing above the root should sift: {sifted} against {shortcut}"
        )

    def test_heappushpop_leaves_the_heap_alone_on_the_shortcut(self) -> None:
        heap = list(range(self.SIZE))
        heapq.heapify(heap)
        before = heap.copy()

        returned = heapq.heappushpop(heap, -1)

        assert returned == -1
        assert heap == before, "the shortcut should not touch the heap"

    def test_heapreplace_costs_one_comparison_less_than_pop_then_push(self) -> None:
        """The gap is exactly one at every size tried, not a tolerance."""
        combined = counted(lambda h: heapq.heapreplace(h, CountingInt(h[0] + 1)), self.SIZE)
        separate = counted(
            lambda h: (heapq.heappop(h), heapq.heappush(h, CountingInt(0))), self.SIZE
        )

        assert combined < separate, (
            f"heapreplace should not cost more than pop+push: {combined} against {separate}"
        )

    @pytest.mark.timing
    def test_heappushpop_beats_push_then_pop_on_realistic_items(self) -> None:
        """Timed at n=1,000, where the gap is widest.

        Random items make the shortcut fire about half the time, which is the
        realistic case and where the claim earns its keep: measured 5.9x here
        against 1.6x at n=100,000, so the smaller heap is the framing with the
        larger margin rather than the one that merely passes.
        """
        import random

        size = 1_000
        rng = random.Random(7)
        items = [rng.randrange(size) for _ in range(20_000)]

        def combined() -> None:
            heap = [rng.randrange(size) for _ in range(size)]
            heapq.heapify(heap)
            for item in items:
                heapq.heappushpop(heap, item)

        def separate() -> None:
            heap = [rng.randrange(size) for _ in range(size)]
            heapq.heapify(heap)
            for item in items:
                heapq.heappush(heap, item)
                heapq.heappop(heap)

        combined_time = measure_time(combined, iterations=3)
        separate_time = measure_time(separate, iterations=3)

        assert separate_time > 2.0 * combined_time, (
            f"heappushpop should beat push+pop clearly: "
            f"{combined_time:.2e}s against {separate_time:.2e}s"
        )


class TestHeapLayout:
    """The Min-Heap Property block: root at 0, children at 2i+1 and 2i+2."""

    def test_the_root_is_the_minimum(self) -> None:
        import random

        data = list(range(500))
        random.Random(3).shuffle(data)
        heapq.heapify(data)

        assert data[0] == min(data), "heap[0] should be the minimum"

    def test_children_are_at_the_documented_indices(self) -> None:
        import random

        data = list(range(500))
        random.Random(5).shuffle(data)
        heapq.heapify(data)

        for parent in range(len(data)):
            for child in (2 * parent + 1, 2 * parent + 2):
                if child < len(data):
                    assert data[parent] <= data[child], (
                        f"heap property violated at {parent} -> {child}"
                    )


MAX_HEAP = pytest.mark.skipif(
    not hasattr(heapq, "heapify_max"), reason="max-heap functions are new in 3.14"
)


@MAX_HEAP
class TestMaxHeapOperations:
    """The Max-Heap Operations table, untested until now."""

    SMALL_SIZE = 1_000
    LARGE_SIZE = 100_000

    def test_heapify_max_puts_the_maximum_at_the_root(self) -> None:
        data = [3, 1, 4, 1, 5, 9, 2, 6]

        heapify_max(data)

        assert data[0] == 9, f"the page prints 9 as the root, got {data[0]}"

    def test_max_heap_property_holds_throughout(self) -> None:
        import random

        data = list(range(500))
        random.Random(13).shuffle(data)

        heapify_max(data)

        for parent in range(len(data)):
            for child in (2 * parent + 1, 2 * parent + 2):
                if child < len(data):
                    assert data[parent] >= data[child], (
                        f"max-heap property violated at {parent} -> {child}"
                    )

    def test_push_and_pop_max_round_trip(self) -> None:
        data = [3, 1, 4, 1, 5, 9, 2, 6]
        heapify_max(data)

        heappush_max(data, 10)

        assert heappop_max(data) == 10, "the pushed maximum should come back first"

    def test_draining_a_max_heap_yields_descending_order(self) -> None:
        import random

        data = list(range(200))
        random.Random(17).shuffle(data)
        heapify_max(data)

        drained = [heappop_max(data) for _ in range(200)]

        assert drained == sorted(drained, reverse=True)

    @staticmethod
    def _counted_max(operation: Callable[[list[CountingInt]], Any], size: int) -> int:
        """Comparisons made by one operation on a freshly max-heapified list."""
        heap = [CountingInt(value) for value in range(size)]
        heapify_max(heap)
        CountingInt.comparisons = 0
        operation(heap)
        return CountingInt.comparisons

    def test_replace_max_and_pushpop_max_keep_the_size(self) -> None:
        data = [3, 1, 4, 1, 5, 9, 2, 6]
        heapify_max(data)
        size = len(data)

        heapreplace_max(data, 7)
        assert len(data) == size, "heapreplace_max should not change the size"

        heappushpop_max(data, 8)
        assert len(data) == size, "heappushpop_max should not change the size"

    def test_heappushpop_max_skips_the_sift_when_the_item_wins(self) -> None:
        """The max-heap twin of heappushpop's shortcut.

        An item at or above the root comes straight back out, so a test that
        pushes one exercises no sift at all: one comparison against 19 at
        n=1,023 and 31 at n=65,535.
        """
        for size in (1_023, 65_535):
            shortcut = self._counted_max(lambda h: heappushpop_max(h, CountingInt(10**9)), size)
            sifted = self._counted_max(lambda h: heappushpop_max(h, CountingInt(h[0] - 1)), size)

            assert shortcut == 1, (
                f"an item above the root should cost one comparison at n={size}, got {shortcut}"
            )
            assert sifted > 10 * shortcut, (
                f"an item below the root should sift at n={size}: {sifted} against {shortcut}"
            )

    def test_heappushpop_max_sift_path_is_logarithmic(self) -> None:
        small = self._counted_max(lambda h: heappushpop_max(h, CountingInt(h[0] - 1)), 1_023)
        large = self._counted_max(lambda h: heappushpop_max(h, CountingInt(h[0] - 1)), 65_535)

        # 64x the heap: log predicts about 1.6x, linear would be 64x.
        assert large < 5 * small, (
            f"heappushpop_max does not look logarithmic: {small} against {large} "
            f"comparisons for a 64x heap"
        )

    def test_heapreplace_max_is_logarithmic(self) -> None:
        """1,024x the heap costs about twice the comparisons, not 1,024 times."""
        small = self._counted_max(lambda h: heapreplace_max(h, CountingInt(h[0] - 1)), 1_023)
        large = self._counted_max(lambda h: heapreplace_max(h, CountingInt(h[0] - 1)), 1_048_575)

        assert large < 5 * small, (
            f"heapreplace_max does not look logarithmic: {small} against {large} "
            f"comparisons for a 1,024x heap"
        )

    def test_the_combined_max_operations_allocate_nothing(self) -> None:
        """The O(1) space column: the peak does not follow the heap."""
        peaks: list[int] = []
        for size in (1_000, 100_000):
            heap = list(range(size))
            heapify_max(heap)

            tracemalloc.start()
            try:
                heapreplace_max(heap, -1)
                heappushpop_max(heap, heap[0] - 1)
                peaks.append(tracemalloc.get_traced_memory()[1])
            finally:
                tracemalloc.stop()

        # The 100,000-item heap's own storage is roughly 800 KB.
        assert max(peaks) < 10_000, (
            f"the combined max operations should allocate nothing per element: {peaks} bytes"
        )

    @pytest.mark.timing
    def test_heapify_max_is_on(self) -> None:
        small_list = list(range(self.SMALL_SIZE))
        large_list = list(range(self.LARGE_SIZE))

        small_time = measure_time(lambda: heapify_max(small_list.copy()), iterations=50)
        large_time = measure_time(lambda: heapify_max(large_list.copy()), iterations=50)

        ratio = self.LARGE_SIZE / self.SMALL_SIZE
        assert is_linear_time(small_time, large_time, ratio), (
            f"heapify_max() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    @pytest.mark.timing
    def test_heappop_max_is_ologn(self) -> None:
        small_heap = list(range(self.SMALL_SIZE))
        large_heap = list(range(self.LARGE_SIZE))
        heapify_max(small_heap)
        heapify_max(large_heap)

        def pop_small() -> None:
            heappush_max(small_heap, heappop_max(small_heap))

        def pop_large() -> None:
            heappush_max(large_heap, heappop_max(large_heap))

        small_time = measure_time(pop_small)
        large_time = measure_time(pop_large)

        assert is_logarithmic_time(small_time, large_time, self.SMALL_SIZE, self.LARGE_SIZE), (
            f"heappop_max() doesn't appear O(log n): {small_time:.2e}s vs {large_time:.2e}s"
        )


PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "heapq.md"

# Counts are asserted so a broken extractor cannot pass by finding nothing.
EXPECTED_BLOCKS = 13
EXPECTED_MAX_HEAP_BLOCKS = 2


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


def _needs_max_heap(source: str) -> bool:
    return "_max(" in source


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

    The Priority Queue Simulation block did not: it pushed `(priority, task)`
    with neither name bound, raising NameError. Nothing here executed the
    page's code before, which is how that survived.
    """

    def test_the_page_has_the_expected_blocks(self) -> None:
        blocks = _blocks()

        assert len(blocks) == EXPECTED_BLOCKS, (
            f"expected {EXPECTED_BLOCKS} python blocks, found {len(blocks)}"
        )
        gated = [line for line, source in blocks if _needs_max_heap(source)]
        assert len(gated) == EXPECTED_MAX_HEAP_BLOCKS, (
            f"expected {EXPECTED_MAX_HEAP_BLOCKS} max-heap blocks, found {gated}"
        )

    def test_every_block_runs(self, tmp_path: pathlib.Path) -> None:
        has_max_heap = hasattr(heapq, "heapify_max")
        failures: list[str] = []
        ran = 0

        for line, source in _blocks():
            if _needs_max_heap(source) and not has_max_heap:
                continue
            ran += 1
            result = _run(source, tmp_path)
            if result.returncode != 0:
                failures.append(f"{PAGE.name}:{line} raised: {result.stderr.strip()}")

        assert not failures, "\n".join(failures)
        expected = EXPECTED_BLOCKS if has_max_heap else EXPECTED_BLOCKS - EXPECTED_MAX_HEAP_BLOCKS
        assert ran == expected, f"ran {ran} blocks, expected {expected}"

    def test_the_runner_catches_a_broken_block(self, tmp_path: pathlib.Path) -> None:
        """A runner that cannot fail proves nothing about the blocks it ran."""
        original = _blocks()[0][1]
        broken = original + "\nheapq.heappush(heap_queue, (priority, task))\n"
        assert broken != original, "the mutation did not change the block"

        result = _run(broken, tmp_path)

        assert result.returncode != 0
        assert "NameError" in result.stderr


class TestDocumentedOutputs:
    """Every result the page prints or writes in a comment."""

    def test_heapify_transform_result(self) -> None:
        data = [5, 3, 7, 1, 9]

        heapq.heapify(data)

        assert data == [1, 3, 7, 5, 9]

    def test_iterative_operations_results(self) -> None:
        heap = [5, 3, 7]
        heapq.heapify(heap)
        assert heap == [3, 5, 7]

        heapq.heappush(heap, 1)
        assert heap == [1, 3, 7, 5]

        heapq.heappush(heap, 6)
        assert heapq.heappop(heap) == 1

    def test_priority_queue_drains_in_priority_order(self) -> None:
        tasks = [(3, "low"), (1, "high"), (2, "medium")]
        heapq.heapify(tasks)

        drained = [heapq.heappop(tasks)[1] for _ in range(3)]

        assert drained == ["high", "medium", "low"]

    def test_top_k_results(self) -> None:
        data = [3, 1, 4, 1, 5, 9, 2, 6]

        assert heapq.nlargest(3, data) == [9, 6, 5]
        assert heapq.nsmallest(3, data) == [1, 1, 2]

    def test_merge_result(self) -> None:
        merged = heapq.merge([1, 3, 5], [2, 4, 6], [1.5, 2.5, 3.5])

        assert list(merged) == [1, 1.5, 2, 2.5, 3, 3.5, 4, 5, 6]

    @MAX_HEAP
    def test_max_heap_priority_queue_output(self) -> None:
        tasks = [(1, "low"), (5, "urgent"), (3, "medium")]
        heapify_max(tasks)

        drained = [heappop_max(tasks) for _ in range(3)]

        assert drained == [(5, "urgent"), (3, "medium"), (1, "low")]
