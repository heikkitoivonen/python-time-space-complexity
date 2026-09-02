"""Tests to verify documented complexity of reprlib.

docs/stdlib/reprlib.md had no test coverage before this file, and successive
reviews turned up eight defects, each of the last five found in the fix for
the one before it:

* The Truncation row claimed O(1) space while the row above it (`repr()`)
  already prices output at O(k) -- a truncated call still returns a string
  whose length grows with the limit, so the truncated case cannot be O(1)
  either.
* The "Truncating Long Outputs" example's displayed output for the
  `maxstring` case was wrong on both the content and the position of the
  ellipsis: the page said `'xxxxxxxxxxxxxxxxxxxx'...` (quotes closed before
  the ellipsis); the actual output truncates *inside* the quotes,
  `'xxxxxxx...xxxxxxxx'`.
* The "Default Shorthand" example's displayed output was missing an entry:
  the page said `{0: 0, 1: 1, 2: 4, ...}`; the actual default `maxdict` is
  4, so the real output is `{0: 0, 1: 1, 2: 4, 3: 9, ...}`.
* The fix for the first point above then priced *all* truncation at O(k) in
  terms of the configured limit, without saying what that means for the
  input size n -- and the examples separately mislabeled several fixed-limit
  calls as O(n). Reading `Lib/reprlib.py` explains why neither was
  sufficient: `repr_list`/`repr_tuple`/`repr_deque`/`repr_array`/`repr_str`
  pull only k items via `islice` (or a direct slice for `str`), so a fixed k
  costs O(min(n, k)) -- no more once n exceeds k. But `repr_dict`/`repr_set`/
  `repr_frozenset` call `sorted()` on the *whole* input before truncating
  the rendered output, which is O(n log n) regardless of the limit. One
  table row cannot describe both; see TestReprTruncation for the measured
  contrast between a list (flat as n grows) and a dict (which is not).
* Splitting that row still left the sorted containers' space at O(k). The
  `sorted()` call materializes an n-element list before any truncation
  happens -- as does the `list(x)` fallback it drops to when the elements
  are not orderable -- so peak space is O(n + k), and no output limit
  reduces it. The elapsed-time tests could not have caught this: an
  implementation that sorted without allocating would time the same. See
  TestSortedContainersHoldTheWholeInput, which measures the allocation.
* That same row then described the sort as giving "a deterministic order"
  while, in the same sentence, acknowledging the `list(x)` fallback -- the
  one path that is not ordered at all. It renders in iteration order, which
  for a set of hash-randomized elements differs between processes, so the
  page was promising exactly what the fallback does not provide. See
  TestTheSortFallbackIsNotOrdered.
* Correcting that also changed the time column to call the fallback O(n),
  on the strength of a comparator that raised on comparison one -- a
  generalisation from a single input shape. `_possibly_sorted()` catches
  the exception whenever it arrives, so a comparator that raises late has
  already paid for the whole sort, discards the ordering, and builds
  `list(x)` on top. O(n log n) is restored as the bound, with O(n) named as
  the immediate-failure case; both ends are now tested. Getting *that*
  measurement right needed shuffling the elements: drawn from `range(n)`
  they enter the set in ascending order, where Timsort finishes in n-1
  comparisons and the sort looks linear.
* Which was the next defect, because that observation belonged in the docs
  and went only into a test comment. Timsort's adaptivity is not a
  measurement artefact to work around; it is the row's best case. An
  already-ascending input costs n-1 comparisons however late a comparison
  fails, so the row reads O(n) best / O(n log n) worst. The page's own
  "Default Shorthand" example, built from `range(1000)`, is the O(n) shape
  and had been annotated with the worst case; it now says so, and
  test_the_documented_dict_example_takes_the_linear_path pins the property
  that makes it true.

`recursive_repr()` was previously tested indirectly under
tests/test_functools_complexity.py, because `functools.recursive_repr`
happens to work too -- `functools.py` imports the name from `reprlib` for
its own internal use (`partial.__repr__`). That import is not part of the
documented functools API, so the test now uses the import the documentation
actually recommends: `from reprlib import recursive_repr`.
"""

