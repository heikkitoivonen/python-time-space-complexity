"""Tests for docs/stdlib/graphlib.md.

The page prices a `TopologicalSorter` by nodes and edges: one dictionary
entry per node, one successor-list entry per edge. The sort's per-node and
per-edge steps each look a node up in a dictionary or set, so the nodes here
count their own `__hash__` calls: an exact count, with no tolerance, that
scales with the work on the paths exercised. It is not a count of every
operation, and the list scans and tuple building beside it are not counted. Space is settled by traced allocation at sizes far
apart, and only `is_active()` needs a stopwatch.

Measurement scope:

* Construction without a graph hashes nothing and peaks under 2 KB. With a
  graph it hashes in proportion to v + e: a 10,000-node chain hashes 9 to 11
  times a 1,000-node one, and two nodes joined by 100,000 repeated edges
  hash more than 50 times two joined by 1,000. The 200,000-edge graph peaks
  more than 20 times the 2,000-edge one.
* `add(node, *predecessors)` hashes between k + 1 and 2(k + 1) times for k =
  1,000 predecessors, the same count beside a 10-node graph as beside a
  100,000-node one; the peak for 200,000 predecessors is more than 5 times
  that for 20,000. A second `add()` for the same node keeps it blocked until
  the predecessors of both calls are done, and `add()` after `prepare()`
  raises `ValueError`.
* `prepare()` on a 10,000-node chain hashes 9 to 11 times a 1,000-node one,
  on a fan-out of the same sizes likewise, and on two nodes joined by
  100,000 repeated edges more than 50 times two joined by 1,000. Its peak
  over those 100,000 repeated edges stays under 10 KB, while over a
  200,000-node chain it exceeds 1 MB: it holds O(v), not O(e).
* `get_ready()` hashes exactly r times for r = 1,000 and 100,000 ready
  nodes, returns each node once over a whole sort, and its peak grows more
  than 5 times from r = 20,000 to 200,000. It returns an empty tuple while
  handed-out nodes are not done, with `is_active()` still `True`.
* `done(*nodes)` hashes exactly len(nodes) + d times: 1 + d for a root with
  d = 1,000 and 100,000 successors, and 3 for a node named twice as one
  successor's predecessor. Its peak grows more than 5 times from d = 20,000
  to 200,000 with one node passed, and from 20,000 to 200,000 nodes passed
  that have no successors. A whole sort of a 5,000-node graph with 9,998 edges spends
  exactly 2v + e hashes across `get_ready()` and `done()`. A node not yet
  handed out, one already done, and one never added each raise `ValueError`.
* `is_active()` and `bool()` hash nothing, and a timing test bounds
  `is_active()` under 5 times as costly with 1,000,000 ready nodes as with 100, where a
  scan would predict 10,000 times. They agree, and turn `False` once only
  nodes blocked by a cycle are left.
* `static_order()` hashes nothing and leaves `add()` usable until its first
  `next()`, which raises `CycleError` on a cyclic graph. A full traversal
  hashes 9 to 11 times as much on a 10,000-node chain as on a 1,000-node
  one. Its peak over 100,000 repeated edges between two nodes stays under
  10 KB, and over a fan-out grows more than 3 times from 20,000 nodes to
  200,000. A second traversal of the same sorter raises `ValueError`. A
  sorter built from a mapping whose predecessors are an iterator consumes
  it, so a second sorter from the same mapping lacks those edges.
* `prepare()` is guarded on `sys.version_info`: from 3.14 a second call
  before a node is handed out hashes as much as the first, a call after a
  `get_ready()` that returned nothing raises `CycleError` again on a cyclic
  graph, and a
  `static_order()` traversal after `prepare()` hashes exactly as much as one
  without it, so the cycle search runs again; before 3.14 the second call
  raises `ValueError` saying it cannot prepare. After a `get_ready()` that
  handed out a node it raises that on every version.
* `CycleError` is asserted to be a `ValueError` whose `args[1]` starts and
  ends with the same node, and `get_ready()` still hands out the nodes the
  cycle does not block.
* Every fenced Python block runs in its own subprocess, and a mutated
  assertion in one of them is asserted to fail.

Not settled here:

* That the module is pure Python, one dictionary entry per node and one
  successor-list entry per edge, is read from Lib/graphlib.py.
* Hashing and comparing a node are treated as O(1); counting `__hash__`
  calls measures the number of lookups, not their cost for a costly node.
* The order within one ready group is not guaranteed by the documentation,
  so no test pins it; the examples assert groups as sets.
* `TopologicalSorter[T]`, available from 3.11, is left out of the official
  documentation and is not priced on the page.
* The space bounds count allocation during the call; the sorter's own
  O(v + e) is measured only through construction.
"""

