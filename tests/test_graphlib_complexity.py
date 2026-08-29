"""Tests to verify documented time complexity of graphlib operations.

A spot check of docs/stdlib/graphlib.md, which found the page's complexity
table sound but five of its eleven code blocks broken - all from the same
mistake, calling `prepare()` and then `static_order()`. `static_order()`
prepares internally, and a sorter can be prepared only once, so those
examples raised ValueError rather than sorting anything.

Two of them buried it: a class held one sorter and offered two methods that
each prepared it, and the failure was swallowed by `except Exception` and
reported as a circular dependency.

So this file covers the API contract as well as the bounds, and ends by
executing every Python block on the page. That last test is the one that
would have caught the bug: the complexity claims were right the whole time.
"""

import gc
import io
import sys
import time
from collections.abc import Callable
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
from typing import Any

import pytest

# CPython 3.14 allows repeated prepare() calls until the first get_ready();
# every earlier version allows exactly one. See TestApiContract.
RELAXED_PREPARE = sys.version_info >= (3, 14)

PROJECT_ROOT = Path(__file__).parent.parent
GRAPHLIB_PAGE = PROJECT_ROOT / "docs" / "stdlib" / "graphlib.md"


def measure(func: Callable[[], Any], repeats: int = 5) -> float:
    """Fastest of several runs, with the collector held off during each."""
    times: list[float] = []
    for _ in range(repeats):
        gc.collect()
        gc.disable()
        try:
            start = time.perf_counter()
            func()
            times.append(time.perf_counter() - start)
        finally:
            gc.enable()
    return min(times)


def measure_fresh(
    build: Callable[[], TopologicalSorter],
    action: Callable[[TopologicalSorter], Any],
    repeats: int = 3,
) -> float:
    """Time `action` on a newly built sorter each run.

    Needed because prepare() can be called only once per sorter - the same
    constraint that broke five of the page's examples, and this file's first
    draft of these tests.
    """
    times: list[float] = []
    for _ in range(repeats):
        sorter = build()
        gc.collect()
        gc.disable()
        try:
            start = time.perf_counter()
            action(sorter)
            times.append(time.perf_counter() - start)
        finally:
            gc.enable()
    return min(times)


def chain(size: int) -> TopologicalSorter:
    """A dependency chain of `size` nodes, so v == size and e == size - 1."""
    sorter: TopologicalSorter = TopologicalSorter()
    for node in range(1, size):
        sorter.add(node, node - 1)
    sorter.add(0)
    return sorter


def fan_out(size: int) -> TopologicalSorter:
    """One root that `size - 1` nodes depend on."""
    sorter: TopologicalSorter = TopologicalSorter()
    for node in range(1, size):
        sorter.add(node, 0)
    sorter.add(0)
    return sorter


class TestApiContract:
    """The behaviour the page's examples got wrong.

    These are cheap, deterministic, and pin the mistake directly.
    """

    def test_repeated_prepare_is_version_dependent(self) -> None:
        """3.14 relaxed this; up to 3.13 a second prepare() raises.

        The page stated the restriction unconditionally, which is wrong on
        3.14 - and an earlier version of this test asserted the same thing
        and failed there.
        """
        sorter = chain(3)
        sorter.prepare()
        if RELAXED_PREPARE:
            sorter.prepare()  # allowed: the sort has not started
        else:
            with pytest.raises(ValueError, match="cannot prepare"):
                sorter.prepare()

    def test_prepare_after_the_sort_starts_always_fails(self) -> None:
        """What every supported version agrees on."""
        sorter = chain(3)
        sorter.prepare()
        sorter.get_ready()
        with pytest.raises(ValueError, match="cannot prepare"):
            sorter.prepare()

    def test_static_order_prepares_internally(self) -> None:
        # No prepare() call, and it still sorts.
        assert list(chain(4).static_order()) == [0, 1, 2, 3]

    def test_preparing_first_then_calling_static_order(self) -> None:
        """Exactly the page's bug, in five blocks - up to 3.13.

        On 3.14 the same code happens to work, which is why the page needs
        the version qualification rather than a flat prohibition.
        """
        sorter = chain(4)
        sorter.prepare()
        if RELAXED_PREPARE:
            assert list(sorter.static_order()) == [0, 1, 2, 3]
        else:
            with pytest.raises(ValueError, match="cannot prepare"):
                list(sorter.static_order())

    def test_a_sorter_cannot_be_reused_for_a_second_traversal(self) -> None:
        """Why a class must keep the graph rather than a prepared sorter.

        True on every version, including 3.14 - which relaxed prepare() but
        not this. The message differs, so match on the type only.
        """
        sorter = chain(4)
        assert list(sorter.static_order()) == [0, 1, 2, 3]
        with pytest.raises(ValueError):
            list(sorter.static_order())

    def test_nodes_cannot_be_added_after_prepare(self) -> None:
        sorter = chain(3)
        sorter.prepare()
        with pytest.raises(ValueError, match="cannot be added"):
            sorter.add(99, 0)

    def test_get_ready_before_prepare_fails(self) -> None:
        with pytest.raises(ValueError, match="prepare"):
            TopologicalSorter().get_ready()