import gc
import io
import math
import os
import random
import reprlib
import subprocess
import sys
import textwrap
import time
import tracemalloc
from collections.abc import Callable
from pathlib import Path
from reprlib import recursive_repr
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
REPRLIB_PAGE = PROJECT_ROOT / "docs" / "stdlib" / "reprlib.md"


def best_time(func: Callable[[], Any], repeats: int = 5) -> float:
    """Return the fastest of several runs, the least noisy estimate."""
    times: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        func()
        times.append(time.perf_counter() - start)
    return min(times)


class TestRecursiveRepr:
    """docs/stdlib/reprlib.md: `recursive_repr()` -- O(1), "short-circuits a
    __repr__ call already in progress"."""

    def test_short_circuits_a_reentrant_repr_call(self) -> None:
        class Node:
            def __init__(self) -> None:
                self.child: Node | None = None

            @recursive_repr("<...>")
            def __repr__(self) -> str:
                return f"Node({self.child!r})"

        node = Node()
        node.child = node  # a cycle: without protection this recurses forever

        assert repr(node) == "Node(<...>)"

    def test_a_non_reentrant_call_is_unaffected(self) -> None:
        class Leaf:
            @recursive_repr()
            def __repr__(self) -> str:
                return "Leaf()"

        assert repr(Leaf()) == "Leaf()"

    def test_the_fillvalue_defaults_to_ellipsis_style(self) -> None:
        class Node:
            def __init__(self) -> None:
                self.child: Node | None = None

            @recursive_repr()
            def __repr__(self) -> str:
                return f"Node({self.child!r})"

        node = Node()
        node.child = node

        assert repr(node) == "Node(...)"


class TestReprTruncation:
    """docs/stdlib/reprlib.md, as corrected by this class.

    The returned string's length tracks the limit rather than a constant, so
    the output alone is O(k) on every path. Everything else diverges by
    container type: only list/tuple/deque/array/str stop *reading* their
    input at k. dict/set/frozenset sort the whole input first, so their time
    tracks n regardless of the limit -- and so does their space, which
    TestSortedContainersHoldTheWholeInput covers.
    """

    def test_maxlist_truncates_and_marks_it(self) -> None:
        printer = reprlib.Repr()
        printer.maxlist = 3

        result = printer.repr(list(range(100)))

        assert result == "[0, 1, 2, ...]"

    def test_maxstring_truncates_inside_the_quotes(self) -> None:
        """The exact documented output -- the ellipsis lands inside the
        quotes, not after the closing one."""
        printer = reprlib.Repr()
        printer.maxstring = 20

        result = printer.repr("x" * 1000)

        assert result == "'xxxxxxx...xxxxxxxx'"

    def test_a_short_value_is_not_truncated(self) -> None:
        printer = reprlib.Repr()
        printer.maxlist = 3

        assert printer.repr([1, 2]) == "[1, 2]"

    def test_the_output_length_tracks_the_limit(self) -> None:
        """O(k) space: a larger limit produces a longer returned string,
        not a fixed-size one."""
        narrow, wide = reprlib.Repr(), reprlib.Repr()
        narrow.maxstring = 20
        wide.maxstring = 200
        source = "x" * 10_000

        assert len(wide.repr(source)) > len(narrow.repr(source)) * 5

    @pytest.mark.timing
    def test_list_time_does_not_grow_with_source_size_past_a_fixed_limit(self) -> None:
        """O(min(n, k)): islice stops at maxlist regardless of n."""
        printer = reprlib.Repr()
        printer.maxlist = 3

        small = list(range(200))
        large = list(range(200_000))

        small_time = best_time(lambda: printer.repr(small))
        large_time = best_time(lambda: printer.repr(large))

        assert large_time < small_time * 10, (
            f"1,000x the source size should not cost noticeably more once a "
            f"fixed maxlist bounds what is read: n=200 {small_time:.2e}s vs "
            f"n=200,000 {large_time:.2e}s"
        )

    @pytest.mark.timing
    def test_string_time_does_not_grow_with_source_size_past_a_fixed_limit(self) -> None:
        """O(min(n, k)): repr_str slices to maxstring before doing anything else."""
        printer = reprlib.Repr()
        printer.maxstring = 20

        small = "x" * 200
        large = "x" * 2_000_000

        small_time = best_time(lambda: printer.repr(small))
        large_time = best_time(lambda: printer.repr(large))

        assert large_time < small_time * 10, (
            f"10,000x the source size should not cost noticeably more once "
            f"a fixed maxstring bounds what is read: n=200 {small_time:.2e}s "
            f"vs n=2,000,000 {large_time:.2e}s"
        )

    @pytest.mark.timing
    def test_dict_time_grows_with_source_size_despite_the_same_fixed_limit(self) -> None:
        """The contrasting O(n log n): sorted() sees the whole input first."""
        printer = reprlib.Repr()
        printer.maxdict = 4

        small = {i: i for i in range(200)}
        large = {i: i for i in range(200_000)}

        small_time = best_time(lambda: printer.repr(small))
        large_time = best_time(lambda: printer.repr(large))

        assert large_time > small_time * 20, (
            f"1,000x the source size should cost far more even though "
            f"maxdict is unchanged, because the whole dict is sorted before "
            f"truncating the output: n=200 {small_time:.2e}s vs "
            f"n=200,000 {large_time:.2e}s"
        )

    def test_default_repr_shorthand_matches_the_documented_output(self) -> None:
        large_dict = {i: i**2 for i in range(1000)}

        assert reprlib.repr(large_dict) == "{0: 0, 1: 1, 2: 4, 3: 9, ...}"