from __future__ import annotations

import gc
import pathlib
import re
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections import deque
from collections.abc import Callable
from functools import partial
from graphlib import CycleError, TopologicalSorter
from typing import Any

import pytest

PAGE = pathlib.Path(__file__).parent.parent / "docs" / "stdlib" / "graphlib.md"
EXPECTED_BLOCKS = 7
RELAXED_PREPARE = sys.version_info >= (3, 14)


class Node:
    """A graph node that counts every hash taken of it, across all nodes."""

    __slots__ = ("value",)
    hashes = 0

    def __init__(self, value: int) -> None:
        self.value = value

    def __hash__(self) -> int:
        Node.hashes += 1
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Node) and other.value == self.value

    def __repr__(self) -> str:
        return f"Node({self.value})"


def hashes_during(func: Callable[[], Any]) -> int:
    """How many node hashes func takes."""
    Node.hashes = 0
    func()
    return Node.hashes


def peak_bytes(func: Callable[[], Any]) -> int:
    """Peak traced allocation while func runs."""
    gc.collect()
    tracemalloc.start()
    try:
        func()
        return tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()


def best_ns(func: Callable[[], Any], repeats: int = 7, inner: int = 1_000) -> float:
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


def nodes(count: int) -> list[Node]:
    return [Node(value) for value in range(count)]


def chain_graph(size: int) -> dict[Node, list[Node]]:
    """`size` nodes, each depending on the one before: v = size, e = size - 1."""
    made = nodes(size)
    graph = {made[0]: []}
    for before, after in zip(made, made[1:], strict=False):
        graph[after] = [before]
    return graph


def fan_out_graph(size: int) -> dict[Node, list[Node]]:
    """One root that the other `size - 1` nodes depend on."""
    made = nodes(size)
    graph: dict[Node, list[Node]] = {made[0]: []}
    for node in made[1:]:
        graph[node] = [made[0]]
    return graph


def repeated_edge_graph(edges: int) -> dict[Node, list[Node]]:
    """Two nodes, the second naming the first `edges` times: v = 2, e = edges."""
    first, second = Node(0), Node(1)
    return {first: [], second: [first] * edges}


def all_ready(count: int) -> TopologicalSorter[Node]:
    """A prepared sorter whose `count` nodes are all ready at once."""
    sorter: TopologicalSorter[Node] = TopologicalSorter()
    for node in nodes(count):
        sorter.add(node)
    sorter.prepare()
    return sorter


def root_handed_out(successors: int) -> tuple[TopologicalSorter[Node], Node]:
    """A prepared fan-out whose root has been returned by get_ready()."""
    graph = fan_out_graph(successors + 1)
    root = next(iter(graph))
    sorter = TopologicalSorter(graph)
    sorter.prepare()
    assert sorter.get_ready() == (root,)
    return sorter, root