class TestCycleDetection:
    """docs/stdlib/graphlib.md: CycleError, raised during prepare()."""

    def test_a_cycle_raises_from_prepare(self) -> None:
        sorter: TopologicalSorter = TopologicalSorter()
        sorter.add(1, 2)
        sorter.add(2, 1)
        with pytest.raises(CycleError):
            sorter.prepare()

    def test_the_cycle_is_reported_in_the_exception(self) -> None:
        sorter: TopologicalSorter = TopologicalSorter()
        sorter.add(1, 2)
        sorter.add(2, 1)
        try:
            sorter.prepare()
        except CycleError as error:
            assert error.args[1] == [1, 2, 1]
        else:  # pragma: no cover
            raise AssertionError("expected a CycleError")

    def test_static_order_surfaces_the_same_error(self) -> None:
        sorter: TopologicalSorter = TopologicalSorter()
        sorter.add("a", "b")
        sorter.add("b", "a")
        with pytest.raises(CycleError):
            list(sorter.static_order())

    def test_detection_costs_a_traversal_not_a_search(self) -> None:
        """Cycle finding rides along with prepare(), so it is O(v + e)."""
        small_time = measure_fresh(lambda: chain(25_000), lambda s: s.prepare())
        large_time = measure_fresh(lambda: chain(100_000), lambda s: s.prepare())

        assert large_time < small_time * 12, (
            f"prepare() with cycle detection should stay linear: "
            f"{small_time:.2e}s vs {large_time:.2e}s"
        )