class TestSortedContainersHoldTheWholeInput:
    """docs/stdlib/reprlib.md, as corrected by this class.

    The dict/set/frozenset row named the O(n log n) sort but still priced
    space at O(k), the size of the returned string. `_possibly_sorted()`
    calls `sorted(x)`, which materializes an n-element list before anything
    is truncated -- and its `except Exception: return list(x)` fallback,
    taken when the elements are not orderable, materializes n as well. Peak
    space is therefore O(n + k), and no output limit reduces it.

    The elapsed-time tests above cannot catch this: a hypothetical
    implementation that sorted lazily would be just as slow and hold
    nothing. These measure the allocation itself.
    """

    SMALL = 1_000
    LARGE = 100_000

    @staticmethod
    def _peak_bytes(func: Callable[[], Any]) -> int:
        """Peak allocation *during* the call.

        The sorted copy is released when repr() returns, so sampling after
        the fact reports nothing -- the reading has to be the peak, not the
        residue.
        """
        gc.collect()
        tracemalloc.start()
        try:
            tracemalloc.reset_peak()
            base = tracemalloc.get_traced_memory()[0]
            func()
            return tracemalloc.get_traced_memory()[1] - base
        finally:
            tracemalloc.stop()

    def test_every_element_is_compared_not_just_the_limit(self) -> None:
        """Exact, no tolerance: sorting n keys needs at least n-1 comparisons,
        where touching only the k rendered ones would need a handful."""
        comparisons = {"n": 0}

        class Counted:
            def __init__(self, value: int) -> None:
                self.value = value

            def __hash__(self) -> int:
                return hash(self.value)

            def __eq__(self, other: object) -> bool:
                return isinstance(other, Counted) and self.value == other.value

            def __lt__(self, other: "Counted") -> bool:
                comparisons["n"] += 1
                return self.value < other.value

        printer = reprlib.Repr()
        printer.maxdict = 4
        source = {Counted(value): value for value in range(self.SMALL)}

        printer.repr(source)

        assert comparisons["n"] >= self.SMALL - 1, (
            f"every key must reach the sort, not just the {printer.maxdict} "
            f"rendered ones: {comparisons['n']} comparisons for n={self.SMALL}"
        )

    def test_peak_space_holds_the_whole_sorted_copy(self) -> None:
        printer = reprlib.Repr()
        printer.maxdict = 4

        small = {value: value for value in range(self.SMALL)}
        large = {value: value for value in range(self.LARGE)}

        small_peak = self._peak_bytes(lambda: printer.repr(small))
        large_peak = self._peak_bytes(lambda: printer.repr(large))

        assert large_peak > small_peak * 20, (
            f"a fixed maxdict of {printer.maxdict} bounds the returned "
            f"string, not the sorted copy, so 100x the input should hold "
            f"about 100x more: n={self.SMALL:,} {small_peak:,}B vs "
            f"n={self.LARGE:,} {large_peak:,}B"
        )

    def test_a_set_pays_the_same_way(self) -> None:
        printer = reprlib.Repr()
        printer.maxset = 4

        # Built outside the measured call: constructing the source scales
        # with n by itself, and would carry this assertion even if repr()
        # allocated nothing at all.
        small = set(range(self.SMALL))
        large = set(range(self.LARGE))

        small_peak = self._peak_bytes(lambda: printer.repr(small))
        large_peak = self._peak_bytes(lambda: printer.repr(large))

        assert large_peak > small_peak * 20, (
            f"repr_set sorts through the same helper: n={self.SMALL:,} "
            f"{small_peak:,}B vs n={self.LARGE:,} {large_peak:,}B"
        )

    def test_the_unsortable_fallback_materializes_everything_too(self) -> None:
        """`except Exception: return list(x)` is not a cheaper path -- it
        builds the same n-element list, just without ordering it."""

        class Unsortable:
            """Hashable but not orderable, so sorted() raises."""

            def __init__(self, value: int) -> None:
                self.value = value

            def __hash__(self) -> int:
                return hash(self.value)

            def __repr__(self) -> str:
                return f"U{self.value}"

        printer = reprlib.Repr()
        printer.maxset = 3

        small = {Unsortable(value) for value in range(self.SMALL)}
        large = {Unsortable(value) for value in range(self.LARGE)}

        with pytest.raises(TypeError):
            # Unorderable by construction, which pyright is right about --
            # that is the branch this test depends on reprlib taking.
            sorted(small)  # type: ignore[reportArgumentType]

        assert printer.repr(small).endswith(", ...}"), "still renders, unsorted"

        small_peak = self._peak_bytes(lambda: printer.repr(small))
        large_peak = self._peak_bytes(lambda: printer.repr(large))

        assert large_peak > small_peak * 20, (
            f"the fallback holds n elements as well: n={self.SMALL:,} "
            f"{small_peak:,}B vs n={self.LARGE:,} {large_peak:,}B"
        )

    def test_a_sequence_holds_nothing_extra(self) -> None:
        """The contrast that makes the split rows worth having: islice never
        builds a copy, so a list's peak does not move with n at all.

        Both lists are built outside the measured call, for the same reason
        the sorted cases are -- an earlier draft built them inside it and
        failed here, having measured 4MB of `list(range(100_000))` rather
        than anything repr() did.
        """
        printer = reprlib.Repr()
        printer.maxlist = 4

        small = list(range(self.SMALL))
        large = list(range(self.LARGE))

        small_peak = self._peak_bytes(lambda: printer.repr(small))
        large_peak = self._peak_bytes(lambda: printer.repr(large))

        assert large_peak < small_peak * 3, (
            f"a list is read k items deep and copied not at all: "
            f"n={self.SMALL:,} {small_peak:,}B vs n={self.LARGE:,} "
            f"{large_peak:,}B"
        )