class TestConstructionAddsEachEntry:
    """`TopologicalSorter(graph=None)` | O(1); O(v + e) with `graph`.

    Hash counts separate the two terms: a chain grows v and e together,
    repeated edges between two nodes grow e alone.
    """

    def test_an_empty_sorter_does_no_work(self) -> None:
        assert hashes_during(TopologicalSorter) == 0
        assert peak_bytes(TopologicalSorter) < 2_000

    def test_a_graph_costs_its_nodes(self) -> None:
        small, large = chain_graph(1_000), chain_graph(10_000)

        ratio = hashes_during(lambda: TopologicalSorter(large)) / hashes_during(
            lambda: TopologicalSorter(small)
        )

        assert 9 < ratio < 11, f"10x the chain cost {ratio:.1f}x the hashes"

    def test_a_graph_costs_its_edges(self) -> None:
        few, many = repeated_edge_graph(1_000), repeated_edge_graph(100_000)

        ratio = hashes_during(lambda: TopologicalSorter(many)) / hashes_during(
            lambda: TopologicalSorter(few)
        )

        assert ratio > 50, f"100x the edges cost only {ratio:.1f}x the hashes"

    def test_the_sorter_holds_its_edges(self) -> None:
        few, many = repeated_edge_graph(2_000), repeated_edge_graph(200_000)

        few_peak = peak_bytes(lambda: TopologicalSorter(few))
        many_peak = peak_bytes(lambda: TopologicalSorter(many))

        assert many_peak > few_peak * 20, f"{few_peak} bytes vs {many_peak} bytes"


class TestAddCostsItsPredecessors:
    """`add(node, *predecessors)` | O(k) | O(k), whatever the graph's size."""

    def test_hashes_follow_k_not_the_graph(self) -> None:
        predecessors = [Node(-index) for index in range(1, 1_001)]
        counts = []
        for size in (10, 100_000):
            sorter = TopologicalSorter(chain_graph(size))
            counts.append(hashes_during(partial(sorter.add, Node(-5_000), *predecessors)))

        assert counts[0] == counts[1], f"graph size changed add(): {counts}"
        assert 1_001 <= counts[0] <= 2_002, f"k = 1,000 took {counts[0]} hashes"

    def test_space_follows_k(self) -> None:
        few, many = nodes(20_000), nodes(200_000)

        few_peak = peak_bytes(lambda: TopologicalSorter().add(Node(-1), *few))
        many_peak = peak_bytes(lambda: TopologicalSorter().add(Node(-1), *many))

        assert many_peak > few_peak * 5, f"{few_peak} bytes vs {many_peak} bytes"

    def test_repeated_calls_add_to_the_predecessors(self) -> None:
        sorter: TopologicalSorter[str] = TopologicalSorter()
        sorter.add("app", "lib")
        sorter.add("app", "config", "lib")
        sorter.prepare()

        assert set(sorter.get_ready()) == {"lib", "config"}
        sorter.done("lib")
        assert sorter.get_ready() == ()
        sorter.done("config")
        assert sorter.get_ready() == ("app",)

    def test_nodes_cannot_be_added_after_prepare(self) -> None:
        sorter: TopologicalSorter[int] = TopologicalSorter({1: [0]})
        sorter.prepare()
        with pytest.raises(ValueError, match="cannot be added"):
            sorter.add(2, 1)