class TestGraphlibComplexity:
    """Test graphlib complexities as documented in docs/stdlib/graphlib.md."""

    SMALL_SIZE = 25_000
    LARGE_SIZE = 100_000
    SIZE_RATIO = LARGE_SIZE / SMALL_SIZE

    def test_init_is_o1(self) -> None:
        assert measure(TopologicalSorter, repeats=20) < 1e-4

    def test_add_does_not_depend_on_graph_size(self) -> None:
        small, large = chain(self.SMALL_SIZE), chain(self.LARGE_SIZE)

        small_time = measure(lambda: small.add(-1, -2), repeats=20)
        large_time = measure(lambda: large.add(-3, -4), repeats=20)

        assert large_time < small_time * 3, (
            f"add() should not care how big the graph already is: "
            f"{small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_add_is_ok_in_its_predecessors(self) -> None:
        few = list(range(2))
        many = list(range(200))

        few_time = measure(lambda: TopologicalSorter().add("x", *few), repeats=20)
        many_time = measure(lambda: TopologicalSorter().add("x", *many), repeats=20)

        assert many_time > few_time * 3, (
            f"add() should scale with its predecessor count: "
            f"few={few_time:.2e}s many={many_time:.2e}s"
        )

    def test_prepare_is_linear_in_the_graph(self) -> None:
        small_time = measure_fresh(lambda: chain(self.SMALL_SIZE), lambda s: s.prepare())
        large_time = measure_fresh(lambda: chain(self.LARGE_SIZE), lambda s: s.prepare())

        ratio = large_time / small_time
        assert ratio < self.SIZE_RATIO * 3, (
            f"prepare() doesn't appear O(v + e): {ratio:.1f}x for {self.SIZE_RATIO:.0f}x the graph"
        )

    def test_prepare_is_linear_for_a_shallow_graph_too(self) -> None:
        """Depth should not matter: chain and fan-out are both O(v + e)."""
        small_time = measure_fresh(lambda: fan_out(self.SMALL_SIZE), lambda s: s.prepare())
        large_time = measure_fresh(lambda: fan_out(self.LARGE_SIZE), lambda s: s.prepare())

        assert large_time / small_time < self.SIZE_RATIO * 3, (
            f"fan-out prepare() doesn't appear linear: {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_static_order_is_linear_in_the_graph(self) -> None:
        small_time = measure_fresh(lambda: chain(self.SMALL_SIZE), lambda s: list(s.static_order()))
        large_time = measure_fresh(lambda: chain(self.LARGE_SIZE), lambda s: list(s.static_order()))

        assert large_time / small_time < self.SIZE_RATIO * 3, (
            f"static_order() doesn't appear O(v + e): {small_time:.2e}s vs {large_time:.2e}s"
        )

    def test_get_ready_scales_with_what_it_returns(self) -> None:
        """The table said O(1) amortized; one call is O(k) in the k returned.

        Both sizes are chosen large enough to measure reliably - an earlier
        version timed a single ready node, which is sub-microsecond and went
        flaky under load.
        """

        def ready_of(count: int) -> float:
            sorter: TopologicalSorter = TopologicalSorter()
            for node in range(count):
                sorter.add(node)
            sorter.prepare()
            gc.collect()
            gc.disable()
            try:
                start = time.perf_counter()
                sorter.get_ready()
                return time.perf_counter() - start
            finally:
                gc.enable()

        small = min(ready_of(1_000) for _ in range(5))
        large = min(ready_of(100_000) for _ in range(5))

        assert large > small * 20, (
            f"get_ready() returns k nodes and costs O(k), not O(1): "
            f"k=1000 {small:.2e}s k=100000 {large:.2e}s"
        )

    def test_get_ready_is_o1_amortized_per_node(self) -> None:
        """Across a whole sort, each node is handed out exactly once."""
        size = 5_000
        sorter = fan_out(size)
        sorter.prepare()

        handed_out = 0
        while sorter.is_active():
            group = sorter.get_ready()
            handed_out += len(group)
            sorter.done(*group)

        assert handed_out == size

    def test_done_scales_with_the_node_degree(self) -> None:
        def done_on_root_with(degree: int) -> float:
            sorter: TopologicalSorter = TopologicalSorter()
            for node in range(1, degree + 1):
                sorter.add(node, 0)
            sorter.add(0)
            sorter.prepare()
            sorter.get_ready()
            gc.collect()
            start = time.perf_counter()
            sorter.done(0)
            return time.perf_counter() - start

        small = min(done_on_root_with(100) for _ in range(5))
        large = min(done_on_root_with(10_000) for _ in range(5))

        assert large > small * 10, (
            f"done() is O(d) in the node's successors: d=100 {small:.2e}s d=10000 {large:.2e}s"
        )


class TestDocumentedExamplesRun:
    """Every Python block on the page must execute.

    This is the test that would have caught the bug this spot check found.
    The complexity table was correct throughout; the examples were not, and
    nothing on the page or in the suite ran them.
    """

    def _blocks(self) -> list[tuple[int, str]]:
        blocks: list[tuple[int, str]] = []
        inside = False
        start = 0
        body: list[str] = []
        for number, line in enumerate(
            GRAPHLIB_PAGE.read_text(encoding="utf-8").splitlines(), start=1
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
        assert len(self._blocks()) >= 10

    def test_every_example_executes(self) -> None:
        failures: list[str] = []
        for line_number, source in self._blocks():
            captured, real_stdout = io.StringIO(), sys.stdout
            try:
                sys.stdout = captured
                exec(  # noqa: S102 - executing the docs is the point
                    compile(source, f"graphlib.md:{line_number}", "exec"),
                    {"__name__": "__main__"},
                )
            except ModuleNotFoundError as error:
                # Blocks illustrating third-party alternatives, e.g. networkx.
                if error.name in {"networkx"}:
                    continue
                failures.append(f"line {line_number}: {error!r}")
            except Exception as error:  # noqa: BLE001 - report, do not raise
                failures.append(f"line {line_number}: {type(error).__name__}: {error}")
            finally:
                sys.stdout = real_stdout

        assert not failures, "examples in docs/stdlib/graphlib.md failed:\n" + "\n".join(failures)