class TestTheSortFallbackIsNotOrdered:
    """docs/stdlib/reprlib.md, as corrected by this class.

    The dict/set/frozenset row said these sort the entire input "for a
    deterministic order" while, in the same breath, acknowledging the
    `list(x)` fallback -- which is precisely the path that is *not* ordered.
    The row now says these attempt to sort, and that a failed comparison
    leaves iteration order, which for a set of hash-randomized elements
    varies from one process to the next.

    The time column took three goes to get right, each one generalising from
    whatever single input the previous test happened to use:

    1. O(n log n), flat, with no best case named.
    2. A comparator raising on comparison one costs 1 comparison, so the
       fallback was called O(n) -- true only of that comparator.
       `_possibly_sorted()` catches the exception whenever it arrives, so
       one raising late has already paid for the whole sort.
    3. O(n log n) restored as the bound -- but measured only on scattered
       input, so it named no best case either. Timsort is adaptive: an
       already-ascending input takes exactly n-1 comparisons however late a
       comparison fails.

    So there are two independent parameters, and the tests below cross them
    rather than sampling one point: the input's existing order decides
    between O(n) and O(n log n), and the failure position decides how much
    of that is paid before the fallback discards it.
    """

    class Unorderable:
        """Hashable via a string, so hash randomization reaches it, with no
        ordering at all."""

        def __init__(self, name: str) -> None:
            self.name = name

        def __hash__(self) -> int:
            return hash(self.name)

        def __repr__(self) -> str:
            return self.name

    @staticmethod
    def _counting_set(
        size: int, raise_after: float, *, ordered: bool = False
    ) -> tuple[set, dict[str, int]]:
        """A set whose elements count comparisons and raise past a threshold.

        `ordered` picks which end of the adaptive sort is being measured, and
        it is the difference between the two documented bounds rather than a
        detail: drawn from `range(size)` the values land in the set already
        ascending, Timsort spots the single run and finishes in n-1
        comparisons. A "the sort did super-linear work" assertion left on
        that input silently measures the best case, which is how the first
        draft of this test mismeasured the sort as linear.
        """
        comparisons = {"n": 0}

        class Counted:
            def __init__(self, value: int) -> None:
                self.value = value

            def __hash__(self) -> int:
                return hash(self.value)

            def __repr__(self) -> str:
                return f"c{self.value}"

            def __lt__(self, other: "Counted") -> bool:
                comparisons["n"] += 1
                if comparisons["n"] > raise_after:
                    raise TypeError("not orderable")
                return self.value < other.value

        values = (
            list(range(size)) if ordered else random.Random(12345).sample(range(10 * size), size)
        )
        return {Counted(value) for value in values}, comparisons

    def test_an_already_ordered_input_sorts_in_linear_comparisons(self) -> None:
        """The O(n) best case. Timsort is adaptive: it finds one run and
        confirms it, which is exactly n-1 comparisons, at any n."""
        printer = reprlib.Repr()
        printer.maxset = 4

        counts = []
        for size in (1_000, 10_000):
            source, comparisons = self._counting_set(size, math.inf, ordered=True)
            printer.repr(source)
            counts.append(comparisons["n"])

        assert counts == [999, 9_999], f"one pass, no swaps: {counts}"

    def test_a_scattered_input_is_the_superlinear_worst_case(self) -> None:
        """The other end, and the contrast that makes the range meaningful:
        the same n, merely in a different order, costs several times more."""
        printer = reprlib.Repr()
        printer.maxset = 4
        size = 10_000

        ordered_source, ordered_comparisons = self._counting_set(size, math.inf, ordered=True)
        scattered_source, scattered_comparisons = self._counting_set(size, math.inf)
        printer.repr(ordered_source)
        printer.repr(scattered_source)

        ordered = ordered_comparisons["n"]
        scattered = scattered_comparisons["n"]

        assert scattered > ordered * 5, (
            f"scattered input should cost far more than the linear best "
            f"case at the same n={size:,}: ordered={ordered:,} "
            f"scattered={scattered:,}"
        )
        assert scattered < size * math.log2(size), (
            f"and still sit under n log2 n: scattered={scattered:,} vs "
            f"{size * math.log2(size):,.0f}"
        )

    def test_an_ordered_input_stays_linear_even_when_it_fails_late(self) -> None:
        """Failure position and input order are separate parameters. A late
        raise costs the whole sort -- but on ordered input the whole sort is
        only n-1 comparisons, so this is still O(n)."""
        printer = reprlib.Repr()
        printer.maxset = 4
        size = 2_000

        source, comparisons = self._counting_set(size, math.inf, ordered=True)
        printer.repr(source)
        full = comparisons["n"]

        source, comparisons = self._counting_set(size, full - 1, ordered=True)
        printer.repr(source)

        assert full == size - 1
        assert comparisons["n"] == size - 1, (
            f"a late failure on an ordered input pays the ordered price, not "
            f"the n log n one: {comparisons['n']}"
        )

    def test_the_documented_dict_example_takes_the_linear_path(self) -> None:
        """The page annotates its "Default Shorthand" example as O(n), which
        holds only because those keys are already ascending. Pinned so the
        annotation cannot quietly stop matching the example."""
        large_dict = {i: i**2 for i in range(1000)}

        assert list(large_dict) == sorted(large_dict), (
            "sorted() receives the keys in iteration order; ascending order "
            "is what puts this example on the adaptive n-1 path"
        )

    def test_an_immediate_failure_costs_a_single_comparison(self) -> None:
        """Exact, no tolerance: one comparison whatever n is. This is the
        cheap end of the fallback, not its bound."""
        printer = reprlib.Repr()
        printer.maxset = 4

        counts = []
        for size in (1_000, 100_000):
            source, comparisons = self._counting_set(size, raise_after=0)
            printer.repr(source)
            counts.append(comparisons["n"])

        assert counts == [1, 1], f"the first failure should end the sort: {counts}"

    def test_a_late_failure_pays_for_the_entire_sort(self) -> None:
        """The shape the O(n) fallback claim overlooked.

        `_possibly_sorted()` catches the exception whenever it arrives, so a
        comparator that survives until the sort's last comparison does all
        Theta(n log n) of them, throws the ordering away, and builds
        `list(x)` as well. Self-calibrating: the threshold comes from the
        same input's successful sort, so nothing is hardcoded.
        """
        printer = reprlib.Repr()
        printer.maxset = 4
        size = 2_000

        source, comparisons = self._counting_set(size, raise_after=math.inf)
        sorted_render = printer.repr(source)
        full = comparisons["n"]

        source, comparisons = self._counting_set(size, raise_after=full - 1)
        late_render = printer.repr(source)
        late = comparisons["n"]

        assert late == full, (
            f"the sort should reach its final comparison before failing: {late} of {full}"
        )
        assert full > size * 2, (
            f"a sort doing only O(n) comparisons would leave nothing for the "
            f"fallback to waste: {full} comparisons for n={size:,}"
        )
        assert late_render != sorted_render, (
            "and all of it is discarded -- the rendering must be the "
            "unordered fallback, not the order those comparisons established"
        )
        assert late_render == "{" + ", ".join(repr(item) for item in list(source)[:4]) + ", ...}"

    def test_the_fallback_renders_in_iteration_order(self) -> None:
        """Not an arbitrary unspecified order -- exactly `list(x)`, which is
        what makes it vary with the hash seed."""
        printer = reprlib.Repr()
        printer.maxset = 4

        elements = {self.Unorderable(f"t{index}") for index in range(12)}
        rendered = printer.repr(elements)
        expected = ", ".join(repr(item) for item in list(elements)[:4])

        assert rendered == "{" + expected + ", ...}"

    def test_the_fallback_order_differs_between_processes(self) -> None:
        """The claim the word "deterministic" got wrong, shown directly.

        Three seeds is enough: sampled over twelve, all twelve produced a
        distinct ordering, so a coincidental three-way match is not a
        realistic flake.
        """
        outputs = {self._render_under_seed(seed, orderable=False) for seed in ("1", "2", "3")}

        assert len(outputs) > 1, (
            f"an unordered fallback over hash-randomized elements should not "
            f"render the same way in every process: {outputs}"
        )

    def test_a_successful_sort_is_stable_between_processes(self) -> None:
        """The contrast, and the half of the claim that does hold: when the
        elements are orderable, the sort makes the output reproducible."""
        outputs = {self._render_under_seed(seed, orderable=True) for seed in ("1", "2", "3")}

        assert len(outputs) == 1, (
            f"a sorted rendering should not depend on the hash seed: {outputs}"
        )

    @staticmethod
    def _render_under_seed(seed: str, *, orderable: bool) -> str:
        """Render a set in a fresh interpreter under a given PYTHONHASHSEED.

        The seed only takes effect at startup, so this cannot be done
        in-process.
        """
        script = textwrap.dedent(
            """
            import reprlib

            class Unorderable:
                def __init__(self, name):
                    self.name = name
                def __hash__(self):
                    return hash(self.name)
                def __repr__(self):
                    return self.name

            printer = reprlib.Repr()
            printer.maxset = 4
            names = [f"t{i}" for i in range(12)]
            elements = set(names) if ORDERABLE else {Unorderable(n) for n in names}
            print(printer.repr(elements))
            """
        ).replace("ORDERABLE", str(orderable))

        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "PYTHONHASHSEED": seed},
        )
        return completed.stdout.strip()