class TestPrepareIsOneTraversal:
    """`prepare()` | O(v + e) | O(v): finds the ready nodes and searches for
    a cycle. Shape at a fixed size does not matter, edges count even between
    the same two nodes, and the space it allocates follows nodes alone."""

    @pytest.mark.parametrize("shape", [chain_graph, fan_out_graph])
    def test_hashes_follow_the_nodes(self, shape: Callable[[int], dict[Node, list[Node]]]) -> None:
        small, large = TopologicalSorter(shape(1_000)), TopologicalSorter(shape(10_000))

        ratio = hashes_during(large.prepare) / hashes_during(small.prepare)

        assert 9 < ratio < 11, f"10x the {shape.__name__} cost {ratio:.1f}x the hashes"

    def test_hashes_follow_the_edges(self) -> None:
        few = TopologicalSorter(repeated_edge_graph(1_000))
        many = TopologicalSorter(repeated_edge_graph(100_000))

        ratio = hashes_during(many.prepare) / hashes_during(few.prepare)

        assert ratio > 50, f"100x the edges cost only {ratio:.1f}x the hashes"

    def test_space_follows_nodes_not_edges(self) -> None:
        edges = TopologicalSorter(repeated_edge_graph(100_000))
        long_chain = TopologicalSorter(chain_graph(200_000))

        edges_peak = peak_bytes(edges.prepare)
        chain_peak = peak_bytes(long_chain.prepare)

        assert edges_peak < 10_000, f"100,000 edges between two nodes: {edges_peak} bytes"
        assert chain_peak > 1_000_000, f"a 200,000-node chain: {chain_peak} bytes"

    def test_repeated_prepare_depends_on_the_version(self) -> None:
        sorter = TopologicalSorter(chain_graph(1_000))
        first = hashes_during(sorter.prepare)
        if RELAXED_PREPARE:
            assert hashes_during(sorter.prepare) == first, "the second search was cheaper"
        else:
            with pytest.raises(ValueError, match="cannot prepare"):
                sorter.prepare()

    def test_an_empty_get_ready_does_not_start_the_sort(self) -> None:
        sorter: TopologicalSorter[str] = TopologicalSorter({"a": ["b"], "b": ["a"]})
        with pytest.raises(CycleError):
            sorter.prepare()
        assert sorter.get_ready() == ()

        if RELAXED_PREPARE:
            with pytest.raises(CycleError):
                sorter.prepare()
        else:
            with pytest.raises(ValueError, match="cannot prepare"):
                sorter.prepare()

    def test_prepare_after_the_sort_starts_always_fails(self) -> None:
        sorter: TopologicalSorter[int] = TopologicalSorter({1: [0]})
        sorter.prepare()
        sorter.get_ready()
        with pytest.raises(ValueError, match="cannot prepare"):
            sorter.prepare()


class TestCycleError:
    """`CycleError`: a `ValueError` raised by `prepare()`, carrying one cycle,
    after which the nodes the cycle does not block are still handed out."""

    def test_the_cycle_is_reported(self) -> None:
        sorter: TopologicalSorter[str] = TopologicalSorter({"a": ["b"], "b": ["a"]})
        with pytest.raises(CycleError) as caught:
            sorter.prepare()

        assert isinstance(caught.value, ValueError)
        cycle = caught.value.args[1]
        assert cycle[0] == cycle[-1]
        assert set(cycle) == {"a", "b"}

    def test_the_rest_of_the_graph_is_still_sorted(self) -> None:
        graph = {"a": ["b"], "b": ["a"], "c": [], "d": ["c"]}
        sorter: TopologicalSorter[str] = TopologicalSorter(graph)
        with pytest.raises(CycleError):
            sorter.prepare()

        handed_out: list[str] = []
        while sorter.is_active():
            group = sorter.get_ready()
            handed_out.extend(group)
            sorter.done(*group)

        assert handed_out == ["c", "d"]
        assert not sorter


class TestGetReadyReturnsEachNodeOnce:
    """`get_ready()` | O(r) | O(r): a tuple of the r nodes made ready."""

    @pytest.mark.parametrize("ready", [1_000, 100_000])
    def test_one_hash_per_returned_node(self, ready: int) -> None:
        sorter = all_ready(ready)
        returned: tuple[Node, ...] = ()

        def call() -> None:
            nonlocal returned
            returned = sorter.get_ready()

        assert hashes_during(call) == ready
        assert isinstance(returned, tuple) and len(returned) == ready

    def test_space_follows_what_it_returns(self) -> None:
        small, large = all_ready(20_000), all_ready(200_000)

        small_peak = peak_bytes(small.get_ready)
        large_peak = peak_bytes(large.get_ready)

        assert large_peak > small_peak * 5, f"{small_peak} bytes vs {large_peak} bytes"

    def test_nothing_new_until_something_is_done(self) -> None:
        sorter: TopologicalSorter[str] = TopologicalSorter({"b": ["a"]})
        sorter.prepare()

        assert sorter.get_ready() == ("a",)
        assert sorter.get_ready() == ()
        assert sorter.is_active()

    def test_each_node_is_returned_once_over_a_sort(self) -> None:
        sorter = TopologicalSorter(fan_out_graph(5_000))
        sorter.prepare()
        returned: list[Node] = []
        while sorter.is_active():
            group = sorter.get_ready()
            returned.extend(group)
            sorter.done(*group)

        assert len(returned) == len(set(returned)) == 5_000


class TestDoneReleasesSuccessors:
    """`done(*nodes)` | O(len(nodes) + d) | O(len(nodes) + d), and O(v + e) over a sort."""

    @pytest.mark.parametrize("successors", [1_000, 100_000])
    def test_one_hash_per_node_and_successor_entry(self, successors: int) -> None:
        sorter, root = root_handed_out(successors)

        assert hashes_during(lambda: sorter.done(root)) == 1 + successors

    def test_a_repeated_edge_is_two_successor_entries(self) -> None:
        first, second = Node(0), Node(1)
        sorter = TopologicalSorter({second: [first, first]})
        sorter.prepare()
        assert sorter.get_ready() == (first,)

        assert hashes_during(lambda: sorter.done(first)) == 3
        assert sorter.get_ready() == (second,)

    def test_space_follows_the_successors_it_unblocks(self) -> None:
        small, small_root = root_handed_out(20_000)
        large, large_root = root_handed_out(200_000)

        small_peak = peak_bytes(lambda: small.done(small_root))
        large_peak = peak_bytes(lambda: large.done(large_root))

        assert large_peak > small_peak * 5, f"{small_peak} bytes vs {large_peak} bytes"

    def test_space_follows_the_nodes_passed(self) -> None:
        def handed_out(count: int) -> tuple[TopologicalSorter[Node], tuple[Node, ...]]:
            sorter = all_ready(count)
            return sorter, sorter.get_ready()

        small, small_group = handed_out(20_000)
        large, large_group = handed_out(200_000)

        small_peak = peak_bytes(lambda: small.done(*small_group))
        large_peak = peak_bytes(lambda: large.done(*large_group))

        assert large_peak > small_peak * 5, f"{small_peak} bytes vs {large_peak} bytes"

    def test_a_whole_sort_is_linear_in_nodes_and_edges(self) -> None:
        graph = chain_graph(5_000)
        made = list(graph)
        for node in made[1:]:
            graph[node].append(made[0])
        edges = sum(len(predecessors) for predecessors in graph.values())
        sorter = TopologicalSorter(graph)
        sorter.prepare()

        def run() -> None:
            while sorter.is_active():
                group = sorter.get_ready()
                sorter.done(*group)

        assert edges == 9_998
        assert hashes_during(run) == 2 * len(made) + edges

    def test_misuse_is_rejected(self) -> None:
        sorter: TopologicalSorter[str] = TopologicalSorter({"b": ["a"]})
        sorter.prepare()
        with pytest.raises(ValueError, match="not passed out"):
            sorter.done("b")
        with pytest.raises(ValueError, match="was not added"):
            sorter.done("z")
        sorter.get_ready()
        sorter.done("a")
        with pytest.raises(ValueError, match="already marked done"):
            sorter.done("a")


class TestIsActiveIsConstant:
    """`is_active()`, `bool(sorter)` | O(1) | O(1)."""

    def test_it_hashes_nothing(self) -> None:
        sorter = all_ready(10_000)

        assert hashes_during(sorter.is_active) == 0
        assert hashes_during(lambda: bool(sorter)) == 0

    @pytest.mark.timing
    def test_it_does_not_scan_the_ready_nodes(self) -> None:
        small, large = all_ready(100), all_ready(1_000_000)

        small_ns = best_ns(small.is_active)
        large_ns = best_ns(large.is_active)

        assert large_ns < small_ns * 5, (
            f"is_active() cost {small_ns:.0f}ns with 100 ready nodes and "
            f"{large_ns:.0f}ns with 1,000,000; a scan would be 10,000x"
        )

    def test_bool_agrees_with_is_active(self) -> None:
        sorter: TopologicalSorter[str] = TopologicalSorter({"b": ["a"]})
        sorter.prepare()
        while sorter.is_active():
            assert bool(sorter)
            sorter.done(*sorter.get_ready())

        assert not sorter