class TestDocumentedExamplesRun:
    """Every Python block on docs/stdlib/reprlib.md must execute and print
    exactly what its comments say -- which is how the wrong outputs above
    were found in the first place."""

    def _blocks(self) -> list[tuple[int, str]]:
        blocks: list[tuple[int, str]] = []
        inside = False
        start = 0
        body: list[str] = []
        for number, line in enumerate(
            REPRLIB_PAGE.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not inside and line.strip() == "```python":
                inside, start, body = True, number, []
            elif inside and line.strip() == "```":
                blocks.append((start, "\n".join(body)))
                inside = False
            elif inside:
                body.append(line)
        return blocks

    def _run(self, source: str, label: str) -> str:
        captured, real_stdout = io.StringIO(), sys.stdout
        try:
            sys.stdout = captured
            exec(  # noqa: S102 - executing the docs is the point
                compile(source, f"reprlib.md:{label}", "exec"),
                {"__name__": "__main__"},
            )
        finally:
            sys.stdout = real_stdout
        return captured.getvalue()

    def test_the_page_has_examples_to_check(self) -> None:
        assert len(self._blocks()) >= 3

    def test_every_example_executes(self) -> None:
        failures: list[str] = []
        for line_number, source in self._blocks():
            try:
                self._run(source, str(line_number))
            except Exception as error:  # noqa: BLE001 - report, do not raise
                failures.append(f"line {line_number}: {type(error).__name__}: {error}")

        assert not failures, "examples on the page do not run:\n" + "\n".join(failures)

    def test_the_truncating_example_prints_what_the_page_says(self) -> None:
        source = next(body for _, body in self._blocks() if "maxlist" in body)

        assert self._run(source, "truncating").splitlines() == [
            "[0, 1, 2, ...]",
            "'xxxxxxx...xxxxxxxx'",
        ]

    def test_the_default_shorthand_example_prints_what_the_page_says(self) -> None:
        source = next(body for _, body in self._blocks() if "large_dict" in body)

        assert self._run(source, "shorthand").splitlines() == [
            "{0: 0, 1: 1, 2: 4, 3: 9, ...}",
        ]

    def test_the_recursive_guard_example_prints_what_the_page_says(self) -> None:
        source = next(body for _, body in self._blocks() if "recursive_repr" in body)

        assert self._run(source, "recursive-guard").splitlines() == ["Node(<...>)"]