class TestStaticOrderIsLazy:
    """`static_order()` | O(v + e) | O(v): a generator that prepares on its
    first `next()` and hands out one ready group at a time."""

    def test_calling_it_runs_nothing(self) -> None:
        sorter: TopologicalSorter[str] = TopologicalSorter({"a": ["b"], "b": ["a"]})
        order = iter(sorter.static_order())

        sorter.add("c", "a")  # still allowed: prepare() has not run
        with pytest.raises(CycleError):
            next(order)

    def test_calling_it_hashes_nothing(self) -> None:
        sorter = TopologicalSorter(chain_graph(10_000))

        assert hashes_during(sorter.static_order) == 0

    def test_a_traversal_is_linear(self) -> None:
        small = TopologicalSorter(chain_graph(1_000))
        large = TopologicalSorter(chain_graph(10_000))

        ratio = hashes_during(lambda: deque(large.static_order(), maxlen=0)) / hashes_during(
            lambda: deque(small.static_order(), maxlen=0)
        )

        assert 9 < ratio < 11, f"10x the chain cost {ratio:.1f}x the hashes"

    def test_space_follows_nodes_not_edges(self) -> None:
        sorter = TopologicalSorter(repeated_edge_graph(100_000))

        peak = peak_bytes(lambda: deque(sorter.static_order(), maxlen=0))

        assert peak < 10_000, f"100,000 edges between two nodes: {peak} bytes"

    def test_space_follows_the_nodes(self) -> None:
        small = TopologicalSorter(fan_out_graph(20_000))
        large = TopologicalSorter(fan_out_graph(200_000))

        small_peak = peak_bytes(lambda: deque(small.static_order(), maxlen=0))
        large_peak = peak_bytes(lambda: deque(large.static_order(), maxlen=0))

        assert large_peak > small_peak * 3, f"{small_peak} bytes vs {large_peak} bytes"

    def test_an_iterator_of_predecessors_serves_one_sorter(self) -> None:
        graph = {"b": iter(["a"])}

        assert list(TopologicalSorter(graph).static_order()) == ["a", "b"]
        assert list(TopologicalSorter(graph).static_order()) == ["b"]

    def test_a_sorter_is_spent_by_one_traversal(self) -> None:
        sorter: TopologicalSorter[int] = TopologicalSorter({1: [0], 2: [1]})
        assert list(sorter.static_order()) == [0, 1, 2]
        with pytest.raises(ValueError):
            list(sorter.static_order())

    def test_preparing_first_depends_on_the_version(self) -> None:
        fresh = TopologicalSorter(chain_graph(1_000))
        prepared = TopologicalSorter(chain_graph(1_000))
        prepared.prepare()

        if RELAXED_PREPARE:
            unprepared_cost = hashes_during(lambda: list(fresh.static_order()))
            prepared_cost = hashes_during(lambda: list(prepared.static_order()))
            assert prepared_cost == unprepared_cost, "the cycle search did not run again"
        else:
            with pytest.raises(ValueError, match="cannot prepare"):
                list(prepared.static_order())


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
        target = "assert done == ['c', 'd']"
        line, source = next((n, s) for n, s in _blocks() if target in s)
        mutated = source.replace(target, "assert done == ['d', 'c']", 1)

        assert mutated != source, f"the mutation matched nothing in {PAGE.name}:{line}"
        assert _run_block(mutated, tmp_path).returncode != 0
